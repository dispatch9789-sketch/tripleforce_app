"""Flask-WTF forms for all modules."""
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import (
    StringField, TextAreaField, PasswordField, BooleanField,
    SelectField, FloatField, IntegerField, DateField, DateTimeField,
    SubmitField, HiddenField,
)
from wtforms.validators import DataRequired, Email, Optional, Length, NumberRange


# ═══════════════════════════════════════════════════════════════
#  AUTH FORMS
# ═══════════════════════════════════════════════════════════════
class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    remember = BooleanField("Remember me")
    submit = SubmitField("Log In")


class PasswordResetRequestForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    submit = SubmitField("Send Reset Link")


class PasswordResetForm(FlaskForm):
    password = PasswordField("New Password", validators=[DataRequired(), Length(min=8)])
    confirm = PasswordField("Confirm Password", validators=[DataRequired()])
    submit = SubmitField("Reset Password")


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField("Current Password", validators=[DataRequired()])
    new_password = PasswordField("New Password", validators=[DataRequired(), Length(min=8)])
    confirm = PasswordField("Confirm New Password", validators=[DataRequired()])
    submit = SubmitField("Change Password")


# ═══════════════════════════════════════════════════════════════
#  CUSTOMER FORMS
# ═══════════════════════════════════════════════════════════════
CUSTOMER_CATEGORIES = [
    "Laboratory", "Hospital", "Pharmacy", "Imaging Center",
    "Dialysis Center", "Physician Office", "Law Firm",
    "Auto Parts", "Dealership", "Other Commercial",
]

DELIVERY_TYPES = ["STAT", "Same-day", "Scheduled", "Route", "Standard"]
BILLING_TERMS = ["COD", "Net 7", "Net 15", "Net 30", "Net 45", "Net 60", "Prepaid"]


class CustomerForm(FlaskForm):
    business_name = StringField("Business Name", validators=[DataRequired(), Length(max=255)])
    category = SelectField("Business Category", choices=[(c, c) for c in CUSTOMER_CATEGORIES], default="Other Commercial")
    status = SelectField("Status", choices=[("prospect", "Prospect"), ("active", "Active Client"), ("archived", "Archived")], default="prospect")
    address = StringField("Address")
    city = StringField("City")
    state = StringField("State", default="NJ")
    zip_code = StringField("ZIP Code")
    preferred_delivery_type = SelectField("Preferred Delivery Type", choices=[("", "— Select —")] + [(d, d) for d in DELIVERY_TYPES])
    billing_terms = SelectField("Billing Terms", choices=[("", "— Select —")] + [(t, t) for t in BILLING_TERMS])
    rate_agreement = TextAreaField("Rate Agreement")
    tax_exempt = BooleanField("Tax Exempt")
    last_contact_date = DateField("Last Contact Date", validators=[Optional()])
    next_follow_up = DateField("Next Follow-up Date", validators=[Optional()])
    notes = TextAreaField("Notes")
    contract = FileField("Upload Contract", validators=[FileAllowed(["pdf", "doc", "docx", "jpg", "png"], "Documents only")])
    submit = SubmitField("Save Customer")


class ContactForm(FlaskForm):
    name = StringField("Contact Name", validators=[DataRequired(), Length(max=200)])
    title = StringField("Title/Position")
    email = StringField("Email", validators=[Optional(), Email()])
    phone = StringField("Phone")
    is_primary = BooleanField("Primary Contact")
    notes = TextAreaField("Notes")
    submit = SubmitField("Save Contact")


# ═══════════════════════════════════════════════════════════════
#  QUOTE / CALCULATOR FORMS
# ═══════════════════════════════════════════════════════════════
class QuoteCalculatorForm(FlaskForm):
    customer_id = SelectField("Customer (optional)", coerce=str, validators=[Optional()])
    customer_name = StringField("Customer Name (if no account)")
    customer_email = StringField("Customer Email", validators=[Optional(), Email()])
    pickup_address = StringField("Pickup Address", validators=[DataRequired()])
    delivery_address = StringField("Delivery Address", validators=[DataRequired()])
    estimated_mileage = FloatField("Estimated Mileage", validators=[DataRequired(), NumberRange(min=0)])
    trip_type = SelectField("Trip Type", choices=[("one-way", "One-Way"), ("round-trip", "Round Trip")], default="one-way")
    is_rush = BooleanField("Rush Service")
    is_stat = BooleanField("STAT Service")
    is_same_day = BooleanField("Same-Day Service")
    is_after_hours = BooleanField("After Hours")
    is_weekend = BooleanField("Weekend")
    is_holiday = BooleanField("Holiday")
    temperature_controlled = BooleanField("Temperature Controlled")
    wait_time_minutes = FloatField("Wait Time (minutes)", default=0, validators=[Optional()])
    additional_stops = IntegerField("Additional Stops", default=0, validators=[Optional()])
    toll_charge = FloatField("Toll Charge", default=0, validators=[Optional()])
    parking_charge = FloatField("Parking Charge", default=0, validators=[Optional()])
    special_handling = BooleanField("Special Handling")
    apply_route_discount = BooleanField("Apply Route Discount")
    apply_contract_discount = BooleanField("Apply Contract Discount")
    manual_adjustment = FloatField("Manual Adjustment (+/-)", default=0, validators=[Optional()])
    manual_adjustment_note = StringField("Adjustment Note")
    tax_rate = FloatField("Tax Rate %", default=0, validators=[Optional()])
    notes = TextAreaField("Notes")
    submit = SubmitField("Calculate Quote")


class QuoteSaveForm(FlaskForm):
    expires_at = DateField("Quote Valid Until", validators=[Optional()])
    notes = TextAreaField("Notes")
    submit = SubmitField("Save Quote")


# ═══════════════════════════════════════════════════════════════
#  DELIVERY FORMS
# ═══════════════════════════════════════════════════════════════
SERVICE_TYPES = ["Standard", "Rush", "STAT", "Same-day", "Scheduled", "Route"]

# What is being transported (distinct from Service Type = urgency)
DELIVERY_TYPES = [
    "Medical Specimen / Lab Sample",
    "Pharmacy / Medication",
    "Medical Supplies / Equipment",
    "Documents / Records",
    "General Package",
    "Auto Parts",
    "Other",
]

# How the physical trip is structured (distinct from Service Type and Delivery Type)
TRIP_TYPES = ["One-way", "Round Trip", "Multi-stop"]

# Medical courier temperature handling (dropdown on the customer form)
TEMPERATURE_REQUIREMENTS = [
    "Room Temperature",
    "Refrigerated",
    "Frozen",
    "Other / Special Requirement",
]


class DeliveryForm(FlaskForm):
    customer_id = SelectField("Customer", coerce=int, validators=[Optional()])
    quote_id = HiddenField()
    pickup_contact = StringField("Pickup Contact")
    pickup_address = StringField("Pickup Address", validators=[DataRequired()])
    pickup_instructions = TextAreaField("Pickup Instructions")
    pickup_datetime = DateTimeField("Pickup Date & Time", format="%Y-%m-%dT%H:%M", validators=[Optional()])
    delivery_contact = StringField("Delivery Contact")
    delivery_address = StringField("Delivery Address", validators=[DataRequired()])
    delivery_instructions = TextAreaField("Delivery Instructions")
    delivery_deadline = DateTimeField("Delivery Deadline", format="%Y-%m-%dT%H:%M", validators=[Optional()])
    service_type = SelectField("Service Type", choices=[(s, s) for s in SERVICE_TYPES], default="Standard")
    package_type = StringField("Package Type")
    quantity = IntegerField("Quantity", default=1, validators=[Optional()])
    special_handling = TextAreaField("Special Handling Instructions")
    mileage = FloatField("Mileage", default=0, validators=[Optional()])
    driver_id = SelectField("Assign Driver", coerce=int, validators=[Optional()])
    quote_amount = FloatField("Quote Amount", default=0, validators=[Optional()])
    internal_notes = TextAreaField("Internal Notes")
    customer_notes = TextAreaField("Customer Notes")
    requires_chain_of_custody = BooleanField("Chain of Custody Required")
    requires_pod = BooleanField("Proof of Delivery Required", default=True)
    # Medical fields
    is_medical = BooleanField("Medical Courier Delivery")
    specimen_id = StringField("Specimen/Package ID")
    pickup_facility = StringField("Pickup Facility")
    delivery_facility = StringField("Delivery Facility")
    temperature_requirement = StringField("Temperature Requirement")
    tamper_seal_number = StringField("Tamper Seal Number")
    submit = SubmitField("Save Delivery")


# ═══════════════════════════════════════════════════════════════
#  PUBLIC CUSTOMER PICKUP REQUEST
#  (Customer-facing form shown on the public /request-pickup page.
#   Contains ONLY customer-visible fields — no driver/internal/staff
#   fields. Writes to the same Delivery model as the staff form.)
# ═══════════════════════════════════════════════════════════════
class CustomerPickupRequestForm(FlaskForm):
    # Who is requesting the pickup
    company_facility_name = StringField("Company / Facility Name", validators=[Optional(), Length(max=255)])
    requester_name = StringField("Your Name", validators=[DataRequired(), Length(max=200)])
    requester_phone = StringField("Your Phone", validators=[DataRequired(), Length(max=50)])
    requester_email = StringField("Your Email", validators=[Optional(), Email(), Length(max=200)])

    # Pickup details
    pickup_contact = StringField("Pickup Contact Name", validators=[Optional(), Length(max=200)])
    pickup_contact_phone = StringField("Pickup Contact Phone", validators=[Optional(), Length(max=50)])
    pickup_address = StringField("Pickup Address", validators=[DataRequired(), Length(max=500)])
    pickup_instructions = TextAreaField("Pickup Instructions", validators=[Optional(), Length(max=2000)])
    pickup_date = StringField("Pickup Date", validators=[Optional()])
    pickup_time = StringField("Pickup Time", validators=[Optional()])

    # Delivery details
    delivery_contact = StringField("Delivery Contact Name", validators=[Optional(), Length(max=200)])
    delivery_contact_phone = StringField("Delivery Contact Phone", validators=[Optional(), Length(max=50)])
    delivery_address = StringField("Delivery Address", validators=[DataRequired(), Length(max=500)])
    delivery_instructions = TextAreaField("Delivery Instructions", validators=[Optional(), Length(max=2000)])
    requested_delivery_deadline = DateTimeField("Requested Delivery Deadline", format="%Y-%m-%dT%H:%M", validators=[Optional()])

    # Service details
    service_type = SelectField("Service Type", choices=[(s, s) for s in SERVICE_TYPES], default="Standard")
    delivery_type = SelectField("Delivery Type", choices=[("", "— Select —")] + [(d, d) for d in DELIVERY_TYPES], validators=[Optional()])
    delivery_type_other = StringField("If Other, please describe", validators=[Optional(), Length(max=200)])
    trip_type = SelectField("Trip Type", choices=[("", "— Select —")] + [(t, t) for t in TRIP_TYPES], validators=[Optional()])
    package_type = StringField("Package Type", validators=[Optional(), Length(max=100)])
    quantity = IntegerField("Quantity", default=1, validators=[Optional(), NumberRange(min=1)])
    package_weight = StringField("Approximate Weight", validators=[Optional(), Length(max=50)])
    package_size = StringField("Package Size", validators=[Optional(), Length(max=100)])
    special_handling = TextAreaField("Special Handling Instructions", validators=[Optional(), Length(max=2000)])
    reference_number = StringField("Reference / PO / Account Number", validators=[Optional(), Length(max=100)])

    # Medical courier options
    is_medical = BooleanField("This is a medical courier delivery")
    pickup_facility = StringField("Pickup Facility", validators=[Optional(), Length(max=255)])
    delivery_facility = StringField("Delivery Facility", validators=[Optional(), Length(max=255)])
    temperature_requirement = SelectField(
        "Temperature Requirement",
        choices=[("", "— Select —")] + [(t, t) for t in TEMPERATURE_REQUIREMENTS],
        validators=[Optional()],
    )

    # Recurring route
    is_recurring = SelectField("Is this a recurring route?", choices=[("No", "No"), ("Yes", "Yes")], default="No", validators=[Optional()])
    recurring_route_notes = TextAreaField("Route / Schedule Notes", validators=[Optional(), Length(max=2000)])

    customer_notes = TextAreaField("Additional Notes", validators=[Optional(), Length(max=2000)])
    submit = SubmitField("Request Pickup")


class DeliveryStatusForm(FlaskForm):
    status = SelectField("Update Status", choices=[(s, s) for s in [
        "New Request", "Quote Pending", "Confirmed", "Scheduled",
        "Driver Assigned", "En Route to Pickup", "Arrived at Pickup",
        "Picked Up", "In Transit", "Arrived at Delivery",
        "Delivered", "Completed", "Cancelled",
    ]])
    notes = TextAreaField("Notes")
    latitude = HiddenField()
    longitude = HiddenField()
    submit = SubmitField("Update Status")


# ═══════════════════════════════════════════════════════════════
#  PROOF OF DELIVERY FORM
# ═══════════════════════════════════════════════════════════════
class ProofOfDeliveryForm(FlaskForm):
    recipient_name = StringField("Recipient Name", validators=[DataRequired(), Length(max=200)])
    signature_data = HiddenField("Signature")  # base64 PNG from canvas
    photo = FileField("Delivery Photo", validators=[FileAllowed(["jpg", "jpeg", "png"], "Images only")])
    delivery_date = DateField("Delivery Date", validators=[DataRequired()])
    delivery_time = StringField("Delivery Time (HH:MM)")
    driver_name = StringField("Driver Name")
    notes = TextAreaField("Delivery Notes")
    refused = BooleanField("Delivery Refused")
    refusal_reason = TextAreaField("Refusal Reason")
    exception_reason = TextAreaField("Delivery Exception Reason")
    gps_latitude = HiddenField()
    gps_longitude = HiddenField()
    submit = SubmitField("Submit Proof of Delivery")


# ═══════════════════════════════════════════════════════════════
#  CHAIN OF CUSTODY FORM
# ═══════════════════════════════════════════════════════════════
class ChainOfCustodyForm(FlaskForm):
    person_releasing = StringField("Person Releasing Package")
    person_accepting = StringField("Person Accepting Package")
    release_time = DateTimeField("Release Time", format="%Y-%m-%dT%H:%M", validators=[Optional()])
    acceptance_time = DateTimeField("Acceptance Time", format="%Y-%m-%dT%H:%M", validators=[Optional()])
    temperature = FloatField("Temperature (°F)", validators=[Optional()])
    tamper_seal = StringField("Tamper Seal Number")
    package_condition = StringField("Package Condition")
    incident_report = TextAreaField("Incident/Exception Report")
    driver_acknowledged = BooleanField("Driver Acknowledges")
    submit = SubmitField("Add Chain of Custody Entry")


# ═══════════════════════════════════════════════════════════════
#  INVOICE FORMS
# ═══════════════════════════════════════════════════════════════
class InvoiceForm(FlaskForm):
    customer_id = SelectField("Customer", coerce=int, validators=[Optional()])
    billing_name = StringField("Billing Name", validators=[DataRequired()])
    billing_address = TextAreaField("Billing Address")
    service_date = DateField("Service Date", validators=[Optional()])
    delivery_description = TextAreaField("Delivery Description")
    mileage = FloatField("Mileage", default=0, validators=[Optional()])
    base_charge = FloatField("Base Charge", default=0, validators=[Optional()])
    additional_charges = FloatField("Additional Charges", default=0, validators=[Optional()])
    discounts = FloatField("Discounts", default=0, validators=[Optional()])
    tax_amount = FloatField("Tax Amount", default=0, validators=[Optional()])
    payment_terms = SelectField("Payment Terms", choices=[(t, t) for t in ["Net 7", "Net 15", "Net 30", "Net 45", "Net 60", "COD", "Prepaid"]], default="Net 30")
    due_date = DateField("Due Date", validators=[Optional()])
    payment_instructions = TextAreaField("Payment Instructions")
    notes = TextAreaField("Notes")
    status = SelectField("Status", choices=[(s, s) for s in ["Draft", "Sent", "Viewed", "Partially Paid", "Paid", "Overdue", "Cancelled"]], default="Draft")
    submit = SubmitField("Save Invoice")


class InvoiceLineItemForm(FlaskForm):
    description = StringField("Description", validators=[DataRequired()])
    quantity = FloatField("Quantity", default=1, validators=[Optional()])
    unit_price = FloatField("Unit Price", default=0, validators=[Optional()])
    total = FloatField("Total", default=0, validators=[Optional()])
    submit = SubmitField("Add Line Item")


class PaymentForm(FlaskForm):
    amount = FloatField("Payment Amount", validators=[DataRequired(), NumberRange(min=0.01)])
    payment_date = DateField("Payment Date", validators=[DataRequired()])
    payment_method = SelectField("Payment Method", choices=[(m, m) for m in ["Check", "Credit Card", "ACH", "Cash", "Zelle", "Other"]], default="Check")
    reference_number = StringField("Reference Number")
    notes = TextAreaField("Notes")
    submit = SubmitField("Record Payment")


# ═══════════════════════════════════════════════════════════════
#  DRIVER FORM
# ═══════════════════════════════════════════════════════════════
class DriverForm(FlaskForm):
    name = StringField("Driver Name", validators=[DataRequired(), Length(max=200)])
    phone = StringField("Phone")
    email = StringField("Email", validators=[Optional(), Email()])
    license_number = StringField("License Number")
    license_expiration = DateField("License Expiration", validators=[Optional()])
    vehicle_make = StringField("Vehicle Make")
    vehicle_model = StringField("Vehicle Model")
    vehicle_plate = StringField("Vehicle Plate")
    vehicle_insurance_expiration = DateField("Insurance Expiration", validators=[Optional()])
    notes = TextAreaField("Notes")
    submit = SubmitField("Save Driver")


# ═══════════════════════════════════════════════════════════════
#  REMINDER FORM
# ═══════════════════════════════════════════════════════════════
REMINDER_TYPES = [
    "Call Prospect", "Outreach Email", "Quote Follow-up",
    "Contract Renewal", "Invoice Payment", "Scheduled Delivery",
    "Customer Complaint", "Document Expiration", "Other",
]


class ReminderForm(FlaskForm):
    customer_id = SelectField("Customer (optional)", coerce=int, validators=[Optional()])
    title = StringField("Title", validators=[DataRequired(), Length(max=255)])
    reminder_type = SelectField("Type", choices=[(t, t) for t in REMINDER_TYPES], default="Other")
    description = TextAreaField("Description")
    due_date = DateField("Due Date", validators=[DataRequired()])
    priority = SelectField("Priority", choices=[("low", "Low"), ("normal", "Normal"), ("high", "High"), ("urgent", "Urgent")], default="normal")
    submit = SubmitField("Save Reminder")


# ═══════════════════════════════════════════════════════════════
#  SETTINGS FORMS
# ═══════════════════════════════════════════════════════════════
class CompanySettingsForm(FlaskForm):
    company_name = StringField("Company Name", validators=[DataRequired()])
    business_type = StringField("Business Type")
    primary_market = StringField("Primary Market")
    primary_service = StringField("Primary Service")
    email = StringField("Business Email", validators=[Email()])
    phone = StringField("Phone")
    website = StringField("Website")
    address = TextAreaField("Address")
    logo = FileField("Upload Logo", validators=[FileAllowed(["png", "jpg", "jpeg", "gif"], "Images only")])
    invoice_prefix = StringField("Invoice Prefix", default="INV")
    quote_prefix = StringField("Quote Prefix", default="QT")
    order_prefix = StringField("Order Prefix", default="TF")
    payment_instructions = TextAreaField("Payment Instructions")
    default_payment_terms = StringField("Default Payment Terms", default="Net 30")
    tax_rate = FloatField("Default Tax Rate %", default=0, validators=[Optional()])
    submit = SubmitField("Save Settings")


class PricingSettingsForm(FlaskForm):
    base_charge = FloatField("Base Delivery Charge ($)", validators=[DataRequired()])
    per_mile_charge = FloatField("Per-Mile Charge ($)", validators=[DataRequired()])
    minimum_charge = FloatField("Minimum Charge ($)", validators=[DataRequired()])
    rush_charge = FloatField("Rush Surcharge ($)")
    stat_charge = FloatField("STAT Surcharge ($)")
    same_day_charge = FloatField("Same-Day Surcharge ($)")
    after_hours_charge = FloatField("After-Hours Surcharge ($)")
    weekend_charge = FloatField("Weekend Surcharge ($)")
    holiday_charge = FloatField("Holiday Surcharge ($)")
    wait_time_per_minute = FloatField("Wait Time Per Minute ($)")
    additional_stop_charge = FloatField("Additional Stop Charge ($)")
    toll_charge = FloatField("Default Toll Charge ($)")
    parking_charge = FloatField("Default Parking Charge ($)")
    special_handling_charge = FloatField("Special Handling Charge ($)")
    temperature_controlled_charge = FloatField("Temperature-Controlled Charge ($)")
    route_discount_pct = FloatField("Route Discount (%)")
    contract_discount_pct = FloatField("Contract Discount (%)")
    tax_rate = FloatField("Tax Rate (%)")
    submit = SubmitField("Save Pricing")


class EmailTemplateForm(FlaskForm):
    template_type = SelectField("Template Type", coerce=str, validators=[DataRequired()])
    subject = StringField("Subject", validators=[DataRequired()])
    body = TextAreaField("Body", validators=[DataRequired()])
    is_active = BooleanField("Active")
    submit = SubmitField("Save Template")


# ═══════════════════════════════════════════════════════════════
#  EXPENSE FORM
# ═══════════════════════════════════════════════════════════════
class ExpenseForm(FlaskForm):
    date = DateField("Date", validators=[DataRequired()])
    category = SelectField("Category", choices=[(c, c) for c in ["Fuel", "Maintenance", "Insurance", "Supplies", "Phone", "Internet", "Rent", "Other"]], default="Other")
    description = StringField("Description")
    amount = FloatField("Amount", validators=[DataRequired(), NumberRange(min=0.01)])
    vendor = StringField("Vendor")
    submit = SubmitField("Save Expense")


# ═══════════════════════════════════════════════════════════════
#  USER MANAGEMENT FORMS
# ═══════════════════════════════════════════════════════════════
ROLE_CHOICES = [("admin", "Administrator"), ("dispatcher", "Dispatcher"), ("driver", "Driver")]


class UserForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    first_name = StringField("First Name")
    last_name = StringField("Last Name")
    phone = StringField("Phone")
    role = SelectField("Role", choices=ROLE_CHOICES, default="dispatcher")
    password = PasswordField("Password (min 8 chars)", validators=[DataRequired(), Length(min=8)])
    is_active_user = BooleanField("Active", default=True)
    submit = SubmitField("Save User")


class UserEditForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    first_name = StringField("First Name")
    last_name = StringField("Last Name")
    phone = StringField("Phone")
    role = SelectField("Role", choices=ROLE_CHOICES, default="dispatcher")
    is_active_user = BooleanField("Active", default=True)
    new_password = PasswordField("New Password (leave blank to keep current)", validators=[Optional(), Length(min=8)])
    submit = SubmitField("Save Changes")


# ═══════════════════════════════════════════════════════════════
#  DRIVER PORTAL FORMS
# ═══════════════════════════════════════════════════════════════
class DeliveryStatusUpdateForm(FlaskForm):
    status = SelectField("Update Status", choices=[], validators=[DataRequired()])
    notes = TextAreaField("Notes")
    submit = SubmitField("Update Status")


class DriverPODForm(FlaskForm):
    recipient_name = StringField("Recipient Name", validators=[DataRequired()])
    delivery_date = DateField("Delivery Date", validators=[DataRequired()])
    delivery_time = StringField("Delivery Time (HH:MM)")
    notes = TextAreaField("Notes")
    refused = BooleanField("Delivery Refused")
    refusal_reason = TextAreaField("Refusal Reason")
    submit = SubmitField("Submit Proof of Delivery")


# ═══════════════════════════════════════════════════════════════
#  OUTREACH TRACKER FORMS
# ═══════════════════════════════════════════════════════════════
class ProspectForm(FlaskForm):
    organization_name = StringField("Organization / Prospect Name", validators=[DataRequired(), Length(max=255)])
    organization_type = StringField("Organization Type", validators=[Optional(), Length(max=100)])
    contact_person = StringField("Contact Person", validators=[Optional(), Length(max=200)])
    contact_title = StringField("Contact Title / Department", validators=[Optional(), Length(max=200)])
    email = StringField("Email", validators=[Optional(), Email(), Length(max=255)])
    phone = StringField("Phone", validators=[Optional(), Length(max=50)])
    website = StringField("Website", validators=[Optional(), Length(max=255)])
    procurement_vendor_route = StringField("Procurement / Vendor Route", validators=[Optional(), Length(max=255)])
    outreach_subject = StringField("Outreach Subject", validators=[Optional(), Length(max=255)])
    outreach_status = SelectField("Outreach Status", choices=[], validators=[DataRequired()])
    date_contacted = DateField("Date Contacted", validators=[Optional()])
    follow_up_date = DateField("Follow-Up Date", validators=[Optional()])
    response_status = StringField("Response Summary", validators=[Optional(), Length(max=100)])
    vendor_application_date = DateField("Vendor Application Date", validators=[Optional()])
    vendor_registration_status = SelectField("Vendor Registration Status", choices=[], validators=[DataRequired()])
    opportunity_stage = SelectField("Opportunity Stage", choices=[], validators=[DataRequired()])
    notes = TextAreaField("Notes", validators=[Optional()])
    submit = SubmitField("Save Prospect")


class ProspectStatusForm(FlaskForm):
    outreach_status = SelectField("Outreach Status", choices=[], validators=[DataRequired()])
    opportunity_stage = SelectField("Opportunity Stage", choices=[], validators=[DataRequired()])
    vendor_registration_status = SelectField("Vendor Registration Status", choices=[], validators=[DataRequired()])
    response_status = StringField("Response Summary", validators=[Optional(), Length(max=100)])
    submit = SubmitField("Update Status")


class ProspectNotesForm(FlaskForm):
    notes = TextAreaField("Notes", validators=[Optional()])
    submit = SubmitField("Save Notes")


class ProspectFollowUpForm(FlaskForm):
    follow_up_date = DateField("Follow-Up Date", validators=[DataRequired()])
    outreach_status = SelectField("Outreach Status", choices=[], validators=[DataRequired()])
    submit = SubmitField("Save Follow-Up")


class ProspectImportForm(FlaskForm):
    csv_file = FileField("CSV file", validators=[FileRequired(), FileAllowed(["csv"], "CSV files only")])
    submit = SubmitField("Import")

