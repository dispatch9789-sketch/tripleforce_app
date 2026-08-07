"""Invoices blueprint: generation, editing, payments, PDF, email."""
import csv
from io import StringIO
from datetime import date, timedelta

from flask import Blueprint, render_template, redirect, url_for, request, flash, send_file, Response
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Invoice, InvoiceLineItem, Payment, Delivery, Customer
from app.forms import InvoiceForm, InvoiceLineItemForm, PaymentForm
from app.utils import (
    dispatcher_or_above,
    get_next_invoice_number, get_company_settings,
    generate_invoice_pdf, send_email, render_email_template,
)

invoices = Blueprint("invoices", __name__)


@invoices.route("/")
@login_required
@dispatcher_or_above
def index():
    status = request.args.get("status", "")
    page = request.args.get("page", 1, type=int)

    query = Invoice.query
    if status:
        query = query.filter(Invoice.status == status)
    pagination = query.order_by(Invoice.created_at.desc()).paginate(page=page, per_page=20, error_out=False)
    return render_template("invoices/index.html", invoices=pagination.items, pagination=pagination, status=status)


@invoices.route("/new", methods=["GET", "POST"])
@login_required
@dispatcher_or_above
def new():
    form = InvoiceForm()
    customers = Customer.query.filter_by(is_archived=False).order_by(Customer.business_name).all()
    form.customer_id.choices = [(0, "— Select —")] + [(c.id, c.business_name) for c in customers]

    # Pre-fill from delivery if specified
    delivery_id = request.args.get("delivery_id", type=int)
    delivery = None
    if delivery_id:
        delivery = Delivery.query.get(delivery_id)
        if delivery:
            form.billing_name.data = delivery.customer.business_name if delivery.customer else ""
            form.billing_address.data = delivery.customer.address if delivery.customer else ""
            form.delivery_description.data = f"Delivery {delivery.order_number}: {delivery.pickup_address} → {delivery.delivery_address}"
            form.mileage.data = delivery.mileage
            form.base_charge.data = delivery.quote_amount

    if form.validate_on_submit():
        invoice_number = get_next_invoice_number()
        customer_id = form.customer_id.data if form.customer_id.data and form.customer_id.data > 0 else None

        subtotal = (form.base_charge.data or 0) + (form.additional_charges.data or 0) - (form.discounts.data or 0)
        total = subtotal + (form.tax_amount.data or 0)

        settings = get_company_settings()
        due = form.due_date.data
        if not due:
            terms_str = form.payment_terms.data or settings.default_payment_terms or "Net 30"
            days = 30
            for d in [7, 15, 30, 45, 60]:
                if str(d) in terms_str:
                    days = d
                    break
            due = date.today() + timedelta(days=days)

        invoice = Invoice(
            invoice_number=invoice_number,
            customer_id=customer_id,
            delivery_id=delivery_id if delivery_id else None,
            billing_name=form.billing_name.data,
            billing_address=form.billing_address.data,
            service_date=form.service_date.data,
            delivery_description=form.delivery_description.data,
            pickup_address=delivery.pickup_address if delivery else None,
            delivery_address=delivery.delivery_address if delivery else None,
            mileage=form.mileage.data,
            base_charge=form.base_charge.data or 0,
            additional_charges=form.additional_charges.data or 0,
            discounts=form.discounts.data or 0,
            subtotal=subtotal,
            tax_amount=form.tax_amount.data or 0,
            total_due=total,
            paid_amount=0,
            balance_due=total,
            payment_terms=form.payment_terms.data,
            due_date=due,
            payment_instructions=form.payment_instructions.data,
            notes=form.notes.data,
            status=form.status.data,
            created_by=current_user.id,
        )
        db.session.add(invoice)

        # Mark delivery as invoiced
        if delivery:
            delivery.invoice_status = "Invoiced"

        db.session.commit()
        flash(f"Invoice {invoice_number} created.", "success")
        return redirect(url_for("invoices.detail", invoice_id=invoice.id))

    return render_template("invoices/form.html", form=form, title="New Invoice", delivery=delivery)


@invoices.route("/<int:invoice_id>")
@login_required
@dispatcher_or_above
def detail(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    line_item_form = InvoiceLineItemForm()
    payment_form = PaymentForm()
    payment_form.payment_date.data = date.today()
    return render_template("invoices/detail.html", invoice=invoice,
                           line_item_form=line_item_form, payment_form=payment_form)


@invoices.route("/<int:invoice_id>/edit", methods=["GET", "POST"])
@login_required
@dispatcher_or_above
def edit(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    form = InvoiceForm(obj=invoice)
    customers = Customer.query.filter_by(is_archived=False).order_by(Customer.business_name).all()
    form.customer_id.choices = [(0, "— Select —")] + [(c.id, c.business_name) for c in customers]

    if form.validate_on_submit():
        customer_id = form.customer_id.data if form.customer_id.data and form.customer_id.data > 0 else None
        invoice.customer_id = customer_id
        invoice.billing_name = form.billing_name.data
        invoice.billing_address = form.billing_address.data
        invoice.service_date = form.service_date.data
        invoice.delivery_description = form.delivery_description.data
        invoice.mileage = form.mileage.data
        invoice.base_charge = form.base_charge.data or 0
        invoice.additional_charges = form.additional_charges.data or 0
        invoice.discounts = form.discounts.data or 0
        invoice.tax_amount = form.tax_amount.data or 0
        invoice.subtotal = (form.base_charge.data or 0) + (form.additional_charges.data or 0) - (form.discounts.data or 0)
        invoice.total_due = invoice.subtotal + (form.tax_amount.data or 0)
        invoice.balance_due = invoice.total_due - (invoice.paid_amount or 0)
        invoice.payment_terms = form.payment_terms.data
        invoice.due_date = form.due_date.data
        invoice.payment_instructions = form.payment_instructions.data
        invoice.notes = form.notes.data
        invoice.status = form.status.data
        db.session.commit()
        flash("Invoice updated.", "success")
        return redirect(url_for("invoices.detail", invoice_id=invoice_id))

    return render_template("invoices/form.html", form=form, title="Edit Invoice", invoice=invoice)


@invoices.route("/<int:invoice_id>/line-item", methods=["POST"])
@login_required
@dispatcher_or_above
def add_line_item(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    form = InvoiceLineItemForm()
    if form.validate_on_submit():
        item = InvoiceLineItem(
            invoice_id=invoice_id,
            description=form.description.data,
            quantity=form.quantity.data,
            unit_price=form.unit_price.data,
            total=(form.quantity.data or 1) * (form.unit_price.data or 0),
        )
        db.session.add(item)
        db.session.commit()
        flash("Line item added.", "success")
    return redirect(url_for("invoices.detail", invoice_id=invoice_id) + "#line-items")


@invoices.route("/<int:invoice_id>/line-item/<int:item_id>/delete", methods=["POST"])
@login_required
@dispatcher_or_above
def delete_line_item(invoice_id, item_id):
    item = InvoiceLineItem.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash("Line item removed.", "info")
    return redirect(url_for("invoices.detail", invoice_id=invoice_id) + "#line-items")


@invoices.route("/<int:invoice_id>/payment", methods=["POST"])
@login_required
@dispatcher_or_above
def record_payment(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    form = PaymentForm()
    if form.validate_on_submit():
        payment = Payment(
            invoice_id=invoice_id,
            customer_id=invoice.customer_id,
            amount=form.amount.data,
            payment_date=form.payment_date.data,
            payment_method=form.payment_method.data,
            reference_number=form.reference_number.data,
            notes=form.notes.data,
        )
        db.session.add(payment)

        invoice.paid_amount = (invoice.paid_amount or 0) + form.amount.data
        invoice.balance_due = invoice.total_due - invoice.paid_amount

        if invoice.paid_amount >= invoice.total_due:
            invoice.status = "Paid"
        elif invoice.paid_amount > 0:
            invoice.status = "Partially Paid"

        # Mark delivery as paid if applicable
        if invoice.delivery and invoice.status == "Paid":
            invoice.delivery.invoice_status = "Paid"

        db.session.commit()
        flash(f"Payment of ${form.amount.data:.2f} recorded.", "success")
    else:
        for field, errors in form.errors.items():
            for e in errors:
                flash(f"{field}: {e}", "danger")
    return redirect(url_for("invoices.detail", invoice_id=invoice_id) + "#payments")


@invoices.route("/<int:invoice_id>/status", methods=["POST"])
@login_required
@dispatcher_or_above
def update_status(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    new_status = request.form.get("status")
    if new_status in ["Draft", "Sent", "Viewed", "Partially Paid", "Paid", "Overdue", "Cancelled"]:
        invoice.status = new_status
        if new_status == "Sent":
            invoice.sent_at = date.today()
        db.session.commit()
        flash(f"Invoice marked as {new_status}.", "success")
    return redirect(url_for("invoices.detail", invoice_id=invoice_id))


@invoices.route("/<int:invoice_id>/pdf")
@login_required
@dispatcher_or_above
def pdf(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    settings = get_company_settings()
    buf = generate_invoice_pdf(invoice, settings)
    return send_file(buf, as_attachment=True, download_name=f"Invoice_{invoice.invoice_number}.pdf",
                     mimetype="application/pdf")


@invoices.route("/<int:invoice_id>/email", methods=["POST"])
@login_required
@dispatcher_or_above
def email_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    to = request.form.get("email")
    if not to and invoice.customer and invoice.customer.primary_contact:
        to = invoice.customer.primary_contact.email
    if not to:
        flash("No email address available.", "danger")
        return redirect(url_for("invoices.detail", invoice_id=invoice_id))

    settings = get_company_settings()
    subject, body = render_email_template("invoice_sent", {
        "customer_name": invoice.billing_name or "Customer",
        "invoice_number": invoice.invoice_number,
        "total": f"{invoice.total_due:.2f}",
        "payment_terms": invoice.payment_terms or "Net 30",
        "due_date": invoice.due_date.strftime("%B %d, %Y") if invoice.due_date else "N/A",
        "payment_instructions": invoice.payment_instructions or settings.payment_instructions or "",
    })
    buf = generate_invoice_pdf(invoice, settings)
    attachments = [(f"Invoice_{invoice.invoice_number}.pdf", "application/pdf", buf.getvalue())]
    success = send_email(to, subject, body, attachments=attachments)
    if success:
        invoice.status = "Sent"
        invoice.sent_at = date.today()
        db.session.commit()
        flash(f"Invoice emailed to {to}.", "success")
    else:
        flash("Email could not be sent. Check mail settings.", "warning")
    return redirect(url_for("invoices.detail", invoice_id=invoice_id))


@invoices.route("/export")
@login_required
@dispatcher_or_above
def export_csv():
    """Export invoices to CSV."""
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Invoice #", "Customer", "Service Date", "Due Date", "Total Due",
                     "Paid", "Balance", "Status", "Created"])

    for inv in Invoice.query.order_by(Invoice.created_at.desc()).all():
        writer.writerow([
            inv.invoice_number,
            inv.billing_name or "",
            inv.service_date, inv.due_date,
            f"{inv.total_due:.2f}", f"{inv.paid_amount:.2f}", f"{inv.balance:.2f}",
            inv.status, inv.created_at,
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=invoices.csv"}
    )
