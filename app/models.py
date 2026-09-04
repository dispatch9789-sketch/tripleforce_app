"""Database models for Triple Force Logistic LLC.

All models use SQLAlchemy with SQLite by default.
To upgrade to PostgreSQL, change DATABASE_URL in .env — no model changes needed.
"""
from datetime import datetime, date
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db


# ── Association table for delivery-driver (future multi-driver support) ──
delivery_drivers = db.Table(
    "delivery_drivers",
    db.Column("delivery_id", db.Integer, db.ForeignKey("deliveries.id"), primary_key=True),
    db.Column("driver_id", db.Integer, db.ForeignKey("drivers.id"), primary_key=True),
)


# ═══════════════════════════════════════════════════════════════
#  USERS
# ═══════════════════════════════════════════════════════════════
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    phone = db.Column(db.String(30))
    role = db.Column(db.String(20), default="admin")  # admin, dispatcher, driver
    is_active_user = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

    # Link to Driver record if role == "driver"
    driver_record_id = db.Column(db.Integer, db.ForeignKey("drivers.id"), nullable=True)
    driver_record = db.relationship("Driver", foreign_keys=[driver_record_id], backref="user_account")

    # Password reset token (structure for future email reset)
    reset_token = db.Column(db.String(100))
    reset_token_expires = db.Column(db.DateTime)

    @property
    def is_active(self):
        """Flask-Login uses this property to check if user is allowed to log in."""
        return self.is_active_user

    @property
    def is_admin(self):
        return self.role == "admin"

    @property
    def is_dispatcher(self):
        return self.role in ("admin", "dispatcher")

    @property
    def is_driver(self):
        return self.role == "driver"

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method="pbkdf2:sha256", salt_length=16)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def full_name(self):
        return f"{self.first_name or ''} {self.last_name or ''}".strip()

    def __repr__(self):
        return f"<User {self.email}>"


# ═══════════════════════════════════════════════════════════════
#  DRIVERS
# ═══════════════════════════════════════════════════════════════
class Driver(db.Model):
    __tablename__ = "drivers"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(30))
    email = db.Column(db.String(255))
    license_number = db.Column(db.String(100))
    license_expiration = db.Column(db.Date)
    vehicle_make = db.Column(db.String(100))
    vehicle_model = db.Column(db.String(100))
    vehicle_plate = db.Column(db.String(50))
    vehicle_insurance_expiration = db.Column(db.Date)
    is_active = db.Column(db.Boolean, default=True)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    deliveries = db.relationship("Delivery", secondary=delivery_drivers, back_populates="drivers")


# ═══════════════════════════════════════════════════════════════
#  CUSTOMERS & CONTACTS
# ═══════════════════════════════════════════════════════════════
class Customer(db.Model):
    __tablename__ = "customers"
    id = db.Column(db.Integer, primary_key=True)

    # Core info
    business_name = db.Column(db.String(255), nullable=False, index=True)
    category = db.Column(db.String(50), nullable=False, default="Other")  # Laboratory, Hospital, etc.
    status = db.Column(db.String(20), default="prospect")  # prospect, active, archived

    # Address
    address = db.Column(db.String(500))
    city = db.Column(db.String(100))
    state = db.Column(db.String(50), default="NJ")
    zip_code = db.Column(db.String(20))

    # Business details
    preferred_delivery_type = db.Column(db.String(50))  # STAT, Same-day, Scheduled, Route
    billing_terms = db.Column(db.String(100))  # Net 15, Net 30, COD, etc.
    rate_agreement = db.Column(db.Text)
    tax_exempt = db.Column(db.Boolean, default=False)

    # CRM fields
    last_contact_date = db.Column(db.Date)
    next_follow_up = db.Column(db.Date)
    notes = db.Column(db.Text)

    # Contract document path
    contract_filename = db.Column(db.String(255))

    is_archived = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    contacts = db.relationship("Contact", back_populates="customer", cascade="all, delete-orphan")
    quotes = db.relationship("Quote", back_populates="customer")
    deliveries = db.relationship("Delivery", back_populates="customer")
    invoices = db.relationship("Invoice", back_populates="customer")
    payments = db.relationship("Payment", back_populates="customer")
    reminders = db.relationship("Reminder", back_populates="customer")

    @property
    def total_revenue(self):
        return sum(inv.paid_amount or 0 for inv in self.invoices if inv.status == "Paid")

    @property
    def primary_contact(self):
        return next((c for c in self.contacts if c.is_primary), self.contacts[0] if self.contacts else None)

    def __repr__(self):
        return f"<Customer {self.business_name}>"


class Contact(db.Model):
    __tablename__ = "contacts"
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    title = db.Column(db.String(100))
    email = db.Column(db.String(255))
    phone = db.Column(db.String(30))
    is_primary = db.Column(db.Boolean, default=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    customer = db.relationship("Customer", back_populates="contacts")


# ═══════════════════════════════════════════════════════════════
#  QUOTES & LINE ITEMS
# ═══════════════════════════════════════════════════════════════
class Quote(db.Model):
    __tablename__ = "quotes"
    id = db.Column(db.Integer, primary_key=True)
    quote_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"))
    customer_name = db.Column(db.String(255))  # for walk-in / prospect quotes
    customer_email = db.Column(db.String(255))

    # Route info
    pickup_address = db.Column(db.String(500))
    delivery_address = db.Column(db.String(500))
    estimated_mileage = db.Column(db.Float, default=0.0)
    trip_type = db.Column(db.String(20), default="one-way")  # one-way, round-trip

    # Service options (booleans)
    is_rush = db.Column(db.Boolean, default=False)
    is_stat = db.Column(db.Boolean, default=False)
    is_same_day = db.Column(db.Boolean, default=False)
    is_after_hours = db.Column(db.Boolean, default=False)
    is_weekend = db.Column(db.Boolean, default=False)
    is_holiday = db.Column(db.Boolean, default=False)
    temperature_controlled = db.Column(db.Boolean, default=False)

    # Charges
    base_charge = db.Column(db.Float, default=0.0)
    mileage_charge = db.Column(db.Float, default=0.0)
    rush_charge = db.Column(db.Float, default=0.0)
    after_hours_charge = db.Column(db.Float, default=0.0)
    weekend_charge = db.Column(db.Float, default=0.0)
    holiday_charge = db.Column(db.Float, default=0.0)
    wait_time_charge = db.Column(db.Float, default=0.0)
    additional_stop_charge = db.Column(db.Float, default=0.0)
    toll_charge = db.Column(db.Float, default=0.0)
    parking_charge = db.Column(db.Float, default=0.0)
    special_handling_charge = db.Column(db.Float, default=0.0)
    temp_control_charge = db.Column(db.Float, default=0.0)

    # Discounts & adjustments
    route_discount = db.Column(db.Float, default=0.0)
    contract_discount = db.Column(db.Float, default=0.0)
    manual_adjustment = db.Column(db.Float, default=0.0)
    manual_adjustment_note = db.Column(db.String(500))

    # Tax & total
    tax_rate = db.Column(db.Float, default=0.0)
    tax_amount = db.Column(db.Float, default=0.0)
    total = db.Column(db.Float, default=0.0)

    # Status: pending, accepted, declined, expired, converted
    status = db.Column(db.String(20), default="pending", index=True)

    # Metadata
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.Date)

    # Relationships
    customer = db.relationship("Customer", back_populates="quotes")
    line_items = db.relationship("QuoteLineItem", back_populates="quote", cascade="all, delete-orphan")
    delivery = db.relationship("Delivery", back_populates="quote", uselist=False)

    def __repr__(self):
        return f"<Quote {self.quote_number}>"


class QuoteLineItem(db.Model):
    __tablename__ = "quote_line_items"
    id = db.Column(db.Integer, primary_key=True)
    quote_id = db.Column(db.Integer, db.ForeignKey("quotes.id"), nullable=False)
    description = db.Column(db.String(500), nullable=False)
    quantity = db.Column(db.Float, default=1.0)
    unit_price = db.Column(db.Float, default=0.0)
    total = db.Column(db.Float, default=0.0)

    quote = db.relationship("Quote", back_populates="line_items")


# ═══════════════════════════════════════════════════════════════
#  DELIVERIES & STATUS HISTORY
# ═══════════════════════════════════════════════════════════════
DELIVERY_STATUSES = [
    "New Request", "Quote Pending", "Confirmed", "Scheduled",
    "Driver Assigned", "En Route to Pickup", "Arrived at Pickup",
    "Picked Up", "In Transit", "Arrived at Delivery",
    "Delivered", "Completed", "Cancelled",
]


class Delivery(db.Model):
    __tablename__ = "deliveries"
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"))
    quote_id = db.Column(db.Integer, db.ForeignKey("quotes.id"))

    # Pickup info
    pickup_contact = db.Column(db.String(200))
    pickup_address = db.Column(db.String(500))
    pickup_instructions = db.Column(db.Text)
    pickup_datetime = db.Column(db.DateTime)
    actual_pickup_time = db.Column(db.DateTime)

    # Delivery info
    delivery_contact = db.Column(db.String(200))
    delivery_address = db.Column(db.String(500))
    delivery_instructions = db.Column(db.Text)
    delivery_deadline = db.Column(db.DateTime)
    actual_delivery_time = db.Column(db.DateTime)

    # Service details
    service_type = db.Column(db.String(50))  # STAT, Same-day, Scheduled, Route
    package_type = db.Column(db.String(100))
    quantity = db.Column(db.Integer, default=1)
    special_handling = db.Column(db.Text)
    mileage = db.Column(db.Float, default=0.0)

    # Status & assignments
    status = db.Column(db.String(30), default="New Request", index=True)
    driver_id = db.Column(db.Integer, db.ForeignKey("drivers.id"))
    quote_amount = db.Column(db.Float, default=0.0)

    # Notes
    internal_notes = db.Column(db.Text)
    customer_notes = db.Column(db.Text)

    # Requirements
    requires_chain_of_custody = db.Column(db.Boolean, default=False)
    requires_pod = db.Column(db.Boolean, default=True)
    invoice_status = db.Column(db.String(20), default="Uninvoiced")  # Uninvoiced, Invoiced, Paid

    # Medical courier fields
    is_medical = db.Column(db.Boolean, default=False)
    specimen_id = db.Column(db.String(200))
    pickup_facility = db.Column(db.String(255))
    delivery_facility = db.Column(db.String(255))
    temperature_requirement = db.Column(db.String(100))
    temp_at_pickup = db.Column(db.Float)
    temp_at_delivery = db.Column(db.Float)
    tamper_seal_number = db.Column(db.String(100))
    package_condition = db.Column(db.String(200))

    # Public pickup-request operational fields (customer-facing form)
    company_facility_name = db.Column(db.String(255))
    pickup_contact_phone = db.Column(db.String(50))
    delivery_contact_phone = db.Column(db.String(50))
    delivery_type = db.Column(db.String(50))          # what is being transported
    delivery_type_other = db.Column(db.String(200))   # free-text when delivery_type == Other
    trip_type = db.Column(db.String(30))              # how the trip is structured
    # delivery_deadline (Requested Delivery Deadline) already exists above
    reference_number = db.Column(db.String(100))      # PO / account / case ref
    package_weight = db.Column(db.String(50))         # approximate, free-text (e.g. "5 lbs")
    package_size = db.Column(db.String(100))           # approximate, free-text
    is_recurring = db.Column(db.Boolean, default=False)
    recurring_route_notes = db.Column(db.Text)

    # Metadata
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    customer = db.relationship("Customer", back_populates="deliveries")
    quote = db.relationship("Quote", back_populates="delivery")
    driver = db.relationship("Driver", backref="assigned_deliveries")
    drivers = db.relationship("Driver", secondary=delivery_drivers, back_populates="deliveries")
    status_history = db.relationship("DeliveryStatusHistory", back_populates="delivery", cascade="all, delete-orphan",
                                     order_by="DeliveryStatusHistory.timestamp.desc()")
    pod = db.relationship("ProofOfDelivery", back_populates="delivery", uselist=False)
    chain_of_custody = db.relationship("ChainOfCustody", back_populates="delivery", cascade="all, delete-orphan",
                                      order_by="ChainOfCustody.timestamp")
    invoice = db.relationship("Invoice", back_populates="delivery", uselist=False)

    def __repr__(self):
        return f"<Delivery {self.order_number}>"

    @property
    def is_public_request(self):
        """Whether this delivery originated from the public pickup form."""
        return self.created_by is None and any(
            "public website" in (history.notes or "").lower()
            for history in self.status_history
        )


class DeliveryStatusHistory(db.Model):
    __tablename__ = "delivery_status_history"
    id = db.Column(db.Integer, primary_key=True)
    delivery_id = db.Column(db.Integer, db.ForeignKey("deliveries.id"), nullable=False)
    status = db.Column(db.String(30), nullable=False)
    notes = db.Column(db.Text)
    latitude = db.Column(db.Float)  # future GPS
    longitude = db.Column(db.Float)  # future GPS
    updated_by = db.Column(db.String(100))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    delivery = db.relationship("Delivery", back_populates="status_history")


# ═══════════════════════════════════════════════════════════════
#  PROOF OF DELIVERY
# ═══════════════════════════════════════════════════════════════
class ProofOfDelivery(db.Model):
    __tablename__ = "proofs_of_delivery"
    id = db.Column(db.Integer, primary_key=True)
    delivery_id = db.Column(db.Integer, db.ForeignKey("deliveries.id"), nullable=False, unique=True)

    recipient_name = db.Column(db.String(200), nullable=False)
    signature_filename = db.Column(db.String(255))  # stored image of signature
    photo_filename = db.Column(db.String(255))  # delivery photo
    delivery_date = db.Column(db.Date, nullable=False)
    delivery_time = db.Column(db.Time)
    driver_name = db.Column(db.String(200))
    notes = db.Column(db.Text)

    # Exception handling
    refused = db.Column(db.Boolean, default=False)
    refusal_reason = db.Column(db.Text)
    exception_reason = db.Column(db.Text)

    # GPS structure (future)
    gps_latitude = db.Column(db.Float)
    gps_longitude = db.Column(db.Float)

    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    delivery = db.relationship("Delivery", back_populates="pod")


# ═══════════════════════════════════════════════════════════════
#  CHAIN OF CUSTODY
# ═══════════════════════════════════════════════════════════════
class ChainOfCustody(db.Model):
    __tablename__ = "chain_of_custody"
    id = db.Column(db.Integer, primary_key=True)
    delivery_id = db.Column(db.Integer, db.ForeignKey("deliveries.id"), nullable=False)

    # Handoff details
    person_releasing = db.Column(db.String(200))
    person_accepting = db.Column(db.String(200))
    release_time = db.Column(db.DateTime)
    acceptance_time = db.Column(db.DateTime)

    # Temperature logging
    temperature = db.Column(db.Float)
    tamper_seal = db.Column(db.String(100))
    package_condition = db.Column(db.String(200))

    # Incident / exception
    incident_report = db.Column(db.Text)

    # Driver acknowledgment
    driver_acknowledged = db.Column(db.Boolean, default=False)
    driver_acknowledgment_time = db.Column(db.DateTime)

    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    delivery = db.relationship("Delivery", back_populates="chain_of_custody")


# ═══════════════════════════════════════════════════════════════
#  INVOICES & LINE ITEMS
# ═══════════════════════════════════════════════════════════════
INVOICE_STATUSES = ["Draft", "Sent", "Viewed", "Partially Paid", "Paid", "Overdue", "Cancelled"]


class Invoice(db.Model):
    __tablename__ = "invoices"
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"))
    delivery_id = db.Column(db.Integer, db.ForeignKey("deliveries.id"))

    # Billing
    billing_name = db.Column(db.String(255))
    billing_address = db.Column(db.Text)
    service_date = db.Column(db.Date)

    # Delivery summary
    delivery_description = db.Column(db.Text)
    pickup_address = db.Column(db.String(500))
    delivery_address = db.Column(db.String(500))
    mileage = db.Column(db.Float, default=0.0)

    # Charges
    base_charge = db.Column(db.Float, default=0.0)
    additional_charges = db.Column(db.Float, default=0.0)
    discounts = db.Column(db.Float, default=0.0)
    subtotal = db.Column(db.Float, default=0.0)
    tax_amount = db.Column(db.Float, default=0.0)
    total_due = db.Column(db.Float, default=0.0)
    paid_amount = db.Column(db.Float, default=0.0)
    balance_due = db.Column(db.Float, default=0.0)

    # Terms
    payment_terms = db.Column(db.String(100), default="Net 30")
    due_date = db.Column(db.Date)
    payment_instructions = db.Column(db.Text)
    notes = db.Column(db.Text)

    # Status: Draft, Sent, Viewed, Partially Paid, Paid, Overdue, Cancelled
    status = db.Column(db.String(20), default="Draft", index=True)

    # Metadata
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    sent_at = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    customer = db.relationship("Customer", back_populates="invoices")
    delivery = db.relationship("Delivery", back_populates="invoice")
    line_items = db.relationship("InvoiceLineItem", back_populates="invoice", cascade="all, delete-orphan")
    payments = db.relationship("Payment", back_populates="invoice", cascade="all, delete-orphan")

    @property
    def balance(self):
        return (self.total_due or 0) - (self.paid_amount or 0)

    def __repr__(self):
        return f"<Invoice {self.invoice_number}>"


class InvoiceLineItem(db.Model):
    __tablename__ = "invoice_line_items"
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoices.id"), nullable=False)
    description = db.Column(db.String(500), nullable=False)
    quantity = db.Column(db.Float, default=1.0)
    unit_price = db.Column(db.Float, default=0.0)
    total = db.Column(db.Float, default=0.0)

    invoice = db.relationship("Invoice", back_populates="line_items")


# ═══════════════════════════════════════════════════════════════
#  PAYMENTS
# ═══════════════════════════════════════════════════════════════
class Payment(db.Model):
    __tablename__ = "payments"
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoices.id"), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"))

    amount = db.Column(db.Float, nullable=False)
    payment_date = db.Column(db.Date, nullable=False, default=date.today)
    payment_method = db.Column(db.String(50))  # Check, Credit Card, ACH, Cash, Other
    reference_number = db.Column(db.String(200))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    invoice = db.relationship("Invoice", back_populates="payments")
    customer = db.relationship("Customer", back_populates="payments")


# ═══════════════════════════════════════════════════════════════
#  EXPENSES
# ═══════════════════════════════════════════════════════════════
class Expense(db.Model):
    __tablename__ = "expenses"
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, default=date.today)
    category = db.Column(db.String(100))  # Fuel, Maintenance, Insurance, Supplies, Other
    description = db.Column(db.String(500))
    amount = db.Column(db.Float, nullable=False)
    vendor = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ═══════════════════════════════════════════════════════════════
#  REMINDERS
# ═══════════════════════════════════════════════════════════════
REMINDER_TYPES = [
    "Call Prospect", "Outreach Email", "Quote Follow-up",
    "Contract Renewal", "Invoice Payment", "Scheduled Delivery",
    "Customer Complaint", "Document Expiration", "Other",
]


class Reminder(db.Model):
    __tablename__ = "reminders"
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"))
    title = db.Column(db.String(255), nullable=False)
    reminder_type = db.Column(db.String(50), default="Other")
    description = db.Column(db.Text)
    due_date = db.Column(db.Date, nullable=False, index=True)
    is_completed = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.DateTime)
    priority = db.Column(db.String(20), default="normal")  # low, normal, high, urgent
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    customer = db.relationship("Customer", back_populates="reminders")

    @property
    def is_overdue(self):
        return not self.is_completed and self.due_date < date.today()

    @property
    def is_today(self):
        return self.due_date == date.today()


# ═══════════════════════════════════════════════════════════════
#  EMAIL TEMPLATES
# ═══════════════════════════════════════════════════════════════
EMAIL_TEMPLATE_TYPES = [
    "quote_sent", "quote_accepted", "delivery_confirmed", "driver_assigned",
    "pickup_completed", "delivery_in_progress", "delivery_completed",
    "proof_of_delivery", "invoice_sent", "invoice_due", "invoice_overdue",
    "customer_followup",
]


class EmailTemplate(db.Model):
    __tablename__ = "email_templates"
    id = db.Column(db.Integer, primary_key=True)
    template_type = db.Column(db.String(50), unique=True, nullable=False)
    subject = db.Column(db.String(500), nullable=False)
    body = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ═══════════════════════════════════════════════════════════════
#  COMPANY SETTINGS
# ═══════════════════════════════════════════════════════════════
class CompanySettings(db.Model):
    __tablename__ = "company_settings"
    id = db.Column(db.Integer, primary_key=True, default=1)
    company_name = db.Column(db.String(255), default="Triple Force Logistic LLC")
    business_type = db.Column(db.String(100), default="Courier and Logistics Company")
    primary_market = db.Column(db.String(100), default="New Jersey")
    primary_service = db.Column(db.String(100), default="Medical Courier Services")
    email = db.Column(db.String(255), default="dispatch@tripleforcelogistic.com")
    phone = db.Column(db.String(30))
    website = db.Column(db.String(255))
    address = db.Column(db.Text)
    logo_filename = db.Column(db.String(255))
    # Invoice info
    invoice_prefix = db.Column(db.String(10), default="INV")
    invoice_next_number = db.Column(db.Integer, default=1001)
    quote_prefix = db.Column(db.String(10), default="QT")
    quote_next_number = db.Column(db.Integer, default=1001)
    order_prefix = db.Column(db.String(10), default="TF")
    order_next_number = db.Column(db.Integer, default=1001)
    payment_instructions = db.Column(db.Text, default="Make checks payable to Triple Force Logistic LLC.")
    default_payment_terms = db.Column(db.String(50), default="Net 30")
    tax_rate = db.Column(db.Float, default=0.0)  # NJ sales tax, if applicable
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ═══════════════════════════════════════════════════════════════
#  PRICING SETTINGS
# ═══════════════════════════════════════════════════════════════
class PricingSettings(db.Model):
    __tablename__ = "pricing_settings"
    id = db.Column(db.Integer, primary_key=True, default=1)
    # Base rates
    base_charge = db.Column(db.Float, default=15.00)
    per_mile_charge = db.Column(db.Float, default=2.50)
    minimum_charge = db.Column(db.Float, default=20.00)

    # Surcharges (flat amounts)
    rush_charge = db.Column(db.Float, default=25.00)
    stat_charge = db.Column(db.Float, default=35.00)
    same_day_charge = db.Column(db.Float, default=15.00)
    after_hours_charge = db.Column(db.Float, default=20.00)
    weekend_charge = db.Column(db.Float, default=15.00)
    holiday_charge = db.Column(db.Float, default=30.00)
    wait_time_per_minute = db.Column(db.Float, default=1.00)
    additional_stop_charge = db.Column(db.Float, default=10.00)
    toll_charge = db.Column(db.Float, default=0.00)
    parking_charge = db.Column(db.Float, default=0.00)
    special_handling_charge = db.Column(db.Float, default=15.00)
    temperature_controlled_charge = db.Column(db.Float, default=25.00)

    # Discounts (percentages 0-100)
    route_discount_pct = db.Column(db.Float, default=10.0)
    contract_discount_pct = db.Column(db.Float, default=5.0)

    # Tax
    tax_rate = db.Column(db.Float, default=0.0)  # NJ sales tax if applicable
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ═══════════════════════════════════════════════════════════════
#  UPLOADED DOCUMENTS
# ═══════════════════════════════════════════════════════════════
class UploadedDocument(db.Model):
    __tablename__ = "uploaded_documents"
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"))
    delivery_id = db.Column(db.Integer, db.ForeignKey("deliveries.id"))
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255))
    document_type = db.Column(db.String(50))  # contract, pod_photo, signature, other
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)


# ═══════════════════════════════════════════════════════════════
#  OUTREACH TRACKER — B2B prospect & follow-up pipeline
# ═══════════════════════════════════════════════════════════════

OUTREACH_STATUSES = [
    "Drafted - Pending Approval",
    "Ready to Send",
    "Sent",
    "Follow-Up Needed",
    "Responded",
    "Closed",
]

OPPORTUNITY_STAGES = [
    "Prospect",
    "Contacted",
    "Follow-Up",
    "Vendor Registration",
    "Application Submitted",
    "Under Review",
    "Approved Vendor",
    "Contract Opportunity",
    "Won",
    "Not Interested",
]

VENDOR_REGISTRATION_STATUSES = [
    "Not Started",
    "Started",
    "Application Submitted",
    "Under Review",
    "Approved",
    "Rejected",
]


class Prospect(db.Model):
    """A B2B outreach prospect (lab, imaging center, ASC, dialysis, etc.).

    The database is the single source of truth -- every action in the Outreach
    Tracker (add, edit, mark-sent, follow-up, response, vendor status, stage,
    notes, archive) writes a committed row here. ``dedupe_key`` prevents
    duplicate prospects (org + email, falling back to org + phone, org + website,
    org alone) so re-importing the CSV never creates duplicates.
    """

    __tablename__ = "prospects"

    id = db.Column(db.Integer, primary_key=True)
    organization_name = db.Column(db.String(255), nullable=False, index=True)
    organization_type = db.Column(db.String(100))  # Laboratory, Imaging, ASC, Dialysis, etc.
    contact_person = db.Column(db.String(200))
    contact_title = db.Column(db.String(200))
    email = db.Column(db.String(255))
    phone = db.Column(db.String(50))
    website = db.Column(db.String(255))
    procurement_vendor_route = db.Column(db.String(255))  # vendor portal / procurement channel
    outreach_subject = db.Column(db.String(255))
    outreach_status = db.Column(db.String(50), default="Drafted - Pending Approval", index=True)
    date_contacted = db.Column(db.Date)
    follow_up_date = db.Column(db.Date, index=True)
    response_status = db.Column(db.String(100))
    vendor_application_date = db.Column(db.Date)
    vendor_registration_status = db.Column(db.String(50), default="Not Started")
    opportunity_stage = db.Column(db.String(50), default="Prospect", index=True)
    notes = db.Column(db.Text)
    dedupe_key = db.Column(db.String(255), unique=True, index=True)
    archived = db.Column(db.Boolean, default=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @staticmethod
    def build_dedupe_key(organization_name, email="", phone="", website=""):
        """Stable duplicate-detection key (org + email -> org + phone -> org + website -> org)."""
        org = (organization_name or "").strip().lower()
        email = (email or "").strip().lower()
        phone = (phone or "").strip().lower()
        website = (website or "").strip().lower()
        if org and email:
            return f"{org}|{email}"
        if org and phone:
            return f"{org}|{phone}"
        if org and website:
            return f"{org}|{website}"
        return org or None


# ═══════════════════════════════════════════════════════════════
#  DRIVER DASHBOARD — Work sessions, routes, stops, checklist, messages
#  All tables below are ADDITIVE. No existing table is altered.
# ═══════════════════════════════════════════════════════════════

# Default checklist items seeded on first run
DEFAULT_CHECKLIST_ITEMS = [
    "Vehicle condition checked",
    "Fuel level checked",
    "Tires and lights checked",
    "Required supplies/equipment present",
    "Phone charged and route ready",
]


class DriverWorkSession(db.Model):
    """A driver's work session (clock-in to clock-out).

    Stores timestamps server-side so calculations are not dependent on the
    phone screen remaining open.  ``status`` tracks the driver's current
    state: clocked_in, on_break, on_route, route_completed, off_duty.
    """
    __tablename__ = "driver_work_sessions"
    id = db.Column(db.Integer, primary_key=True)
    driver_id = db.Column(db.Integer, db.ForeignKey("drivers.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    clock_in_time = db.Column(db.DateTime, nullable=False)
    clock_out_time = db.Column(db.DateTime)  # NULL = still clocked in
    status = db.Column(db.String(20), default="clocked_in", index=True)  # clocked_in, on_break, on_route, route_completed, off_duty
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    driver = db.relationship("Driver", foreign_keys=[driver_id])
    user = db.relationship("User", foreign_keys=[user_id])
    breaks = db.relationship("DriverBreak", back_populates="work_session", cascade="all, delete-orphan")
    route_sessions = db.relationship("DriverRouteSession", back_populates="work_session", cascade="all, delete-orphan")
    stop_events = db.relationship("DriverStopEvent", back_populates="work_session", cascade="all, delete-orphan")


class DriverBreak(db.Model):
    """A break period within a work session."""
    __tablename__ = "driver_breaks"
    id = db.Column(db.Integer, primary_key=True)
    work_session_id = db.Column(db.Integer, db.ForeignKey("driver_work_sessions.id"), nullable=False, index=True)
    driver_id = db.Column(db.Integer, db.ForeignKey("drivers.id"), nullable=False, index=True)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime)  # NULL = still on break
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    work_session = db.relationship("DriverWorkSession", back_populates="breaks")
    driver = db.relationship("Driver", foreign_keys=[driver_id])


class DriverRouteSession(db.Model):
    """A route session (start-route to end-route) within a work session."""
    __tablename__ = "driver_route_sessions"
    id = db.Column(db.Integer, primary_key=True)
    work_session_id = db.Column(db.Integer, db.ForeignKey("driver_work_sessions.id"), nullable=False, index=True)
    driver_id = db.Column(db.Integer, db.ForeignKey("drivers.id"), nullable=False, index=True)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime)  # NULL = route still active
    start_odometer = db.Column(db.Float)
    end_odometer = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    work_session = db.relationship("DriverWorkSession", back_populates="route_sessions")
    driver = db.relationship("Driver", foreign_keys=[driver_id])
    stop_events = db.relationship("DriverStopEvent", back_populates="route_session")


class DriverStopEvent(db.Model):
    """A completed stop within a route (delivery, pickup, or other)."""
    __tablename__ = "driver_stop_events"
    id = db.Column(db.Integer, primary_key=True)
    driver_id = db.Column(db.Integer, db.ForeignKey("drivers.id"), nullable=False, index=True)
    work_session_id = db.Column(db.Integer, db.ForeignKey("driver_work_sessions.id"), nullable=False, index=True)
    route_session_id = db.Column(db.Integer, db.ForeignKey("driver_route_sessions.id"), nullable=True, index=True)
    delivery_id = db.Column(db.Integer, db.ForeignKey("deliveries.id"), nullable=True)
    stop_type = db.Column(db.String(20), nullable=False)  # delivery, pickup, other
    completed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    work_session = db.relationship("DriverWorkSession", back_populates="stop_events")
    route_session = db.relationship("DriverRouteSession", back_populates="stop_events")
    driver = db.relationship("Driver", foreign_keys=[driver_id])


class DriverMileageLog(db.Model):
    """Odometer entries for mileage tracking."""
    __tablename__ = "driver_mileage_logs"
    id = db.Column(db.Integer, primary_key=True)
    driver_id = db.Column(db.Integer, db.ForeignKey("drivers.id"), nullable=False, index=True)
    route_session_id = db.Column(db.Integer, db.ForeignKey("driver_route_sessions.id"), nullable=True)
    log_date = db.Column(db.Date, nullable=False, index=True)
    start_odometer = db.Column(db.Float)
    end_odometer = db.Column(db.Float)
    miles = db.Column(db.Float)
    source = db.Column(db.String(20), default="manual")  # manual, gps, route_api
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    driver = db.relationship("Driver", foreign_keys=[driver_id])


class ChecklistItem(db.Model):
    """Admin-editable checklist definitions."""
    __tablename__ = "checklist_items"
    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(255), nullable=False)
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ChecklistResponse(db.Model):
    """Driver responses to checklist items for a specific date."""
    __tablename__ = "checklist_responses"
    id = db.Column(db.Integer, primary_key=True)
    driver_id = db.Column(db.Integer, db.ForeignKey("drivers.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    checklist_item_id = db.Column(db.Integer, db.ForeignKey("checklist_items.id"), nullable=False)
    response_date = db.Column(db.Date, nullable=False, index=True)
    is_completed = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.DateTime)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("driver_id", "checklist_item_id", "response_date", name="uq_checklist_response"),
    )


class DriverMessage(db.Model):
    """Dispatch-to-driver messages and alerts."""
    __tablename__ = "driver_messages"
    id = db.Column(db.Integer, primary_key=True)
    driver_id = db.Column(db.Integer, db.ForeignKey("drivers.id"), nullable=False, index=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False, index=True)
    priority = db.Column(db.String(20), default="normal")  # normal, urgent
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    driver = db.relationship("Driver", foreign_keys=[driver_id])
    sender = db.relationship("User", foreign_keys=[sender_id])


class DriverCorrection(db.Model):
    """Audit trail for dispatch/admin corrections to driver data."""
    __tablename__ = "driver_corrections"
    id = db.Column(db.Integer, primary_key=True)
    driver_id = db.Column(db.Integer, db.ForeignKey("drivers.id"), nullable=False, index=True)
    corrected_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    correction_type = db.Column(db.String(50), nullable=False)  # clock_in, clock_out, break, route, stop, mileage
    description = db.Column(db.Text, nullable=False)
    reason = db.Column(db.Text, nullable=False)
    old_value = db.Column(db.Text)
    new_value = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    driver = db.relationship("Driver", foreign_keys=[driver_id])
    corrector = db.relationship("User", foreign_keys=[corrected_by])


class DriverWeeklySummary(db.Model):
    """Historical weekly summaries (retained for at least 42 weeks)."""
    __tablename__ = "driver_weekly_summaries"
    id = db.Column(db.Integer, primary_key=True)
    driver_id = db.Column(db.Integer, db.ForeignKey("drivers.id"), nullable=False, index=True)
    week_start = db.Column(db.Date, nullable=False, index=True)
    week_end = db.Column(db.Date, nullable=False)
    total_work_hours = db.Column(db.Float, default=0.0)
    total_drive_hours = db.Column(db.Float, default=0.0)
    total_miles = db.Column(db.Float, default=0.0)
    total_stops = db.Column(db.Integer, default=0)
    total_deliveries = db.Column(db.Integer, default=0)
    total_pickups = db.Column(db.Integer, default=0)
    stops_per_hour = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("driver_id", "week_start", name="uq_weekly_summary"),
    )
