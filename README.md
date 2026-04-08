# Mobi Invoice Termux

A professional invoicing solution designed for Termux and mobile environments, built with Flask and optimized for performance and security.

## Features

### Core Functionality
- ✅ Invoice creation and management
- ✅ Quote generation
- ✅ Customer management
- ✅ Product/service catalog
- ✅ Recurring invoices
- ✅ Payment tracking
- ✅ GST compliance (India)
- ✅ Multi-currency support

### Technical Enhancements
- ✅ **Performance & Scalability**
  - Database optimization with indexing
  - Hybrid caching layer (memory + database)
  - Background job processing
  - API rate limiting
  - Automated database backups

- ✅ **Security Improvements**
  - Two-factor authentication (2FA)
  - Role-based access control (RBAC)
  - Comprehensive audit logging
  - Data encryption (field-level)
  - Secure session management

### User Interface
- 📱 Mobile-responsive design
- 🎨 Modern Bootstrap 5 UI
- ⚡ Fast loading times
- 🖨️ Print-friendly invoices
- 📊 Dashboard with analytics

## Installation

### Prerequisites
- Python 3.8+
- Termux (for Android) or any Unix-like system

### Setup Instructions

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd mobi-invoice-termux
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   export SECRET_KEY="your-secret-key-here"
   export FLASK_ENV="development"
   ```

4. **Initialize the database**
   ```bash
   python -c "from app import app, db; app.app_context().push(); db.create_all()"
   ```

5. **Run the application**
   ```bash
   python app.py
   ```

6. **Access the application**
   - Open your browser and go to `http://localhost:5000`
   - Default login: Create a new account

## Project Structure

```
mobi-invoice-termux/
├── app.py                      # Main Flask application
├── requirements.txt             # Python dependencies
├── .gitignore                  # Git ignore file
├── vercel.json                 # Vercel deployment config
├── templates/                  # HTML templates
│   ├── base.html              # Base template
│   ├── login.html             # Login page
│   ├── dashboard.html         # Dashboard
│   └── ...
├── static/                     # Static files
│   ├── css/
│   │   └── style.css          # Custom styles
│   ├── js/
│   │   └── app.js             # JavaScript functions
│   └── images/                # Image assets
├── database_optimization.py    # Database performance module
├── cache_layer.py             # Caching system
├── background_jobs.py         # Background task processing
├── rate_limiting.py           # API rate limiting
├── database_backup.py         # Backup system
├── two_factor_auth.py         # 2FA implementation
├── rbac_system.py             # Role-based access control
├── audit_logging.py           # Audit logging
├── data_encryption.py         # Data encryption
├── session_management.py      # Session management
└── TECHNICAL_ENHANCEMENTS_REPORT.md  # Implementation details
```

## Configuration

### Environment Variables
- `SECRET_KEY`: Flask secret key (required)
- `FLASK_ENV`: Environment (development/production)
- `DATABASE_URL`: Database connection string (optional, defaults to SQLite)

### Database Configuration
- Default: SQLite (`mobi_invoice.db`)
- Production: Configure with PostgreSQL or MySQL

## Security Features

### Authentication & Authorization
- Secure password hashing with bcrypt
- Session-based authentication
- Role-based access control
- Two-factor authentication support

### Data Protection
- Field-level encryption for sensitive data
- Audit logging for all operations
- SQL injection prevention
- XSS protection
- CSRF protection

### Performance Features
- Database query optimization
- Intelligent caching
- Background job processing
- Rate limiting
- Database backups

## API Endpoints

### Authentication
- `POST /login` - User login
- `GET /logout` - User logout
- `POST /register` - User registration

### Invoices
- `GET /invoices` - List invoices
- `POST /invoices/create` - Create invoice
- `GET /invoices/<id>` - View invoice
- `PUT /invoices/<id>/edit` - Update invoice
- `POST /api/send-invoice/<id>` - Send invoice via email

### Customers
- `GET /customers` - List customers
- `POST /customers/add` - Add customer
- `PUT /customers/<id>/edit` - Update customer
- `DELETE /customers/<id>` - Delete customer

## Deployment

### Vercel (Recommended)
1. Connect your repository to Vercel
2. Set environment variables
3. Deploy automatically

### Manual Deployment
1. Set production environment variables
2. Install production dependencies
3. Run with Gunicorn:
   ```bash
   gunicorn -w 4 -b 0.0.0.0:5000 app:app
   ```

## Development

### Running Tests
```bash
python -m pytest tests/
```

### Code Quality
```bash
black app.py
flake8 app.py
```

### Database Migrations
```bash
# Create migration
flask db migrate -m "Description"

# Apply migration
flask db upgrade
```

## Performance Optimization

The application includes several performance optimizations:

1. **Database Indexing**: All frequently queried fields are indexed
2. **Caching**: Hybrid memory + database caching
3. **Background Jobs**: Async processing for heavy tasks
4. **Rate Limiting**: Prevents abuse and ensures stability
5. **Query Optimization**: Efficient database queries

## Security Best Practices

1. **Input Validation**: All user inputs are validated
2. **SQL Injection Prevention**: Using ORM and parameterized queries
3. **XSS Protection**: Output escaping and CSP headers
4. **CSRF Protection**: Token-based CSRF protection
5. **Secure Headers**: Security-focused HTTP headers

## Support

For support and contributions:
- Create an issue for bug reports
- Submit pull requests for features
- Check the documentation for common issues

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Changelog

### v2.0.0 - Technical Enhancements
- Added database optimization
- Implemented caching layer
- Added background job processing
- Implemented rate limiting
- Added database backup system
- Implemented two-factor authentication
- Added role-based access control
- Implemented audit logging
- Added data encryption
- Enhanced session management

### v1.0.0 - Initial Release
- Basic invoicing functionality
- User authentication
- Customer management
- Invoice generation
- Mobile-responsive design