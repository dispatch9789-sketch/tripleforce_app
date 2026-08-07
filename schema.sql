-- Triple Force Logistic LLC - Database Schema
-- Generated for SQLite (compatible with PostgreSQL for production upgrade)
-- Run: sqlite3 tripleforce.db < schema.sql
-- Or:  python init_db.py  (creates tables + sample data)

-- Table: company_settings
DROP TABLE IF EXISTS company_settings;

CREATE TABLE company_settings (
	id INTEGER NOT NULL, 
	company_name VARCHAR(255), 
	business_type VARCHAR(100), 
	primary_market VARCHAR(100), 
	primary_service VARCHAR(100), 
	email VARCHAR(255), 
	phone VARCHAR(30), 
	website VARCHAR(255), 
	address TEXT, 
	logo_filename VARCHAR(255), 
	invoice_prefix VARCHAR(10), 
	invoice_next_number INTEGER, 
	quote_prefix VARCHAR(10), 
	quote_next_number INTEGER, 
	order_prefix VARCHAR(10), 
	order_next_number INTEGER, 
	payment_instructions TEXT, 
	default_payment_terms VARCHAR(50), 
	tax_rate FLOAT, 
	updated_at DATETIME, 
	PRIMARY KEY (id)
)

;

-- Table: customers
DROP TABLE IF EXISTS customers;

CREATE TABLE customers (
	id INTEGER NOT NULL, 
	business_name VARCHAR(255) NOT NULL, 
	category VARCHAR(50) NOT NULL, 
	status VARCHAR(20), 
	address VARCHAR(500), 
	city VARCHAR(100), 
	state VARCHAR(50), 
	zip_code VARCHAR(20), 
	preferred_delivery_type VARCHAR(50), 
	billing_terms VARCHAR(100), 
	rate_agreement TEXT, 
	tax_exempt BOOLEAN, 
	last_contact_date DATE, 
	next_follow_up DATE, 
	notes TEXT, 
	contract_filename VARCHAR(255), 
	is_archived BOOLEAN, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id)
)

;

-- Table: drivers
DROP TABLE IF EXISTS drivers;

CREATE TABLE drivers (
	id INTEGER NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	phone VARCHAR(30), 
	email VARCHAR(255), 
	license_number VARCHAR(100), 
	license_expiration DATE, 
	vehicle_make VARCHAR(100), 
	vehicle_model VARCHAR(100), 
	vehicle_plate VARCHAR(50), 
	vehicle_insurance_expiration DATE, 
	is_active BOOLEAN, 
	notes TEXT, 
	created_at DATETIME, 
	PRIMARY KEY (id)
)

;

-- Table: email_templates
DROP TABLE IF EXISTS email_templates;

CREATE TABLE email_templates (
	id INTEGER NOT NULL, 
	template_type VARCHAR(50) NOT NULL, 
	subject VARCHAR(500) NOT NULL, 
	body TEXT NOT NULL, 
	is_active BOOLEAN, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE (template_type)
)

;

-- Table: expenses
DROP TABLE IF EXISTS expenses;

CREATE TABLE expenses (
	id INTEGER NOT NULL, 
	date DATE NOT NULL, 
	category VARCHAR(100), 
	description VARCHAR(500), 
	amount FLOAT NOT NULL, 
	vendor VARCHAR(200), 
	created_at DATETIME, 
	PRIMARY KEY (id)
)

;

-- Table: pricing_settings
DROP TABLE IF EXISTS pricing_settings;

CREATE TABLE pricing_settings (
	id INTEGER NOT NULL, 
	base_charge FLOAT, 
	per_mile_charge FLOAT, 
	minimum_charge FLOAT, 
	rush_charge FLOAT, 
	stat_charge FLOAT, 
	same_day_charge FLOAT, 
	after_hours_charge FLOAT, 
	weekend_charge FLOAT, 
	holiday_charge FLOAT, 
	wait_time_per_minute FLOAT, 
	additional_stop_charge FLOAT, 
	toll_charge FLOAT, 
	parking_charge FLOAT, 
	special_handling_charge FLOAT, 
	temperature_controlled_charge FLOAT, 
	route_discount_pct FLOAT, 
	contract_discount_pct FLOAT, 
	tax_rate FLOAT, 
	updated_at DATETIME, 
	PRIMARY KEY (id)
)

;

-- Table: contacts
DROP TABLE IF EXISTS contacts;

CREATE TABLE contacts (
	id INTEGER NOT NULL, 
	customer_id INTEGER NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	title VARCHAR(100), 
	email VARCHAR(255), 
	phone VARCHAR(30), 
	is_primary BOOLEAN, 
	notes TEXT, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(customer_id) REFERENCES customers (id)
)

;

-- Table: reminders
DROP TABLE IF EXISTS reminders;

CREATE TABLE reminders (
	id INTEGER NOT NULL, 
	customer_id INTEGER, 
	title VARCHAR(255) NOT NULL, 
	reminder_type VARCHAR(50), 
	description TEXT, 
	due_date DATE NOT NULL, 
	is_completed BOOLEAN, 
	completed_at DATETIME, 
	priority VARCHAR(20), 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(customer_id) REFERENCES customers (id)
)

;

-- Table: users
DROP TABLE IF EXISTS users;

CREATE TABLE users (
	id INTEGER NOT NULL, 
	email VARCHAR(255) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	first_name VARCHAR(100), 
	last_name VARCHAR(100), 
	phone VARCHAR(30), 
	role VARCHAR(20), 
	is_active_user BOOLEAN, 
	created_at DATETIME, 
	last_login DATETIME, 
	driver_record_id INTEGER, 
	reset_token VARCHAR(100), 
	reset_token_expires DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(driver_record_id) REFERENCES drivers (id)
)

;

-- Table: quotes
DROP TABLE IF EXISTS quotes;

CREATE TABLE quotes (
	id INTEGER NOT NULL, 
	quote_number VARCHAR(50) NOT NULL, 
	customer_id INTEGER, 
	customer_name VARCHAR(255), 
	customer_email VARCHAR(255), 
	pickup_address VARCHAR(500), 
	delivery_address VARCHAR(500), 
	estimated_mileage FLOAT, 
	trip_type VARCHAR(20), 
	is_rush BOOLEAN, 
	is_stat BOOLEAN, 
	is_same_day BOOLEAN, 
	is_after_hours BOOLEAN, 
	is_weekend BOOLEAN, 
	is_holiday BOOLEAN, 
	temperature_controlled BOOLEAN, 
	base_charge FLOAT, 
	mileage_charge FLOAT, 
	rush_charge FLOAT, 
	after_hours_charge FLOAT, 
	weekend_charge FLOAT, 
	holiday_charge FLOAT, 
	wait_time_charge FLOAT, 
	additional_stop_charge FLOAT, 
	toll_charge FLOAT, 
	parking_charge FLOAT, 
	special_handling_charge FLOAT, 
	temp_control_charge FLOAT, 
	route_discount FLOAT, 
	contract_discount FLOAT, 
	manual_adjustment FLOAT, 
	manual_adjustment_note VARCHAR(500), 
	tax_rate FLOAT, 
	tax_amount FLOAT, 
	total FLOAT, 
	status VARCHAR(20), 
	notes TEXT, 
	created_by INTEGER, 
	created_at DATETIME, 
	expires_at DATE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(customer_id) REFERENCES customers (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
)

;

-- Table: deliveries
DROP TABLE IF EXISTS deliveries;

CREATE TABLE deliveries (
	id INTEGER NOT NULL, 
	order_number VARCHAR(50) NOT NULL, 
	customer_id INTEGER, 
	quote_id INTEGER, 
	pickup_contact VARCHAR(200), 
	pickup_address VARCHAR(500), 
	pickup_instructions TEXT, 
	pickup_datetime DATETIME, 
	actual_pickup_time DATETIME, 
	delivery_contact VARCHAR(200), 
	delivery_address VARCHAR(500), 
	delivery_instructions TEXT, 
	delivery_deadline DATETIME, 
	actual_delivery_time DATETIME, 
	service_type VARCHAR(50), 
	package_type VARCHAR(100), 
	quantity INTEGER, 
	special_handling TEXT, 
	mileage FLOAT, 
	status VARCHAR(30), 
	driver_id INTEGER, 
	quote_amount FLOAT, 
	internal_notes TEXT, 
	customer_notes TEXT, 
	requires_chain_of_custody BOOLEAN, 
	requires_pod BOOLEAN, 
	invoice_status VARCHAR(20), 
	is_medical BOOLEAN, 
	specimen_id VARCHAR(200), 
	pickup_facility VARCHAR(255), 
	delivery_facility VARCHAR(255), 
	temperature_requirement VARCHAR(100), 
	temp_at_pickup FLOAT, 
	temp_at_delivery FLOAT, 
	tamper_seal_number VARCHAR(100), 
	package_condition VARCHAR(200), 
	created_by INTEGER, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(customer_id) REFERENCES customers (id), 
	FOREIGN KEY(quote_id) REFERENCES quotes (id), 
	FOREIGN KEY(driver_id) REFERENCES drivers (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
)

;

-- Table: quote_line_items
DROP TABLE IF EXISTS quote_line_items;

CREATE TABLE quote_line_items (
	id INTEGER NOT NULL, 
	quote_id INTEGER NOT NULL, 
	description VARCHAR(500) NOT NULL, 
	quantity FLOAT, 
	unit_price FLOAT, 
	total FLOAT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(quote_id) REFERENCES quotes (id)
)

;

-- Table: chain_of_custody
DROP TABLE IF EXISTS chain_of_custody;

CREATE TABLE chain_of_custody (
	id INTEGER NOT NULL, 
	delivery_id INTEGER NOT NULL, 
	person_releasing VARCHAR(200), 
	person_accepting VARCHAR(200), 
	release_time DATETIME, 
	acceptance_time DATETIME, 
	temperature FLOAT, 
	tamper_seal VARCHAR(100), 
	package_condition VARCHAR(200), 
	incident_report TEXT, 
	driver_acknowledged BOOLEAN, 
	driver_acknowledgment_time DATETIME, 
	timestamp DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(delivery_id) REFERENCES deliveries (id)
)

;

-- Table: delivery_drivers
DROP TABLE IF EXISTS delivery_drivers;

CREATE TABLE delivery_drivers (
	delivery_id INTEGER NOT NULL, 
	driver_id INTEGER NOT NULL, 
	PRIMARY KEY (delivery_id, driver_id), 
	FOREIGN KEY(delivery_id) REFERENCES deliveries (id), 
	FOREIGN KEY(driver_id) REFERENCES drivers (id)
)

;

-- Table: delivery_status_history
DROP TABLE IF EXISTS delivery_status_history;

CREATE TABLE delivery_status_history (
	id INTEGER NOT NULL, 
	delivery_id INTEGER NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	notes TEXT, 
	latitude FLOAT, 
	longitude FLOAT, 
	updated_by VARCHAR(100), 
	timestamp DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(delivery_id) REFERENCES deliveries (id)
)

;

-- Table: invoices
DROP TABLE IF EXISTS invoices;

CREATE TABLE invoices (
	id INTEGER NOT NULL, 
	invoice_number VARCHAR(50) NOT NULL, 
	customer_id INTEGER, 
	delivery_id INTEGER, 
	billing_name VARCHAR(255), 
	billing_address TEXT, 
	service_date DATE, 
	delivery_description TEXT, 
	pickup_address VARCHAR(500), 
	delivery_address VARCHAR(500), 
	mileage FLOAT, 
	base_charge FLOAT, 
	additional_charges FLOAT, 
	discounts FLOAT, 
	subtotal FLOAT, 
	tax_amount FLOAT, 
	total_due FLOAT, 
	paid_amount FLOAT, 
	balance_due FLOAT, 
	payment_terms VARCHAR(100), 
	due_date DATE, 
	payment_instructions TEXT, 
	notes TEXT, 
	status VARCHAR(20), 
	created_by INTEGER, 
	created_at DATETIME, 
	sent_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(customer_id) REFERENCES customers (id), 
	FOREIGN KEY(delivery_id) REFERENCES deliveries (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
)

;

-- Table: proofs_of_delivery
DROP TABLE IF EXISTS proofs_of_delivery;

CREATE TABLE proofs_of_delivery (
	id INTEGER NOT NULL, 
	delivery_id INTEGER NOT NULL, 
	recipient_name VARCHAR(200) NOT NULL, 
	signature_filename VARCHAR(255), 
	photo_filename VARCHAR(255), 
	delivery_date DATE NOT NULL, 
	delivery_time TIME, 
	driver_name VARCHAR(200), 
	notes TEXT, 
	refused BOOLEAN, 
	refusal_reason TEXT, 
	exception_reason TEXT, 
	gps_latitude FLOAT, 
	gps_longitude FLOAT, 
	timestamp DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE (delivery_id), 
	FOREIGN KEY(delivery_id) REFERENCES deliveries (id)
)

;

-- Table: uploaded_documents
DROP TABLE IF EXISTS uploaded_documents;

CREATE TABLE uploaded_documents (
	id INTEGER NOT NULL, 
	customer_id INTEGER, 
	delivery_id INTEGER, 
	filename VARCHAR(255) NOT NULL, 
	original_filename VARCHAR(255), 
	document_type VARCHAR(50), 
	uploaded_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(customer_id) REFERENCES customers (id), 
	FOREIGN KEY(delivery_id) REFERENCES deliveries (id)
)

;

-- Table: invoice_line_items
DROP TABLE IF EXISTS invoice_line_items;

CREATE TABLE invoice_line_items (
	id INTEGER NOT NULL, 
	invoice_id INTEGER NOT NULL, 
	description VARCHAR(500) NOT NULL, 
	quantity FLOAT, 
	unit_price FLOAT, 
	total FLOAT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(invoice_id) REFERENCES invoices (id)
)

;

-- Table: payments
DROP TABLE IF EXISTS payments;

CREATE TABLE payments (
	id INTEGER NOT NULL, 
	invoice_id INTEGER NOT NULL, 
	customer_id INTEGER, 
	amount FLOAT NOT NULL, 
	payment_date DATE NOT NULL, 
	payment_method VARCHAR(50), 
	reference_number VARCHAR(200), 
	notes TEXT, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(invoice_id) REFERENCES invoices (id), 
	FOREIGN KEY(customer_id) REFERENCES customers (id)
)

;

