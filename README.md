# Triple Force Logistic LLC — Logistics Management Application

A complete, mobile-friendly logistics management web application for Triple Force Logistic LLC, a New Jersey medical courier and logistics company.

## Features

- **Secure Multi-Role Login** — Password hashing, session protection, CSRF protection, three role types: admin, dispatcher, driver
- **Role-Based Access Control** — Admins have full access; dispatchers manage operations; drivers access only their Driver Portal
- **Dashboard** — Deliveries today, in-progress, completed, pending quotes, unpaid invoices, revenue stats, reminders
- **Customer/Prospect CRM** — Laboratories, hospitals, pharmacies, imaging centers, dialysis centers, law firms, auto parts, and more
- **Quote Calculator** — Mileage-based pricing, STAT/rush/same-day surcharges, after-hours/weekend/holiday surcharges, wait time, tolls, discounts, tax
- **Medical Courier Dispatch** — Kanban-style board with 13 delivery stages, list view, delivery details, chain of custody
- **Driver Portal** — Driver-specific dashboard showing assigned deliveries, status updates, proof of delivery capture, chain of custody entry
- **Pickup & Delivery Tracking** — Status history with timestamps, GPS structure for future live tracking
- **Proof of Delivery** — Mobile-friendly signature pad, photo upload, GPS capture, refused delivery option, PDF export
- **Chain of Custody** — Specimen IDs, chain-of-custody log, temperature logging, tamper seals, incident reports
- **Invoice Generation** — Convert deliveries to invoices, line items, payments, PDF export, email, CSV export
- **Revenue Dashboard** — Daily/weekly/monthly/annual revenue, outstanding/overdue invoices, top clients, service breakdowns, CSV/PDF export
- **User Management** — Admin-only CRUD for system users with role assignment, activate/deactivate accounts
- **Email Notifications** — 12 editable email templates for quotes, deliveries, invoices, and follow-ups
- **Reporting** — Revenue reports, customer exports, invoice exports, CSV and PDF formats
- **Reminders** — Follow-up calls, outreach emails, contract renewals, invoice payments, document expirations
- **Universal Search** — Search across customers, quotes, deliveries, and invoices
- **Settings** — Editable company info, pricing rules, email templates, driver management, expense tracking, logo upload
- **Dark Mode** — Full dark mode support with toggle

---

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.10+ / Flask 3.0 |
| Database | SQLite (upgradeable to PostgreSQL) |
| ORM | SQLAlchemy |
| Auth | Flask-Login, Werkzeug password hashing |
| Forms | Flask-WTF with CSRF protection |
| Email | Flask-Mail |
| PDF | ReportLab |
| Frontend | Bootstrap 5, Bootstrap Icons |
| Fonts | Inter (Google Fonts) |

---

## Installation (Windows)

### Prerequisites

1. **Install Python 3.10 or newer**
   - Download from https://www.python.org/downloads/
   - During installation, check "Add Python to PATH"
   - Verify: open Command Prompt, type `python --version`

### Step 1: Download and Extract

1. Download the project ZIP file
2. Extract it to a folder, e.g., `C:\tripleforce`

### Step 2: Create Virtual Environment (Recommended)

```cmd
cd C:\tripleforce
python -m venv venv
venv\Scripts\activate
```

### Step 3: Install Dependencies

```cmd
pip install -r requirements.txt
```

### Step 4: Configure Environment

```cmd
copy .env.example .env
```

Open `.env` in Notepad and change these values:
- `SECRET_KEY` — Generate a random key (see below)
- `MAIL_USERNAME` — Your Gmail address (for sending emails)
- `MAIL_PASSWORD` — Your Gmail App Password (NOT your regular password)

Generate a secret key:
```cmd
python -c "import secrets; print(secrets.token_hex(32))"
```

### Step 5: Initialize Database

```cmd
python init_db.py
```

This creates the database, admin user, company settings, default pricing, email templates, and sample data.

### Step 6: Run the Application

```cmd
python run.py
```

### Step 7: Open in Browser

Open your web browser and go to:
```
http://localhost:5000
```

**Default login credentials:**

| Role | Email | Password |
|------|-------|----------|
| Admin | `admin@tripleforcelogistic.com` | `ChangeMe123!` |
| Dispatcher | `dispatch@tripleforcelogistic.com` | `ChangeMe123!` |
| Driver | `mike@tripleforcelogistic.com` | `ChangeMe123!` |

**IMPORTANT: Change all passwords immediately after first login via Settings > User Management.**

---

## Accessing from iPhone (Same Network)

### Step 1: Find Your Windows Computer's IP Address

1. Open Command Prompt on your Windows PC
2. Type: `ipconfig`
3. Look for "IPv4 Address" — it will look like `192.168.1.100` or `10.0.0.50`

### Step 2: Ensure Firewall Allows Port 5000

1. Open Windows Defender Firewall
2. Click "Advanced Settings" → "Inbound Rules" → "New Rule"
3. Select "Port" → TCP → Specific local ports: `5000`
4. Select "Allow the connection" → Name it "Triple Force Logistic"
5. Complete the wizard

### Step 3: Start the Server

```cmd
python run.py
```

The app is configured to listen on `0.0.0.0:5000`, which means it accepts connections from other devices.

### Step 4: Open on iPhone

1. Make sure your iPhone is connected to the **same Wi-Fi network** as your Windows PC
2. Open Safari (or any browser)
3. Type: `http://YOUR-WINDOWS-IP:5000`
   - Example: `http://192.168.1.100:5000`
4. Log in with your credentials

### Tips for iPhone Use

- Add to Home Screen: In Safari, tap the Share button → "Add to Home Screen" for app-like access
- The interface is fully mobile-responsive with large touch targets
- The signature pad works with your finger or stylus
- GPS location capture works on iPhone for proof of delivery

---

## Changing Pricing Rates

All rates are editable from the web interface:

1. Log in and go to **Settings** → **Pricing** tab
2. Edit any of these:
   - Base delivery charge
   - Per-mile charge
   - Minimum charge
   - STAT/rush/same-day surcharges
   - After-hours/weekend/holiday surcharges
   - Wait time per minute
   - Additional stop charge
   - Toll/parking charges
   - Special handling charge
   - Temperature-controlled charge
   - Route discount percentage
   - Contract discount percentage
   - Tax rate

3. Click **Save Pricing**

Changes take effect immediately for all new quotes.

---

## Adding Your Company Logo

1. Go to **Settings** → **Company Info** tab
2. Scroll to "Upload Logo"
3. Select an image file (PNG, JPG, or GIF)
4. Click **Save Settings**

The logo will appear in the sidebar. Recommended size: 200x60 pixels.

---

## Email Setup (Gmail)

To send quotes, invoices, and notifications via email:

### Step 1: Enable 2-Factor Authentication on Your Gmail Account

1. Go to https://myaccount.google.com/security
2. Enable 2-Step Verification

### Step 2: Create an App Password

1. Go to https://myaccount.google.com/apppasswords
2. Create a new app password for "Mail"
3. Copy the 16-character password

### Step 3: Configure .env File

```
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=dispatch@tripleforcelogistic.com
MAIL_PASSWORD=your-16-char-app-password
MAIL_DEFAULT_SENDER=dispatch@tripleforcelogistic.com
```

### Step 4: Restart the Application

Email templates can be edited from **Settings** → **Email Templates**.

---

## Project Structure

```
tripleforce/
├── app/
│   ├── __init__.py          # Flask app factory
│   ├── config.py            # Configuration
│   ├── extensions.py        # Flask extensions
│   ├── models.py            # All database models
│   ├── forms.py             # All WTForms
│   ├── utils.py             # Quote calculator, PDF generation, email, helpers
│   ├── auth/                # Login, logout, password reset
│   ├── main/                # Dashboard, search, settings, drivers, expenses
│   ├── customers/           # CRM (customers & prospects)
│   ├── quotes/              # Quote calculator, save, convert, PDF
│   ├── dispatch/            # Dispatch board, tracking, POD, chain of custody
│   ├── invoices/            # Invoice generation, payments, PDF, CSV
│   ├── reports/             # Revenue dashboard, exports
│   ├── reminders/           # Follow-up reminders
│   ├── users/               # User management (admin-only CRUD)
│   ├── driver_portal/       # Driver portal (dashboard, POD, custody)
│   ├── templates/           # All HTML/Jinja2 templates
│   │   ├── auth/            # Login, change password
│   │   ├── main/            # Dashboard, settings
│   │   ├── customers/       # Customer views
│   │   ├── quotes/          # Quote views
│   │   ├── dispatch/        # Dispatch views
│   │   ├── invoices/        # Invoice views
│   │   ├── reports/         # Revenue dashboard
│   │   ├── reminders/       # Reminder views
│   │   ├── users/           # User management views
│   │   ├── driver_portal/   # Driver portal views
│   │   └── errors/         # Error pages (403, 404, 500, CSRF)
│   └── static/
│       ├── css/app.css      # Custom styles
│       ├── js/app.js        # Custom JavaScript
│       └── uploads/         # Uploaded files (logos, signatures, photos)
├── run.py                   # Application entry point
├── init_db.py               # Database initialization script
├── schema.sql               # SQL database schema
├── test_app.py              # Comprehensive test suite (113 tests)
├── requirements.txt         # Python dependencies
├── .env.example             # Environment variable template
├── API_DOCS.md              # API documentation
├── HOSTING.md               # Hosting platform guide
├── render.yaml              # Render deployment config
├── Procfile                 # Heroku/Process config
├── Dockerfile               # Docker config
├── docker-compose.yml       # Docker Compose config
├── gunicorn.conf.py         # Gunicorn config
└── README.md                # This file
```

---

## Database Models

| Model | Description |
|-------|-------------|
| User | Admin/dispatcher/driver accounts with hashed passwords |
| Driver | Driver info, vehicle, license, insurance |
| Customer | Business clients and prospects |
| Contact | Multiple contacts per customer |
| Quote | Delivery quotes with all charge fields |
| QuoteLineItem | Additional line items on quotes |
| Delivery | Delivery orders with full pickup/delivery info |
| DeliveryStatusHistory | Timestamped status changes |
| ProofOfDelivery | POD records with signature, photo, GPS |
| ChainOfCustody | Medical courier chain of custody log |
| Invoice | Customer invoices |
| InvoiceLineItem | Line items on invoices |
| Payment | Payment records |
| Expense | Business expenses |
| Reminder | Follow-up reminders |
| EmailTemplate | Editable email templates |
| CompanySettings | Company info, branding, numbering |
| PricingSettings | All editable rate cards |
| UploadedDocument | File uploads |

---

## Security Notes

- **Passwords** are hashed using PBKDF2-SHA256 with random salt
- **CSRF protection** on all forms via Flask-WTF
- **Session protection** via Flask-Login
- **File upload restrictions** — only allowed file types (images, PDFs, docs)
- **Secure filename handling** — all uploaded files are sanitized and timestamped
- **Environment variables** — no credentials in code; all in `.env`
- **Error handling** — custom 404/500/403 error pages
- **Input sanitization** — form validation on all inputs

**IMPORTANT — HIPAA Notice:**
This application is NOT HIPAA-compliant out of the box. HIPAA compliance requires:
- Formal security risk assessment
- HIPAA-compliant hosting (encrypted at rest and in transit)
- Business Associate Agreements (BAAs) with all vendors
- Written policies and procedures
- Access controls and audit logging
- Regular security testing
- Staff training

Do not store Protected Health Information (PHI) in this system until proper HIPAA controls are in place.

---

## Database Backups

To back up your data, simply copy the `tripleforce.db` file:

```cmd
copy tripleforce.db tripleforce_backup_%date%.db
```

For automatic backups, set up a Windows Task Scheduler job to copy the file daily.

---

## Upgrading to PostgreSQL (Future)

When you're ready to scale:

1. Install PostgreSQL on your server
2. Create a database:
   ```sql
   CREATE DATABASE tripleforce;
   CREATE USER tfuser WITH PASSWORD 'yourpassword';
   GRANT ALL PRIVILEGES ON DATABASE tripleforce TO tfuser;
   ```
3. Update `.env`:
   ```
   DATABASE_URL=postgresql://tfuser:yourpassword@localhost:5432/tripleforce
   ```
4. Install the PostgreSQL driver:
   ```cmd
   pip install psycopg2-binary
   ```
5. Re-initialize: `python init_db.py`

No model changes needed — SQLAlchemy handles the database abstraction.

---

## Deployment to Cloud (Future)

### Option 1: PythonAnywhere (Easiest)
1. Create account at pythonanywhere.com
2. Upload the project
3. Create a web app with Flask
4. Set the virtual environment and install requirements
5. Point the WSGI file to `app:create_app()`

### Option 2: Heroku
1. Create a `Procfile`: `web: gunicorn run:app`
2. Add `psycopg2-binary` to requirements
3. Provision Heroku Postgres
4. Set config vars (SECRET_KEY, DATABASE_URL, MAIL_*)
5. Deploy: `git push heroku main`

### Option 3: VPS (DigitalOcean, Linode)
1. Install Python, Nginx, Gunicorn
2. Clone the project
3. Set up virtual environment and install requirements
4. Run with Gunicorn: `gunicorn -w 4 -b 0.0.0.0:5000 run:app`
5. Configure Nginx as reverse proxy with SSL (Let's Encrypt)

---

## Local Testing

After starting the app, verify these features:

1. **Login** — Use the credentials above
2. **Dashboard** — Should show stats and recent activity
3. **Customers** — View sample customers, add a new one
4. **Quote Calculator** — Enter addresses and mileage, check pricing
5. **Quotes** — Save a quote, convert to delivery
6. **Dispatch Board** — View delivery stages, update status
7. **Proof of Delivery** — Fill out POD form, sign on mobile
8. **Invoices** — Create invoice, record payment, download PDF
9. **Reports** — View revenue dashboard, export CSV
10. **Settings** — Update company info and pricing

---

## Troubleshooting

**"ModuleNotFoundError"** — Make sure you activated your virtual environment and ran `pip install -r requirements.txt`

**"Port 5000 already in use"** — Change the port in `.env`: `PORT=5001`

**Can't access from iPhone** — Check:
- Both devices on same Wi-Fi network
- Windows firewall allows port 5000
- You're using the correct IP address (run `ipconfig` to verify)
- Try `http://` not `https://`

**Email not sending** — Check:
- `.env` has correct MAIL_* settings
- Using App Password, not regular Gmail password
- 2-Factor Authentication is enabled on your Google account

**Database locked** — Make sure only one instance of the app is running

---

## License

This application is built for Triple Force Logistic LLC. All rights reserved.

---

## Support

For questions or customization, contact your developer.

**Company:** Triple Force Logistic LLC
**Email:** dispatch@tripleforcelogistic.com
**Primary Service:** Medical Courier Services
**Primary Market:** New Jersey

---

## Production Deployment

### Recommended Platform: Render.com

See [HOSTING.md](HOSTING.md) for the full platform comparison (Render vs Railway vs Fly.io vs DigitalOcean) and step-by-step deployment instructions.

Render is recommended because:
- Zero-config Flask deployment (reads `Procfile` automatically)
- One-click Blueprint deploy via `render.yaml`
- Free automatic SSL certificates
- Managed PostgreSQL addon ($7/month)
- Newark, NJ region (closest to your market)
- Push-to-deploy from GitHub

**Cost:** $7/month (SQLite) or $14/month (with PostgreSQL)

### Quick Deploy to Render

1. Push this project to GitHub
2. Sign up at https://render.com
3. Click "New" → "Blueprint" and select your repo
4. Render reads `render.yaml` and configures everything
5. Add environment variables (SECRET_KEY, MAIL_USERNAME, MAIL_PASSWORD) in the dashboard
6. Run `python init_db.py` in the Render Shell after first deploy

### Alternative Platforms

The project includes deployment configs for all major platforms:

| Platform | Config File | Command |
|----------|-------------|---------|
| Render | `render.yaml` | Blueprint deploy from GitHub |
| Railway | `railway.json` | `railway up` |
| Fly.io | `fly.toml` + `Dockerfile` | `fly deploy` |
| Any VPS | `Dockerfile` + `docker-compose.yml` | `docker-compose up -d` |
| Heroku | `Procfile` + `runtime.txt` | `git push heroku main` |

### Production Checklist

Before going live:

- [ ] Change `SECRET_KEY` to a strong random value (generate with `python -c "import secrets; print(secrets.token_hex(32))"`)
- [ ] Change admin password from `ChangeMe123!` to a strong unique password
- [ ] Set `FLASK_ENV=production` and `FLASK_DEBUG=0`
- [ ] Configure email credentials (MAIL_USERNAME, MAIL_PASSWORD)
- [ ] Set up PostgreSQL (set `DATABASE_URL` to managed PostgreSQL connection string)
- [ ] Enable SSL/HTTPS (automatic on Render, Railway, Fly.io)
- [ ] Set up automated database backups
- [ ] Test all functionality in production environment
- [ ] Review and update all email templates
- [ ] Upload company logo via Settings
- [ ] Update pricing rates via Settings → Pricing
- [ ] Do NOT store PHI until HIPAA compliance review is complete
