# Mobi Invoice Termux - Technical Enhancements Setup Guide

## 🚀 Quick Start

### Prerequisites
- Python 3.8+ 
- Termux (for Android deployment)
- Git

### Installation Steps

1. **Clone the Repository**
```bash
git clone <repository-url>
cd mobi-invoice-termux
```

2. **Install Dependencies**
```bash
# Standard installation
pip install -r requirements.txt

# For Termux (lightweight version)
pip install flask flask-sqlalchemy flask-login cryptography pyotp qrcode[pil]
```

3. **Environment Configuration**
```bash
# Create .env file
cp .env.example .env

# Edit .env with your settings
SECRET_KEY=your-super-secret-key-here
DATABASE_URL=sqlite:///mobi_invoice.db
ENCRYPTION_MASTER_SECRET=your-encryption-secret
FLASK_ENV=development  # or production
```

4. **Initialize Database**
```bash
python -c "
from main import app_instance
with app_instance.app.app_context():
    app_instance.db.create_all()
    print('Database initialized successfully!')
"
```

5. **Run the Application**
```bash
python main.py
```

The application will be available at `http://localhost:5000`

## 🔧 Configuration

### Security Configuration
```python
# config.py
import os

class Config:
    # Basic Flask Config
    SECRET_KEY = os.environ.get('SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    
    # Security Settings
    SESSION_COOKIE_SECURE = os.environ.get('FLASK_ENV') == 'production'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Rate Limiting
    RATE_LIMIT_DEFAULT = '100/hour'
    RATE_LIMIT_AUTH = '5/15minutes'
    
    # Encryption
    ENCRYPTION_MASTER_SECRET = os.environ.get('ENCRYPTION_MASTER_SECRET')
    
    # Background Jobs
    CELERY_BROKER_URL = 'redis://localhost:6379/0'  # Optional
    CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'  # Optional
    
    # Cache
    CACHE_TYPE = 'simple'  # or 'redis'
    CACHE_REDIS_URL = 'redis://localhost:6379/1'  # Optional
```

### Database Optimization
```python
# Run database optimization
python -c "
from database_optimization import initialize_database_optimization
initialize_database_optimization()
print('Database optimization completed!')
"
```

### Cache Setup
```python
# For Redis cache (recommended for production)
pip install redis

# Update config.py
CACHE_TYPE = 'redis'
CACHE_REDIS_URL = 'redis://localhost:6379/1'
```

## 📱 Termux Deployment

### Termux Setup
```bash
# Install Termux on Android
# Download from F-Droid or GitHub

# Update packages
pkg update && pkg upgrade

# Install Python
pkg install python

# Install required packages
pkg install clang make libffi openssl libjpeg-turbo

# Install Python dependencies
pip install flask flask-sqlalchemy cryptography pyotp qrcode[pil]
```

### Termux-Specific Configuration
```python
# termux_config.py
import os

# Termux-specific settings
TERMUX_MODE = True

# Lightweight configurations for mobile
CACHE_TYPE = 'simple'  # Use simple cache instead of Redis
BACKGROUND_JOB_WORKERS = 2  # Fewer workers for mobile
RATE_LIMIT_DEFAULT = '50/hour'  # More conservative rate limiting
```

### Running on Termux
```bash
# Set environment variables
export FLASK_ENV=production
export TERMUX_MODE=1

# Run the application
python main.py
```

## 🏭 Production Deployment

### Gunicorn Setup
```bash
# Install Gunicorn
pip install gunicorn gevent

# Create gunicorn.conf.py
bind = "0.0.0.0:5000"
workers = 4
worker_class = "gevent"
worker_connections = 1000
timeout = 30
keepalive = 2
max_requests = 1000
max_requests_jitter = 100
preload_app = True
```

### Systemd Service (Linux)
```ini
# /etc/systemd/system/mobi-invoice.service
[Unit]
Description=Mobi Invoice Application
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/path/to/mobi-invoice
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/gunicorn -c gunicorn.conf.py main:app
ExecReload=/bin/kill -s HUP $MAINPID
Restart=always

[Install]
WantedBy=multi-user.target
```

### Nginx Configuration
```nginx
# /etc/nginx/sites-available/mobi-invoice
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static {
        alias /path/to/mobi-invoice/static;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

## 🔍 Monitoring and Maintenance

### Health Check Endpoint
```bash
# Application health check
curl http://localhost:5000/api/health

# Expected response
{
    "status": "healthy",
    "timestamp": "2023-10-15T10:30:00.000Z",
    "database": "ok",
    "cache": "ok",
    "version": "2.0.0-enhanced"
}
```

### Log Monitoring
```python
# Enable comprehensive logging
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(name)s %(levelname)s %(message)s',
    handlers=[
        logging.FileHandler('/var/log/mobi-invoice/app.log'),
        logging.StreamHandler()
    ]
)
```

### Database Maintenance
```bash
# Run daily maintenance script
python -c "
from database_optimization import db_optimizer
db_optimizer.optimize_database()
db_optimizer.cleanup_old_data(days_to_keep=90)
print('Database maintenance completed!')
"
```

### Backup Automation
```bash
# Create backup script
#!/bin/bash
# backup.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/path/to/backups"

python -c "
from database_backup import backup_manager
backup = backup_manager.create_backup(
    backup_type='FULL',
    user_id=1,
    compression=True,
    description='Automated daily backup'
)
print(f'Backup created: {backup.filename}')
"

# Keep only last 30 days of backups
find $BACKUP_DIR -name "*.db*" -mtime +30 -delete
```

## 🔒 Security Hardening

### SSL/TLS Setup
```bash
# Generate SSL certificate (Let's Encrypt recommended)
certbot --nginx -d your-domain.com

# Or use self-signed certificate for development
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365
```

### Firewall Configuration
```bash
# UFW (Ubuntu)
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable

# iptables rules
sudo iptables -A INPUT -p tcp --dport 5000 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 443 -j ACCEPT
```

### Security Headers
```python
# Already implemented in session_management.py
# Headers automatically added:
# X-Content-Type-Options: nosniff
# X-Frame-Options: DENY
# X-XSS-Protection: 1; mode=block
# Referrer-Policy: strict-origin-when-cross-origin
```

## 📊 Performance Tuning

### Database Optimization
```sql
-- SQLite optimizations
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA cache_size = 10000;
PRAGMA temp_store = MEMORY;
```

### Application Caching
```python
# Enable aggressive caching for production
CACHE_CONFIG = {
    'default_timeout': 3600,  # 1 hour
    'key_prefix': 'mobi_invoice',
    'threshold': 500  # Only cache responses larger than 500 bytes
}
```

### Background Job Optimization
```python
# Optimize for your server resources
BACKGROUND_JOB_CONFIG = {
    'workers': min(4, os.cpu_count()),
    'queue_max_size': 1000,
    'job_timeout': 300,  # 5 minutes
}
```

## 🧪 Testing

### Run All Tests
```bash
# Run unit tests
pytest tests/

# Run with coverage
pytest --cov=. tests/

# Run integration tests
pytest tests/integration/

# Run performance tests
python -c "
from demo_enhancements import run_comprehensive_demo
run_comprehensive_demo()
"
```

### Load Testing
```bash
# Install locust
pip install locust

# Create locustfile.py (example provided in documentation)
locust -f locustfile.py --host=http://localhost:5000
```

## 🚨 Troubleshooting

### Common Issues

1. **Database Connection Errors**
```bash
# Check database file permissions
ls -la mobi_invoice.db

# Recreate database
rm mobi_invoice.db
python -c "from main import app_instance; app_instance.db.create_all()"
```

2. **Cache Issues**
```bash
# Clear cache
python -c "
from cache_layer import cache
cache.clear()
print('Cache cleared!')
"
```

3. **Background Job Issues**
```bash
# Check job status
python -c "
from background_jobs import job_manager
stats = job_manager.get_stats()
print(stats)
"
```

4. **Memory Issues (Termux)**
```python
# Reduce resource usage in termux_config.py
BACKGROUND_JOB_WORKERS = 1
CACHE_TYPE = 'simple'
RATE_LIMIT_DEFAULT = '25/hour'
```

### Log Analysis
```bash
# View application logs
tail -f /var/log/mobi-invoice/app.log

# Search for errors
grep "ERROR" /var/log/mobi-invoice/app.log

# Monitor performance
grep "slow query" /var/log/mobi-invoice/app.log
```

## 📚 API Documentation

### Authentication Endpoints
```
POST /login              # User login
POST /logout             # User logout
POST /two-factor-verify  # 2FA verification
```

### Admin Endpoints
```
GET  /admin              # Admin dashboard
POST /admin/backup       # Create backup
POST /admin/cleanup      # System cleanup
```

### API Endpoints
```
GET  /api/health         # Health check
GET  /api/stats          # System statistics
```

## 🔄 Updates and Maintenance

### Update Procedure
```bash
# 1. Backup current version
python -c "from database_backup import backup_manager; backup_manager.create_backup(user_id=1, description='Pre-update backup')"

# 2. Update code
git pull origin main

# 3. Update dependencies
pip install -r requirements.txt

# 4. Run database migrations
python -c "from database_optimization import initialize_database_optimization; initialize_database_optimization()"

# 5. Restart application
sudo systemctl restart mobi-invoice
```

### Regular Maintenance Tasks
```bash
# Daily (cron job)
0 2 * * * /path/to/backup.sh
0 3 * * * /path/to/maintenance.sh

# Weekly (cron job)
0 4 * * 0 /path/to/weekly_cleanup.sh
```

## 📞 Support

### Documentation
- [Technical Enhancements Report](TECHNICAL_ENHANCEMENTS_REPORT.md)
- [API Documentation](docs/api.md)
- [Security Guide](docs/security.md)

### Community
- GitHub Issues: Report bugs and request features
- Wiki: Community-contributed documentation
- Discussions: Ask questions and share experiences

---

**🎉 Congratulations!** Your Mobi Invoice Termux application is now enhanced with enterprise-grade security, performance, and scalability features. The system is production-ready and suitable for deployment in various environments from development to production.