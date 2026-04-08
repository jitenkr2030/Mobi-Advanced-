"""
Two-Factor Authentication Module
Provides TOTP-based 2FA for enhanced security
"""

import pyotp
import qrcode
import io
import base64
import secrets
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from flask import current_app
from app import db, User

logger = logging.getLogger(__name__)

class TwoFactorAuth:
    """Manages two-factor authentication functionality"""
    
    def __init__(self, app_name: str = "Mobi Invoice"):
        self.app_name = app_name
    
    def generate_secret(self) -> str:
        """Generate a new TOTP secret"""
        return pyotp.random_base32()
    
    def generate_qr_code(self, user_email: str, secret: str) -> str:
        """
        Generate QR code for TOTP setup
        
        Args:
            user_email: User's email address
            secret: TOTP secret
        
        Returns:
            Base64 encoded QR code image
        """
        totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(
            name=user_email,
            issuer_name=self.app_name
        )
        
        # Generate QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(totp_uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        return base64.b64encode(buffer.getvalue()).decode()
    
    def verify_token(self, secret: str, token: str, window: int = 1) -> bool:
        """
        Verify TOTP token
        
        Args:
            secret: TOTP secret
            token: User-provided token
            window: Time window for token validation (default: 1)
        
        Returns:
            True if token is valid
        """
        try:
            totp = pyotp.TOTP(secret)
            return totp.verify(token, valid_window=window)
        except Exception as e:
            logger.error(f"Token verification error: {e}")
            return False
    
    def get_current_token(self, secret: str) -> str:
        """Get current TOTP token (for testing purposes)"""
        try:
            totp = pyotp.TOTP(secret)
            return totp.now()
        except Exception as e:
            logger.error(f"Error generating current token: {e}")
            return ""
    
    def get_time_remaining(self) -> int:
        """Get seconds remaining until next token"""
        return pyotp.TOTP('').interval - (datetime.now().timestamp() % pyotp.TOTP('').interval)
    
    def generate_backup_codes(self, count: int = 10) -> List[str]:
        """Generate backup codes"""
        codes = []
        for _ in range(count):
            code = secrets.token_hex(4).upper()
            codes.append(code)
        return codes

class TwoFactorManager:
    """Manages 2FA setup and verification for users"""
    
    def __init__(self):
        self.tfa = TwoFactorAuth()
    
    def setup_2fa(self, user_id: int) -> Dict[str, Any]:
        """
        Set up 2FA for user
        
        Args:
            user_id: User ID
        
        Returns:
            Setup information including secret and QR code
        """
        user = User.query.get(user_id)
        if not user:
            raise ValueError("User not found")
        
        # Generate secret
        secret = self.tfa.generate_secret()
        backup_codes = self.tfa.generate_backup_codes()
        
        # Generate QR code
        qr_code = self.tfa.generate_qr_code(user.email, secret)
        
        # Store secret temporarily (not enabled yet)
        user.two_factor_secret = secret
        db.session.commit()
        
        return {
            'secret': secret,
            'qr_code': qr_code,
            'backup_codes': backup_codes,
            'manual_entry_key': secret,
            'instructions': {
                'step1': 'Scan the QR code with your authenticator app',
                'step2': 'Enter the verification code to enable 2FA',
                'step3': 'Save your backup codes in a safe place'
            }
        }
    
    def enable_2fa(self, user_id: int, verification_code: str) -> bool:
        """
        Enable 2FA for user after verification
        
        Args:
            user_id: User ID
            verification_code: Code from authenticator app
        
        Returns:
            True if 2FA enabled successfully
        """
        user = User.query.get(user_id)
        if not user or not user.two_factor_secret:
            return False
        
        # Verify the code
        if not self.tfa.verify_token(user.two_factor_secret, verification_code):
            return False
        
        # Enable 2FA
        user.two_factor_enabled = True
        db.session.commit()
        
        logger.info(f"2FA enabled for user {user_id}")
        return True
    
    def disable_2fa(self, user_id: int, verification_code: str) -> bool:
        """
        Disable 2FA for user
        
        Args:
            user_id: User ID
            verification_code: Current 2FA code
        
        Returns:
            True if 2FA disabled successfully
        """
        user = User.query.get(user_id)
        if not user or not user.two_factor_enabled:
            return False
        
        # Verify the code
        if not self.tfa.verify_token(user.two_factor_secret, verification_code):
            return False
        
        # Disable 2FA
        user.two_factor_enabled = False
        user.two_factor_secret = None
        db.session.commit()
        
        logger.info(f"2FA disabled for user {user_id}")
        return True
    
    def verify_2fa(self, user_id: int, code: str) -> bool:
        """
        Verify 2FA code for login
        
        Args:
            user_id: User ID
            code: 2FA code or backup code
        
        Returns:
            True if code is valid
        """
        user = User.query.get(user_id)
        if not user or not user.two_factor_enabled or not user.two_factor_secret:
            return False
        
        # Try TOTP verification first
        if self.tfa.verify_token(user.two_factor_secret, code):
            return True
        
        # Try backup code verification
        return self.verify_backup_code(user_id, code)
    
    def verify_backup_code(self, user_id: int, code: str) -> bool:
        """
        Verify backup code (simplified implementation)
        
        Args:
            user_id: User ID
            code: Backup code
        
        Returns:
            True if backup code is valid
        """
        # In a real implementation, you'd store and track backup codes
        # For this demo, we'll use a simple validation
        user = User.query.get(user_id)
        if not user:
            return False
        
        # Simple backup code validation (8-character hex string)
        if len(code) == 8 and all(c in '0123456789ABCDEF' for c in code.upper()):
            logger.info(f"Backup code used for user {user_id}")
            return True
        
        return False
    
    def regenerate_backup_codes(self, user_id: int, verification_code: str) -> List[str]:
        """
        Regenerate backup codes
        
        Args:
            user_id: User ID
            verification_code: Current 2FA code
        
        Returns:
            New backup codes
        """
        user = User.query.get(user_id)
        if not user or not user.two_factor_enabled:
            raise ValueError("2FA not enabled for user")
        
        # Verify current code
        if not self.tfa.verify_token(user.two_factor_secret, verification_code):
            raise ValueError("Invalid verification code")
        
        # Generate new backup codes
        new_codes = self.tfa.generate_backup_codes()
        
        # In a real implementation, you'd store these in the database
        logger.info(f"Backup codes regenerated for user {user_id}")
        
        return new_codes
    
    def get_2fa_status(self, user_id: int) -> Dict[str, Any]:
        """
        Get 2FA status for user
        
        Args:
            user_id: User ID
        
        Returns:
            2FA status information
        """
        user = User.query.get(user_id)
        if not user:
            return {'error': 'User not found'}
        
        return {
            'enabled': user.two_factor_enabled,
            'has_secret': bool(user.two_factor_secret),
            'setup_completed': user.two_factor_enabled and bool(user.two_factor_secret)
        }
    
    def force_2fa_reset(self, user_id: int, admin_user_id: int) -> bool:
        """
        Force reset 2FA for user (admin function)
        
        Args:
            user_id: User ID to reset
            admin_user_id: Admin user ID performing the reset
        
        Returns:
            True if reset successful
        """
        user = User.query.get(user_id)
        admin_user = User.query.get(admin_user_id)
        
        if not user or not admin_user:
            return False
        
        # Check if admin has permission (simplified)
        if admin_user.role not in ['ADMIN', 'MANAGER']:
            return False
        
        # Reset 2FA
        user.two_factor_enabled = False
        user.two_factor_secret = None
        db.session.commit()
        
        logger.info(f"2FA force reset for user {user_id} by admin {admin_user_id}")
        return True

class TwoFactorMiddleware:
    """Middleware for handling 2FA in web requests"""
    
    def __init__(self, app=None):
        self.app = app
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize middleware with Flask app"""
        app.before_request(self._before_request)
    
    def _before_request(self):
        """Before request handler for 2FA checks"""
        # Skip 2FA check for certain endpoints
        skip_paths = ['/static/', '/login', '/logout', '/2fa/verify', '/health']
        if any(request.path.startswith(path) for path in skip_paths):
            return
        
        # Skip if user not logged in
        if not hasattr(g, 'user') or not g.user:
            return
        
        # Skip if user doesn't have 2FA enabled
        if not g.user.two_factor_enabled:
            return
        
        # Check if 2FA verification is completed in session
        if session.get('2fa_verified'):
            return
        
        # Redirect to 2FA verification
        return redirect(url_for('two_factor_verify'))

# 2FA decorators
def require_2fa(f):
    """Decorator to require 2FA verification"""
    from functools import wraps
    from flask import session, redirect, url_for
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hasattr(g, 'user') or not g.user:
            return redirect(url_for('login'))
        
        if g.user.two_factor_enabled and not session.get('2fa_verified'):
            return redirect(url_for('two_factor_verify'))
        
        return f(*args, **kwargs)
    
    return decorated_function

def two_factor_required(f):
    """Decorator that specifically requires 2FA to be enabled"""
    from functools import wraps
    from flask import abort
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hasattr(g, 'user') or not g.user:
            abort(401)
        
        if not g.user.two_factor_enabled:
            abort(403, "Two-factor authentication is required")
        
        if not session.get('2fa_verified'):
            abort(401, "Two-factor authentication verification required")
        
        return f(*args, **kwargs)
    
    return decorated_function

# 2FA utilities
class TwoFactorUtils:
    """Utility functions for 2FA management"""
    
    @staticmethod
    def generate_recovery_codes(user_id: int, count: int = 5) -> List[str]:
        """Generate recovery codes for account recovery"""
        codes = []
        for _ in range(count):
            code = secrets.token_hex(8).upper()
            codes.append(code)
        
        logger.info(f"Recovery codes generated for user {user_id}")
        return codes
    
    @staticmethod
    def validate_2fa_setup(secret: str, verification_code: str) -> bool:
        """Validate 2FA setup before enabling"""
        tfa = TwoFactorAuth()
        return tfa.verify_token(secret, verification_code)
    
    @staticmethod
    def get_2fa_statistics() -> Dict[str, Any]:
        """Get 2FA usage statistics"""
        try:
            total_users = User.query.count()
            users_with_2fa = User.query.filter_by(two_factor_enabled=True).count()
            users_with_secret = User.query.filter(User.two_factor_secret.isnot(None)).count()
            
            return {
                'total_users': total_users,
                'users_with_2fa_enabled': users_with_2fa,
                'users_with_2fa_setup': users_with_secret,
                'adoption_rate': round((users_with_2fa / total_users * 100), 2) if total_users > 0 else 0,
                'setup_completion_rate': round((users_with_2fa / users_with_secret * 100), 2) if users_with_secret > 0 else 0
            }
        except Exception as e:
            logger.error(f"Error getting 2FA statistics: {e}")
            return {'error': str(e)}

# Global 2FA manager instance
two_factor_manager = TwoFactorManager()

# Initialize 2FA system
def initialize_two_factor_auth(app):
    """Initialize 2FA system"""
    logger.info("Initializing 2FA system...")
    
    # Initialize middleware
    TwoFactorMiddleware(app)
    
    logger.info("2FA system initialized")

if __name__ == "__main__":
    # Test 2FA functionality
    from flask import Flask
    
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'test-secret-key'
    
    with app.app_context():
        # Test 2FA setup
        print("Testing 2FA setup...")
        
        # Create a test user (would normally exist in database)
        test_user_id = 1
        
        try:
            # Setup 2FA
            setup_info = two_factor_manager.setup_2fa(test_user_id)
            print(f"2FA setup info generated for user {test_user_id}")
            print(f"Secret: {setup_info['secret']}")
            print(f"Backup codes: {setup_info['backup_codes']}")
            
            # Test token verification
            current_token = two_factor_manager.tfa.get_current_token(setup_info['secret'])
            print(f"Current token: {current_token}")
            
            # Test verification
            is_valid = two_factor_manager.tfa.verify_token(setup_info['secret'], current_token)
            print(f"Token verification: {is_valid}")
            
            # Test enabling 2FA
            enabled = two_factor_manager.enable_2fa(test_user_id, current_token)
            print(f"2FA enabled: {enabled}")
            
            # Test status
            status = two_factor_manager.get_2fa_status(test_user_id)
            print(f"2FA status: {status}")
            
            # Test statistics
            stats = TwoFactorUtils.get_2fa_statistics()
            print(f"2FA statistics: {stats}")
            
        except Exception as e:
            print(f"2FA test failed: {e}")
            import traceback
            traceback.print_exc()