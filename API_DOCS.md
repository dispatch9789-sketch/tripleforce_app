# Triple Force Logistic API Documentation

This document describes all application routes, their purposes, and request/response details.

**Base URL:** `http://localhost:5000` (development) or `https://your-domain.com` (production)

---

## Authentication

All routes except `/auth/login`, `/auth/reset-password`, and static assets require an authenticated session.

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/auth/login` | Display login form |
| POST | `/auth/login` | Authenticate user, create session |
| GET | `/auth/logout` | Destroy session, redirect to login |
| GET | `/auth/reset-password` | Request password reset email |
| POST | `/auth/reset-password` | Send reset token via email |
| GET | `/auth/reset-password/<token>` | Display password reset form |
| POST | `/auth/reset-password/<token>` | Submit new password |
| GET | `/auth/change-password` | Display password change form |
| POST | `/auth/change-password` | Submit password change |

### Login Request
```
POST /auth/login
Content-Type: application/x-www-form-urlencoded

email=admin@tripleforcelogistic.com&password=ChangeMe123!&remember_me=y
```

### Login Response
- **200 OK**: Redirects to `/` (dashboard)
- **200 OK**: Re-renders login form with error message

---

## Dashboard

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/` | Main dashboard with stats, recent deliveries, activity, reminders |
| GET | `/search?q=<query>` | Universal search across customers, quotes, deliveries, invoices |

### Dashboard Data
The dashboard endpoint renders a template with the following data:
- Deliveries scheduled today, in-progress, completed today
- Pending quotes count
- Revenue: today, this week, this month
- Recent deliveries (last 10)
- Recent customer activity (last 5)
- Upcoming reminders (next 5)
- Unpaid invoices summary

---

## Customers (CRM)

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/customers/` | List all customers with filters (status, category, search) |
| GET | `/customers/<id>` | Customer detail with contacts, quotes, deliveries, invoices |
| GET | `/customers/new` | Display new customer form |
| POST | `/customers/new` | Create new customer |
| GET | `/customers/<id>/edit` | Display edit customer form |
| POST | `/customers/<id>/edit` | Update customer |
| POST | `/customers/<id>/archive` | Archive customer (soft delete) |
| POST | `/customers/<id>/contact` | Add a contact to customer |
| GET | `/customers/export` | Export all customers as CSV |

### Customer Fields
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| business_name | String(200) | Yes | Company or contact name |
| category | String(50) | No | laboratory, hospital, pharmacy, imaging_center, dialysis_center, law_firm, auto_parts, other |
| status | String(20) | No | active, prospect, inactive |
| primary_contact_name | String(100) | No | Main contact person |
| primary_contact_email | String(120) | No | Email address |
| primary_contact_phone | String(20) | No | Phone number |
| billing_address | Text | No | Billing street address |
| billing_city | String(100) | No | City |
| billing_state | String(2) | No | State abbreviation |
| billing_zip | String(10) | No | ZIP code |
| preferred_delivery_time | String(100) | No | Preferred delivery window |
| billing_terms | String(50) | No | Net 30, COD, etc. |
| tax_id | String(50) | No | Tax ID for invoicing |
| notes | Text | No | Free-form notes |

### CSV Export
```
GET /customers/export
Response: CSV file download
Columns: Business Name, Category, Status, Contact, Email, Phone, City, State, ZIP, Billing Terms, Created Date
```

---

## Quotes

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/quotes/` | List all quotes with status filter |
| GET | `/quotes/calculator` | Display quote calculator form |
| POST | `/quotes/calculator` | Calculate quote and show results |
| POST | `/quotes/save` | Save calculated quote to database |
| GET | `/quotes/<id>` | Quote detail view |
| POST | `/quotes/<id>/status` | Update quote status |
| GET | `/quotes/<id>/pdf` | Download quote as PDF |
| POST | `/quotes/<id>/email` | Email quote to customer |
| POST | `/quotes/<id>/convert` | Convert quote to delivery order |

### Quote Calculator Request
```
POST /quotes/calculator
Content-Type: application/x-www-form-urlencoded

pickup_address=123 Market St, Newark, NJ
delivery_address=455 Broad St, Bloomfield, NJ
estimated_mileage=8.5
trip_type=one-way      # or round-trip
is_stat=y              # optional checkbox
is_rush=y              # optional checkbox
is_same_day=y          # optional checkbox
is_after_hours=y        # optional checkbox
is_weekend=y            # optional checkbox
is_holiday=y            # optional checkbox
temperature_controlled=y # optional checkbox
tax_rate=0              # percentage
submit=Calculate Quote
```

### Quote Calculation Logic
```
base_charge      = pricing.base_charge
mileage_charge   = mileage × pricing.per_mile_charge
rush_charge      = is_stat ? pricing.stat_charge : (is_rush ? pricing.rush_charge : 0)
after_hours_chg  = is_after_hours ? pricing.after_hours_charge : 0
weekend_charge   = is_weekend ? pricing.weekend_charge : 0
holiday_charge   = is_holiday ? pricing.holiday_charge : 0
temp_charge      = temperature_controlled ? pricing.temperature_controlled_charge : 0
subtotal         = base + mileage + rush + after_hours + weekend + holiday + temp
route_discount   = subtotal × (pricing.route_discount_pct / 100)
contract_discount = subtotal × (pricing.contract_discount_pct / 100)
tax_amount       = (subtotal - discounts) × (tax_rate / 100)
total            = subtotal - discounts + tax_amount
minimum          = max(total, pricing.minimum_charge)
```

### Quote PDF
```
GET /quotes/<id>/pdf
Response: application/pdf
Content-Disposition: attachment; filename="Quote_QT-1001.pdf"
```

---

## Dispatch

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/dispatch/` | Dispatch board (Kanban view by default) |
| GET | `/dispatch/?view=list` | Dispatch list view |
| GET | `/dispatch/?view=calendar` | Dispatch calendar view |
| GET | `/dispatch/new` | New delivery form |
| POST | `/dispatch/new` | Create new delivery |
| GET | `/dispatch/<id>` | Delivery detail view |
| GET | `/dispatch/<id>/edit` | Edit delivery form |
| POST | `/dispatch/<id>/edit` | Update delivery |
| POST | `/dispatch/<id>/status` | Update delivery status |
| GET | `/dispatch/<id>/pod` | Proof of delivery form |
| POST | `/dispatch/<id>/pod` | Submit proof of delivery |
| GET | `/dispatch/<id>/pod/pdf` | Download POD as PDF |
| POST | `/dispatch/<id>/pod/email` | Email POD to customer |
| POST | `/dispatch/<id>/custody` | Add chain of custody entry |

### Delivery Statuses (13 stages)
1. `New Request` — Order received
2. `Scheduled` — Pickup/delivery times set
3. `Assigned` — Driver assigned
4. `En Route to Pickup` — Driver heading to pickup
5. `At Pickup` — Driver at pickup location
6. `Picked Up` — Package in transit
7. `En Route to Delivery` — Driver heading to delivery
8. `At Delivery` — Driver at delivery location
9. `Delivered` — Package delivered successfully
10. `Refused` — Delivery refused by recipient
11. `Cancelled` — Delivery cancelled
12. `On Hold` — Delivery paused
13. `Returned` — Package returned to origin

### Proof of Delivery Fields
| Field | Type | Description |
|-------|------|-------------|
| recipient_name | String(200) | Person who received delivery |
| delivery_datetime | DateTime | Actual delivery time |
| signature_data | Text | Base64-encoded signature image |
| photo_filename | String(255) | Uploaded delivery photo |
| gps_latitude | Float | GPS latitude at delivery |
| gps_longitude | Float | GPS longitude at delivery |
| delivery_notes | Text | Additional notes |
| was_refused | Boolean | Whether delivery was refused |
| refusal_reason | String(500) | If refused, why |

### Chain of Custody Entry
```
POST /dispatch/<id>/custody
Content-Type: application/x-www-form-urlencoded

handler_name=John Driver
action=Picked Up
notes=Specimen SM-2026-001 picked up from lab
timestamp=2026-08-02T10:30:00
```

---

## Invoices

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/invoices/` | List all invoices with status filter |
| GET | `/invoices/new` | New invoice form |
| POST | `/invoices/new` | Create new invoice |
| GET | `/invoices/<id>` | Invoice detail view |
| GET | `/invoices/<id>/edit` | Edit invoice form |
| POST | `/invoices/<id>/edit` | Update invoice |
| POST | `/invoices/<id>/line-items` | Add line item to invoice |
| POST | `/invoices/<id>/line-items/<line_id>/delete` | Delete line item |
| POST | `/invoices/<id>/payment` | Record a payment |
| POST | `/invoices/<id>/status` | Update invoice status |
| GET | `/invoices/<id>/pdf` | Download invoice as PDF |
| POST | `/invoices/<id>/email` | Email invoice to customer |
| GET | `/invoices/export` | Export all invoices as CSV |

### Invoice Statuses
- `Draft` — Not yet sent
- `Sent` — Emailed to customer
- `Partially Paid` — Some payment received
- `Paid` — Fully paid
- `Overdue` — Past due date, unpaid
- `Cancelled` — Voided

### Payment Recording
```
POST /invoices/<id>/payment
Content-Type: application/x-www-form-urlencoded

amount=50.00
payment_date=2026-08-02
payment_method=Check     # Cash, Check, Credit Card, Bank Transfer, Other
reference_number=CHK-001
```

### Invoice PDF
```
GET /invoices/<id>/pdf
Response: application/pdf
Content-Disposition: attachment; filename="Invoice_INV-1001.pdf"
```

---

## Reports

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/reports/` | Revenue dashboard with charts |
| GET | `/reports/export/revenue` | Export revenue data as CSV |
| GET | `/reports/export/invoices` | Export all invoices as CSV |
| GET | `/reports/export/deliveries` | Export all deliveries as CSV |
| GET | `/reports/export/customers` | Export all customers as CSV |
| GET | `/reports/pdf` | Download revenue summary as PDF |

### Revenue Dashboard Data
- Revenue: today, this week, this month, this year
- Outstanding, overdue, paid invoices count
- Completed, cancelled deliveries count
- Total mileage
- Average delivery value
- Expenses this month
- Net revenue this month
- Monthly revenue chart (last 6 months)
- Top clients by revenue
- Revenue by service type

---

## Reminders

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/reminders/` | List all reminders |
| GET | `/reminders/new` | New reminder form |
| POST | `/reminders/new` | Create reminder |
| POST | `/reminders/<id>/complete` | Mark reminder as complete |
| POST | `/reminders/<id>/delete` | Delete reminder |

### Reminder Types
- `follow_up_call` — Customer follow-up call
- `outreach_email` — Sales outreach email
- `contract_renewal` — Contract expiration reminder
- `invoice_payment` — Invoice payment follow-up
- `document_expiration` — License/insurance expiration
- `custom` — Custom reminder

### Reminder Priority Levels
- `high` — Red badge
- `medium` — Orange badge
- `low` — Blue badge

---

## Settings

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/settings` | Settings page (Company Info tab) |
| POST | `/settings/company` | Update company information |
| POST | `/settings/pricing` | Update pricing rates |
| GET | `/settings/email-templates` | List email templates |
| GET | `/settings/email-templates/<id>` | Edit email template form |
| POST | `/settings/email-templates/<id>` | Update email template |
| POST | `/settings/drivers` | Add/update driver |
| POST | `/settings/drivers/<id>/delete` | Delete driver |
| POST | `/settings/expenses` | Add expense |
| POST | `/settings/expenses/<id>/delete` | Delete expense |
| POST | `/settings/logo` | Upload company logo |

### Pricing Settings (Editable)
| Field | Default | Description |
|-------|---------|-------------|
| base_charge | $15.00 | Flat base charge per delivery |
| per_mile_charge | $2.50 | Charge per mile |
| minimum_charge | $20.00 | Minimum delivery charge |
| rush_charge | $25.00 | Rush delivery surcharge |
| stat_charge | $35.00 | STAT delivery surcharge |
| same_day_charge | $15.00 | Same-day delivery surcharge |
| after_hours_charge | $20.00 | After-hours surcharge |
| weekend_charge | $15.00 | Weekend surcharge |
| holiday_charge | $30.00 | Holiday surcharge |
| wait_time_per_minute | $1.00 | Per-minute wait time charge |
| additional_stop_charge | $10.00 | Per additional stop |
| toll_charge | $0.00 | Toll reimbursement |
| parking_charge | $0.00 | Parking reimbursement |
| special_handling_charge | $15.00 | Special handling fee |
| temperature_controlled_charge | $25.00 | Temperature-controlled delivery fee |
| route_discount_pct | 10% | Route discount percentage |
| contract_discount_pct | 5% | Contract discount percentage |
| tax_rate | 0% | Default tax rate |

---

## Error Handling

| Status Code | Route | Description |
|------------|-------|-------------|
| 404 | Any unmatched route | Page not found |
| 403 | Insufficient permissions | Access forbidden |
| 500 | Server error | Internal server error |

All errors render user-friendly HTML error pages.

---

## Database Schema Overview

### Tables (19 models)
1. **users** — Login accounts (admin, dispatcher, driver)
2. **drivers** — Driver profiles, vehicle, license info
3. **customers** — Business clients and prospects
4. **contacts** — Multiple contacts per customer
5. **quotes** — Delivery quotes with all charge fields
6. **quote_line_items** — Additional line items on quotes
7. **deliveries** — Delivery orders with full pickup/delivery info
8. **delivery_status_history** — Timestamped status changes
9. **proof_of_deliveries** — POD records with signature, photo, GPS
10. **chain_of_custody** — Medical courier custody log
11. **invoices** — Customer invoices
12. **invoice_line_items** — Line items on invoices
13. **payments** — Payment records
14. **expenses** — Business expenses
15. **reminders** — Follow-up reminders
16. **email_templates** — Editable email templates
17. **company_settings** — Company info, branding, numbering
18. **pricing_settings** — All editable rate cards
19. **uploaded_documents** — File uploads

### Relationships
```
Customer (1) ──── (N) Contact
Customer (1) ──── (N) Quote
Customer (1) ──── (N) Delivery
Customer (1) ──── (N) Invoice
Quote (1) ──── (N) QuoteLineItem
Delivery (1) ──── (N) DeliveryStatusHistory
Delivery (1) ──── (1) ProofOfDelivery
Delivery (1) ──── (N) ChainOfCustody
Invoice (1) ──── (N) InvoiceLineItem
Invoice (1) ──── (N) Payment
```

---

## Security

- **Authentication**: Flask-Login session-based auth
- **Password hashing**: PBKDF2-SHA256 with random salt (Werkzeug)
- **CSRF protection**: Flask-WTF on all POST forms
- **Session protection**: 8-hour lifetime, HttpOnly cookies
- **File upload validation**: Extension whitelist, size limit (16MB)
- **SQL injection**: SQLAlchemy ORM parameterized queries
- **XSS**: Jinja2 auto-escaping on all template output
- **Production**: ProxyFix for reverse proxy headers, HTTPS cookies

---

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| SECRET_KEY | dev-secret-key | Flask session signing key |
| DATABASE_URL | sqlite:///tripleforce.db | Database connection string |
| FLASK_ENV | development | Flask environment |
| FLASK_DEBUG | 1 | Debug mode toggle |
| HOST | 0.0.0.0 | Server bind address |
| PORT | 5000 | Server port |
| MAIL_SERVER | smtp.gmail.com | SMTP server |
| MAIL_PORT | 587 | SMTP port |
| MAIL_USE_TLS | True | Enable TLS |
| MAIL_USERNAME | (none) | SMTP username |
| MAIL_PASSWORD | (none) | SMTP password |
| MAIL_DEFAULT_SENDER | dispatch@tripleforcelogistic.com | From address |
| MAX_CONTENT_LENGTH | 16777216 | Max upload size (16MB) |
| UPLOAD_FOLDER | app/static/uploads | Upload directory |
