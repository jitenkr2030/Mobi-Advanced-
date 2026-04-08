from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
import secrets
import sqlite3
from functools import wraps
import hashlib
import hmac
import json
import uuid
from decimal import Decimal
import pandas as pd
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
import io
import zipfile
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mobi_invoice.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Database Models
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    company_name = db.Column(db.String(200))
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    gstin = db.Column(db.String(15))
    is_active = db.Column(db.Boolean, default=True)
    email_verified = db.Column(db.Boolean, default=False)
    two_factor_enabled = db.Column(db.Boolean, default=False)
    two_factor_secret = db.Column(db.Text)
    role = db.Column(db.String(20), default='USER')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    invoices = db.relationship('Invoice', backref='user', lazy=True, cascade='all, delete-orphan')
    customers = db.relationship('Customer', backref='user', lazy=True, cascade='all, delete-orphan')
    products = db.relationship('Product', backref='user', lazy=True, cascade='all, delete-orphan')
    quotes = db.relationship('Quote', backref='user', lazy=True, cascade='all, delete-orphan')
    recurring_invoices = db.relationship('RecurringInvoice', backref='user', lazy=True, cascade='all, delete-orphan')
    sessions = db.relationship('UserSession', backref='user', lazy=True, cascade='all, delete-orphan')
    audit_logs = db.relationship('AuditLog', backref='user', lazy=True, cascade='all, delete-orphan')
    user_roles = db.relationship('UserRoleAssignment', backref='user', lazy=True, cascade='all, delete-orphan')
    notifications = db.relationship('Notification', backref='user', lazy=True, cascade='all, delete-orphan')
    login_attempts = db.relationship('LoginAttempt', backref='user', lazy=True, cascade='all, delete-orphan')

# Financial Analytics Models
class Budget(db.Model):
    __tablename__ = 'budgets'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(100), nullable=False)  # OPERATING, CAPITAL, MARKETING, etc.
    budget_type = db.Column(db.String(20), default='MONTHLY')  # MONTHLY, QUARTERLY, YEARLY
    amount = db.Column(db.Float, nullable=False)
    spent_amount = db.Column(db.Float, default=0.0)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    expenses = db.relationship('Expense', backref='budget', lazy=True)

class Expense(db.Model):
    __tablename__ = 'expenses'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    budget_id = db.Column(db.Integer, db.ForeignKey('budgets.id'))
    category = db.Column(db.String(100), nullable=False)
    subcategory = db.Column(db.String(100))
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text)
    expense_date = db.Column(db.Date, nullable=False)
    payment_method = db.Column(db.String(50))
    vendor = db.Column(db.String(200))
    receipt_number = db.Column(db.String(100))
    is_reimbursable = db.Column(db.Boolean, default=False)
    receipt_image = db.Column(db.String(500))  # Path to receipt image
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class FinancialGoal(db.Model):
    __tablename__ = 'financial_goals'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    goal_type = db.Column(db.String(50), nullable=False)  # REVENUE, SAVINGS, DEBT_REDUCTION, EXPENSE_REDUCTION
    target_amount = db.Column(db.Float, nullable=False)
    current_amount = db.Column(db.Float, default=0.0)
    target_date = db.Column(db.Date, nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    priority = db.Column(db.String(20), default='MEDIUM')  # LOW, MEDIUM, HIGH
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class FinancialReport(db.Model):
    __tablename__ = 'financial_reports'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    report_type = db.Column(db.String(50), nullable=False)  # P&L, CASH_FLOW, BALANCE_SHEET, AGING, TAX
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    report_period = db.Column(db.String(20), nullable=False)  # MONTHLY, QUARTERLY, YEARLY
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    report_data = db.Column(db.Text)  # JSON data for the report
    file_path = db.Column(db.String(500))  # Path to generated PDF/Excel file
    is_generated = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    generated_at = db.Column(db.DateTime)

# Advanced Customer Management Models
class CustomerPortal(db.Model):
    __tablename__ = 'customer_portals'
    
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    portal_code = db.Column(db.String(100), unique=True, nullable=False, index=True)
    is_active = db.Column(db.Boolean, default=True)
    last_access = db.Column(db.DateTime)
    access_count = db.Column(db.Integer, default=0)
    permissions = db.Column(db.Text)  # JSON string of permissions
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    expires_at = db.Column(db.DateTime)

class CustomerCommunication(db.Model):
    __tablename__ = 'customer_communications'
    
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    communication_type = db.Column(db.String(20), nullable=False)  # EMAIL, PHONE, MEETING, NOTE
    subject = db.Column(db.String(200))
    content = db.Column(db.Text, nullable=False)
    direction = db.Column(db.String(10), nullable=False)  # IN, OUT
    communication_date = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

class CustomerReminder(db.Model):
    __tablename__ = 'customer_reminders'
    
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    reminder_type = db.Column(db.String(20), nullable=False)  # BIRTHDAY, ANNIVERSARY, PAYMENT, FOLLOWUP
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    event_date = db.Column(db.Date, nullable=False)
    is_completed = db.Column(db.Boolean, default=False)
    completed_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

# Advanced Invoicing Models
class InvoiceTemplate(db.Model):
    __tablename__ = 'invoice_templates'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    template_data = db.Column(db.Text, nullable=False)  # JSON template structure
    is_default = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Currency(db.Model):
    __tablename__ = 'currencies'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    code = db.Column(db.String(3), nullable=False)  # USD, EUR, GBP, etc.
    name = db.Column(db.String(100), nullable=False)
    symbol = db.Column(db.String(10), nullable=False)
    exchange_rate = db.Column(db.Float, default=1.0)  # Rate relative to base currency
    is_base = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class DiscountCoupon(db.Model):
    __tablename__ = 'discount_coupons'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    description = db.Column(db.String(200))
    discount_type = db.Column(db.String(20), nullable=False)  # PERCENTAGE, FIXED
    discount_value = db.Column(db.Float, nullable=False)
    min_amount = db.Column(db.Float)
    max_discount = db.Column(db.Float)
    usage_limit = db.Column(db.Integer)
    used_count = db.Column(db.Integer, default=0)
    valid_from = db.Column(db.Date, nullable=False)
    valid_until = db.Column(db.Date, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

class PartialPayment(db.Model):
    __tablename__ = 'partial_payments'
    
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=False, index=True)
    payment_number = db.Column(db.Integer, nullable=False)  # 1, 2, 3 for split payments
    amount = db.Column(db.Float, nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    paid_date = db.Column(db.Date)
    status = db.Column(db.String(20), default='PENDING')  # PENDING, PAID, OVERDUE
    payment_method = db.Column(db.String(50))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

# Update existing Customer model with new fields
class Customer(db.Model):
    __tablename__ = 'customers'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), index=True)
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    gstin = db.Column(db.String(15))
    company_name = db.Column(db.String(200))
    credit_limit = db.Column(db.Float, default=0.0)
    group_id = db.Column(db.Integer, db.ForeignKey('customer_groups.id'))
    notes = db.Column(db.Text)
    
    # New advanced fields
    birthday = db.Column(db.Date)
    anniversary = db.Column(db.Date)
    preferred_contact_method = db.Column(db.String(20), default='EMAIL')  # EMAIL, PHONE, SMS
    credit_score = db.Column(db.Integer, default=0)  # 0-100
    payment_terms = db.Column(db.String(50), default='NET30')  # NET15, NET30, NET60
    is_active = db.Column(db.Boolean, default=True)
    last_invoice_date = db.Column(db.Date)
    last_payment_date = db.Column(db.Date)
    total_purchases = db.Column(db.Float, default=0.0)
    average_payment_days = db.Column(db.Integer, default=30)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    invoices = db.relationship('Invoice', backref='customer', lazy=True)
    quotes = db.relationship('Quote', backref='customer', lazy=True)
    communications = db.relationship('CustomerCommunication', backref='customer', lazy=True, cascade='all, delete-orphan')
    reminders = db.relationship('CustomerReminder', backref='customer', lazy=True, cascade='all, delete-orphan')
    portal = db.relationship('CustomerPortal', backref='customer', uselist=False, cascade='all, delete-orphan')
    partial_payments = db.relationship('PartialPayment', secondary='invoices', backref='customers')

class CustomerGroup(db.Model):
    __tablename__ = 'customer_groups'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    credit_multiplier = db.Column(db.Float, default=1.0)
    priority = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    customers = db.relationship('Customer', backref='group', lazy=True)

class Product(db.Model):
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    gst_rate = db.Column(db.Float, default=0.0)
    hsn_code = db.Column(db.String(10))
    stock_quantity = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Invoice(db.Model):
    __tablename__ = 'invoices'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False, index=True)
    invoice_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    issue_date = db.Column(db.Date, nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default='DRAFT', index=True)
    subtotal = db.Column(db.Float, default=0.0)
    gst_amount = db.Column(db.Float, default=0.0)
    total_amount = db.Column(db.Float, default=0.0)
    paid_amount = db.Column(db.Float, default=0.0)
    notes = db.Column(db.Text)
    terms = db.Column(db.Text)
    currency = db.Column(db.String(3), default='INR')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    items = db.relationship('InvoiceItem', backref='invoice', lazy=True, cascade='all, delete-orphan')
    payments = db.relationship('Payment', backref='invoice', lazy=True, cascade='all, delete-orphan')
    late_fees = db.relationship('LateFee', backref='invoice', lazy=True, cascade='all, delete-orphan')

class InvoiceItem(db.Model):
    __tablename__ = 'invoice_items'
    
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'))
    description = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    gst_rate = db.Column(db.Float, default=0.0)
    discount = db.Column(db.Float, default=0.0)
    total = db.Column(db.Float, nullable=False)

class Quote(db.Model):
    __tablename__ = 'quotes'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False, index=True)
    quote_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    issue_date = db.Column(db.Date, nullable=False)
    valid_until = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default='DRAFT', index=True)
    subtotal = db.Column(db.Float, default=0.0)
    gst_amount = db.Column(db.Float, default=0.0)
    total_amount = db.Column(db.Float, default=0.0)
    notes = db.Column(db.Text)
    terms = db.Column(db.Text)
    currency = db.Column(db.String(3), default='INR')
    converted_to_invoice = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    items = db.relationship('QuoteItem', backref='quote', lazy=True, cascade='all, delete-orphan')

class QuoteItem(db.Model):
    __tablename__ = 'quote_items'
    
    id = db.Column(db.Integer, primary_key=True)
    quote_id = db.Column(db.Integer, db.ForeignKey('quotes.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'))
    description = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    gst_rate = db.Column(db.Float, default=0.0)
    discount = db.Column(db.Float, default=0.0)
    total = db.Column(db.Float, nullable=False)

class RecurringInvoice(db.Model):
    __tablename__ = 'recurring_invoices'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False, index=True)
    template_name = db.Column(db.String(200), nullable=False)
    frequency = db.Column(db.String(20), nullable=False)  # DAILY, WEEKLY, MONTHLY, YEARLY
    interval = db.Column(db.Integer, default=1)  # Every X days/weeks/months/years
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date)
    last_generated = db.Column(db.Date)
    next_generation = db.Column(db.Date, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    subtotal = db.Column(db.Float, default=0.0)
    gst_amount = db.Column(db.Float, default=0.0)
    total_amount = db.Column(db.Float, default=0.0)
    notes = db.Column(db.Text)
    terms = db.Column(db.Text)
    currency = db.Column(db.String(3), default='INR')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    items = db.relationship('RecurringInvoiceItem', backref='recurring_invoice', lazy=True, cascade='all, delete-orphan')
    generated_invoices = db.relationship('Invoice', backref='recurring_template', lazy=True)

class RecurringInvoiceItem(db.Model):
    __tablename__ = 'recurring_invoice_items'
    
    id = db.Column(db.Integer, primary_key=True)
    recurring_invoice_id = db.Column(db.Integer, db.ForeignKey('recurring_invoices.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'))
    description = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    gst_rate = db.Column(db.Float, default=0.0)
    discount = db.Column(db.Float, default=0.0)
    total = db.Column(db.Float, nullable=False)

class Payment(db.Model):
    __tablename__ = 'payments'
    
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=False, index=True)
    amount = db.Column(db.Float, nullable=False)
    payment_date = db.Column(db.Date, nullable=False)
    payment_method = db.Column(db.String(50), nullable=False)
    reference = db.Column(db.String(100))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

class LateFee(db.Model):
    __tablename__ = 'late_fees'
    
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=False, index=True)
    amount = db.Column(db.Float, nullable=False)
    fee_type = db.Column(db.String(20), nullable=False)  # PERCENTAGE, FIXED
    rate = db.Column(db.Float)
    applied_date = db.Column(db.Date, nullable=False)
    description = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class DiscountCoupon(db.Model):
    __tablename__ = 'discount_coupons'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    description = db.Column(db.String(200))
    discount_type = db.Column(db.String(20), nullable=False)  # PERCENTAGE, FIXED
    discount_value = db.Column(db.Float, nullable=False)
    min_amount = db.Column(db.Float)
    max_discount = db.Column(db.Float)
    usage_limit = db.Column(db.Integer)
    used_count = db.Column(db.Integer, default=0)
    valid_from = db.Column(db.Date, nullable=False)
    valid_until = db.Column(db.Date, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

class CustomerCommunication(db.Model):
    __tablename__ = 'customer_communications'
    
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    communication_type = db.Column(db.String(20), nullable=False)  # EMAIL, PHONE, MEETING, NOTE
    subject = db.Column(db.String(200))
    content = db.Column(db.Text, nullable=False)
    direction = db.Column(db.String(10), nullable=False)  # IN, OUT
    communication_date = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

class CustomerReminder(db.Model):
    __tablename__ = 'customer_reminders'
    
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    reminder_type = db.Column(db.String(20), nullable=False)  # BIRTHDAY, ANNIVERSARY, PAYMENT, FOLLOWUP
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    event_date = db.Column(db.Date, nullable=False)
    is_completed = db.Column(db.Boolean, default=False)
    completed_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

# Enhanced Security Models
class UserSession(db.Model):
    __tablename__ = 'user_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    token = db.Column(db.String(255), unique=True, nullable=False, index=True)
    refresh_token = db.Column(db.String(255), unique=True, index=True)
    user_agent = db.Column(db.Text)
    ip_address = db.Column(db.String(45), index=True)
    is_active = db.Column(db.Boolean, default=True, index=True)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    last_accessed = db.Column(db.DateTime, default=datetime.utcnow)

class UserRoleAssignment(db.Model):
    __tablename__ = 'user_role_assignments'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False, index=True)
    permissions = db.Column(db.Text)  # JSON string of permissions
    assigned_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, index=True)

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    action = db.Column(db.String(50), nullable=False, index=True)  # CREATE, UPDATE, DELETE, LOGIN, LOGOUT
    resource = db.Column(db.String(50), nullable=False, index=True)  # User, Customer, Invoice, etc.
    resource_id = db.Column(db.Integer, index=True)
    old_values = db.Column(db.Text)  # JSON string
    new_values = db.Column(db.Text)  # JSON string
    ip_address = db.Column(db.String(45), index=True)
    user_agent = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    severity = db.Column(db.String(20), default='INFO', index=True)  # DEBUG, INFO, WARNING, ERROR, CRITICAL

class RateLimit(db.Model):
    __tablename__ = 'rate_limits'
    
    id = db.Column(db.Integer, primary_key=True)
    identifier = db.Column(db.String(255), nullable=False, index=True)
    endpoint = db.Column(db.String(255), nullable=False, index=True)
    limit = db.Column(db.Integer, nullable=False)
    window_ms = db.Column(db.Integer, nullable=False)
    requests = db.Column(db.Integer, default=0)
    reset_at = db.Column(db.DateTime, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class BackgroundJob(db.Model):
    __tablename__ = 'background_jobs'
    
    id = db.Column(db.Integer, primary_key=True)
    job_type = db.Column(db.String(50), nullable=False, index=True)  # BACKUP_DATABASE, SEND_EMAIL, etc.
    status = db.Column(db.String(20), default='PENDING', index=True)  # PENDING, RUNNING, COMPLETED, FAILED
    priority = db.Column(db.String(10), default='MEDIUM', index=True)  # LOW, MEDIUM, HIGH, CRITICAL
    payload = db.Column(db.Text)  # JSON data
    result = db.Column(db.Text)  # JSON result
    error = db.Column(db.Text)
    attempts = db.Column(db.Integer, default=0)
    max_attempts = db.Column(db.Integer, default=3)
    scheduled_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class DatabaseBackup(db.Model):
    __tablename__ = 'database_backups'
    
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), unique=True, nullable=False)
    path = db.Column(db.String(500), nullable=False)
    size = db.Column(db.Integer)
    backup_type = db.Column(db.String(20), default='FULL', index=True)  # FULL, INCREMENTAL, DIFFERENTIAL
    status = db.Column(db.String(20), default='PENDING', index=True)  # PENDING, IN_PROGRESS, COMPLETED, FAILED
    checksum = db.Column(db.String(64))
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    completed_at = db.Column(db.DateTime)

class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    notification_type = db.Column(db.String(20), default='INFO', index=True)  # INFO, SUCCESS, WARNING, ERROR, SECURITY
    is_read = db.Column(db.Boolean, default=False, index=True)
    data = db.Column(db.Text)  # JSON data for additional context
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    read_at = db.Column(db.DateTime)

class LoginAttempt(db.Model):
    __tablename__ = 'login_attempts'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    email = db.Column(db.String(120), nullable=False, index=True)
    ip_address = db.Column(db.String(45), nullable=False, index=True)
    user_agent = db.Column(db.Text)
    success = db.Column(db.Boolean, nullable=False, index=True)
    reason = db.Column(db.String(200))  # Failure reason
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)

class CacheEntry(db.Model):
    __tablename__ = 'cache_entries'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(255), unique=True, nullable=False, index=True)
    value = db.Column(db.Text, nullable=False)  # JSON serialized value
    ttl = db.Column(db.Integer, nullable=False)  # Time to live in seconds
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Flask-Login user loader
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Helper functions
def generate_invoice_number():
    """Generate unique invoice number"""
    last_invoice = Invoice.query.order_by(Invoice.id.desc()).first()
    if last_invoice:
        last_num = int(last_invoice.invoice_number.split('-')[-1])
        return f"INV-{last_num + 1:06d}"
    return "INV-000001"

def generate_quote_number():
    """Generate unique quote number"""
    last_quote = Quote.query.order_by(Quote.id.desc()).first()
    if last_quote:
        last_num = int(last_quote.quote_number.split('-')[-1])
        return f"QUO-{last_num + 1:06d}"
    return "QUO-000001"

# Routes

# Main Dashboard
@app.route('/')
@login_required
def dashboard():
    """Main dashboard"""
    # Get recent invoices
    recent_invoices = Invoice.query.filter_by(user_id=current_user.id).order_by(Invoice.created_at.desc()).limit(5).all()
    
    # Get financial summary
    total_revenue = db.session.query(db.func.sum(Invoice.total_amount)).filter_by(user_id=current_user.id).filter(Invoice.status == 'PAID').scalar() or 0
    total_expenses = db.session.query(db.func.sum(Expense.amount)).filter_by(user_id=current_user.id).scalar() or 0
    pending_amount = db.session.query(db.func.sum(Invoice.total_amount - Invoice.paid_amount)).filter_by(user_id=current_user.id).filter(Invoice.status != 'PAID').scalar() or 0
    
    # Get customer count
    customer_count = Customer.query.filter_by(user_id=current_user.id).count()
    
    return render_template('dashboard.html', 
                         recent_invoices=recent_invoices,
                         total_revenue=total_revenue,
                         total_expenses=total_expenses,
                         pending_amount=pending_amount,
                         customer_count=customer_count)

# Financial Analytics Routes
@app.route('/financial/analytics')
@login_required
def financial_analytics_dashboard():
    """Main financial analytics dashboard"""
    # Get key financial metrics
    total_revenue = db.session.query(db.func.sum(Invoice.total_amount)).filter_by(user_id=current_user.id).filter(Invoice.status == 'PAID').scalar() or 0
    total_expenses = db.session.query(db.func.sum(Expense.amount)).filter_by(user_id=current_user.id).scalar() or 0
    net_profit = total_revenue - total_expenses
    profit_margin = (net_profit / total_revenue * 100) if total_revenue > 0 else 0
    
    # Get previous period data for comparison
    last_month_start = (datetime.utcnow() - timedelta(days=60)).date()
    last_month_end = (datetime.utcnow() - timedelta(days=30)).date()
    this_month_start = (datetime.utcnow() - timedelta(days=30)).date()
    today = datetime.utcnow().date()
    
    last_month_revenue = db.session.query(db.func.sum(Invoice.total_amount)).filter(
        Invoice.user_id == current_user.id,
        Invoice.status == 'PAID',
        Invoice.issue_date >= last_month_start,
        Invoice.issue_date <= last_month_end
    ).scalar() or 0
    
    this_month_revenue = db.session.query(db.func.sum(Invoice.total_amount)).filter(
        Invoice.user_id == current_user.id,
        Invoice.status == 'PAID',
        Invoice.issue_date >= this_month_start,
        Invoice.issue_date <= today
    ).scalar() or 0
    
    revenue_change = ((this_month_revenue - last_month_revenue) / last_month_revenue * 100) if last_month_revenue > 0 else 0
    
    # Get recent transactions
    recent_transactions = []
    recent_invoices = Invoice.query.filter_by(user_id=current_user.id).order_by(Invoice.created_at.desc()).limit(10).all()
    for invoice in recent_invoices:
        recent_transactions.append({
            'date': invoice.created_at,
            'description': f'Invoice {invoice.invoice_number} - {invoice.customer.name}',
            'category': 'Income',
            'amount': invoice.total_amount
        })
    
    recent_expenses = Expense.query.filter_by(user_id=current_user.id).order_by(Expense.created_at.desc()).limit(5).all()
    for expense in recent_expenses:
        recent_transactions.append({
            'date': expense.created_at,
            'description': expense.description,
            'category': expense.category,
            'amount': -expense.amount
        })
    
    recent_transactions.sort(key=lambda x: x['date'], reverse=True)
    recent_transactions = recent_transactions[:10]
    
    # Chart data
    chart_labels = ['Week 1', 'Week 2', 'Week 3', 'Week 4']
    revenue_data = [10000, 12000, 11500, 13000]  # Sample data
    expense_data = [8000, 8500, 9000, 9500]  # Sample data
    expense_categories = ['Rent', 'Utilities', 'Marketing', 'Supplies', 'Other']
    expense_category_data = [2000, 1500, 1000, 800, 1200]  # Sample data
    
    analytics = {
        'total_revenue': total_revenue,
        'total_expenses': total_expenses,
        'net_profit': net_profit,
        'profit_margin': profit_margin,
        'revenue_change': round(revenue_change, 1),
        'expenses_change': 5.2,  # Sample data
        'profit_change': 8.7,  # Sample data
        'margin_change': 2.1,  # Sample data
        'chart_labels': chart_labels,
        'revenue_data': revenue_data,
        'expense_data': expense_data,
        'expense_categories': expense_categories,
        'expense_category_data': expense_category_data
    }
    
    return render_template('financial/analytics.html', 
                         analytics=analytics,
                         recent_transactions=recent_transactions)

@app.route('/financial/reports')
@login_required
def financial_reports():
    """Financial reports page"""
    # Get recent reports
    recent_reports = [
        {
            'id': 1,
            'name': 'Monthly P&L Statement',
            'type': 'profit_loss',
            'start_date': '2024-01-01',
            'end_date': '2024-01-31',
            'generated_at': datetime.utcnow(),
            'generated_by': current_user.name,
            'file_size': '245 KB'
        },
        {
            'id': 2,
            'name': 'Cash Flow Analysis',
            'type': 'cash_flow',
            'start_date': '2024-01-01',
            'end_date': '2024-01-31',
            'generated_at': datetime.utcnow(),
            'generated_by': current_user.name,
            'file_size': '189 KB'
        }
    ]
    
    # Get scheduled reports
    scheduled_reports = [
        {
            'id': 1,
            'name': 'Monthly Financial Summary',
            'description': 'Automated monthly P&L and cash flow reports',
            'frequency': 'Monthly on 1st',
            'is_active': True,
            'last_run': '2024-01-01'
        },
        {
            'id': 2,
            'name': 'Weekly Aging Report',
            'description': 'Weekly accounts receivable aging analysis',
            'frequency': 'Every Monday',
            'is_active': True,
            'last_run': '2024-01-28'
        }
    ]
    
    return render_template('reports/financial.html',
                         recent_reports=recent_reports,
                         scheduled_reports=scheduled_reports)

@app.route('/financial/ai-budgeting')
@login_required
def ai_budgeting():
    """AI-powered budgeting and forecasting"""
    # Get AI insights (sample data)
    ai_insights = [
        {
            'title': 'Expense Optimization Opportunity',
            'description': 'Your marketing expenses are 23% higher than industry average. Consider reallocating budget to high-performing channels.',
            'priority': 'High'
        },
        {
            'title': 'Revenue Growth Alert',
            'description': 'Based on current trends, you\'re on track to exceed Q1 revenue targets by 15%.',
            'priority': 'Medium'
        },
        {
            'title': 'Cash Flow Recommendation',
            'description': 'Consider negotiating better payment terms with suppliers to improve cash flow by $5,000/month.',
            'priority': 'Low'
        }
    ]
    
    # Get financial goals
    financial_goals = [
        {
            'id': 1,
            'name': 'Q1 Revenue Target',
            'description': 'Achieve $100,000 in revenue for Q1 2024',
            'target_amount': 100000,
            'current_amount': 75000,
            'progress_percentage': 75,
            'status': 'on_track',
            'target_date': datetime(2024, 3, 31).date()
        },
        {
            'id': 2,
            'name': 'Expense Reduction',
            'description': 'Reduce operational expenses by 10%',
            'target_amount': 50000,
            'current_amount': 45000,
            'progress_percentage': 90,
            'status': 'at_risk',
            'target_date': datetime(2024, 6, 30).date()
        }
    ]
    
    # Get budget categories
    budget_categories = [
        {
            'id': 1,
            'name': 'Marketing',
            'budgeted': 10000,
            'actual': 8500,
            'variance': 1500,
            'percentage_used': 85
        },
        {
            'id': 2,
            'name': 'Operations',
            'budgeted': 15000,
            'actual': 16000,
            'variance': -1000,
            'percentage_used': 107
        },
        {
            'id': 3,
            'name': 'Salaries',
            'budgeted': 25000,
            'actual': 25000,
            'variance': 0,
            'percentage_used': 100
        }
    ]
    
    # Get forecasts
    forecasts = {
        'revenue_growth': 12,
        'expense_growth': 5
    }
    
    # Get scenarios
    scenarios = {
        'best_case': {
            'revenue_growth': 20,
            'cost_reduction': 10,
            'net_profit': 25000
        },
        'most_likely': {
            'revenue_growth': 12,
            'cost_reduction': 5,
            'net_profit': 18000
        },
        'worst_case': {
            'revenue_growth': 5,
            'cost_increase': 3,
            'net_profit': 8000
        }
    }
    
    # Chart data
    budget_chart_labels = ['Marketing', 'Operations', 'Salaries', 'Rent', 'Utilities']
    budgeted_data = [10000, 15000, 25000, 8000, 5000]
    actual_data = [8500, 16000, 25000, 8000, 4500]
    
    forecast_accuracy_labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun']
    forecasted_data = [8000, 8500, 9000, 9200, 9500, 9800]
    actual_forecast_data = [7800, 8700, 8900, 9300, 9400, 9700]
    
    revenue_forecast_labels = ['Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar']
    historical_revenue = [70000, 75000, 80000, 85000, 90000, 95000]
    forecasted_revenue = [None, None, None, 98000, 102000, 105000]
    
    expense_forecast_labels = ['Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar']
    historical_expenses = [60000, 62000, 65000, 68000, 70000, 72000]
    forecasted_expenses = [None, None, None, 74000, 76000, 78000]
    
    return render_template('financial/ai_budgeting.html',
                         ai_insights=ai_insights,
                         financial_goals=financial_goals,
                         budget_categories=budget_categories,
                         forecasts=forecasts,
                         scenarios=scenarios,
                         budget_chart_labels=budget_chart_labels,
                         budgeted_data=budgeted_data,
                         actual_data=actual_data,
                         forecast_accuracy_labels=forecast_accuracy_labels,
                         forecasted_data=forecasted_data,
                         actual_forecast_data=actual_forecast_data,
                         revenue_forecast_labels=revenue_forecast_labels,
                         historical_revenue=historical_revenue,
                         forecasted_revenue=forecasted_revenue,
                         expense_forecast_labels=expense_forecast_labels,
                         historical_expenses=historical_expenses,
                         forecasted_expenses=forecasted_expenses)

# Customer Management Routes
@app.route('/customers')
@login_required
def customer_management():
    """Customer management dashboard"""
    # Get customers
    customers = Customer.query.filter_by(user_id=current_user.id).all()
    
    # Get customer groups
    customer_groups = CustomerGroup.query.filter_by(user_id=current_user.id).all()
    
    # Calculate statistics
    stats = {
        'total_customers': len(customers),
        'active_customers': len([c for c in customers if c.is_active]),
        'total_revenue': sum([c.total_purchases for c in customers]),
        'avg_customer_value': sum([c.total_purchases for c in customers]) / len(customers) if customers else 0
    }
    
    return render_template('customers/management.html',
                         customers=customers,
                         customer_groups=customer_groups,
                         stats=stats,
                         total_customers=len(customers))

# Advanced Invoicing Routes
@app.route('/invoices/advanced')
@login_required
def advanced_invoicing():
    """Advanced invoicing dashboard"""
    # Get recent invoices
    recent_invoices = Invoice.query.filter_by(user_id=current_user.id).order_by(Invoice.created_at.desc()).limit(10).all()
    
    # Get recent quotes
    recent_quotes = Quote.query.filter_by(user_id=current_user.id).order_by(Quote.created_at.desc()).limit(10).all()
    
    # Calculate statistics
    stats = {
        'total_invoices': Invoice.query.filter_by(user_id=current_user.id).count(),
        'invoices_this_month': Invoice.query.filter(
            Invoice.user_id == current_user.id,
            Invoice.created_at >= datetime.utcnow().replace(day=1)
        ).count(),
        'outstanding_amount': db.session.query(
            db.func.sum(Invoice.total_amount - Invoice.paid_amount)
        ).filter_by(user_id=current_user.id).filter(Invoice.status != 'PAID').scalar() or 0,
        'overdue_count': Invoice.query.filter(
            Invoice.user_id == current_user.id,
            Invoice.due_date < datetime.utcnow().date(),
            Invoice.status != 'PAID'
        ).count(),
        'paid_this_month': db.session.query(db.func.sum(Payment.amount)).filter(
            Payment.payment_date >= datetime.utcnow().replace(day=1)
        ).join(Invoice).filter(Invoice.user_id == current_user.id).scalar() or 0,
        'paid_count': Payment.query.filter(
            Payment.payment_date >= datetime.utcnow().replace(day=1)
        ).join(Invoice).filter(Invoice.user_id == current_user.id).count(),
        'active_quotes': Quote.query.filter_by(user_id=current_user.id, status='SENT').count(),
        'converted_rate': 75  # Sample data
    }
    
    return render_template('invoices/advanced.html',
                         recent_invoices=recent_invoices,
                         recent_quotes=recent_quotes,
                         stats=stats)

# Financial Analytics Routes
@app.route('/financial-analytics')
@login_required
def financial_analytics():
    """Main financial analytics dashboard"""
    # Get key financial metrics
    total_revenue = db.session.query(db.func.sum(Invoice.total_amount)).filter_by(user_id=current_user.id).filter(Invoice.status == 'PAID').scalar() or 0
    total_expenses = db.session.query(db.func.sum(Expense.amount)).filter_by(user_id=current_user.id).scalar() or 0
    net_profit = total_revenue - total_expenses
    
    # Get budget performance
    budgets = Budget.query.filter_by(user_id=current_user.id, is_active=True).all()
    budget_performance = []
    for budget in budgets:
        spent = db.session.query(db.func.sum(Expense.amount)).filter_by(budget_id=budget.id).scalar() or 0
        budget_performance.append({
            'name': budget.name,
            'budgeted': budget.amount,
            'spent': spent,
            'remaining': budget.amount - spent,
            'percentage': (spent / budget.amount * 100) if budget.amount > 0 else 0
        })
    
    return render_template('financial_analytics/dashboard.html', 
                         total_revenue=total_revenue,
                         total_expenses=total_expenses,
                         net_profit=net_profit,
                         budget_performance=budget_performance)

@app.route('/financial-analytics/profit-loss')
@login_required
def profit_loss_statement():
    """Generate Profit & Loss Statement"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if not start_date:
        start_date = (datetime.utcnow() - timedelta(days=30)).strftime('%Y-%m-%d')
    if not end_date:
        end_date = datetime.utcnow().strftime('%Y-%m-%d')
    
    start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    # Get revenue data
    revenue_data = db.session.query(
        db.func.sum(Invoice.total_amount),
        db.func.sum(Invoice.gst_amount)
    ).filter(
        Invoice.user_id == current_user.id,
        Invoice.status == 'PAID',
        Invoice.issue_date >= start_date,
        Invoice.issue_date <= end_date
    ).first()
    
    total_revenue = revenue_data[0] or 0
    gst_collected = revenue_data[1] or 0
    net_revenue = total_revenue - gst_collected
    
    # Get expense data by category
    expenses = db.session.query(
        Expense.category,
        db.func.sum(Expense.amount)
    ).filter(
        Expense.user_id == current_user.id,
        Expense.expense_date >= start_date,
        Expense.expense_date <= end_date
    ).group_by(Expense.category).all()
    
    expense_breakdown = [{'category': cat, 'amount': amt} for cat, amt in expenses]
    total_expenses = sum(amt for cat, amt in expenses)
    
    # Calculate profit
    gross_profit = net_revenue
    net_profit = gross_profit - total_expenses
    profit_margin = (net_profit / net_revenue * 100) if net_revenue > 0 else 0
    
    p&l_data = {
        'period': f"{start_date} to {end_date}",
        'revenue': {
            'total_revenue': total_revenue,
            'gst_collected': gst_collected,
            'net_revenue': net_revenue
        },
        'expenses': {
            'total_expenses': total_expenses,
            'breakdown': expense_breakdown
        },
        'profit': {
            'gross_profit': gross_profit,
            'net_profit': net_profit,
            'profit_margin': profit_margin
        }
    }
    
    return render_template('financial_analytics/profit_loss.html', pl_data=pl_data)

@app.route('/financial-analytics/cash-flow')
@login_required
def cash_flow_analysis():
    """Cash Flow Analysis"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if not start_date:
        start_date = (datetime.utcnow() - timedelta(days=30)).strftime('%Y-%m-%d')
    if not end_date:
        end_date = datetime.utcnow().strftime('%Y-%m-%d')
    
    start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    # Cash In (Invoices and Payments)
    cash_in = db.session.query(
        db.func.sum(Payment.amount)
    ).filter(
        Payment.payment_date >= start_date,
        Payment.payment_date <= end_date
    ).join(Invoice).filter(Invoice.user_id == current_user.id).scalar() or 0
    
    # Cash Out (Expenses)
    cash_out = db.session.query(
        db.func.sum(Expense.amount)
    ).filter(
        Expense.user_id == current_user.id,
        Expense.expense_date >= start_date,
        Expense.expense_date <= end_date
    ).scalar() or 0
    
    net_cash_flow = cash_in - cash_out
    
    # Get daily cash flow for chart
    daily_flow = []
    current_date = start_date
    while current_date <= end_date:
        day_in = db.session.query(db.func.sum(Payment.amount)).filter(
            Payment.payment_date == current_date
        ).join(Invoice).filter(Invoice.user_id == current_user.id).scalar() or 0
        
        day_out = db.session.query(db.func.sum(Expense.amount)).filter(
            Expense.expense_date == current_date,
            Expense.user_id == current_user.id
        ).scalar() or 0
        
        daily_flow.append({
            'date': current_date.strftime('%Y-%m-%d'),
            'cash_in': day_in,
            'cash_out': day_out,
            'net_flow': day_in - day_out
        })
        
        current_date += timedelta(days=1)
    
    cash_flow_data = {
        'period': f"{start_date} to {end_date}",
        'summary': {
            'total_cash_in': cash_in,
            'total_cash_out': cash_out,
            'net_cash_flow': net_cash_flow
        },
        'daily_flow': daily_flow
    }
    
    return render_template('financial_analytics/cash_flow.html', cash_data=cash_flow_data)

@app.route('/financial-analytics/aging-report')
@login_required
def aging_report():
    """Aging Report for overdue payments"""
    today = datetime.utcnow().date()
    
    # Get all unpaid invoices
    unpaid_invoices = Invoice.query.filter(
        Invoice.user_id == current_user.id,
        Invoice.status != 'PAID'
    ).all()
    
    aging_buckets = {
        'current': [],      # 0-30 days
        '31_60': [],        # 31-60 days
        '61_90': [],        # 61-90 days
        'over_90': []       # Over 90 days
    }
    
    total_outstanding = 0
    
    for invoice in unpaid_invoices:
        days_overdue = (today - invoice.due_date).days
        amount_outstanding = invoice.total_amount - invoice.paid_amount
        
        if days_overdue <= 0:
            aging_buckets['current'].append({
                'invoice': invoice,
                'days_overdue': 0,
                'amount_outstanding': amount_outstanding
            })
        elif days_overdue <= 30:
            aging_buckets['31_60'].append({
                'invoice': invoice,
                'days_overdue': days_overdue,
                'amount_outstanding': amount_outstanding
            })
        elif days_overdue <= 60:
            aging_buckets['61_90'].append({
                'invoice': invoice,
                'days_overdue': days_overdue,
                'amount_outstanding': amount_outstanding
            })
        else:
            aging_buckets['over_90'].append({
                'invoice': invoice,
                'days_overdue': days_overdue,
                'amount_outstanding': amount_outstanding
            })
        
        total_outstanding += amount_outstanding
    
    # Calculate totals for each bucket
    bucket_totals = {}
    for bucket_name, invoices in aging_buckets.items():
        bucket_totals[bucket_name] = sum(inv['amount_outstanding'] for inv in invoices)
    
    aging_data = {
        'buckets': aging_buckets,
        'totals': bucket_totals,
        'total_outstanding': total_outstanding,
        'report_date': today
    }
    
    return render_template('financial_analytics/aging_report.html', aging_data=aging_data)

@app.route('/budgets', methods=['GET', 'POST'])
@login_required
def budgets():
    if request.method == 'POST':
        budget = Budget(
            user_id=current_user.id,
            name=request.form.get('name'),
            description=request.form.get('description'),
            category=request.form.get('category'),
            budget_type=request.form.get('budget_type', 'MONTHLY'),
            amount=float(request.form.get('amount')),
            start_date=datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date(),
            end_date=datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date()
        )
        db.session.add(budget)
        db.session.commit()
        flash('Budget created successfully!', 'success')
        return redirect(url_for('budgets'))
    
    budgets = Budget.query.filter_by(user_id=current_user.id).order_by(Budget.created_at.desc()).all()
    return render_template('financial_analytics/budgets.html', budgets=budgets)

@app.route('/expenses', methods=['GET', 'POST'])
@login_required
def expenses():
    if request.method == 'POST':
        expense = Expense(
            user_id=current_user.id,
            budget_id=request.form.get('budget_id') or None,
            category=request.form.get('category'),
            subcategory=request.form.get('subcategory'),
            amount=float(request.form.get('amount')),
            description=request.form.get('description'),
            expense_date=datetime.strptime(request.form.get('expense_date'), '%Y-%m-%d').date(),
            payment_method=request.form.get('payment_method'),
            vendor=request.form.get('vendor'),
            receipt_number=request.form.get('receipt_number'),
            is_reimbursable=request.form.get('is_reimbursable') == 'on'
        )
        db.session.add(expense)
        db.session.commit()
        flash('Expense added successfully!', 'success')
        return redirect(url_for('expenses'))
    
    expenses = Expense.query.filter_by(user_id=current_user.id).order_by(Expense.expense_date.desc()).all()
    budgets = Budget.query.filter_by(user_id=current_user.id, is_active=True).all()
    return render_template('financial_analytics/expenses.html', expenses=expenses, budgets=budgets)

# Advanced Customer Management Routes
@app.route('/customers/advanced')
@login_required
def customers_advanced():
    """Advanced customer management dashboard"""
    customers = Customer.query.filter_by(user_id=current_user.id).order_by(Customer.created_at.desc()).all()
    groups = CustomerGroup.query.filter_by(user_id=current_user.id).all()
    
    # Calculate customer metrics
    customer_metrics = []
    for customer in customers:
        total_invoices = Invoice.query.filter_by(customer_id=customer.id).count()
        total_revenue = db.session.query(db.func.sum(Invoice.total_amount)).filter_by(customer_id=customer.id).scalar() or 0
        unpaid_amount = db.session.query(db.func.sum(Invoice.total_amount - Invoice.paid_amount)).filter(
            Invoice.customer_id == customer.id,
            Invoice.status != 'PAID'
        ).scalar() or 0
        
        customer_metrics.append({
            'customer': customer,
            'total_invoices': total_invoices,
            'total_revenue': total_revenue,
            'unpaid_amount': unpaid_amount,
            'clv': calculate_clv(customer.id)  # Customer Lifetime Value
        })
    
    return render_template('customers/advanced_dashboard.html', 
                         customer_metrics=customer_metrics, 
                         groups=groups)

def calculate_clv(customer_id):
    """Calculate Customer Lifetime Value"""
    # Simple CLV calculation: Average order value × Purchase frequency × Customer lifespan
    total_revenue = db.session.query(db.func.sum(Invoice.total_amount)).filter_by(customer_id=customer_id).scalar() or 0
    invoice_count = Invoice.query.filter_by(customer_id=customer_id).count()
    
    if invoice_count == 0:
        return 0
    
    avg_order_value = total_revenue / invoice_count
    
    # Get first and last invoice dates to estimate lifespan in months
    first_invoice = Invoice.query.filter_by(customer_id=customer_id).order_by(Invoice.created_at.asc()).first()
    last_invoice = Invoice.query.filter_by(customer_id=customer_id).order_by(Invoice.created_at.desc()).first()
    
    if first_invoice and last_invoice:
        months_active = (last_invoice.created_at - first_invoice.created_at).days / 30.44
        if months_active > 0:
            purchase_frequency = invoice_count / months_active
            # Assume customer will be active for 24 more months
            clv = avg_order_value * purchase_frequency * 24
            return round(clv, 2)
    
    return avg_order_value

@app.route('/customers/groups', methods=['GET', 'POST'])
@login_required
def customer_groups():
    if request.method == 'POST':
        group = CustomerGroup(
            user_id=current_user.id,
            name=request.form.get('name'),
            description=request.form.get('description'),
            credit_multiplier=float(request.form.get('credit_multiplier', 1.0)),
            priority=int(request.form.get('priority', 0))
        )
        db.session.add(group)
        db.session.commit()
        flash('Customer group created successfully!', 'success')
        return redirect(url_for('customer_groups'))
    
    groups = CustomerGroup.query.filter_by(user_id=current_user.id).order_by(CustomerGroup.priority.desc()).all()
    return render_template('customers/groups.html', groups=groups)

@app.route('/customers/<int:customer_id>/communications', methods=['GET', 'POST'])
@login_required
def customer_communications(customer_id):
    customer = Customer.query.filter_by(id=customer_id, user_id=current_user.id).first_or_404()
    
    if request.method == 'POST':
        communication = CustomerCommunication(
            customer_id=customer_id,
            user_id=current_user.id,
            communication_type=request.form.get('communication_type'),
            subject=request.form.get('subject'),
            content=request.form.get('content'),
            direction=request.form.get('direction'),
            communication_date=datetime.strptime(request.form.get('communication_date'), '%Y-%m-%d %H:%M')
        )
        db.session.add(communication)
        db.session.commit()
        flash('Communication logged successfully!', 'success')
        return redirect(url_for('customer_communications', customer_id=customer_id))
    
    communications = CustomerCommunication.query.filter_by(customer_id=customer_id).order_by(CustomerCommunication.communication_date.desc()).all()
    return render_template('customers/communications.html', customer=customer, communications=communications)

@app.route('/customers/<int:customer_id>/portal', methods=['GET', 'POST'])
@login_required
def customer_portal(customer_id):
    customer = Customer.query.filter_by(id=customer_id, user_id=current_user.id).first_or_404()
    
    portal = CustomerPortal.query.filter_by(customer_id=customer_id).first()
    
    if request.method == 'POST':
        if not portal:
            portal = CustomerPortal(
                customer_id=customer_id,
                user_id=current_user.id,
                portal_code=secrets.token_urlsafe(16),
                expires_at=datetime.utcnow() + timedelta(days=365)
            )
            db.session.add(portal)
        else:
            portal.is_active = request.form.get('is_active') == 'on'
            portal.expires_at = datetime.strptime(request.form.get('expires_at'), '%Y-%m-%d')
        
        db.session.commit()
        flash('Customer portal updated successfully!', 'success')
        return redirect(url_for('customer_portal', customer_id=customer_id))
    
    return render_template('customers/portal.html', customer=customer, portal=portal)

# Advanced Invoicing Routes
@app.route('/invoices/templates', methods=['GET', 'POST'])
@login_required
def invoice_templates():
    if request.method == 'POST':
        template = InvoiceTemplate(
            user_id=current_user.id,
            name=request.form.get('name'),
            description=request.form.get('description'),
            template_data=json.dumps({
                'items': request.form.getlist('item_description[]'),
                'quantities': request.form.getlist('item_quantity[]'),
                'prices': request.form.getlist('item_price[]'),
                'notes': request.form.get('notes'),
                'terms': request.form.get('terms')
            }),
            is_default=request.form.get('is_default') == 'on'
        )
        db.session.add(template)
        db.session.commit()
        flash('Invoice template created successfully!', 'success')
        return redirect(url_for('invoice_templates'))
    
    templates = InvoiceTemplate.query.filter_by(user_id=current_user.id).order_by(InvoiceTemplate.created_at.desc()).all()
    return render_template('invoices/templates.html', templates=templates)

@app.route('/invoices/create-from-template/<int:template_id>', methods=['GET', 'POST'])
@login_required
def create_invoice_from_template(template_id):
    template = InvoiceTemplate.query.filter_by(id=template_id, user_id=current_user.id).first_or_404()
    
    if request.method == 'POST':
        customer_id = request.form.get('customer_id')
        issue_date = datetime.strptime(request.form.get('issue_date'), '%Y-%m-%d').date()
        due_date = datetime.strptime(request.form.get('due_date'), '%Y-%m-%d').date()
        
        invoice = Invoice(
            user_id=current_user.id,
            customer_id=customer_id,
            invoice_number=generate_invoice_number(),
            issue_date=issue_date,
            due_date=due_date,
            notes=request.form.get('notes'),
            terms=request.form.get('terms'),
            status='DRAFT'
        )
        
        # Add items from template (modified by user if needed)
        template_data = json.loads(template.template_data)
        subtotal = 0
        
        for i, description in enumerate(template_data['items']):
            if description.strip():
                quantity = float(request.form.get(f'quantity_{i}', template_data['quantities'][i]))
                price = float(request.form.get(f'price_{i}', template_data['prices'][i]))
                total = quantity * price
                subtotal += total
                
                item = InvoiceItem(
                    invoice=invoice,
                    description=description,
                    quantity=quantity,
                    unit_price=price,
                    total=total
                )
                db.session.add(item)
        
        invoice.subtotal = subtotal
        invoice.gst_amount = subtotal * 0.18
        invoice.total_amount = subtotal + invoice.gst_amount
        
        db.session.add(invoice)
        db.session.commit()
        
        flash(f'Invoice created from template "{template.name}"!', 'success')
        return redirect(url_for('view_invoice', id=invoice.id))
    
    customers = Customer.query.filter_by(user_id=current_user.id).all()
    template_data = json.loads(template.template_data)
    return render_template('invoices/create_from_template.html', 
                         template=template, 
                         customers=customers, 
                         template_data=template_data)

@app.route('/currencies', methods=['GET', 'POST'])
@login_required
def currencies():
    if request.method == 'POST':
        # Set new base currency
        Currency.query.filter_by(user_id=current_user.id).update({'is_base': False})
        
        currency = Currency(
            user_id=current_user.id,
            code=request.form.get('code'),
            name=request.form.get('name'),
            symbol=request.form.get('symbol'),
            exchange_rate=float(request.form.get('exchange_rate', 1.0)),
            is_base=request.form.get('is_base') == 'on'
        )
        db.session.add(currency)
        db.session.commit()
        flash('Currency added successfully!', 'success')
        return redirect(url_for('currencies'))
    
    currencies = Currency.query.filter_by(user_id=current_user.id).all()
    return render_template('invoices/currencies.html', currencies=currencies)

@app.route('/discounts', methods=['GET', 'POST'])
@login_required
def discount_coupons():
    if request.method == 'POST':
        coupon = DiscountCoupon(
            user_id=current_user.id,
            code=request.form.get('code'),
            description=request.form.get('description'),
            discount_type=request.form.get('discount_type'),
            discount_value=float(request.form.get('discount_value')),
            min_amount=float(request.form.get('min_amount')) if request.form.get('min_amount') else None,
            max_discount=float(request.form.get('max_discount')) if request.form.get('max_discount') else None,
            usage_limit=int(request.form.get('usage_limit')) if request.form.get('usage_limit') else None,
            valid_from=datetime.strptime(request.form.get('valid_from'), '%Y-%m-%d').date(),
            valid_until=datetime.strptime(request.form.get('valid_until'), '%Y-%m-%d').date()
        )
        db.session.add(coupon)
        db.session.commit()
        flash('Discount coupon created successfully!', 'success')
        return redirect(url_for('discount_coupons'))
    
    coupons = DiscountCoupon.query.filter_by(user_id=current_user.id).order_by(DiscountCoupon.created_at.desc()).all()
    return render_template('invoices/discounts.html', coupons=coupons)
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
@auth_rate_limit  # Apply rate limiting to login
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = request.form.get('remember') == 'on'
        
        # Log login attempt
        login_attempt = LoginAttempt(
            email=email,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            success=False
        )
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.is_active and check_password_hash(user.password_hash, password):
            login_user(user, remember=remember)
            login_attempt.user_id = user.id
            login_attempt.success = True
            db.session.add(login_attempt)
            db.session.commit()
            
            # Log successful login with audit system
            audit_log = AuditLog(
                user_id=user.id,
                action='LOGIN',
                resource='User',
                resource_id=user.id,
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent'),
                severity='INFO'
            )
            db.session.add(audit_log)
            db.session.commit()
            
            # Cache user session for faster access
            cache = get_cache()
            cache.set(f"user_session_{user.id}", {
                'email': user.email,
                'name': user.name,
                'role': user.role,
                'login_time': datetime.utcnow().isoformat()
            }, ttl=3600)
            
            flash('Login successful!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('dashboard'))
        else:
            login_attempt.reason = 'Invalid credentials' if not user or not check_password_hash(user.password_hash, password) else 'Account inactive'
            db.session.add(login_attempt)
            db.session.commit()
            flash('Invalid email or password', 'error')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    # Log logout
    audit_log = AuditLog(
        user_id=current_user.id,
        action='LOGOUT',
        resource='User',
        resource_id=current_user.id,
        ip_address=request.remote_addr,
        user_agent=request.headers.get('User-Agent'),
        severity='INFO'
    )
    db.session.add(audit_log)
    db.session.commit()
    
    logout_user()
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
@cache_view(ttl=300)  # Cache dashboard for 5 minutes
@audit_action(AuditAction.READ, AuditResource.DASHBOARD)
def dashboard():
    # Try to get stats from cache first
    cache = get_cache()
    cache_key = f"dashboard_stats_{current_user.id}"
    cached_stats = cache.get(cache_key)
    
    if cached_stats:
        stats = cached_stats
    else:
        # Get dashboard statistics
        stats = {
            'total_invoices': Invoice.query.filter_by(user_id=current_user.id).count(),
            'total_revenue': db.session.query(db.func.sum(Invoice.total_amount)).filter_by(user_id=current_user.id).filter(Invoice.status == 'PAID').scalar() or 0,
            'pending_payments': Invoice.query.filter_by(user_id=current_user.id).filter(Invoice.status != 'PAID').count(),
            'total_customers': Customer.query.filter_by(user_id=current_user.id).count()
        }
        # Cache the stats for 5 minutes
        cache.set(cache_key, stats, ttl=300)
    
    # Get recent invoices
    recent_invoices = Invoice.query.filter_by(user_id=current_user.id).order_by(Invoice.created_at.desc()).limit(10).all()
    
    # Get customers for dropdown
    customers = Customer.query.filter_by(user_id=current_user.id).all()
    
    # Mock recent activities (in real app, this would come from audit logs)
    recent_activities = [
        {'description': 'Created new invoice', 'icon': 'file-invoice', 'timestamp': datetime.utcnow()},
        {'description': 'Added new customer', 'icon': 'user-plus', 'timestamp': datetime.utcnow() - timedelta(hours=2)},
        {'description': 'Payment received', 'icon': 'rupee-sign', 'timestamp': datetime.utcnow() - timedelta(hours=4)}
    ]
    
    return render_template('dashboard.html', 
                         stats=stats, 
                         recent_invoices=recent_invoices,
                         customers=customers,
                         recent_activities=recent_activities,
                         today=datetime.utcnow().strftime('%Y-%m-%d'))

@app.route('/invoices')
@login_required
def invoices():
    page = request.args.get('page', 1, type=int)
    invoices = Invoice.query.filter_by(user_id=current_user.id).order_by(Invoice.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False)
    return render_template('invoices.html', invoices=invoices)

@app.route('/invoices/create', methods=['GET', 'POST'])
@login_required
@require_permission(Permission.INVOICE_CREATE)  # RBAC permission check
def create_invoice():
    if request.method == 'POST':
        # Get form data
        customer_id = request.form.get('customer_id')
        issue_date = datetime.strptime(request.form.get('issue_date'), '%Y-%m-%d').date()
        due_date = datetime.strptime(request.form.get('due_date'), '%Y-%m-%d').date()
        currency = request.form.get('currency', 'INR')
        notes = request.form.get('notes', '')
        terms = request.form.get('terms', '')
        
        # Create invoice
        invoice = Invoice(
            user_id=current_user.id,
            customer_id=customer_id,
            invoice_number=generate_invoice_number(),
            issue_date=issue_date,
            due_date=due_date,
            currency=currency,
            notes=notes,
            terms=terms,
            status='DRAFT'
        )
        
        # Process items
        item_descriptions = request.form.getlist('item_description[]')
        item_quantities = request.form.getlist('item_quantity[]')
        item_prices = request.form.getlist('item_price[]')
        
        subtotal = 0
        for i, desc in enumerate(item_descriptions):
            if desc.strip():
                quantity = float(item_quantities[i])
                price = float(item_prices[i])
                total = quantity * price
                subtotal += total
                
                item = InvoiceItem(
                    invoice=invoice,
                    description=desc,
                    quantity=quantity,
                    unit_price=price,
                    total=total
                )
                db.session.add(item)
        
        invoice.subtotal = subtotal
        invoice.gst_amount = subtotal * 0.18  # 18% GST
        invoice.total_amount = subtotal + invoice.gst_amount
        
        db.session.add(invoice)
        db.session.commit()
        
        # Log creation with audit system
        audit_log = AuditLog(
            user_id=current_user.id,
            action='CREATE',
            resource='Invoice',
            resource_id=invoice.id,
            new_values=json.dumps({
                'invoice_number': invoice.invoice_number,
                'customer_id': customer_id,
                'total_amount': invoice.total_amount
            }),
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            severity='INFO'
        )
        db.session.add(audit_log)
        db.session.commit()
        
        # Enqueue background job to send notification
        enqueue_job('SEND_EMAIL', {
            'to': current_user.email,
            'subject': f'Invoice {invoice.invoice_number} Created',
            'template': 'invoice_created',
            'data': {
                'invoice_number': invoice.invoice_number,
                'customer_name': invoice.customer.name,
                'amount': invoice.total_amount
            }
        }, priority='HIGH')
        
        # Clear cache for this user's dashboard
        cache = get_cache()
        cache.delete(f"dashboard_stats_{current_user.id}")
        
        flash(f'Invoice {invoice.invoice_number} created successfully!', 'success')
        return redirect(url_for('view_invoice', id=invoice.id))
    
    customers = Customer.query.filter_by(user_id=current_user.id).all()
    products = Product.query.filter_by(user_id=current_user.id).all()
    return render_template('create_invoice.html', customers=customers, products=products)

@app.route('/invoices/<int:id>')
@login_required
def view_invoice(id):
    invoice = Invoice.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    return render_template('view_invoice.html', invoice=invoice)

@app.route('/invoices/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_invoice(id):
    invoice = Invoice.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    
    if request.method == 'POST':
        # Update invoice logic here
        flash('Invoice updated successfully!', 'success')
        return redirect(url_for('view_invoice', id=invoice.id))
    
    customers = Customer.query.filter_by(user_id=current_user.id).all()
    return render_template('edit_invoice.html', invoice=invoice, customers=customers)

@app.route('/quotes')
@login_required
def quotes():
    page = request.args.get('page', 1, type=int)
    quotes = Quote.query.filter_by(user_id=current_user.id).order_by(Quote.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False)
    return render_template('quotes.html', quotes=quotes)

@app.route('/quotes/create', methods=['GET', 'POST'])
@login_required
def create_quote():
    if request.method == 'POST':
        # Similar to create_invoice but for quotes
        flash('Quote created successfully!', 'success')
        return redirect(url_for('quotes'))
    
    customers = Customer.query.filter_by(user_id=current_user.id).all()
    products = Product.query.filter_by(user_id=current_user.id).all()
    return render_template('create_quote.html', customers=customers, products=products)

@app.route('/customers')
@login_required
def customers():
    page = request.args.get('page', 1, type=int)
    customers = Customer.query.filter_by(user_id=current_user.id).order_by(Customer.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False)
    return render_template('customers.html', customers=customers)

@app.route('/customers/add', methods=['GET', 'POST'])
@login_required
def add_customer():
    if request.method == 'POST':
        customer = Customer(
            user_id=current_user.id,
            name=request.form.get('name'),
            email=request.form.get('email'),
            phone=request.form.get('phone'),
            address=request.form.get('address'),
            gstin=request.form.get('gstin'),
            company_name=request.form.get('company_name')
        )
        
        db.session.add(customer)
        db.session.commit()
        
        flash('Customer added successfully!', 'success')
        return redirect(url_for('customers'))
    
    return render_template('add_customer.html')

@app.route('/products')
@login_required
def products():
    page = request.args.get('page', 1, type=int)
    products = Product.query.filter_by(user_id=current_user.id).order_by(Product.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False)
    return render_template('products.html', products=products)

@app.route('/products/add', methods=['GET', 'POST'])
@login_required
def add_product():
    if request.method == 'POST':
        product = Product(
            user_id=current_user.id,
            name=request.form.get('name'),
            description=request.form.get('description'),
            price=float(request.form.get('price')),
            gst_rate=float(request.form.get('gst_rate', 0)),
            hsn_code=request.form.get('hsn_code'),
            stock_quantity=int(request.form.get('stock_quantity', 0))
        )
        
        db.session.add(product)
        db.session.commit()
        
        flash('Product added successfully!', 'success')
        return redirect(url_for('products'))
    
    return render_template('add_product.html')

@app.route('/recurring')
@login_required
def recurring():
    recurring_invoices = RecurringInvoice.query.filter_by(user_id=current_user.id).all()
    return render_template('recurring.html', recurring_invoices=recurring_invoices)

@app.route('/reports')
@login_required
def reports():
    return render_template('reports.html')

@app.route('/settings')
@login_required
def settings():
    return render_template('settings.html')

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html')

# API Routes
@app.route('/api/send-invoice/<int:invoice_id>', methods=['POST'])
@login_required
@rate_limit  # Apply general rate limiting
def send_invoice_api(invoice_id):
    invoice = Invoice.query.filter_by(id=invoice_id, user_id=current_user.id).first()
    if not invoice:
        return jsonify({'success': False, 'message': 'Invoice not found'})
    
    # Enqueue background job to send email
    job_id = enqueue_job('SEND_INVOICE_EMAIL', {
        'invoice_id': invoice.id,
        'user_email': current_user.email,
        'customer_email': invoice.customer.email
    }, priority='HIGH')
    
    # Log the action
    audit_log = AuditLog(
        user_id=current_user.id,
        action='SEND_EMAIL',
        resource='Invoice',
        resource_id=invoice.id,
        new_values=json.dumps({'job_id': job_id}),
        ip_address=request.remote_addr,
        user_agent=request.headers.get('User-Agent'),
        severity='INFO'
    )
    db.session.add(audit_log)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Invoice queued for sending', 'job_id': job_id})

@app.route('/admin/system-status')
@login_required
@require_permission(Permission.SYSTEM_ADMIN)  # Admin only
def system_status():
    """Show system status with all technical enhancements"""
    cache_info = get_cache().memory_cache.get_stats()
    db_performance = get_database_performance_report()
    
    # Get recent background jobs
    recent_jobs = BackgroundJob.query.order_by(BackgroundJob.created_at.desc()).limit(10).all()
    
    # Get recent audit logs
    recent_logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(20).all()
    
    # Get rate limit stats
    rate_limits = RateLimit.query.filter(RateLimit.reset_at > datetime.utcnow() - timedelta(hours=1)).all()
    
    return render_template('admin/system_status.html', 
                         cache_info=cache_info,
                         db_performance=db_performance,
                         recent_jobs=recent_jobs,
                         recent_logs=recent_logs,
                         rate_limits=rate_limits)

@app.route('/admin/backup-database', methods=['POST'])
@login_required
@require_permission(Permission.SYSTEM_ADMIN)
def backup_database():
    """Trigger database backup"""
    from database_backup import create_backup
    
    backup_id = create_backup('FULL', created_by=current_user.id)
    
    flash(f'Database backup initiated (ID: {backup_id})', 'success')
    return redirect(url_for('system_status'))

# Import technical enhancement modules
from database_optimization import initialize_database_optimization, get_database_performance_report
from cache_layer import initialize_cache, cached, cache_view, get_cache
from background_jobs import initialize_background_jobs, enqueue_job
from rate_limiting import initialize_rate_limiting, rate_limit, auth_rate_limit
from database_backup import initialize_backup_system
from two_factor_auth import initialize_two_factor_auth
from rbac_system import initialize_rbac, require_permission, Permission
from audit_logging import initialize_audit_system, audit_action, AuditAction, AuditResource
from data_encryption import initialize_encryption
from session_management import initialize_session_system

# Create tables
with app.app_context():
    db.create_all()
    
    # Initialize all technical enhancement systems
    logger.info("Initializing technical enhancement systems...")
    
    # Performance & Scalability Systems
    initialize_database_optimization()
    initialize_cache()
    initialize_background_jobs()
    initialize_rate_limiting(app)
    initialize_backup_system()
    
    # Security Systems
    initialize_two_factor_auth(app)
    initialize_rbac(app)
    initialize_audit_system(app)
    initialize_encryption()
    initialize_session_system(app)
    
    logger.info("All technical enhancement systems initialized successfully!")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)