"""Customers blueprint: CRM for prospects and active clients."""
import csv
from io import StringIO, BytesIO
from datetime import date

from flask import Blueprint, render_template, redirect, url_for, request, flash, Response, send_file
from flask_login import login_required

from app.extensions import db
from app.models import Customer, Contact, Delivery, Invoice
from app.forms import CustomerForm, ContactForm
from app.utils import dispatcher_or_above, save_uploaded_file

customers = Blueprint("customers", __name__)


@customers.route("/")
@login_required
@dispatcher_or_above
def index():
    page = request.args.get("page", 1, type=int)
    status = request.args.get("status", "")
    category = request.args.get("category", "")
    search = request.args.get("q", "")

    query = Customer.query.filter(Customer.is_archived == False)

    if status:
        query = query.filter(Customer.status == status)
    if category:
        query = query.filter(Customer.category == category)
    if search:
        query = query.filter(
            db.or_(
                Customer.business_name.ilike(f"%{search}%"),
                Customer.city.ilike(f"%{search}%"),
                Customer.address.ilike(f"%{search}%"),
            )
        )

    pagination = query.order_by(Customer.business_name).paginate(page=page, per_page=20, error_out=False)
    return render_template("customers/index.html", customers=pagination.items, pagination=pagination,
                           status=status, category=category, search=search)


@customers.route("/<int:customer_id>")
@login_required
@dispatcher_or_above
def detail(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    deliveries = Delivery.query.filter_by(customer_id=customer_id).order_by(Delivery.created_at.desc()).limit(20).all()
    invoices = Invoice.query.filter_by(customer_id=customer_id).order_by(Invoice.created_at.desc()).limit(20).all()
    contacts = Contact.query.filter_by(customer_id=customer_id).all()
    contact_form = ContactForm()
    return render_template("customers/detail.html", customer=customer, deliveries=deliveries,
                           invoices=invoices, contacts=contacts, contact_form=contact_form)


@customers.route("/new", methods=["GET", "POST"])
@login_required
@dispatcher_or_above
def new():
    form = CustomerForm()
    if form.validate_on_submit():
        customer = Customer(
            business_name=form.business_name.data,
            category=form.category.data,
            status=form.status.data,
            address=form.address.data,
            city=form.city.data,
            state=form.state.data,
            zip_code=form.zip_code.data,
            preferred_delivery_type=form.preferred_delivery_type.data,
            billing_terms=form.billing_terms.data,
            rate_agreement=form.rate_agreement.data,
            tax_exempt=form.tax_exempt.data,
            last_contact_date=form.last_contact_date.data,
            next_follow_up=form.next_follow_up.data,
            notes=form.notes.data,
        )
        if form.contract.data:
            filename = save_uploaded_file(form.contract.data, subfolder="contracts")
            customer.contract_filename = filename

        db.session.add(customer)
        db.session.commit()
        flash(f"Customer '{customer.business_name}' added.", "success")
        return redirect(url_for("customers.detail", customer_id=customer.id))
    return render_template("customers/form.html", form=form, title="Add Customer / Prospect")


@customers.route("/<int:customer_id>/edit", methods=["GET", "POST"])
@login_required
@dispatcher_or_above
def edit(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    form = CustomerForm(obj=customer)
    if form.validate_on_submit():
        customer.business_name = form.business_name.data
        customer.category = form.category.data
        customer.status = form.status.data
        customer.address = form.address.data
        customer.city = form.city.data
        customer.state = form.state.data
        customer.zip_code = form.zip_code.data
        customer.preferred_delivery_type = form.preferred_delivery_type.data
        customer.billing_terms = form.billing_terms.data
        customer.rate_agreement = form.rate_agreement.data
        customer.tax_exempt = form.tax_exempt.data
        customer.last_contact_date = form.last_contact_date.data
        customer.next_follow_up = form.next_follow_up.data
        customer.notes = form.notes.data

        if form.contract.data:
            filename = save_uploaded_file(form.contract.data, subfolder="contracts")
            customer.contract_filename = filename

        db.session.commit()
        flash("Customer updated.", "success")
        return redirect(url_for("customers.detail", customer_id=customer.id))
    return render_template("customers/form.html", form=form, title="Edit Customer", customer=customer)


@customers.route("/<int:customer_id>/archive", methods=["POST"])
@login_required
@dispatcher_or_above
def archive(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    customer.is_archived = True
    customer.status = "archived"
    db.session.commit()
    flash(f"'{customer.business_name}' archived.", "info")
    return redirect(url_for("customers.index"))


@customers.route("/<int:customer_id>/contact", methods=["POST"])
@login_required
@dispatcher_or_above
def add_contact(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    form = ContactForm()
    if form.validate_on_submit():
        contact = Contact(
            customer_id=customer_id,
            name=form.name.data,
            title=form.title.data,
            email=form.email.data,
            phone=form.phone.data,
            is_primary=form.is_primary.data,
            notes=form.notes.data,
        )
        if form.is_primary.data:
            # Unset other primaries
            for c in customer.contacts:
                c.is_primary = False
        db.session.add(contact)
        customer.last_contact_date = date.today()
        db.session.commit()
        flash("Contact added.", "success")
    else:
        for field, errors in form.errors.items():
            for e in errors:
                flash(f"{field}: {e}", "danger")
    return redirect(url_for("customers.detail", customer_id=customer_id))


@customers.route("/export")
@login_required
@dispatcher_or_above
def export_csv():
    """Export all customers to CSV."""
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Business Name", "Category", "Status", "Contact", "Email", "Phone",
                     "Address", "City", "State", "ZIP", "Delivery Type", "Billing Terms",
                     "Last Contact", "Next Follow-up", "Total Revenue"])

    for c in Customer.query.filter_by(is_archived=False).all():
        pc = c.primary_contact
        writer.writerow([
            c.business_name, c.category, c.status,
            pc.name if pc else "", pc.email if pc else "", pc.phone if pc else "",
            c.address, c.city, c.state, c.zip_code,
            c.preferred_delivery_type, c.billing_terms,
            c.last_contact_date, c.next_follow_up,
            f"{c.total_revenue:.2f}",
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=customers.csv"}
    )
