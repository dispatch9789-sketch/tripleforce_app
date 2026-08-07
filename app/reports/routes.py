"""Reports blueprint: revenue dashboard and analytics."""
import csv
from io import StringIO
from datetime import date, timedelta, datetime
from collections import defaultdict

from flask import Blueprint, render_template, request, Response, send_file
from flask_login import login_required
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from io import BytesIO

from app.extensions import db
from app.models import Payment, Invoice, Delivery, Customer, Expense
from app.utils import dispatcher_or_above

reports = Blueprint("reports", __name__)


@reports.route("/")
@login_required
@dispatcher_or_above
def index():
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    year_start = today.replace(month=1, day=1)

    # Revenue summaries
    revenue_today = db.session.query(db.func.sum(Payment.amount)).filter(Payment.payment_date == today).scalar() or 0
    revenue_week = db.session.query(db.func.sum(Payment.amount)).filter(Payment.payment_date >= week_start).scalar() or 0
    revenue_month = db.session.query(db.func.sum(Payment.amount)).filter(Payment.payment_date >= month_start).scalar() or 0
    revenue_year = db.session.query(db.func.sum(Payment.amount)).filter(Payment.payment_date >= year_start).scalar() or 0

    # Invoice stats
    outstanding = db.session.query(db.func.sum(Invoice.balance_due)).filter(
        Invoice.status.in_(["Sent", "Viewed", "Partially Paid", "Overdue"])
    ).scalar() or 0

    overdue_count = Invoice.query.filter(Invoice.status == "Overdue").count()
    overdue_amount = db.session.query(db.func.sum(Invoice.balance_due)).filter(
        Invoice.status == "Overdue"
    ).scalar() or 0

    paid_count = Invoice.query.filter(Invoice.status == "Paid").count()
    paid_amount = db.session.query(db.func.sum(Invoice.paid_amount)).filter(
        Invoice.status == "Paid"
    ).scalar() or 0

    # Delivery stats
    completed = Delivery.query.filter(Delivery.status.in_(["Delivered", "Completed"])).count()
    cancelled = Delivery.query.filter(Delivery.status == "Cancelled").count()
    total_mileage = db.session.query(db.func.sum(Delivery.mileage)).filter(
        Delivery.status.in_(["Delivered", "Completed"])
    ).scalar() or 0

    # Revenue by customer
    cust_revenue = db.session.query(
        Customer.business_name,
        db.func.sum(Payment.amount).label("total")
    ).join(Payment, Payment.customer_id == Customer.id).group_by(Customer.id, Customer.business_name).order_by(
        db.func.sum(Payment.amount).desc()
    ).limit(10).all()

    # Revenue by service type
    svc_revenue = db.session.query(
        Delivery.service_type,
        db.func.sum(Delivery.quote_amount).label("total")
    ).filter(Delivery.status.in_(["Delivered", "Completed"])).group_by(Delivery.service_type).all()

    # Average delivery value
    avg_value = db.session.query(db.func.avg(Delivery.quote_amount)).filter(
        Delivery.status.in_(["Delivered", "Completed"])
    ).scalar() or 0

    # Expenses
    expenses_month = db.session.query(db.func.sum(Expense.amount)).filter(
        Expense.date >= month_start
    ).scalar() or 0

    # Monthly trend (last 6 months)
    monthly = []
    for i in range(5, -1, -1):
        m_start = (today.replace(day=1) - timedelta(days=i * 30)).replace(day=1)
        m_end = (m_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        rev = db.session.query(db.func.sum(Payment.amount)).filter(
            Payment.payment_date >= m_start, Payment.payment_date <= m_end
        ).scalar() or 0
        monthly.append({"month": m_start.strftime("%b %Y"), "revenue": rev})

    return render_template("reports/index.html",
        revenue_today=revenue_today, revenue_week=revenue_week,
        revenue_month=revenue_month, revenue_year=revenue_year,
        outstanding=outstanding, overdue_count=overdue_count,
        overdue_amount=overdue_amount, paid_count=paid_count,
        paid_amount=paid_amount, completed=completed, cancelled=cancelled,
        total_mileage=total_mileage, avg_value=avg_value,
        cust_revenue=cust_revenue, svc_revenue=svc_revenue,
        expenses_month=expenses_month, monthly=monthly,
    )


@reports.route("/export/<report_type>")
@login_required
@dispatcher_or_above
def export_csv(report_type):
    """Export various report types as CSV."""
    output = StringIO()
    writer = csv.writer(output)

    if report_type == "revenue":
        writer.writerow(["Payment Date", "Invoice #", "Customer", "Amount", "Method", "Reference"])
        for p in Payment.query.order_by(Payment.payment_date.desc()).all():
            writer.writerow([
                p.payment_date, p.invoice.invoice_number if p.invoice else "",
                p.customer.business_name if p.customer else "",
                f"{p.amount:.2f}", p.payment_method or "", p.reference_number or "",
            ])
    elif report_type == "invoices":
        writer.writerow(["Invoice #", "Customer", "Service Date", "Due Date", "Total", "Paid", "Balance", "Status"])
        for inv in Invoice.query.order_by(Invoice.created_at.desc()).all():
            writer.writerow([
                inv.invoice_number, inv.billing_name, inv.service_date, inv.due_date,
                f"{inv.total_due:.2f}", f"{inv.paid_amount:.2f}", f"{inv.balance:.2f}", inv.status,
            ])
    elif report_type == "deliveries":
        writer.writerow(["Order #", "Customer", "Status", "Service Type", "Pickup", "Delivery", "Mileage", "Amount"])
        for d in Delivery.query.order_by(Delivery.created_at.desc()).all():
            writer.writerow([
                d.order_number, d.customer.business_name if d.customer else "",
                d.status, d.service_type, d.pickup_address, d.delivery_address,
                d.mileage, f"{d.quote_amount:.2f}",
            ])
    elif report_type == "customers":
        writer.writerow(["Customer", "Category", "Status", "Total Revenue", "Deliveries", "Invoices"])
        for c in Customer.query.filter_by(is_archived=False).all():
            writer.writerow([
                c.business_name, c.category, c.status,
                f"{c.total_revenue:.2f}",
                Delivery.query.filter_by(customer_id=c.id).count(),
                Invoice.query.filter_by(customer_id=c.id).count(),
            ])
    else:
        writer.writerow(["Unknown report type"])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={report_type}_report.csv"}
    )


@reports.route("/pdf")
@login_required
@dispatcher_or_above
def revenue_pdf():
    """Generate a revenue summary PDF."""
    today = date.today()
    month_start = today.replace(day=1)
    year_start = today.replace(month=1, day=1)

    revenue_month = db.session.query(db.func.sum(Payment.amount)).filter(
        Payment.payment_date >= month_start
    ).scalar() or 0
    revenue_year = db.session.query(db.func.sum(Payment.amount)).filter(
        Payment.payment_date >= year_start
    ).scalar() or 0

    outstanding = db.session.query(db.func.sum(Invoice.balance_due)).filter(
        Invoice.status.in_(["Sent", "Viewed", "Partially Paid", "Overdue"])
    ).scalar() or 0

    cust_revenue = db.session.query(
        Customer.business_name, db.func.sum(Payment.amount).label("total")
    ).join(Payment, Payment.customer_id == Customer.id).group_by(Customer.id, Customer.business_name).order_by(
        db.func.sum(Payment.amount).desc()
    ).limit(15).all()

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=0.75*inch, bottomMargin=0.75*inch,
                            leftMargin=0.75*inch, rightMargin=0.75*inch)
    styles = getSampleStyleSheet()
    navy = HexColor("#1a3a5c")
    gray = HexColor("#666666")
    title_style = ParagraphStyle("T", parent=styles["Title"], fontSize=18, textColor=navy)
    heading = ParagraphStyle("H", parent=styles["Heading2"], fontSize=12, textColor=navy, spaceAfter=6)

    elements = [
        Paragraph("Triple Force Logistic LLC", title_style),
        Paragraph(f"Revenue Report — {today.strftime('%B %d, %Y')}", heading),
        Spacer(1, 0.2*inch),
    ]

    summary = [
        ["Metric", "Amount"],
        ["Revenue This Month", f"${revenue_month:,.2f}"],
        ["Revenue This Year", f"${revenue_year:,.2f}"],
        ["Outstanding Invoices", f"${outstanding:,.2f}"],
    ]
    t = Table(summary, colWidths=[3*inch, 2*inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), navy),
        ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#ffffff")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 0.3*inch))

    elements.append(Paragraph("Top Customers by Revenue", heading))
    cust_rows = [["Customer", "Revenue"]] + [
        [name or "N/A", f"${total:,.2f}"] for name, total in cust_revenue
    ]
    ct = Table(cust_rows, colWidths=[3*inch, 2*inch])
    ct.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), navy),
        ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#ffffff")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(ct)

    doc.build(elements)
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name="revenue_report.pdf", mimetype="application/pdf")
