from flask import abort
from flask_login import current_user
from app.models import Delivery, Invoice


def require_customer():
    if (not current_user.is_authenticated or current_user.role != "customer"
            or not current_user.is_active_user or not current_user.customer_id
            or not current_user.customer_record):
        abort(403)
    return current_user.customer_id


def customer_delivery_or_404(delivery_id):
    customer_id = require_customer()
    return Delivery.query.filter_by(id=delivery_id, customer_id=customer_id).first_or_404()


def customer_invoice_or_404(invoice_id):
    customer_id = require_customer()
    invoice = Invoice.query.filter_by(id=invoice_id, customer_id=customer_id).first_or_404()
    if invoice.status not in {"Sent", "Viewed", "Partially Paid", "Paid", "Overdue"}:
        abort(404)
    if invoice.delivery_id and (not invoice.delivery or invoice.delivery.customer_id != customer_id):
        abort(404)
    return invoice
