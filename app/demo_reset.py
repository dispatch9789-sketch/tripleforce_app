"""Admin-only operational data reset used after prototype/demo testing."""

from app.extensions import db
from app.models import (
    ChainOfCustody,
    ChecklistResponse,
    CompanySettings,
    Contact,
    Customer,
    CustomerAccountRequest,
    CustomerInvitation,
    Delivery,
    DeliveryStatusHistory,
    DriverBreak,
    DriverCorrection,
    DriverMessage,
    DriverMileageLog,
    DriverRouteSession,
    DriverStopEvent,
    DriverWeeklySummary,
    DriverWorkSession,
    Invoice,
    InvoiceLineItem,
    Payment,
    ProofOfDelivery,
    Quote,
    QuoteLineItem,
    Reminder,
    UploadedDocument,
    User,
    delivery_drivers,
)


def clear_demo_data():
    """Clear operational prototype data while preserving configuration.

    The delete order follows foreign-key dependencies. The entire reset is one
    database transaction, so an error leaves the existing data untouched.
    """
    counts = {
        "customers": Customer.query.count(),
        "deliveries": Delivery.query.count(),
        "quotes": Quote.query.count(),
        "invoices": Invoice.query.count(),
        "customer_users": User.query.filter_by(role="customer").count(),
        "account_requests": CustomerAccountRequest.query.count(),
    }

    # Customer portal identities and approval records.
    CustomerInvitation.query.delete(synchronize_session=False)
    CustomerAccountRequest.query.delete(synchronize_session=False)

    # Driver activity can point at deliveries. Driver profiles and driver
    # login accounts are deliberately preserved.
    DriverStopEvent.query.delete(synchronize_session=False)
    DriverMileageLog.query.delete(synchronize_session=False)
    DriverBreak.query.delete(synchronize_session=False)
    DriverRouteSession.query.delete(synchronize_session=False)
    DriverWorkSession.query.delete(synchronize_session=False)
    ChecklistResponse.query.delete(synchronize_session=False)
    DriverMessage.query.delete(synchronize_session=False)
    DriverCorrection.query.delete(synchronize_session=False)
    DriverWeeklySummary.query.delete(synchronize_session=False)

    # Operational delivery and billing records.
    UploadedDocument.query.delete(synchronize_session=False)
    Payment.query.delete(synchronize_session=False)
    InvoiceLineItem.query.delete(synchronize_session=False)
    Invoice.query.delete(synchronize_session=False)
    ProofOfDelivery.query.delete(synchronize_session=False)
    ChainOfCustody.query.delete(synchronize_session=False)
    DeliveryStatusHistory.query.delete(synchronize_session=False)
    db.session.execute(delivery_drivers.delete())
    Delivery.query.delete(synchronize_session=False)
    QuoteLineItem.query.delete(synchronize_session=False)
    Quote.query.delete(synchronize_session=False)
    Reminder.query.delete(synchronize_session=False)
    Contact.query.delete(synchronize_session=False)

    # Customer logins must be removed before their owning customer rows.
    User.query.filter_by(role="customer").delete(synchronize_session=False)
    Customer.query.delete(synchronize_session=False)

    settings = db.session.get(CompanySettings, 1)
    if settings:
        settings.order_next_number = 1001
        settings.quote_next_number = 1001
        settings.invoice_next_number = 1001

    db.session.commit()
    return counts
