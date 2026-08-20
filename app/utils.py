"""Utility functions: quote calculation, PDF generation, email helpers, formatting."""
import os
from datetime import datetime, date
from functools import wraps
from io import BytesIO

from flask import current_app, url_for, render_template, abort
from flask_login import current_user

from app.extensions import db, mail
from app.models import (
    CompanySettings, PricingSettings, EmailTemplate,
    Quote, Delivery, Invoice,
)


# ═══════════════════════════════════════════════════════════════
#  ROLE-BASED PERMISSION DECORATORS
# ═══════════════════════════════════════════════════════════════
def role_required(*roles):
    """Decorator: require user to have one of the specified roles."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return current_app.login_manager.unauthorized()
            if current_user.role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def admin_required(f):
    """Decorator: require admin role."""
    return role_required("admin")(f)


def dispatcher_or_above(f):
    """Decorator: require admin or dispatcher role."""
    return role_required("admin", "dispatcher")(f)


def driver_or_above(f):
    """Decorator: require admin, dispatcher, or driver role."""
    return role_required("admin", "dispatcher", "driver")(f)


# ═══════════════════════════════════════════════════════════════
#  SETTINGS HELPERS
# ═══════════════════════════════════════════════════════════════
def get_company_settings():
    """Get or create the singleton company settings row."""
    settings = CompanySettings.query.get(1)
    if not settings:
        settings = CompanySettings(id=1)
        db.session.add(settings)
        db.session.commit()
    return settings


def get_pricing_settings():
    """Get or create the singleton pricing settings row."""
    settings = PricingSettings.query.get(1)
    if not settings:
        settings = PricingSettings(id=1)
        db.session.add(settings)
        db.session.commit()
    return settings


def generate_number(prefix, next_num):
    """Generate a formatted number like TF-1001."""
    return f"{prefix}-{next_num:04d}"


def get_next_invoice_number():
    s = get_company_settings()
    num = generate_number(s.invoice_prefix, s.invoice_next_number)
    s.invoice_next_number += 1
    db.session.commit()
    return num


def get_next_quote_number():
    s = get_company_settings()
    num = generate_number(s.quote_prefix, s.quote_next_number)
    s.quote_next_number += 1
    db.session.commit()
    return num


def get_next_order_number():
    s = get_company_settings()
    num = generate_number(s.order_prefix, s.order_next_number)
    s.order_next_number += 1
    db.session.commit()
    return num


# ═══════════════════════════════════════════════════════════════
#  QUOTE CALCULATOR
# ═══════════════════════════════════════════════════════════════
def calculate_quote(form_data, pricing=None):
    """
    Calculate a delivery quote from form data (dict or form object).
    Returns a dict of all line items and the total.
    """
    if pricing is None:
        pricing = get_pricing_settings()

    print("PRICING DEBUG:", pricing.base_charge, pricing.per_mile_charge)

    mileage = float(form_data.get("estimated_mileage", 0) or 0)
    trip_type = form_data.get("trip_type", "one-way")

    # Double mileage for round-trip
    effective_mileage = mileage * 2 if trip_type == "round-trip" else mileage

    # Base charges
    base_charge = pricing.base_charge
    mileage_charge = effective_mileage * pricing.per_mile_charge

    # Service surcharges
    rush_charge = pricing.rush_charge if form_data.get("is_rush") in (True, "y", "true") else 0
    stat_charge = pricing.stat_charge if form_data.get("is_stat") in (True, "y", "true") else 0
    same_day_charge = pricing.same_day_charge if form_data.get("is_same_day") in (True, "y", "true") else 0
    after_hours_charge = pricing.after_hours_charge if form_data.get("is_after_hours") in (True, "y", "true") else 0
    weekend_charge = pricing.weekend_charge if form_data.get("is_weekend") in (True, "y", "true") else 0
    holiday_charge = pricing.holiday_charge if form_data.get("is_holiday") in (True, "y", "true") else 0

    # Additional charges
    wait_time_minutes = float(form_data.get("wait_time_minutes", 0) or 0)
    wait_time_charge = wait_time_minutes * pricing.wait_time_per_minute
    additional_stop_charge = pricing.additional_stop_charge * float(form_data.get("additional_stops", 0) or 0)
    toll_charge = float(form_data.get("toll_charge", 0) or pricing.toll_charge)
    parking_charge = float(form_data.get("parking_charge", 0) or pricing.parking_charge)
    special_handling_charge = pricing.special_handling_charge if form_data.get("special_handling") in (True, "y", "true") else 0
    temp_control_charge = pricing.temperature_controlled_charge if form_data.get("temperature_controlled") in (True, "y", "true") else 0

    # Subtotal before discounts
    subtotal = (
        base_charge + mileage_charge + rush_charge + stat_charge + same_day_charge +
        after_hours_charge + weekend_charge + holiday_charge + wait_time_charge +
        additional_stop_charge + toll_charge + parking_charge + special_handling_charge +
        temp_control_charge
    )

    # Discounts (percentage)
    route_discount = 0
    if form_data.get("apply_route_discount") in (True, "y", "true"):
        route_discount = subtotal * (pricing.route_discount_pct / 100)
    contract_discount = 0
    if form_data.get("apply_contract_discount") in (True, "y", "true"):
        contract_discount = subtotal * (pricing.contract_discount_pct / 100)

    # Manual adjustment
    manual_adjustment = float(form_data.get("manual_adjustment", 0) or 0)

    # After discounts
    after_discounts = subtotal - route_discount - contract_discount + manual_adjustment

    # Apply minimum charge
    if after_discounts < pricing.minimum_charge:
        after_discounts = pricing.minimum_charge

    # Tax
    tax_rate = float(form_data.get("tax_rate", pricing.tax_rate) or 0)
    tax_amount = after_discounts * (tax_rate / 100)
    total = after_discounts + tax_amount

    return {
        "base_charge": round(base_charge, 2),
        "mileage_charge": round(mileage_charge, 2),
        "effective_mileage": effective_mileage,
        "rush_charge": round(rush_charge, 2),
        "stat_charge": round(stat_charge, 2),
        "same_day_charge": round(same_day_charge, 2),
        "after_hours_charge": round(after_hours_charge, 2),
        "weekend_charge": round(weekend_charge, 2),
        "holiday_charge": round(holiday_charge, 2),
        "wait_time_charge": round(wait_time_charge, 2),
        "additional_stop_charge": round(additional_stop_charge, 2),
        "toll_charge": round(toll_charge, 2),
        "parking_charge": round(parking_charge, 2),
        "special_handling_charge": round(special_handling_charge, 2),
        "temp_control_charge": round(temp_control_charge, 2),
        "subtotal": round(subtotal, 2),
        "route_discount": round(route_discount, 2),
        "contract_discount": round(contract_discount, 2),
        "manual_adjustment": round(manual_adjustment, 2),
        "after_discounts": round(after_discounts, 2),
        "tax_rate": tax_rate,
        "tax_amount": round(tax_amount, 2),
        "total": round(total, 2),
    }


# ═══════════════════════════════════════════════════════════════
#  PDF GENERATION
# ═══════════════════════════════════════════════════════════════
def generate_quote_pdf(quote, settings=None):
    """Generate a PDF for a quote and return BytesIO buffer."""
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT

    if settings is None:
        settings = get_company_settings()

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter,
                            topMargin=0.75*inch, bottomMargin=0.75*inch,
                            leftMargin=0.75*inch, rightMargin=0.75*inch)
    styles = getSampleStyleSheet()
    navy = HexColor("#1a3a5c")
    gray = HexColor("#666666")

    title_style = ParagraphStyle("CustomTitle", parent=styles["Title"], fontSize=20, textColor=navy, spaceAfter=4)
    subtitle_style = ParagraphStyle("Subtitle", parent=styles["Normal"], fontSize=10, textColor=gray, spaceAfter=12)
    heading_style = ParagraphStyle("Heading", parent=styles["Heading2"], fontSize=12, textColor=navy, spaceAfter=6)
    normal_style = styles["Normal"]
    right_style = ParagraphStyle("Right", parent=normal_style, alignment=TA_RIGHT)

    elements = []

    # Header
    elements.append(Paragraph(settings.company_name, title_style))
    elements.append(Paragraph(f"{settings.address or ''}", subtitle_style))
    elements.append(Paragraph(f"Phone: {settings.phone or 'N/A'} | Email: {settings.email}", subtitle_style))
    elements.append(Spacer(1, 0.2*inch))

    # Quote title
    elements.append(Paragraph(f"<b>QUOTE {quote.quote_number}</b>", heading_style))
    elements.append(Paragraph(f"Date: {quote.created_at.strftime('%B %d, %Y') if quote.created_at else 'N/A'}", normal_style))
    if quote.expires_at:
        elements.append(Paragraph(f"Valid Until: {quote.expires_at.strftime('%B %d, %Y')}", normal_style))
    elements.append(Spacer(1, 0.15*inch))

    # Customer info
    elements.append(Paragraph("<b>Prepared For:</b>", heading_style))
    elements.append(Paragraph(quote.customer_name or "N/A", normal_style))
    if quote.customer_email:
        elements.append(Paragraph(quote.customer_email, normal_style))
    elements.append(Spacer(1, 0.15*inch))

    # Route info
    elements.append(Paragraph("<b>Delivery Route</b>", heading_style))
    route_data = [
        ["Pickup:", quote.pickup_address or "N/A"],
        ["Delivery:", quote.delivery_address or "N/A"],
        ["Mileage:", f"{quote.estimated_mileage or 0:.1f} miles ({quote.trip_type or 'one-way'})"],
    ]
    route_table = Table(route_data, colWidths=[1.5*inch, 5*inch])
    route_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TEXTCOLOR", (0, 0), (0, -1), gray),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(route_table)
    elements.append(Spacer(1, 0.2*inch))

    # Charges table
    elements.append(Paragraph("<b>Charges</b>", heading_style))
    charge_rows = [
        ["Description", "Amount"],
        ["Base delivery charge", f"${quote.base_charge:.2f}"],
        ["Mileage charge", f"${quote.mileage_charge:.2f}"],
    ]
    if quote.rush_charge:
        charge_rows.append(["Rush/STAT surcharge", f"${quote.rush_charge:.2f}"])
    if quote.after_hours_charge:
        charge_rows.append(["After-hours surcharge", f"${quote.after_hours_charge:.2f}"])
    if quote.weekend_charge:
        charge_rows.append(["Weekend surcharge", f"${quote.weekend_charge:.2f}"])
    if quote.holiday_charge:
        charge_rows.append(["Holiday surcharge", f"${quote.holiday_charge:.2f}"])
    if quote.wait_time_charge:
        charge_rows.append(["Wait time charge", f"${quote.wait_time_charge:.2f}"])
    if quote.additional_stop_charge:
        charge_rows.append(["Additional stop charge", f"${quote.additional_stop_charge:.2f}"])
    if quote.toll_charge:
        charge_rows.append(["Toll charge", f"${quote.toll_charge:.2f}"])
    if quote.parking_charge:
        charge_rows.append(["Parking charge", f"${quote.parking_charge:.2f}"])
    if quote.special_handling_charge:
        charge_rows.append(["Special handling", f"${quote.special_handling_charge:.2f}"])
    if quote.temp_control_charge:
        charge_rows.append(["Temperature-controlled delivery", f"${quote.temp_control_charge:.2f}"])
    if quote.route_discount:
        charge_rows.append(["Route discount", f"-${quote.route_discount:.2f}"])
    if quote.contract_discount:
        charge_rows.append(["Contract discount", f"-${quote.contract_discount:.2f}"])
    if quote.manual_adjustment:
        charge_rows.append(["Manual adjustment", f"${quote.manual_adjustment:+.2f}"])
    if quote.tax_amount:
        charge_rows.append([f"Tax ({quote.tax_rate:.1f}%)", f"${quote.tax_amount:.2f}"])
    charge_rows.append(["", ""])
    charge_rows.append(["TOTAL", f"${quote.total:.2f}"])

    charges_table = Table(charge_rows, colWidths=[4*inch, 2*inch])
    charges_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), navy),
        ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#ffffff")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, 0), 1, navy),
        ("LINEABOVE", (0, -1), (-1, -1), 1, navy),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, -1), (-1, -1), 12),
        ("TEXTCOLOR", (0, -1), (-1, -1), navy),
    ]))
    elements.append(charges_table)
    elements.append(Spacer(1, 0.3*inch))

    # Notes
    if quote.notes:
        elements.append(Paragraph("<b>Notes:</b>", heading_style))
        elements.append(Paragraph(quote.notes, normal_style))

    # Footer
    elements.append(Spacer(1, 0.4*inch))
    footer_style = ParagraphStyle("Footer", parent=normal_style, fontSize=8, textColor=gray, alignment=TA_CENTER)
    elements.append(Paragraph(
        f"{settings.company_name} | {settings.email} | {settings.phone or ''}",
        footer_style
    ))

    doc.build(elements)
    buf.seek(0)
    return buf


def generate_invoice_pdf(invoice, settings=None):
    """Generate a PDF for an invoice and return BytesIO buffer."""
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.enums import TA_CENTER

    if settings is None:
        settings = get_company_settings()

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter,
                            topMargin=0.75*inch, bottomMargin=0.75*inch,
                            leftMargin=0.75*inch, rightMargin=0.75*inch)
    styles = getSampleStyleSheet()
    navy = HexColor("#1a3a5c")
    gray = HexColor("#666666")

    title_style = ParagraphStyle("CustomTitle", parent=styles["Title"], fontSize=20, textColor=navy, spaceAfter=4)
    subtitle_style = ParagraphStyle("Subtitle", parent=styles["Normal"], fontSize=10, textColor=gray, spaceAfter=12)
    heading_style = ParagraphStyle("Heading", parent=styles["Heading2"], fontSize=12, textColor=navy, spaceAfter=6)
    normal_style = styles["Normal"]
    center_style = ParagraphStyle("Center", parent=normal_style, alignment=TA_CENTER)

    elements = []

    # Header
    elements.append(Paragraph(settings.company_name, title_style))
    elements.append(Paragraph(settings.address or "", subtitle_style))
    elements.append(Paragraph(f"Phone: {settings.phone or 'N/A'} | Email: {settings.email}", subtitle_style))
    elements.append(Spacer(1, 0.2*inch))

    # Invoice title and number
    elements.append(Paragraph(f"<b>INVOICE {invoice.invoice_number}</b>", heading_style))
    inv_info = [
        ["Invoice Date:", invoice.created_at.strftime("%B %d, %Y") if invoice.created_at else "N/A"],
        ["Due Date:", invoice.due_date.strftime("%B %d, %Y") if invoice.due_date else "N/A"],
        ["Status:", invoice.status],
        ["Payment Terms:", invoice.payment_terms or "Net 30"],
    ]
    info_table = Table(inv_info, colWidths=[1.5*inch, 3*inch])
    info_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 0.15*inch))

    # Bill To
    elements.append(Paragraph("<b>Bill To:</b>", heading_style))
    elements.append(Paragraph(invoice.billing_name or "N/A", normal_style))
    if invoice.billing_address:
        elements.append(Paragraph(invoice.billing_address, normal_style))
    elements.append(Spacer(1, 0.15*inch))

    # Line items
    elements.append(Paragraph("<b>Charges</b>", heading_style))
    rows = [["Description", "Qty", "Unit Price", "Total"]]
    for item in invoice.line_items:
        rows.append([item.description, str(item.quantity), f"${item.unit_price:.2f}", f"${item.total:.2f}"])
    if not invoice.line_items:
        rows.append([invoice.delivery_description or "Delivery service", "1", f"${invoice.base_charge:.2f}", f"${invoice.base_charge:.2f}"])

    rows.append(["", "", "", ""])
    rows.append(["Subtotal", "", "", f"${invoice.subtotal:.2f}"])
    if invoice.additional_charges:
        rows.append(["Additional charges", "", "", f"${invoice.additional_charges:.2f}"])
    if invoice.discounts:
        rows.append(["Discounts", "", "", f"-${invoice.discounts:.2f}"])
    if invoice.tax_amount:
        rows.append(["Tax", "", "", f"${invoice.tax_amount:.2f}"])
    rows.append(["TOTAL DUE", "", "", f"${invoice.total_due:.2f}"])
    if invoice.paid_amount:
        rows.append(["Paid", "", "", f"-${invoice.paid_amount:.2f}"])
        rows.append(["BALANCE DUE", "", "", f"${invoice.balance:.2f}"])

    items_table = Table(rows, colWidths=[3.5*inch, 0.7*inch, 1.2*inch, 1.1*inch])
    items_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), navy),
        ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#ffffff")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, 0), 1, navy),
        ("LINEABOVE", (0, -3), (-1, -3), 0.5, gray),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 0.3*inch))

    # Payment instructions
    if invoice.payment_instructions or settings.payment_instructions:
        elements.append(Paragraph("<b>Payment Instructions:</b>", heading_style))
        elements.append(Paragraph(invoice.payment_instructions or settings.payment_instructions, normal_style))

    if invoice.notes:
        elements.append(Spacer(1, 0.15*inch))
        elements.append(Paragraph("<b>Notes:</b>", heading_style))
        elements.append(Paragraph(invoice.notes, normal_style))

    # Footer
    elements.append(Spacer(1, 0.4*inch))
    footer_style = ParagraphStyle("Footer", parent=normal_style, fontSize=8, textColor=gray, alignment=TA_CENTER)
    elements.append(Paragraph(
        f"Thank you for your business! | {settings.company_name} | {settings.email}",
        footer_style
    ))

    doc.build(elements)
    buf.seek(0)
    return buf


def generate_pod_pdf(delivery, settings=None):
    """Generate a proof-of-delivery PDF."""
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.enums import TA_CENTER

    if settings is None:
        settings = get_company_settings()

    pod = delivery.pod
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter,
                            topMargin=0.75*inch, bottomMargin=0.75*inch,
                            leftMargin=0.75*inch, rightMargin=0.75*inch)
    styles = getSampleStyleSheet()
    navy = HexColor("#1a3a5c")
    gray = HexColor("#666666")

    title_style = ParagraphStyle("Title", parent=styles["Title"], fontSize=18, textColor=navy)
    heading_style = ParagraphStyle("Heading", parent=styles["Heading2"], fontSize=11, textColor=navy, spaceAfter=6)
    normal_style = styles["Normal"]

    elements = []
    elements.append(Paragraph(settings.company_name, title_style))
    elements.append(Spacer(1, 0.15*inch))
    elements.append(Paragraph("<b>PROOF OF DELIVERY</b>", heading_style))
    elements.append(Paragraph(f"Order: {delivery.order_number}", normal_style))
    elements.append(Spacer(1, 0.15*inch))

    if pod:
        data = [
            ["Recipient:", pod.recipient_name or "N/A"],
            ["Delivery Date:", pod.delivery_date.strftime("%B %d, %Y") if pod.delivery_date else "N/A"],
            ["Delivery Time:", pod.delivery_time.strftime("%I:%M %p") if pod.delivery_time else "N/A"],
            ["Driver:", pod.driver_name or "N/A"],
            ["Refused:", "Yes" if pod.refused else "No"],
        ]
        if pod.refusal_reason:
            data.append(["Refusal Reason:", pod.refusal_reason])
        if pod.exception_reason:
            data.append(["Exception:", pod.exception_reason])
        if pod.notes:
            data.append(["Notes:", pod.notes])
    else:
        data = [["No proof of delivery recorded.", ""]]

    table = Table(data, colWidths=[1.5*inch, 5*inch])
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 0.3*inch))

    # Delivery route summary
    elements.append(Paragraph("<b>Delivery Route</b>", heading_style))
    route_data = [
        ["Pickup:", delivery.pickup_address or "N/A"],
        ["Delivery:", delivery.delivery_address or "N/A"],
        ["Customer:", delivery.customer.business_name if delivery.customer else "N/A"],
    ]
    route_table = Table(route_data, colWidths=[1.5*inch, 5*inch])
    route_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(route_table)

    # Footer
    elements.append(Spacer(1, 0.5*inch))
    footer_style = ParagraphStyle("Footer", parent=normal_style, fontSize=8, textColor=gray, alignment=TA_CENTER)
    elements.append(Paragraph(
        f"{settings.company_name} | {settings.email} | {settings.phone or ''}",
        footer_style
    ))

    doc.build(elements)
    buf.seek(0)
    return buf


# ═══════════════════════════════════════════════════════════════
#  EMAIL HELPERS
# ═══════════════════════════════════════════════════════════════
def get_email_template(template_type):
    """Get an email template by type, or return a default."""
    template = EmailTemplate.query.filter_by(template_type=template_type, is_active=True).first()
    if template:
        return template

    defaults = {
        "quote_sent": ("Your Quote from {company_name}", "Dear {customer_name},\n\nPlease find your delivery quote ({quote_number}) attached. The total is ${total}.\n\nThank you for considering {company_name}.\n\nBest regards,\n{company_name}"),
        "quote_accepted": ("Quote Accepted - {quote_number}", "Your quote {quote_number} has been accepted. We will process your delivery promptly."),
        "delivery_confirmed": ("Delivery Confirmed - {order_number}", "Your delivery {order_number} has been confirmed. We will keep you updated on the progress."),
        "driver_assigned": ("Driver Assigned - {order_number}", "A driver has been assigned to your delivery {order_number}."),
        "pickup_completed": ("Pickup Completed - {order_number}", "Your package has been picked up for delivery {order_number}."),
        "delivery_in_progress": ("Delivery In Progress - {order_number}", "Your delivery {order_number} is in progress."),
        "delivery_completed": ("Delivery Completed - {order_number}", "Your delivery {order_number} has been completed successfully."),
        "proof_of_delivery": ("Proof of Delivery - {order_number}", "Please find the proof of delivery for order {order_number} attached."),
        "invoice_sent": ("Invoice {invoice_number} from {company_name}", "Dear {customer_name},\n\nPlease find invoice {invoice_number} attached. The total due is ${total}.\n\nPayment Terms: {payment_terms}\nDue Date: {due_date}\n\n{payment_instructions}\n\nThank you for your business."),
        "invoice_due": ("Invoice {invoice_number} Due Soon", "This is a reminder that invoice {invoice_number} for ${total} is due soon."),
        "invoice_overdue": ("OVERDUE: Invoice {invoice_number}", "This is a reminder that invoice {invoice_number} for ${total} is now overdue. Please remit payment as soon as possible."),
        "customer_followup": ("Following Up - {company_name}", "Dear {customer_name},\n\nI wanted to follow up regarding your delivery needs. Please let us know how we can assist you.\n\nBest regards,\n{company_name}"),
    }

    subj, body = defaults.get(template_type, ("Notification from {company_name}", "You have a notification from {company_name}."))
    # Return a lightweight object that mimics EmailTemplate
    class DefaultTemplate:
        def __init__(self, s, b):
            self.subject = s
            self.body = b
    return DefaultTemplate(subj, body)


def send_email(to, subject, body, attachments=None):
    """
    Send an email using Flask-Mail with a hard socket timeout so a slow or
    unresponsive SMTP server cannot hang a Gunicorn worker.
    Returns True on success, False on failure.
    SMTP/socket/TLS/network errors are logged and never crash the worker.
    In development without mail config, logs but doesn't fail.
    """
    import socket
    import smtplib
    import ssl

    previous_timeout = socket.getdefaulttimeout()
    mail_timeout = current_app.config.get("MAIL_TIMEOUT", 10)

    try:
        from flask_mail import Message
        settings = get_company_settings()
        msg = Message(
            subject=subject,
            recipients=[to] if isinstance(to, str) else to,
            body=body,
            sender=settings.email or current_app.config.get("MAIL_DEFAULT_SENDER"),
        )
        if attachments:
            for filename, content_type, data in attachments:
                msg.attach(filename, content_type, data)

        # Apply a short default timeout to all socket operations (SMTP
        # connect, TLS handshake, and send) so a stuck SMTP server cannot
        # block the Gunicorn worker indefinitely.
        socket.setdefaulttimeout(float(mail_timeout))
        mail.send(msg)
        return True
    except (
        smtplib.SMTPException,
        socket.timeout,
        TimeoutError,
        ssl.SSLError,
        OSError,
    ) as e:
        # Network / SMTP / TLS errors must never crash the worker.
        current_app.logger.exception(f"Email send failed: {e}")
        return False
    except Exception as e:
        # Anything else (e.g. missing mail config in dev) is non-fatal too.
        current_app.logger.info(f"Email send failed (expected in dev): {e}")
        return False
    finally:
        # Always restore the previous default socket timeout.
        socket.setdefaulttimeout(previous_timeout)


def render_email_template(template_type, context):
    """Render an email template with context variables."""
    template = get_email_template(template_type)
    settings = get_company_settings()
    ctx = {**context, "company_name": settings.company_name}
    try:
        subject = template.subject.format(**ctx)
        body = template.body.format(**ctx)
    except (KeyError, AttributeError):
        subject = template.subject
        body = template.body
    return subject, body


# ═══════════════════════════════════════════════════════════════
#  FILE UPLOAD HELPERS
# ═══════════════════════════════════════════════════════════════
def allowed_file(filename):
    """Check if a file has an allowed extension."""
    allowed = current_app.config.get("ALLOWED_EXTENSIONS", set())
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed


def secure_filename(filename):
    """Sanitize a filename for safe storage."""
    import re
    import unicodedata
    filename = unicodedata.normalize("NFKD", filename).encode("ascii", "ignore").decode("ascii")
    filename = re.sub(r"[^\w\s.-]", "", filename).strip()
    # Prefix with timestamp to avoid collisions
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_")
    return timestamp + filename


def save_uploaded_file(file_storage, subfolder=""):
    """Save an uploaded file and return the filename (not full path)."""
    if not file_storage or not file_storage.filename:
        return None
    if not allowed_file(file_storage.filename):
        return None
    filename = secure_filename(file_storage.filename)
    upload_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], subfolder)
    os.makedirs(upload_dir, exist_ok=True)
    file_storage.save(os.path.join(upload_dir, filename))
    return filename


# ═══════════════════════════════════════════════════════════════
#  FORMATTING HELPERS
# ═══════════════════════════════════════════════════════════════
def format_currency(value):
    """Format a number as USD currency."""
    if value is None:
        return "$0.00"
    return f"${float(value):,.2f}"


def format_datetime(value, fmt="%b %d, %Y %I:%M %p"):
    """Format a datetime for display."""
    if value is None:
        return "—"
    if isinstance(value, str):
        return value
    try:
        return value.strftime(fmt)
    except (AttributeError, ValueError):
        return str(value)


# ═══════════════════════════════════════════════════════════════
#  JINJA CONTEXT PROCESSOR
# ═══════════════════════════════════════════════════════════════
def inject_settings():
    """Inject company settings into all templates."""
    try:
        settings = get_company_settings()
    except Exception:
        settings = None
    try:
        pricing = get_pricing_settings()
    except Exception:
        pricing = None
    from datetime import date as _date, datetime as _dt
    return {
        "company_settings": settings,
        "pricing_settings": pricing,
        "current_year": datetime.utcnow().year,
        "today": _date.today(),
        "now": _dt.utcnow,
    }


# ═══════════════════════════════════════════════════════════════
#  GOOGLE MAPS ROUTES API - DRIVING DISTANCE
# ═══════════════════════════════════════════════════════════════
def get_driving_distance(pickup_address, delivery_address):
    """
    Call the Google Maps Routes API (computeRoutes) and return the
    driving distance in miles between pickup_address and delivery_address.

    Returns a float (miles, 2 dp) or None on any failure.
    """
    if not pickup_address or not delivery_address:
        return None

    api_key = current_app.config.get("GOOGLE_MAPS_API_KEY") or os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        current_app.logger.error("GOOGLE_MAPS_API_KEY is not configured; cannot calculate mileage.")
        return None

    import json
    import urllib.request
    import urllib.error

    url = "https://routes.googleapis.com/directions/v2:computeRoutes"
    payload = {
        "origin": {"address": pickup_address},
        "destination": {"address": delivery_address},
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE",
        "units": "IMPERIAL",
    }
    body = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": "routes.distanceMeters",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        current_app.logger.error(f"Google Routes API HTTPError {e.code}: {e.reason}")
        return None
    except Exception as e:
        current_app.logger.error(f"Google Routes API request failed: {e}")
        return None

    try:
        routes = data.get("routes", [])
        if not routes:
            current_app.logger.error(f"Google Routes API returned no routes: {data}")
            return None
        distance_meters = float(routes[0].get("distanceMeters", 0))
        miles = round(distance_meters / 1609.344, 2)
        return miles if miles > 0 else None
    except (TypeError, ValueError, IndexError) as e:
        current_app.logger.error(f"Failed to parse Google Routes API response: {e}")
        return None
