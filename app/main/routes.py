"""Main blueprint: dashboard, universal search, settings, drivers, expenses."""
from datetime import datetime, date, timedelta

from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app, jsonify, send_file
from flask_login import login_required, current_user

from app.extensions import db
from app.models import (
    Customer, Quote, Delivery, DeliveryStatusHistory, Invoice, Payment, Reminder,
    CompanySettings, PricingSettings, EmailTemplate, Driver, Expense,
    DELIVERY_STATUSES, EMAIL_TEMPLATE_TYPES,
)
from app.forms import (
    CompanySettingsForm, PricingSettingsForm, EmailTemplateForm,
    DriverForm, ExpenseForm,
)
from app.utils import (
    get_company_settings, get_pricing_settings, save_uploaded_file,
    generate_quote_pdf, generate_invoice_pdf, generate_pod_pdf,
    admin_required, dispatcher_or_above,
)

main = Blueprint("main", __name__)


# ═══════════════════════════════════════════════════════════════
#  DASHBOARD
#  NOTE: the site root "/" is the public customer gateway (see the
#  `public` blueprint). The staff dashboard lives at /dashboard.
# ═══════════════════════════════════════════════════════════════
@main.route("/dashboard")
@login_required
@dispatcher_or_above
def dashboard():
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)

    # Delivery stats
    deliveries_today = Delivery.query.filter(
        db.func.date(Delivery.pickup_datetime) == today,
        Delivery.status != "Cancelled",
    ).count()

    in_progress = Delivery.query.filter(
        Delivery.status.in_(["Driver Assigned", "En Route to Pickup", "Arrived at Pickup",
                             "Picked Up", "In Transit", "Arrived at Delivery"])
    ).count()

    completed_today = Delivery.query.filter(
        db.func.date(Delivery.actual_delivery_time) == today,
        Delivery.status.in_(["Delivered", "Completed"]),
    ).count()

    pending_quotes = Quote.query.filter(Quote.status == "pending").count()

    # Revenue stats
    unpaid_invoices = Invoice.query.filter(
        Invoice.status.in_(["Sent", "Viewed", "Partially Paid", "Overdue"])
    ).count()

    revenue_today = db.session.query(db.func.sum(Payment.amount)).filter(
        Payment.payment_date == today
    ).scalar() or 0

    revenue_week = db.session.query(db.func.sum(Payment.amount)).filter(
        Payment.payment_date >= week_start
    ).scalar() or 0

    revenue_month = db.session.query(db.func.sum(Payment.amount)).filter(
        Payment.payment_date >= month_start
    ).scalar() or 0

    # Recent activity
    recent_customers = Customer.query.order_by(Customer.updated_at.desc()).limit(5).all()
    recent_deliveries = Delivery.query.order_by(Delivery.created_at.desc()).limit(5).all()
    new_pickup_requests = Delivery.query.filter(
        Delivery.status == "New Request",
        Delivery.created_by.is_(None),
        Delivery.status_history.any(DeliveryStatusHistory.notes.ilike("%public website%")),
    ).order_by(Delivery.created_at.desc()).limit(10).all()

    # Reminders
    upcoming_reminders = Reminder.query.filter(
        Reminder.is_completed == False,
        Reminder.due_date <= today + timedelta(days=7),
    ).order_by(Reminder.due_date).limit(10).all()

    overdue_reminders = [r for r in upcoming_reminders if r.is_overdue]

    return render_template("main/dashboard.html",
        deliveries_today=deliveries_today,
        in_progress=in_progress,
        completed_today=completed_today,
        pending_quotes=pending_quotes,
        unpaid_invoices=unpaid_invoices,
        revenue_today=revenue_today,
        revenue_week=revenue_week,
        revenue_month=revenue_month,
        recent_customers=recent_customers,
        recent_deliveries=recent_deliveries,
        new_pickup_requests=new_pickup_requests,
        upcoming_reminders=upcoming_reminders,
        overdue_reminders=overdue_reminders,
    )


# ═══════════════════════════════════════════════════════════════
#  UNIVERSAL SEARCH
# ═══════════════════════════════════════════════════════════════
@main.route("/search")
@login_required
@dispatcher_or_above
def search():
    q = request.args.get("q", "").strip()
    if not q or len(q) < 2:
        return render_template("main/search.html", q=q, results=None)

    results = {"customers": [], "quotes": [], "deliveries": [], "invoices": []}

    # Search customers
    results["customers"] = Customer.query.filter(
        db.or_(
            Customer.business_name.ilike(f"%{q}%"),
            Customer.address.ilike(f"%{q}%"),
            Customer.city.ilike(f"%{q}%"),
        )
    ).limit(20).all()

    # Search quotes
    results["quotes"] = Quote.query.filter(
        db.or_(
            Quote.quote_number.ilike(f"%{q}%"),
            Quote.customer_name.ilike(f"%{q}%"),
            Quote.pickup_address.ilike(f"%{q}%"),
            Quote.delivery_address.ilike(f"%{q}%"),
        )
    ).limit(20).all()

    # Search deliveries
    results["deliveries"] = Delivery.query.filter(
        db.or_(
            Delivery.order_number.ilike(f"%{q}%"),
            Delivery.pickup_address.ilike(f"%{q}%"),
            Delivery.delivery_address.ilike(f"%{q}%"),
            Delivery.pickup_contact.ilike(f"%{q}%"),
            Delivery.delivery_contact.ilike(f"%{q}%"),
        )
    ).limit(20).all()

    # Search invoices
    results["invoices"] = Invoice.query.filter(
        db.or_(
            Invoice.invoice_number.ilike(f"%{q}%"),
            Invoice.billing_name.ilike(f"%{q}%"),
        )
    ).limit(20).all()

    return render_template("main/search.html", q=q, results=results)


# ═══════════════════════════════════════════════════════════════
#  SETTINGS
# ═══════════════════════════════════════════════════════════════
@main.route("/settings")
@login_required
@admin_required
def settings():
    company = get_company_settings()
    pricing = get_pricing_settings()
    company_form = CompanySettingsForm(obj=company)
    pricing_form = PricingSettingsForm(obj=pricing)
    templates = EmailTemplate.query.all()
    drivers = Driver.query.order_by(Driver.name).all()
    expenses = Expense.query.order_by(Expense.date.desc()).limit(50).all()
    driver_form = DriverForm()
    expense_form = ExpenseForm()
    return render_template("main/settings.html",
        company_form=company_form,
        pricing_form=pricing_form,
        email_templates=templates,
        drivers=drivers,
        driver_form=driver_form,
        expenses=expenses,
        expense_form=expense_form,
        template_types=EMAIL_TEMPLATE_TYPES,
    )


@main.route("/settings/company", methods=["POST"])
@login_required
@admin_required
def update_company_settings():
    form = CompanySettingsForm()
    if form.validate_on_submit():
        company = get_company_settings()
        company.company_name = form.company_name.data
        company.business_type = form.business_type.data
        company.primary_market = form.primary_market.data
        company.primary_service = form.primary_service.data
        company.email = form.email.data
        company.phone = form.phone.data
        company.website = form.website.data
        company.address = form.address.data
        company.invoice_prefix = form.invoice_prefix.data
        company.quote_prefix = form.quote_prefix.data
        company.order_prefix = form.order_prefix.data
        company.payment_instructions = form.payment_instructions.data
        company.default_payment_terms = form.default_payment_terms.data
        company.tax_rate = form.tax_rate.data or 0

        if form.logo.data:
            filename = save_uploaded_file(form.logo.data, subfolder="logos")
            if filename:
                company.logo_filename = filename

        db.session.commit()
        flash("Company settings updated.", "success")
    else:
        for field, errors in form.errors.items():
            for e in errors:
                flash(f"{field}: {e}", "danger")
    return redirect(url_for("main.settings") + "#company")


@main.route("/settings/pricing", methods=["POST"])
@login_required
@admin_required
def update_pricing_settings():
    form = PricingSettingsForm()
    if form.validate_on_submit():
        pricing = get_pricing_settings()
        pricing.base_charge = form.base_charge.data
        pricing.per_mile_charge = form.per_mile_charge.data
        pricing.minimum_charge = form.minimum_charge.data
        pricing.loaded_miles_included = form.loaded_miles_included.data
        pricing.loaded_mile_charge = form.loaded_mile_charge.data
        pricing.deadhead_miles_included = form.deadhead_miles_included.data
        pricing.deadhead_mile_charge = form.deadhead_mile_charge.data
        pricing.rush_charge = form.rush_charge.data
        pricing.stat_charge = form.stat_charge.data
        pricing.same_day_charge = form.same_day_charge.data
        pricing.after_hours_charge = form.after_hours_charge.data
        pricing.weekend_charge = form.weekend_charge.data
        pricing.holiday_charge = form.holiday_charge.data
        pricing.sunday_holiday_customer_quote = form.sunday_holiday_customer_quote.data
        pricing.wait_time_included_minutes = form.wait_time_included_minutes.data
        pricing.wait_time_block_minutes = form.wait_time_block_minutes.data
        pricing.wait_time_per_block = form.wait_time_per_block.data
        pricing.additional_stop_charge = form.additional_stop_charge.data
        pricing.toll_charge = form.toll_charge.data
        pricing.parking_charge = form.parking_charge.data
        pricing.special_handling_charge = form.special_handling_charge.data
        pricing.temperature_controlled_charge = form.temperature_controlled_charge.data
        pricing.route_discount_pct = form.route_discount_pct.data
        pricing.contract_discount_pct = form.contract_discount_pct.data
        pricing.tax_rate = form.tax_rate.data
        db.session.commit()
        flash("Pricing updated.", "success")
    else:
        for field, errors in form.errors.items():
            for e in errors:
                flash(f"{field}: {e}", "danger")
    return redirect(url_for("main.settings") + "#pricing")


# ── Email templates ──
@main.route("/settings/email-template/<template_type>", methods=["GET", "POST"])
@login_required
@admin_required
def edit_email_template(template_type):
    template = EmailTemplate.query.filter_by(template_type=template_type).first()
    if request.method == "POST":
        if not template:
            template = EmailTemplate(template_type=template_type)
        template.subject = request.form.get("subject", "")
        template.body = request.form.get("body", "")
        template.is_active = "is_active" in request.form
        db.session.add(template)
        db.session.commit()
        flash("Email template updated.", "success")
        return redirect(url_for("main.settings") + "#email")
    form = EmailTemplateForm()
    if template:
        form.subject.data = template.subject
        form.body.data = template.body
        form.is_active.data = template.is_active
    return render_template("main/edit_email_template.html", form=form, template_type=template_type, template=template)


# ── Drivers ──
@main.route("/drivers/add", methods=["POST"])
@login_required
@admin_required
def add_driver():
    form = DriverForm()
    if form.validate_on_submit():
        driver = Driver(
            name=form.name.data,
            phone=form.phone.data,
            email=form.email.data,
            license_number=form.license_number.data,
            license_expiration=form.license_expiration.data,
            vehicle_make=form.vehicle_make.data,
            vehicle_model=form.vehicle_model.data,
            vehicle_plate=form.vehicle_plate.data,
            vehicle_insurance_expiration=form.vehicle_insurance_expiration.data,
            notes=form.notes.data,
        )
        db.session.add(driver)
        db.session.commit()
        flash(f"Driver '{driver.name}' added.", "success")
    else:
        for field, errors in form.errors.items():
            for e in errors:
                flash(f"{field}: {e}", "danger")
    return redirect(url_for("main.settings") + "#drivers")


@main.route("/drivers/<int:driver_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_driver(driver_id):
    driver = Driver.query.get_or_404(driver_id)
    db.session.delete(driver)
    db.session.commit()
    flash("Driver removed.", "info")
    return redirect(url_for("main.settings") + "#drivers")


# ── Expenses ──
@main.route("/expenses/add", methods=["POST"])
@login_required
@admin_required
def add_expense():
    form = ExpenseForm()
    if form.validate_on_submit():
        expense = Expense(
            date=form.date.data,
            category=form.category.data,
            description=form.description.data,
            amount=form.amount.data,
            vendor=form.vendor.data,
        )
        db.session.add(expense)
        db.session.commit()
        flash("Expense recorded.", "success")
    else:
        for field, errors in form.errors.items():
            for e in errors:
                flash(f"{field}: {e}", "danger")
    return redirect(url_for("main.settings") + "#expenses")


# ═══════════════════════════════════════════════════════════════
#  ERROR HANDLERS
# ═══════════════════════════════════════════════════════════════
def page_not_found(e):
    return render_template("errors/404.html"), 404


def internal_error(e):
    db.session.rollback()
    return render_template("errors/500.html"), 500


def forbidden(e):
    return render_template("errors/403.html"), 403
