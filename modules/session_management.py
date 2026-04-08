"""
Session Management Module
Provides secure session handling with database persistence
"""

import os
import secrets
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from flask import session, request, g, current_app
from app import db, User, UserSession

logger = logging.getLogger(__name__)

class SessionManager:
    """Manages user sessions with database persistence"""
    
    def __init__(self):
        self.default_ttl = 24 * 60 * 60  # 24 hours
        self.remember_me_ttl = 30 * 24 * 60 * 60  # 30 days
        self.max_sessions_per_user = 5
    
    def generate_token(self, length: int = 32) -> str:
        """Generate cryptographically secure session token"""
        return secrets.token_urlsafe(length)
    
    def generate_session_id(self) -> str:
        """Generate unique session ID"""
        timestamp = str(int(datetime.utcnow().timestamp()))
        random_part = secrets.token_urlsafe(16)
        return f"sess_{timestamp}_{random_part}"
    
    def create_session(self, user_id: int, remember_me: bool = False,
                      user_agent: str = None, ip_address: str = None,
                      additional_data: Dict = None) -> UserSession:
        """
        Create a new user session
        
        Args:
            user_id: User ID
            remember_me: Whether to extend session duration
            user_agent: User agent string
            ip_address: Client IP address
            additional_data: Additional session data
        
        Returns:
            UserSession object
        """
        try:
            # Clean up old sessions for this user
            self._cleanup_user_sessions(user_id)
            
            # Generate session tokens
            session_token = self.generate_token()
            refresh_token = self.generate_token(48)
            session_id = self.generate_session_id()
            
            # Set expiration
            ttl = self.remember_me_ttl if remember_me else self.default_ttl
            expires_at = datetime.utcnow() + timedelta(seconds=ttl)
            
            # Get request context
            if not user_agent:
                user_agent = request.headers.get('User-Agent', '') if request else ''
            if not ip_address:
                ip_address = self._get_client_ip()
            
            # Create session record
            user_session = UserSession(
                user_id=user_id,
                token=self._hash_token(session_token),
                refresh_token=self._hash_token(refresh_token),
                user_agent=user_agent,
                ip_address=ip_address,
                expires_at=expires_at,
                is_active=True
            )
            
            db.session.add(user_session)
            db.session.commit()
            
            # Store in Flask session
            session.clear()
            session['session_id'] = session_id
            session['user_id'] = user_id
            session['session_token'] = session_token
            session['refresh_token'] = refresh_token
            session['expires_at'] = expires_at.isoformat()
            session['remember_me'] = remember_me
            
            if additional_data:
                session.update(additional_data)
            
            logger.info(f"Created session for user {user_id}")
            return user_session
            
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            db.session.rollback()
            raise
    
    def validate_session(self, session_token: str = None) -> Optional[UserSession]:
        """
        Validate session token
        
        Args:
            session_token: Session token to validate
        
        Returns:
            UserSession object if valid, None otherwise
        """
        try:
            if not session_token:
                session_token = session.get('session_token')
            
            if not session_token:
                return None
            
            # Hash the token for comparison
            hashed_token = self._hash_token(session_token)
            
            # Find session in database
            user_session = UserSession.query.filter_by(
                token=hashed_token,
                is_active=True
            ).first()
            
            if not user_session:
                return None
            
            # Check if expired
            if user_session.expires_at < datetime.utcnow():
                self._deactivate_session(user_session.id)
                return None
            
            # Update last accessed time
            user_session.last_accessed = datetime.utcnow()
            db.session.commit()
            
            # Update Flask session
            session['last_accessed'] = datetime.utcnow().isoformat()
            
            return user_session
            
        except Exception as e:
            logger.error(f"Session validation error: {e}")
            return None
    
    def refresh_session(self, refresh_token: str) -> Optional[Dict[str, Any]]:
        """
        Refresh session using refresh token
        
        Args:
            refresh_token: Refresh token
        
        Returns:
            New session data if successful
        """
        try:
            if not refresh_token:
                return None
            
            # Hash the refresh token
            hashed_refresh_token = self._hash_token(refresh_token)
            
            # Find session by refresh token
            user_session = UserSession.query.filter_by(
                refresh_token=hashed_refresh_token,
                is_active=True
            ).first()
            
            if not user_session:
                return None
            
            # Check if expired
            if user_session.expires_at < datetime.utcnow():
                self._deactivate_session(user_session.id)
                return None
            
            # Generate new tokens
            new_session_token = self.generate_token()
            new_refresh_token = self.generate_token(48)
            
            # Update session
            user_session.token = self._hash_token(new_session_token)
            user_session.refresh_token = self._hash_token(new_refresh_token)
            user_session.last_accessed = datetime.utcnow()
            
            # Extend expiration if remember me was set
            if session.get('remember_me'):
                user_session.expires_at = datetime.utcnow() + timedelta(seconds=self.remember_me_ttl)
            else:
                user_session.expires_at = datetime.utcnow() + timedelta(seconds=self.default_ttl)
            
            db.session.commit()
            
            # Update Flask session
            session['session_token'] = new_session_token
            session['refresh_token'] = new_refresh_token
            session['expires_at'] = user_session.expires_at.isoformat()
            
            return {
                'session_token': new_session_token,
                'refresh_token': new_refresh_token,
                'expires_at': user_session.expires_at.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Session refresh error: {e}")
            return None
    
    def destroy_session(self, session_token: str = None) -> bool:
        """
        Destroy a session
        
        Args:
            session_token: Session token to destroy
        
        Returns:
            True if session was destroyed
        """
        try:
            if not session_token:
                session_id = session.get('session_id')
                if session_id:
                    user_session = UserSession.query.filter_by(session_id=session_id).first()
                    if user_session:
                        session_token = session.get('session_token')
            
            if session_token:
                hashed_token = self._hash_token(session_token)
                user_session = UserSession.query.filter_by(token=hashed_token).first()
                
                if user_session:
                    self._deactivate_session(user_session.id)
            
            # Clear Flask session
            session.clear()
            
            logger.info("Session destroyed")
            return True
            
        except Exception as e:
            logger.error(f"Failed to destroy session: {e}")
            return False
    
    def destroy_user_sessions(self, user_id: int, exclude_current: bool = True) -> int:
        """
        Destroy all sessions for a user
        
        Args:
            user_id: User ID
            exclude_current: Whether to exclude current session
        
        Returns:
            Number of sessions destroyed
        """
        try:
            query = UserSession.query.filter_by(user_id=user_id, is_active=True)
            
            if exclude_current and 'session_token' in session:
                current_token = self._hash_token(session['session_token'])
                query = query.filter(UserSession.token != current_token)
            
            sessions = query.all()
            count = 0
            
            for user_session in sessions:
                self._deactivate_session(user_session.id)
                count += 1
            
            logger.info(f"Destroyed {count} sessions for user {user_id}")
            return count
            
        except Exception as e:
            logger.error(f"Failed to destroy user sessions: {e}")
            return 0
    
    def get_user_sessions(self, user_id: int) -> List[UserSession]:
        """Get all active sessions for a user"""
        try:
            return UserSession.query.filter_by(
                user_id=user_id,
                is_active=True
            ).order_by(UserSession.last_accessed.desc()).all()
        except Exception as e:
            logger.error(f"Failed to get user sessions: {e}")
            return []
    
    def get_session_info(self, session_token: str = None) -> Optional[Dict[str, Any]]:
        """Get detailed session information"""
        try:
            user_session = self.validate_session(session_token)
            if not user_session:
                return None
            
            return {
                'session_id': user_session.session_id,
                'user_id': user_session.user_id,
                'ip_address': user_session.ip_address,
                'user_agent': user_session.user_agent,
                'created_at': user_session.created_at.isoformat(),
                'last_accessed': user_session.last_accessed.isoformat(),
                'expires_at': user_session.expires_at.isoformat(),
                'is_current': session.get('session_token') and \
                           self._hash_token(session['session_token']) == user_session.token
            }
        except Exception as e:
            logger.error(f"Failed to get session info: {e}")
            return None
    
    def _hash_token(self, token: str) -> str:
        """Hash token for secure storage"""
        return hashlib.sha256(token.encode()).hexdigest()
    
    def _get_client_ip(self) -> str:
        """Get client IP address"""
        if not request:
            return ''
        
        forwarded = request.headers.get('X-Forwarded-For')
        if forwarded:
            return forwarded.split(',')[0].strip()
        
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            return real_ip
        
        return request.remote_addr or ''
    
    def _deactivate_session(self, session_id: int):
        """Deactivate a session"""
        user_session = UserSession.query.get(session_id)
        if user_session:
            user_session.is_active = False
            db.session.commit()
    
    def _cleanup_user_sessions(self, user_id: int):
        """Clean up old sessions for user (enforce max sessions)"""
        try:
            sessions = UserSession.query.filter_by(
                user_id=user_id,
                is_active=True
            ).order_by(UserSession.last_accessed.desc()).all()
            
            if len(sessions) >= self.max_sessions_per_user:
                # Deactivate oldest sessions beyond limit
                for old_session in sessions[self.max_sessions_per_user:]:
                    self._deactivate_session(old_session.id)
                    
        except Exception as e:
            logger.error(f"Failed to cleanup user sessions: {e}")
    
    def cleanup_expired_sessions(self) -> int:
        """Clean up all expired sessions"""
        try:
            expired_sessions = UserSession.query.filter(
                UserSession.expires_at < datetime.utcnow()
            ).all()
            
            count = 0
            for session in expired_sessions:
                self._deactivate_session(session.id)
                count += 1
            
            logger.info(f"Cleaned up {count} expired sessions")
            return count
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired sessions: {e}")
            return 0
    
    def get_session_statistics(self) -> Dict[str, Any]:
        """Get session statistics"""
        try:
            total_sessions = UserSession.query.count()
            active_sessions = UserSession.query.filter_by(is_active=True).count()
            expired_sessions = total_sessions - active_sessions
            
            # Sessions by user
            user_stats = db.session.query(
                UserSession.user_id,
                db.func.count(UserSession.id)
            ).filter_by(is_active=True).group_by(UserSession.user_id).all()
            
            top_users = []
            for user_id, count in user_stats:
                user = User.query.get(user_id)
                top_users.append({
                    'user_id': user_id,
                    'user_email': user.email if user else 'Unknown',
                    'session_count': count
                })
            
            top_users.sort(key=lambda x: x['session_count'], reverse=True)
            
            return {
                'total_sessions': total_sessions,
                'active_sessions': active_sessions,
                'expired_sessions': expired_sessions,
                'top_active_users': top_users[:10],
                'max_sessions_per_user': self.max_sessions_per_user,
                'default_ttl_hours': self.default_ttl / 3600,
                'remember_me_ttl_days': self.remember_me_ttl / (24 * 3600)
            }
            
        except Exception as e:
            logger.error(f"Failed to get session statistics: {e}")
            return {'error': str(e)}

class SessionMiddleware:
    """Middleware for session management"""
    
    def __init__(self, app=None):
        self.app = app
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize middleware with Flask app"""
        app.before_request(self._before_request)
        app.after_request(self._after_request)
    
    def _before_request(self):
        """Before request handler"""
        # Skip session validation for static files and health checks
        if request.path.startswith('/static/') or request.path == '/health':
            return
        
        # Validate session if session token exists
        if 'session_token' in session:
            user_session = session_manager.validate_session()
            if user_session:
                # Set user in context
                user = User.query.get(user_session.user_id)
                if user and user.is_active:
                    g.user = user
                    g.session = user_session
                else:
                    # Invalid user, destroy session
                    session_manager.destroy_session()
            else:
                # Invalid session, clear it
                session.clear()
    
    def _after_request(self, response):
        """After request handler"""
        # Add security headers
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        
        return response

# Session decorators
def require_session(f):
    """Decorator to require valid session"""
    from functools import wraps
    from flask import redirect, url_for
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hasattr(g, 'user') or not g.user:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def require_active_session(f):
    """Decorator to require active non-expired session"""
    from functools import wraps
    from flask import redirect, url_for
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hasattr(g, 'session') or not g.session:
            return redirect(url_for('login'))
        
        if g.session.expires_at < datetime.utcnow():
            session_manager.destroy_session()
            return redirect(url_for('login'))
        
        return f(*args, **kwargs)
    return decorated_function

# Session utilities
class SessionUtils:
    """Utility functions for session management"""
    
    @staticmethod
    def is_session_valid() -> bool:
        """Check if current session is valid"""
        return hasattr(g, 'session') and g.session and g.session.expires_at > datetime.utcnow()
    
    @staticmethod
    def get_session_age() -> Optional[timedelta]:
        """Get session age"""
        if not hasattr(g, 'session'):
            return None
        
        return datetime.utcnow() - g.session.created_at
    
    @staticmethod
    def get_session_ttl() -> Optional[timedelta]:
        """Get session time to live"""
        if not hasattr(g, 'session'):
            return None
        
        return g.session.expires_at - datetime.utcnow()
    
    @staticmethod
    def extend_session(remember_me: bool = False) -> bool:
        """Extend current session"""
        try:
            if not hasattr(g, 'session'):
                return False
            
            ttl = session_manager.remember_me_ttl if remember_me else session_manager.default_ttl
            g.session.expires_at = datetime.utcnow() + timedelta(seconds=ttl)
            
            db.session.commit()
            session['expires_at'] = g.session.expires_at.isoformat()
            
            return True
        except Exception as e:
            logger.error(f"Failed to extend session: {e}")
            return False
    
    @staticmethod
    def get_concurrent_sessions(user_id: int) -> int:
        """Get number of concurrent sessions for user"""
        return len(session_manager.get_user_sessions(user_id))
    
    @staticmethod
    def detect_suspicious_activity(user_id: int) -> List[str]:
        """Detect suspicious session activity"""
        warnings = []
        sessions = session_manager.get_user_sessions(user_id)
        
        # Check for multiple locations
        ip_addresses = set(s.ip_address for s in sessions if s.ip_address)
        if len(ip_addresses) > 2:
            warnings.append(f"Multiple IP addresses detected: {len(ip_addresses)}")
        
        # Check for multiple user agents
        user_agents = set(s.user_agent[:50] for s in sessions if s.user_agent)
        if len(user_agents) > 3:
            warnings.append(f"Multiple user agents detected: {len(user_agents)}")
        
        # Check for old sessions
        old_sessions = [s for s in sessions if s.created_at < datetime.utcnow() - timedelta(days=7)]
        if len(old_sessions) > 0:
            warnings.append(f"Long-lived sessions detected: {len(old_sessions)}")
        
        return warnings

# Global session manager instance
session_manager = SessionManager()

# Initialize session system
def initialize_session_system(app):
    """Initialize session system"""
    logger.info("Initializing session system...")
    
    # Configure Flask session
    app.config['SESSION_COOKIE_SECURE'] = app.config.get('ENV') == 'production'
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
    
    # Initialize middleware
    SessionMiddleware(app)
    
    # Schedule cleanup of expired sessions
    import threading
    import time
    
    def cleanup_task():
        while True:
            try:
                session_manager.cleanup_expired_sessions()
            except Exception as e:
                logger.error(f"Session cleanup error: {e}")
            time.sleep(60 * 60)  # Run every hour
    
    cleanup_thread = threading.Thread(target=cleanup_task, daemon=True)
    cleanup_thread.start()
    
    logger.info("Session system initialized")

if __name__ == "__main__":
    # Test session functionality
    from flask import Flask
    
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'test-secret-key'
    
    with app.test_request_context():
        # Test session creation
        print("Testing session system...")
        
        try:
            # Create a test session
            test_user_id = 1
            session_data = session_manager.create_session(
                user_id=test_user_id,
                remember_me=True,
                user_agent='Test Agent',
                ip_address='127.0.0.1'
            )
            
            print(f"Created session: {session_data.session_id}")
            
            # Validate session
            validated_session = session_manager.validate_session()
            print(f"Session valid: {validated_session is not None}")
            
            # Get session info
            session_info = session_manager.get_session_info()
            print(f"Session info: {session_info}")
            
            # Test session refresh
            refresh_data = session_manager.refresh_session(session['refresh_token'])
            print(f"Session refreshed: {refresh_data is not None}")
            
            # Get user sessions
            user_sessions = session_manager.get_user_sessions(test_user_id)
            print(f"User sessions: {len(user_sessions)}")
            
            # Test session statistics
            stats = session_manager.get_session_statistics()
            print(f"Session statistics: {stats}")
            
            # Test session destruction
            destroyed = session_manager.destroy_session()
            print(f"Session destroyed: {destroyed}")
            
            print("All session tests passed!")
            
        except Exception as e:
            print(f"Session test failed: {e}")
            import traceback
            traceback.print_exc()