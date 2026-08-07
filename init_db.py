"""Database initialization script.

Run this once to create tables and load sample data:
    python init_db.py

This creates:
  - All database tables
  - Default admin user (admin@tripleforcelogistic.com / ChangeMe123!)
  - Company settings (Triple Force Logistic LLC)
  - Default pricing settings
  - Default email templates
  - Sample customers, quotes, deliveries, and invoices
"""
from app import create_app
from app.extensions import db
from app.models import *
from app.utils import get_pricing_settings
from datetime import date, timedelta, datetime


def init_db():
    app = create_app()
    with app.app_context():
        db.create_all()
        print("✓ Tables created")

        # ── Admin user ──
        if not User.query.filter_by(email="admin@tripleforcelogistic.com").first():
            user = User(
                email="admin@tripleforcelogistic.com",
                first_name="Owner",
                last_name="Admin",
                phone="(973) 555-0100",
                role="admin",
            )
            user.set_password("ChangeMe123!")
            db.session.add(user)
            print("✓ Admin user created (admin@tripleforcelogistic.com / ChangeMe123!)")
        else:
            print("• Admin user already exists")

        # ── Dispatcher user ──
        if not User.query.filter_by(email="dispatch@tripleforcelogistic.com").first():
            dispatcher = User(
                email="dispatch@tripleforcelogistic.com",
                first_name="Dispatch",
                last_name="Agent",
                phone="(973) 555-0101",
                role="dispatcher",
            )
            dispatcher.set_password("ChangeMe123!")
            db.session.add(dispatcher)
            print("✓ Dispatcher user created (dispatch@tripleforcelogistic.com / ChangeMe123!)")
        else:
            print("• Dispatcher user already exists")

        # ── Company settings ──
        if not CompanySettings.query.get(1):
            settings = CompanySettings(id=1)
            db.session.add(settings)
            print("✓ Company settings created")
        else:
            print("• Company settings already exist")

        # ── Pricing settings ──
        if not PricingSettings.query.get(1):
            pricing = PricingSettings(id=1)
            db.session.add(pricing)
            print("✓ Pricing settings created")
        else:
            print("• Pricing settings already exist")

        # ── Email templates ──
        from app.utils import get_email_template
        for tmpl_type in EMAIL_TEMPLATE_TYPES:
            existing = EmailTemplate.query.filter_by(template_type=tmpl_type).first()
            if not existing:
                default = get_email_template(tmpl_type)
                t = EmailTemplate(
                    template_type=tmpl_type,
                    subject=default.subject,
                    body=default.body,
                    is_active=True,
                )
                db.session.add(t)
            print(f"✓ Email template '{tmpl_type}' ensured")

        # ── Sample driver ──
        if not Driver.query.first():
            driver = Driver(
                name="Mike Johnson",
                phone="(973) 555-0200",
                email="mike@tripleforcelogistic.com",
                vehicle_make="Ford",
                vehicle_model="Transit Connect",
                vehicle_plate="NJ-COUR01",
            )
            db.session.add(driver)
            db.session.flush()
            print("✓ Sample driver created")

            # ── Driver user account (linked to driver record) ──
            if not User.query.filter_by(email="mike@tripleforcelogistic.com").first():
                driver_user = User(
                    email="mike@tripleforcelogistic.com",
                    first_name="Mike",
                    last_name="Johnson",
                    phone="(973) 555-0200",
                    role="driver",
                    driver_record_id=driver.id,
                )
                driver_user.set_password("ChangeMe123!")
                db.session.add(driver_user)
                print("✓ Driver user created (mike@tripleforcelogistic.com / ChangeMe123!)")

        # ── Sample customers ──
        if not Customer.query.first():
            customers_data = [
                {
                    "business_name": "Newark Medical Laboratory",
                    "category": "Laboratory",
                    "status": "active",
                    "address": "123 Market St",
                    "city": "Newark",
                    "state": "NJ",
                    "zip_code": "07105",
                    "preferred_delivery_type": "STAT",
                    "billing_terms": "Net 30",
                    "rate_agreement": "$2.50/mile, $15 base, $35 STAT surcharge",
                    "last_contact_date": date.today() - timedelta(days=5),
                    "next_follow_up": date.today() + timedelta(days=25),
                    "notes": "Daily specimen pickups. Requires chain of custody.",
                },
                {
                    "business_name": "Saint Michael's Hospital",
                    "category": "Hospital",
                    "status": "active",
                    "address": "90 Central Ave",
                    "city": "Newark",
                    "state": "NJ",
                    "zip_code": "07107",
                    "preferred_delivery_type": "Same-day",
                    "billing_terms": "Net 15",
                    "rate_agreement": "Contract: $3.00/mile flat",
                    "last_contact_date": date.today() - timedelta(days=2),
                    "next_follow_up": date.today() + timedelta(days=13),
                    "notes": "Pharmacy deliveries and inter-facility transport.",
                },
                {
                    "business_name": "Garden State Pharmacy",
                    "category": "Pharmacy",
                    "status": "active",
                    "address": "455 Broad St",
                    "city": "Bloomfield",
                    "state": "NJ",
                    "zip_code": "07003",
                    "preferred_delivery_type": "Scheduled",
                    "billing_terms": "Net 30",
                    "notes": "Prescription deliveries to patients.",
                },
                {
                    "business_name": "Essex Imaging Center",
                    "category": "Imaging Center",
                    "status": "prospect",
                    "address": "200 Bloomfield Ave",
                    "city": "Montclair",
                    "state": "NJ",
                    "zip_code": "07042",
                    "next_follow_up": date.today() + timedelta(days=3),
                    "notes": "Prospect — interested in daily route pickup. Follow up on pricing.",
                },
                {
                    "business_name": "Hudson Dialysis Center",
                    "category": "Dialysis Center",
                    "status": "active",
                    "address": "789 JFK Blvd",
                    "city": "Jersey City",
                    "state": "NJ",
                    "zip_code": "07306",
                    "preferred_delivery_type": "Route",
                    "billing_terms": "Net 30",
                    "rate_agreement": "Route rate: $500/week, 5 days/week",
                    "notes": "Medical supply deliveries. Temperature controlled.",
                },
                {
                    "business_name": "Riverside Physician Group",
                    "category": "Physician Office",
                    "status": "prospect",
                    "address": "100 River Dr",
                    "city": "Paterson",
                    "state": "NJ",
                    "zip_code": "07501",
                    "next_follow_up": date.today() + timedelta(days=7),
                    "notes": "Prospect — needs specimen transport to lab 3x/week.",
                },
                {
                    "business_name": "Law Offices of Smith & Associates",
                    "category": "Law Firm",
                    "status": "active",
                    "address": "50 Washington St",
                    "city": "Hoboken",
                    "state": "NJ",
                    "zip_code": "07030",
                    "preferred_delivery_type": "Same-day",
                    "billing_terms": "COD",
                    "notes": "Legal document deliveries. Confidential.",
                },
                {
                    "business_name": "Garden State Auto Parts",
                    "category": "Auto Parts",
                    "status": "active",
                    "address": "300 Route 22",
                    "city": "Springfield",
                    "state": "NJ",
                    "zip_code": "07081",
                    "preferred_delivery_type": "Standard",
                    "billing_terms": "Net 15",
                    "notes": "Parts delivery to local shops.",
                },
            ]

            for cd in customers_data:
                c = Customer(**cd)
                db.session.add(c)
                db.session.flush()
                # Add a primary contact
                contact = Contact(
                    customer_id=c.id,
                    name=f"Contact at {c.business_name}",
                    phone="(973) 555-0100",
                    email=f"contact@{c.business_name.lower().replace(' ', '').replace('&', 'and').replace('.', '')}.com",
                    is_primary=True,
                )
                db.session.add(contact)
            print("✓ Sample customers created")

        # ── Sample quote ──
        if not Quote.query.first():
            cust = Customer.query.filter_by(business_name="Newark Medical Laboratory").first()
            quote = Quote(
                quote_number="QT-1001",
                customer_id=cust.id if cust else None,
                customer_name=cust.business_name if cust else "Walk-in",
                customer_email=cust.primary_contact.email if cust and cust.primary_contact else None,
                pickup_address="123 Market St, Newark, NJ 07105",
                delivery_address="455 Broad St, Bloomfield, NJ 07003",
                estimated_mileage=8.5,
                trip_type="one-way",
                is_stat=True,
                base_charge=15.00,
                mileage_charge=21.25,
                rush_charge=35.00,
                total=71.25,
                status="pending",
                created_by=1,
                expires_at=date.today() + timedelta(days=30),
                notes="STAT specimen delivery — temperature controlled",
            )
            db.session.add(quote)
            db.session.flush()
            # Update counter to avoid conflicts
            settings = CompanySettings.query.get(1)
            settings.quote_next_number = 1002
            print("✓ Sample quote created")

        # ── Sample delivery ──
        if not Delivery.query.first():
            cust = Customer.query.filter_by(business_name="Saint Michael's Hospital").first()
            driver = Driver.query.first()
            delivery = Delivery(
                order_number="TF-1001",
                customer_id=cust.id if cust else None,
                pickup_contact="Pharmacy Desk",
                pickup_address="90 Central Ave, Newark, NJ 07107",
                delivery_address="789 JFK Blvd, Jersey City, NJ 07306",
                pickup_instructions="Go to pharmacy window, ask for Dr. Chen's packages",
                delivery_instructions="Deliver to receiving dock, door B",
                pickup_datetime=datetime.now() + timedelta(hours=2),
                delivery_deadline=datetime.now() + timedelta(hours=5),
                service_type="Same-day",
                package_type="Medical supplies",
                quantity=3,
                mileage=12.5,
                driver_id=driver.id if driver else None,
                quote_amount=46.25,
                status="Scheduled",
                requires_chain_of_custody=True,
                requires_pod=True,
                is_medical=True,
                specimen_id="SM-2026-001",
                pickup_facility="Saint Michael's Hospital",
                delivery_facility="Hudson Dialysis Center",
                temperature_requirement="Room temperature",
                created_by=1,
            )
            db.session.add(delivery)
            db.session.flush()
            history = DeliveryStatusHistory(
                delivery_id=delivery.id,
                status="Scheduled",
                notes="Delivery scheduled for today",
                updated_by="Admin",
            )
            db.session.add(history)
            settings = CompanySettings.query.get(1)
            settings.order_next_number = 1002
            print("✓ Sample delivery created")

        # ── Sample invoice ──
        if not Invoice.query.first():
            cust = Customer.query.filter_by(business_name="Garden State Pharmacy").first()
            delivery = Delivery.query.first()
            invoice = Invoice(
                invoice_number="INV-1001",
                customer_id=cust.id if cust else None,
                delivery_id=delivery.id if delivery else None,
                billing_name=cust.business_name if cust else "Garden State Pharmacy",
                billing_address=cust.address if cust else "455 Broad St, Bloomfield, NJ 07003",
                service_date=date.today() - timedelta(days=5),
                delivery_description="Prescription delivery route — 5 days",
                mileage=45.0,
                base_charge=112.50,
                subtotal=112.50,
                total_due=112.50,
                paid_amount=0,
                balance_due=112.50,
                payment_terms="Net 30",
                due_date=date.today() + timedelta(days=25),
                status="Sent",
                sent_at=date.today() - timedelta(days=5),
                created_by=1,
            )
            db.session.add(invoice)
            settings = CompanySettings.query.get(1)
            settings.invoice_next_number = 1002
            print("✓ Sample invoice created")

        # ── Sample reminder ──
        if not Reminder.query.first():
            cust = Customer.query.filter_by(business_name="Essex Imaging Center").first()
            reminder = Reminder(
                customer_id=cust.id if cust else None,
                title="Follow up with Essex Imaging Center",
                reminder_type="Call Prospect",
                description="Call to discuss daily route pickup pricing",
                due_date=date.today() + timedelta(days=3),
                priority="high",
            )
            db.session.add(reminder)
            print("✓ Sample reminder created")

        db.session.commit()
        print("\n" + "="*50)
        print("Database initialized successfully!")
        print("="*50)
        print(f"\n--- Login Credentials ---")
        print(f"Admin:      admin@tripleforcelogistic.com / ChangeMe123!")
        print(f"Dispatcher: dispatch@tripleforcelogistic.com / ChangeMe123!")
        print(f"Driver:     mike@tripleforcelogistic.com / ChangeMe123!")
        print(f"\nRun: python run.py")
        print(f"Open: http://localhost:5000")


if __name__ == "__main__":
    init_db()
