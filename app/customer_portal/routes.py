from flask import Blueprint, render_template
from flask_login import login_required
from app.models import Delivery, Invoice
from .access import require_customer, customer_delivery_or_404, customer_invoice_or_404

customer_portal = Blueprint("customer_portal", __name__)


@customer_portal.route("/")
@login_required
def dashboard():
    customer_id = require_customer()
    deliveries = Delivery.query.filter_by(customer_id=customer_id).order_by(Delivery.created_at.desc()).limit(5).all()
    invoice_count = Invoice.query.filter(Invoice.customer_id == customer_id,
        Invoice.status.in_(["Sent", "Viewed", "Partially Paid", "Paid", "Overdue"])).count()
    return render_template("customer_portal/dashboard.html", deliveries=deliveries, invoice_count=invoice_count)


@customer_portal.route("/deliveries")
@login_required
def deliveries():
    customer_id = require_customer()
    rows = Delivery.query.filter_by(customer_id=customer_id).order_by(Delivery.created_at.desc()).all()
    return render_template("customer_portal/deliveries.html", deliveries=rows)


@customer_portal.route("/deliveries/<int:delivery_id>")
@login_required
def delivery_detail(delivery_id):
    delivery = customer_delivery_or_404(delivery_id)
    history = [{"status": item.status, "timestamp": item.timestamp} for item in delivery.status_history]
    return render_template("customer_portal/delivery_detail.html", delivery=delivery, history=history, pod=delivery.pod)


@customer_portal.route("/deliveries/<int:delivery_id>/pod")
@login_required
def pod(delivery_id):
    delivery = customer_delivery_or_404(delivery_id)
    return render_template("customer_portal/pod.html", delivery=delivery, pod=delivery.pod)


@customer_portal.route("/invoices")
@login_required
def invoices():
    customer_id = require_customer()
    rows = Invoice.query.filter(Invoice.customer_id == customer_id,
        Invoice.status.in_(["Sent", "Viewed", "Partially Paid", "Paid", "Overdue"])).order_by(Invoice.created_at.desc()).all()
    # Exclude invoices whose linked delivery belongs to a different customer.
    rows = [i for i in rows if not i.delivery_id or (i.delivery and i.delivery.customer_id == customer_id)]
    return render_template("customer_portal/invoices.html", invoices=rows)


@customer_portal.route("/invoices/<int:invoice_id>")
@login_required
def invoice_detail(invoice_id):
    invoice = customer_invoice_or_404(invoice_id)
    return render_template("customer_portal/invoice_detail.html", invoice=invoice)
