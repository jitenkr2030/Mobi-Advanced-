"""
API Rate Limiting Module
Provides comprehensive rate limiting to prevent abuse and ensure fair usage
"""

import time
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable, Union
from functools import wraps
from flask import Flask, request, jsonify, g, current_app
from app import db, RateLimit

logger = logging.getLogger(__name__)

class RateLimitExceeded(Exception):
    """Exception raised when rate limit is exceeded"""
    def __init__(self, message: str, retry_after: int = 60):
        self.message = message
        self.retry_after = retry_after
        super().__init__(message)

class RateLimiter:
    """Rate limiting implementation with various strategies"""
    
    def __init__(self):
        self.memory_store: Dict[str, Dict[str, Any]] = {}
    
    def _get_key(self, identifier: str, endpoint: str) -> str:
        """Generate rate limit key"""
        key_data = f"{identifier}:{endpoint}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _cleanup_expired(self):
        """Clean up expired rate limit entries"""
        current_time = time.time()
        expired_keys = []
        
        for key, data in self.memory_store.items():
            if data.get('reset_at', 0) <= current_time:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.memory_store[key]
    
    def is_allowed(self, identifier: str, endpoint: str, limit: int, window: int) -> Dict[str, Any]:
        """
        Check if request is allowed based on rate limit
        
        Args:
            identifier: Unique identifier (IP address, user ID, etc.)
            endpoint: API endpoint or route
            limit: Number of requests allowed
            window: Time window in seconds
        
        Returns:
            Dictionary with allowance info
        """
        current_time = time.time()
        key = self._get_key(identifier, endpoint)
        
        # Clean up expired entries
        self._cleanup_expired()
        
        # Get or create rate limit data
        if key not in self.memory_store:
            self.memory_store[key] = {
                'count': 0,
                'reset_at': current_time + window,
                'window': window
            }
        
        data = self.memory_store[key]
        
        # Reset if window has expired
        if current_time >= data['reset_at']:
            data['count'] = 0
            data['reset_at'] = current_time + window
        
        # Check if limit exceeded
        if data['count'] >= limit:
            retry_after = int(data['reset_at'] - current_time)
            return {
                'allowed': False,
                'limit': limit,
                'remaining': 0,
                'reset_time': data['reset_at'],
                'retry_after': retry_after
            }
        
        # Increment counter
        data['count'] += 1
        
        return {
            'allowed': True,
            'limit': limit,
            'remaining': limit - data['count'],
            'reset_time': data['reset_at'],
            'retry_after': 0
        }

class DatabaseRateLimiter:
    """Database-backed rate limiter for persistence"""
    
    def is_allowed(self, identifier: str, endpoint: str, limit: int, window: int) -> Dict[str, Any]:
        """Check rate limit using database storage"""
        current_time = datetime.utcnow()
        reset_at = current_time + timedelta(seconds=window)
        
        try:
            # Find existing rate limit record
            rate_limit = RateLimit.query.filter_by(
                identifier=identifier,
                endpoint=endpoint
            ).first()
            
            if not rate_limit:
                # Create new rate limit record
                rate_limit = RateLimit(
                    identifier=identifier,
                    endpoint=endpoint,
                    limit=limit,
                    window_ms=window * 1000,
                    requests=1,
                    reset_at=reset_at
                )
                db.session.add(rate_limit)
                db.session.commit()
                
                return {
                    'allowed': True,
                    'limit': limit,
                    'remaining': limit - 1,
                    'reset_time': reset_at.timestamp(),
                    'retry_after': 0
                }
            
            # Check if window has expired
            if current_time >= rate_limit.reset_at:
                # Reset counter
                rate_limit.requests = 1
                rate_limit.reset_at = reset_at
                rate_limit.updated_at = current_time
                db.session.commit()
                
                return {
                    'allowed': True,
                    'limit': limit,
                    'remaining': limit - 1,
                    'reset_time': reset_at.timestamp(),
                    'retry_after': 0
                }
            
            # Check if limit exceeded
            if rate_limit.requests >= limit:
                retry_after = int((rate_limit.reset_at - current_time).total_seconds())
                return {
                    'allowed': False,
                    'limit': limit,
                    'remaining': 0,
                    'reset_time': rate_limit.reset_at.timestamp(),
                    'retry_after': retry_after
                }
            
            # Increment counter
            rate_limit.requests += 1
            rate_limit.updated_at = current_time
            db.session.commit()
            
            return {
                'allowed': True,
                'limit': limit,
                'remaining': limit - rate_limit.requests,
                'reset_time': rate_limit.reset_at.timestamp(),
                'retry_after': 0
            }
            
        except Exception as e:
            logger.error(f"Database rate limit check error: {e}")
            db.session.rollback()
            # Allow request if rate limiting fails
            return {
                'allowed': True,
                'limit': limit,
                'remaining': limit,
                'reset_time': reset_at.timestamp(),
                'retry_after': 0
            }
    
    def cleanup_expired(self) -> int:
        """Clean up expired rate limit records"""
        try:
            deleted_count = RateLimit.query.filter(
                RateLimit.reset_at < datetime.utcnow()
            ).delete()
            db.session.commit()
            return deleted_count
        except Exception as e:
            logger.error(f"Rate limit cleanup error: {e}")
            db.session.rollback()
            return 0

class HybridRateLimiter:
    """Hybrid rate limiter using memory first, database as fallback"""
    
    def __init__(self):
        self.memory_limiter = RateLimiter()
        self.db_limiter = DatabaseRateLimiter()
    
    def is_allowed(self, identifier: str, endpoint: str, limit: int, window: int) -> Dict[str, Any]:
        """Check rate limit using memory first, database as backup"""
        # Try memory limiter first
        result = self.memory_limiter.is_allowed(identifier, endpoint, limit, window)
        
        # If memory limiter allows, also update database for persistence
        if result['allowed']:
            try:
                self.db_limiter.is_allowed(identifier, endpoint, limit, window)
            except Exception as e:
                logger.error(f"Database rate limit update error: {e}")
        
        return result

# Rate limiting configurations
RATE_LIMIT_CONFIGS = {
    'default': {
        'limit': 100,
        'window': 900,  # 15 minutes
        'message': 'Rate limit exceeded. Please try again later.'
    },
    'auth': {
        'limit': 5,
        'window': 900,  # 15 minutes
        'message': 'Too many authentication attempts. Please try again later.'
    },
    'strict': {
        'limit': 10,
        'window': 3600,  # 1 hour
        'message': 'Rate limit exceeded. Please try again later.'
    },
    'upload': {
        'limit': 20,
        'window': 3600,  # 1 hour
        'message': 'Upload limit exceeded. Please try again later.'
    }
}

# Global rate limiter instance
rate_limiter = HybridRateLimiter()

def get_client_identifier() -> str:
    """Get client identifier for rate limiting"""
    # Try to get user ID from session/JWT
    if hasattr(g, 'user') and g.user and hasattr(g.user, 'id'):
        return f"user:{g.user.id}"
    
    # Fall back to IP address
    forwarded = request.headers.get('X-Forwarded-For')
    real_ip = request.headers.get('X-Real-IP')
    ip = forwarded.split(',')[0].strip() if forwarded else (real_ip or request.remote_addr)
    return f"ip:{ip}"

def get_endpoint_identifier() -> str:
    """Get endpoint identifier for rate limiting"""
    # Use request endpoint
    endpoint = request.endpoint or request.path
    
    # Add method for more specific limiting
    return f"{request.method}:{endpoint}"

def rate_limit(limit: int = None, window: int = None, config: str = 'default'):
    """
    Decorator for rate limiting Flask routes
    
    Args:
        limit: Custom limit (overrides config)
        window: Custom window in seconds (overrides config)
        config: Configuration name to use
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get configuration
            rate_config = RATE_LIMIT_CONFIGS.get(config, RATE_LIMIT_CONFIGS['default'])
            
            # Use custom values if provided
            request_limit = limit or rate_config['limit']
            request_window = window or rate_config['window']
            
            # Get identifiers
            identifier = get_client_identifier()
            endpoint = get_endpoint_identifier()
            
            # Check rate limit
            result = rate_limiter.is_allowed(identifier, endpoint, request_limit, request_window)
            
            # Add rate limit headers
            response = None
            if hasattr(g, 'rate_limit_response'):
                response = g.rate_limit_response
            
            if not response:
                response = f(*args, **kwargs)
            
            # Convert to Flask response if needed
            if not hasattr(response, 'headers'):
                from flask import make_response
                response = make_response(response)
            
            response.headers['X-RateLimit-Limit'] = str(request_limit)
            response.headers['X-RateLimit-Remaining'] = str(result['remaining'])
            response.headers['X-RateLimit-Reset'] = str(int(result['reset_time']))
            
            if not result['allowed']:
                response.headers['Retry-After'] = str(result['retry_after'])
                
                # Return rate limit exceeded response
                from flask import make_response
                response = make_response(jsonify({
                    'error': 'Rate limit exceeded',
                    'message': rate_config['message'],
                    'retry_after': result['retry_after']
                }), 429)
                
                response.headers['X-RateLimit-Limit'] = str(request_limit)
                response.headers['X-RateLimit-Remaining'] = '0'
                response.headers['X-RateLimit-Reset'] = str(int(result['reset_time']))
                response.headers['Retry-After'] = str(result['retry_after'])
                
                return response
            
            return response
        
        return decorated_function
    return decorator

# Predefined rate limit decorators
def auth_rate_limit(f: Callable) -> Callable:
    """Rate limiting for authentication endpoints"""
    return rate_limit(config='auth')(f)

def strict_rate_limit(f: Callable) -> Callable:
    """Strict rate limiting for sensitive endpoints"""
    return rate_limit(config='strict')(f)

def upload_rate_limit(f: Callable) -> Callable:
    """Rate limiting for upload endpoints"""
    return rate_limit(config='upload')(f)

class RateLimitMiddleware:
    """Flask middleware for rate limiting"""
    
    def __init__(self, app: Flask = None):
        self.app = app
        if app:
            self.init_app(app)
    
    def init_app(self, app: Flask):
        """Initialize middleware with Flask app"""
        app.before_request(self._before_request)
        app.after_request(self._after_request)
        
        # Schedule cleanup
        self._schedule_cleanup()
    
    def _before_request(self):
        """Before request handler"""
        # Skip rate limiting for static files and health checks
        if request.path.startswith('/static/') or request.path == '/health':
            return
        
        # Skip if already rate limited by decorator
        if hasattr(g, 'rate_limit_checked'):
            return
        
        # Apply default rate limiting
        identifier = get_client_identifier()
        endpoint = get_endpoint_identifier()
        
        # Get configuration based on endpoint
        config = self._get_config_for_endpoint(endpoint)
        rate_config = RATE_LIMIT_CONFIGS.get(config, RATE_LIMIT_CONFIGS['default'])
        
        # Check rate limit
        result = rate_limiter.is_allowed(
            identifier, 
            endpoint, 
            rate_config['limit'], 
            rate_config['window']
        )
        
        if not result['allowed']:
            # Store response for after_request
            g.rate_limit_exceeded = True
            g.rate_limit_result = result
            g.rate_limit_config = rate_config
    
    def _after_request(self, response):
        """After request handler"""
        # Handle rate limit exceeded
        if hasattr(g, 'rate_limit_exceeded') and g.rate_limit_exceeded:
            result = g.rate_limit_result
            config = g.rate_limit_config
            
            response = jsonify({
                'error': 'Rate limit exceeded',
                'message': config['message'],
                'retry_after': result['retry_after']
            })
            response.status_code = 429
            
            response.headers['X-RateLimit-Limit'] = str(config['limit'])
            response.headers['X-RateLimit-Remaining'] = '0'
            response.headers['X-RateLimit-Reset'] = str(int(result['reset_time']))
            response.headers['Retry-After'] = str(result['retry_after'])
            
            return response
        
        # Add rate limit headers if not already added
        if 'X-RateLimit-Limit' not in response.headers:
            identifier = get_client_identifier()
            endpoint = get_endpoint_identifier()
            config = self._get_config_for_endpoint(endpoint)
            rate_config = RATE_LIMIT_CONFIGS.get(config, RATE_LIMIT_CONFIGS['default'])
            
            result = rate_limiter.is_allowed(
                identifier, 
                endpoint, 
                rate_config['limit'], 
                rate_config['window']
            )
            
            response.headers['X-RateLimit-Limit'] = str(rate_config['limit'])
            response.headers['X-RateLimit-Remaining'] = str(result['remaining'])
            response.headers['X-RateLimit-Reset'] = str(int(result['reset_time']))
        
        return response
    
    def _get_config_for_endpoint(self, endpoint: str) -> str:
        """Get rate limit configuration for endpoint"""
        # Authentication endpoints
        if any(auth_ep in endpoint.lower() for auth_ep in ['login', 'register', 'auth', 'password']):
            return 'auth'
        
        # Upload endpoints
        if any(upload_ep in endpoint.lower() for upload_ep in ['upload', 'file', 'import']):
            return 'upload'
        
        # Sensitive endpoints
        if any(sensitive_ep in endpoint.lower() for sensitive_ep in ['admin', 'delete', 'bulk']):
            return 'strict'
        
        return 'default'
    
    def _schedule_cleanup(self):
        """Schedule periodic cleanup"""
        import threading
        import time
        
        def cleanup_task():
            while True:
                try:
                    # Clean up expired entries
                    count = rate_limiter.db_limiter.cleanup_expired()
                    if count > 0:
                        logger.info(f"Cleaned up {count} expired rate limit entries")
                except Exception as e:
                    logger.error(f"Rate limit cleanup error: {e}")
                
                # Sleep for 1 hour
                time.sleep(3600)
        
        cleanup_thread = threading.Thread(target=cleanup_task, daemon=True)
        cleanup_thread.start()

# Rate limiting utilities
class RateLimitUtils:
    """Utility functions for rate limiting management"""
    
    @staticmethod
    def get_rate_limit_stats() -> Dict[str, Any]:
        """Get rate limiting statistics"""
        try:
            # Get database stats
            total_limits = RateLimit.query.count()
            active_limits = RateLimit.query.filter(
                RateLimit.reset_at > datetime.utcnow()
            ).count()
            
            # Get memory stats
            memory_stats = rate_limiter.memory_limiter.memory_store
            
            return {
                'database': {
                    'total_limits': total_limits,
                    'active_limits': active_limits,
                    'expired_limits': total_limits - active_limits
                },
                'memory': {
                    'active_entries': len(memory_stats)
                },
                'timestamp': datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting rate limit stats: {e}")
            return {'error': str(e)}
    
    @staticmethod
    def clear_rate_limits(identifier: str = None, endpoint: str = None) -> int:
        """Clear rate limits"""
        try:
            query = RateLimit.query
            
            if identifier:
                query = query.filter_by(identifier=identifier)
            if endpoint:
                query = query.filter_by(endpoint=endpoint)
            
            count = query.count()
            query.delete()
            db.session.commit()
            
            # Clear memory limits
            if identifier and endpoint:
                key = rate_limiter.memory_limiter._get_key(identifier, endpoint)
                rate_limiter.memory_limiter.memory_store.pop(key, None)
            elif identifier:
                # Clear all for identifier
                keys_to_remove = []
                for key, data in rate_limiter.memory_limiter.memory_store.items():
                    if identifier in key:
                        keys_to_remove.append(key)
                for key in keys_to_remove:
                    del rate_limiter.memory_limiter.memory_store[key]
            
            return count
        except Exception as e:
            logger.error(f"Error clearing rate limits: {e}")
            db.session.rollback()
            return 0

# Initialize rate limiting
def initialize_rate_limiting(app: Flask):
    """Initialize rate limiting system"""
    logger.info("Initializing rate limiting system...")
    
    # Initialize middleware
    RateLimitMiddleware(app)
    
    logger.info("Rate limiting system initialized")

if __name__ == "__main__":
    # Test rate limiting
    from flask import Flask
    
    app = Flask(__name__)
    initialize_rate_limiting(app)
    
    @app.route('/test')
    @rate_limit(limit=5, window=60)  # 5 requests per minute
    def test_endpoint():
        return "Hello, World!"
    
    @app.route('/auth')
    @auth_rate_limit
    def auth_endpoint():
        return "Auth endpoint"
    
    with app.test_client() as client:
        # Test rate limiting
        for i in range(7):
            response = client.get('/test')
            print(f"Request {i+1}: {response.status_code}")
            if response.status_code == 429:
                print(f"Rate limited: {response.get_json()}")
                break
        
        # Test auth rate limiting
        for i in range(7):
            response = client.get('/auth')
            print(f"Auth request {i+1}: {response.status_code}")
            if response.status_code == 429:
                print(f"Auth rate limited: {response.get_json()}")
                break