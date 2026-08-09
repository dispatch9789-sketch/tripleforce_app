"""Quotes blueprint: calculator, save, convert to delivery, email, PDF."""
from datetime import date, timedelta

from flask import Blueprint, render_template, redirect, url_for, request, flash, send_file, jsonify
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Quote, Customer, Delivery, DeliveryStatusHistory, Driver
from app.forms import QuoteCalculatorForm, QuoteSaveForm
from app.utils import (
    dispatcher_or_above,
    calculate_quote, get_pricing_settings, get_company_settings,
    get_next_quote_number, get_next_order_number,
    generate_quote_pdf, send_email, render_email_template,
)

quotes = Blueprint("quotes", __name__)


@quotes.route("/")
@login_required
@dispatcher_or_above
def index():
    status = request.args.get("status", "")
    page = request.args.get("page", 1, type=int)

    query = Quote.query
    if status:
        query = query.filter(Quote.status == status)
    pagination = query.order_by(Quote.created_at.desc()).paginate(page=page, per_page=20, error_out=False)
    return render_template("quotes/index.html", quotes=pagination.items, pagination=pagination, status=status)


@quotes.route("/calculator", methods=["GET", "POST"])
@login_required
@dispatcher_or_above
def calculator():
    form = QuoteCalculatorForm()

    # Populate customer dropdown
    customers = Customer.query.filter_by(is_archived=False).order_by(Customer.business_name).all()
    form.customer_id.choices = [("", "— Walk-in / No Account —")] + [(str(c.id), c.business_name) for c in customers]

    calc_result = None
    pricing = get_pricing_settings()

    if form.validate_on_submit():
        # Convert form to dict for calculator
        form_data = {
            "estimated_mileage": form.estimated_mileage.data,
            "trip_type": form.trip_type.data,
            "is_rush": form.is_rush.data,
            "is_stat": form.is_stat.data,
            "is_same_day": form.is_same_day.data,
            "is_after_hours": form.is_after_hours.data,
            "is_weekend": form.is_weekend.data,
            "is_holiday": form.is_holiday.data,
            "temperature_controlled": form.temperature_controlled.data,
            "wait_time_minutes": form.wait_time_minutes.data or 0,
            "additional_stops": form.additional_stops.data or 0,
            "toll_charge": form.toll_charge.data or 0,
            "parking_charge": form.parking_charge.data or 0,
            "special_handling": form.special_handling.data,
            "apply_route_discount": form.apply_route_discount.data,
            "apply_contract_discount": form.apply_contract_discount.data,
            "manual_adjustment": form.manual_adjustment.data or 0,
            "tax_rate": form.tax_rate.data or pricing.tax_rate,
        }
        calc_result = calculate_quote(form_data, pricing)

        # Store in session for saving
        from flask import session
        session["last_quote_calc"] = {**form_data,
            "customer_id": form.customer_id.data,
            "customer_name": form.customer_name.data,
            "customer_email": form.customer_email.data,
            "pickup_address": form.pickup_address.data,
            "delivery_address": form.delivery_address.data,
            "manual_adjustment_note": form.manual_adjustment_note.data,
            "notes": form.notes.data,
            **calc_result,
    return render_template("quotes/calculator.html", form=form, calc_result=calc_result, pricing=pricing)


@quotes.route("/save", methods=["POST"])
@login_required
@dispatcher_or_above
def save():
    from flask import session
    calc = session.get("last_quote_calc")
    if not calc:
        flash("No quote calculation found. Please calculate a quote first.", "warning")
        return redirect(url_for("quotes.calculator"))

    save_form = QuoteSaveForm()
    if not save_form.validate_on_submit():
        # Use default values
        expires = date.today() + timedelta(days=30)
        notes = calc.get("notes", "")
    else:
        expires = save_form.expires_at.data or (date.today() + timedelta(days=30))
        notes = save_form.notes.data or calc.get("notes", "")

    quote_number = get_next_quote_number()

    customer_id = None
    if calc.get("customer_id"):
        try:
            customer_id = int(calc["customer_id"])
        except (ValueError, TypeError):
            customer_id = None

    quote = Quote(
        quote_number=quote_number,
        customer_id=customer_id,
        customer_name=calc.get("customer_name"),
        customer_email=calc.get("customer_email"),
        pickup_address=calc.get("pickup_address"),
        delivery_address=calc.get("delivery_address"),
        estimated_mileage=calc.get("estimated_mileage", 0),
        trip_type=calc.get("trip_type", "one-way"),
        is_rush=calc.get("is_rush", False),
        is_stat=calc.get("is_stat", False),
        is_same_day=calc.get("is_same_day", False),
        is_after_hours=calc.get("is_after_hours", False),
        is_weekend=calc.get("is_weekend", False),
        is_holiday=calc.get("is_holiday", False),
        temperature_controlled=calc.get("temperature_controlled", False),
        base_charge=calc.get("base_charge", 0),
        mileage_charge=calc.get("mileage_charge", 0),
        rush_charge=calc.get("rush_charge", 0),
        after_hours_charge=calc.get("after_hours_charge", 0),
        weekend_charge=calc.get("weekend_charge", 0),
        holiday_charge=calc.get("holiday_charge", 0),
        wait_time_charge=calc.get("wait_time_charge", 0),
        additional_stop_charge=calc.get("additional_stop_charge", 0),
        toll_charge=calc.get("toll_charge", 0),
        parking_charge=calc.get("parking_charge", 0),
        special_handling_charge=calc.get("special_handling_charge", 0),
        temp_control_charge=calc.get("temp_control_charge", 0),
        route_discount=calc.get("route_discount", 0),
        contract_discount=calc.get("contract_discount", 0),
        manual_adjustment=calc.get("manual_adjustment", 0),
        manual_adjustment_note=calc.get("manual_adjustment_note"),
        tax_rate=calc.get("tax_rate", 0),
        tax_amount=calc.get("tax_amount", 0),
        total=calc.get("total", 0),
        notes=notes,
        expires_at=expires,
        created_by=current_user.id,
        status="pending",
    )
    db.session.add(quote)
    db.session.commit()

    session.pop("last_quote_calc", None)
    flash(f"Quote {quote.quote_number} saved.", "success")
    return redirect(url_for("quotes.detail", quote_id=quote.id))


@quotes.route("/<int:quote_id>")
@login_required
@dispatcher_or_above
def detail(quote_id):
    quote = Quote.query.get_or_404(quote_id)
    return render_template("quotes/detail.html", quote=quote)


@quotes.route("/<int:quote_id>/status", methods=["POST"])
@login_required
@dispatcher_or_above
def update_status(quote_id):
    quote = Quote.query.get_or_404(quote_id)
    new_status = request.form.get("status")
    if new_status in ("pending", "accepted", "declined", "expired", "converted"):
        quote.status = new_status
        db.session.commit()
        flash(f"Quote marked as {new_status}.", "success")
    return redirect(url_for("quotes.detail", quote_id=quote_id))


@quotes.route("/<int:quote_id>/pdf")
@login_required
@dispatcher_or_above
def pdf(quote_id):
    quote = Quote.query.get_or_404(quote_id)
    settings = get_company_settings()
    buf = generate_quote_pdf(quote, settings)
    return send_file(buf, as_attachment=True, download_name=f"Quote_{quote.quote_number}.pdf",
                     mimetype="application/pdf")


@quotes.route("/<int:quote_id>/email", methods=["POST"])
@login_required
@dispatcher_or_above
def email_quote(quote_id):
    quote = Quote.query.get_or_404(quote_id)
    to = request.form.get("email", quote.customer_email)
    if not to:
        flash("No email address on file for this quote.", "danger")
        return redirect(url_for("quotes.detail", quote_id=quote_id))

    settings = get_company_settings()
    subject, body = render_email_template("quote_sent", {
        "customer_name": quote.customer_name or "Valued Customer",
        "quote_number": quote.quote_number,
        "total": f"{quote.total:.2f}",
    })

    # Generate PDF attachment
    buf = generate_quote_pdf(quote, settings)
    attachments = [(f"Quote_{quote.quote_number}.pdf", "application/pdf", buf.getvalue())]

    success = send_email(to, subject, body, attachments=attachments)
    if success:
        flash(f"Quote emailed to {to}.", "success")
    else:
        flash("Email could not be sent. Check mail settings in .env.", "warning")
    return redirect(url_for("quotes.detail", quote_id=quote_id))


@quotes.route("/<int:quote_id>/convert", methods=["POST"])
@login_required
@dispatcher_or_above
def convert_to_delivery(quote_id):
    quote = Quote.query.get_or_404(quote_id)

    if quote.status == "converted":
        flash("This quote has already been converted.", "warning")
        return redirect(url_for("quotes.detail", quote_id=quote_id))

    order_number = get_next_order_number()

    delivery = Delivery(
        order_number=order_number,
        customer_id=quote.customer_id,
        quote_id=quote.id,
        pickup_address=quote.pickup_address,
        delivery_address=quote.delivery_address,
        mileage=quote.estimated_mileage,
        service_type="STAT" if quote.is_stat else ("Same-day" if quote.is_same_day else "Standard"),
        quote_amount=quote.total,
        status="Confirmed",
        requires_pod=True,
        is_medical=quote.temperature_controlled,
        temperature_requirement="Temperature controlled" if quote.temperature_controlled else None,
        created_by=current_user.id,
    )
    db.session.add(delivery)

    # Status history entry
    history = DeliveryStatusHistory(
        delivery=delivery,
        status="Confirmed",
        notes=f"Converted from quote {quote.quote_number}",
        updated_by=current_user.full_name or current_user.email,
    )
    db.session.add(history)

    # Mark quote as converted
    quote.status = "converted"
    db.session.commit()

    flash(f"Delivery {order_number} created from quote {quote.quote_number}.", "success")
    return redirect(url_for("dispatch.detail", delivery_id=delivery.id))
