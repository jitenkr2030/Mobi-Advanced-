#!/usr/bin/env python3
"""
Mobi Invoice Termux - Startup Script
Easy startup script for the Mobi Invoice application
"""

import os
import sys
from app import app, db

def check_dependencies():
    """Check if required dependencies are installed"""
    required_modules = [
        'flask', 'flask_sqlalchemy', 'flask_login', 
        'werkzeug', 'cryptography', 'pyotp', 'qrcode', 
        'bcrypt', 'passlib', 'pandas', 'reportlab', 'pillow'
    ]
    
    missing_modules = []
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing_modules.append(module)
    
    if missing_modules:
        print("❌ Missing dependencies:")
        for module in missing_modules:
            print(f"   - {module}")
        print("\n📦 Install with: pip install -r requirements.txt")
        return False
    
    print("✅ All dependencies are installed")
    return True

def setup_database():
    """Initialize the database if it doesn't exist"""
    try:
        with app.app_context():
            # Check if tables exist
            from app import User
            user_count = User.query.count()
            
            if user_count == 0:
                print("📊 Creating database tables...")
                db.create_all()
                
                # Create a default admin user
                from werkzeug.security import generate_password_hash
                admin_user = User(
                    email='admin@mobiinvoice.com',
                    name='Admin User',
                    password_hash=generate_password_hash('admin123'),
                    company_name='Mobi Invoice Demo',
                    is_active=True,
                    role='ADMIN'
                )
                db.session.add(admin_user)
                db.session.commit()
                
                print("✅ Database initialized with admin user:")
                print("   Email: admin@mobiinvoice.com")
                print("   Password: admin123")
                print("   ⚠️  Please change the password after first login!")
            else:
                print("✅ Database already exists")
                
        return True
    except Exception as e:
        print(f"❌ Database setup failed: {e}")
        return False

def main():
    """Main startup function"""
    print("🚀 Starting Mobi Invoice Termux...")
    print("=" * 50)
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Setup database
    if not setup_database():
        sys.exit(1)
    
    print("=" * 50)
    print("🌟 Mobi Invoice Termux is ready!")
    print("📱 Access the application at: http://localhost:5000")
    print("🔧 Default login: admin@mobiinvoice.com / admin123")
    print("⚠️  Change the default password after first login!")
    print("=" * 50)
    print("🛑 Press Ctrl+C to stop the server")
    print()
    
    # Start the Flask application
    try:
        app.run(debug=True, host='0.0.0.0', port=5000)
    except KeyboardInterrupt:
        print("\n👋 Shutting down Mobi Invoice Termux...")

if __name__ == '__main__':
    main()