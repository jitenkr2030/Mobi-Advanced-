"""
Caching Layer Module
Provides Redis/Memcached-like caching functionality for improved performance
"""

import json
import pickle
import hashlib
import time
import logging
from datetime import datetime, timedelta
from typing import Any, Optional, Union, Dict, List, Callable
from functools import wraps
from threading import Lock
from flask import current_app, request
from app import db, CacheEntry

logger = logging.getLogger(__name__)

class CacheManager:
    """In-memory cache manager with Redis-like interface"""
    
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._locks: Dict[str, Lock] = {}
        self._global_lock = Lock()
        self.stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0,
            'evictions': 0
        }
    
    def _get_lock(self, key: str) -> Lock:
        """Get or create a lock for a specific key"""
        if key not in self._locks:
            with self._global_lock:
                if key not in self._locks:
                    self._locks[key] = Lock()
        return self._locks[key]
    
    def _is_expired(self, key: str) -> bool:
        """Check if a cache entry is expired"""
        if key not in self._cache:
            return True
        
        entry = self._cache[key]
        if entry.get('expires_at') and entry['expires_at'] < time.time():
            return True
        
        return False
    
    def _evict_expired(self):
        """Remove expired entries from cache"""
        current_time = time.time()
        expired_keys = []
        
        for key, entry in self._cache.items():
            if entry.get('expires_at') and entry['expires_at'] < current_time:
                expired_keys.append(key)
        
        for key in expired_keys:
            self.delete(key)
            self.stats['evictions'] += 1
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        with self._get_lock(key):
            if self._is_expired(key):
                self.stats['misses'] += 1
                return None
            
            self.stats['hits'] += 1
            entry = self._cache[key]
            entry['accessed_at'] = time.time()
            return entry['value']
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache with optional TTL"""
        try:
            with self._get_lock(key):
                expires_at = None
                if ttl:
                    expires_at = time.time() + ttl
                
                self._cache[key] = {
                    'value': value,
                    'created_at': time.time(),
                    'accessed_at': time.time(),
                    'expires_at': expires_at,
                    'ttl': ttl
                }
                
                self.stats['sets'] += 1
                return True
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        with self._get_lock(key):
            if key in self._cache:
                del self._cache[key]
                self.stats['deletes'] += 1
                return True
            return False
    
    def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        return not self._is_expired(key)
    
    def expire(self, key: str, ttl: int) -> bool:
        """Set expiration for existing key"""
        with self._get_lock(key):
            if key in self._cache and not self._is_expired(key):
                self._cache[key]['expires_at'] = time.time() + ttl
                self._cache[key]['ttl'] = ttl
                return True
            return False
    
    def ttl(self, key: str) -> int:
        """Get remaining TTL for key"""
        with self._get_lock(key):
            if key in self._cache and not self._is_expired(key):
                entry = self._cache[key]
                if entry.get('expires_at'):
                    remaining = int(entry['expires_at'] - time.time())
                    return max(0, remaining)
            return -1
    
    def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """Increment numeric value"""
        with self._get_lock(key):
            if self._is_expired(key):
                return None
            
            entry = self._cache[key]
            try:
                value = int(entry['value'])
                value += amount
                entry['value'] = value
                entry['accessed_at'] = time.time()
                return value
            except (ValueError, TypeError):
                return None
    
    def decrement(self, key: str, amount: int = 1) -> Optional[int]:
        """Decrement numeric value"""
        return self.increment(key, -amount)
    
    def clear(self) -> bool:
        """Clear all cache entries"""
        with self._global_lock:
            self._cache.clear()
            self._locks.clear()
            return True
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = self.stats['hits'] + self.stats['misses']
        hit_rate = (self.stats['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            **self.stats,
            'total_keys': len(self._cache),
            'hit_rate_percent': round(hit_rate, 2),
            'memory_usage_estimate': sum(len(str(entry['value'])) for entry in self._cache.values())
        }
    
    def get_keys(self, pattern: str = "*") -> List[str]:
        """Get keys matching pattern (simple globbing)"""
        import fnmatch
        
        keys = []
        for key in self._cache.keys():
            if not self._is_expired(key) and fnmatch.fnmatch(key, pattern):
                keys.append(key)
        return keys

# Database-backed cache for persistence
class DatabaseCache:
    """Database-backed cache with SQLite backend"""
    
    def __init__(self):
        self.default_ttl = 300  # 5 minutes
    
    def _serialize_value(self, value: Any) -> str:
        """Serialize value for storage"""
        try:
            return json.dumps(value, default=str)
        except (TypeError, ValueError):
            return pickle.dumps(value).hex()
    
    def _deserialize_value(self, serialized: str) -> Any:
        """Deserialize value from storage"""
        try:
            return json.loads(serialized)
        except (json.JSONDecodeError, ValueError):
            try:
                return pickle.loads(bytes.fromhex(serialized))
            except (ValueError, pickle.UnpicklingError):
                return serialized
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from database cache"""
        try:
            entry = CacheEntry.query.filter_by(key=key).first()
            if not entry:
                return None
            
            # Check if expired
            if entry.expires_at < datetime.utcnow():
                db.session.delete(entry)
                db.session.commit()
                return None
            
            # Update last accessed time
            entry.updated_at = datetime.utcnow()
            db.session.commit()
            
            return self._deserialize_value(entry.value)
        except Exception as e:
            logger.error(f"Database cache get error for key {key}: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in database cache"""
        try:
            ttl = ttl or self.default_ttl
            expires_at = datetime.utcnow() + timedelta(seconds=ttl)
            serialized_value = self._serialize_value(value)
            
            entry = CacheEntry.query.filter_by(key=key).first()
            if entry:
                entry.value = serialized_value
                entry.ttl = ttl
                entry.expires_at = expires_at
                entry.updated_at = datetime.utcnow()
            else:
                entry = CacheEntry(
                    key=key,
                    value=serialized_value,
                    ttl=ttl,
                    expires_at=expires_at
                )
                db.session.add(entry)
            
            db.session.commit()
            return True
        except Exception as e:
            logger.error(f"Database cache set error for key {key}: {e}")
            db.session.rollback()
            return False
    
    def delete(self, key: str) -> bool:
        """Delete key from database cache"""
        try:
            entry = CacheEntry.query.filter_by(key=key).first()
            if entry:
                db.session.delete(entry)
                db.session.commit()
                return True
            return False
        except Exception as e:
            logger.error(f"Database cache delete error for key {key}: {e}")
            db.session.rollback()
            return False
    
    def exists(self, key: str) -> bool:
        """Check if key exists in database cache"""
        try:
            entry = CacheEntry.query.filter_by(key=key).first()
            return entry is not None and entry.expires_at >= datetime.utcnow()
        except Exception as e:
            logger.error(f"Database cache exists error for key {key}: {e}")
            return False
    
    def clear_expired(self) -> int:
        """Clear expired entries from database cache"""
        try:
            deleted_count = CacheEntry.query.filter(
                CacheEntry.expires_at < datetime.utcnow()
            ).delete()
            db.session.commit()
            return deleted_count
        except Exception as e:
            logger.error(f"Database cache cleanup error: {e}")
            db.session.rollback()
            return 0

# Hybrid cache that tries memory first, then database
class HybridCache:
    """Hybrid cache combining memory and database storage"""
    
    def __init__(self):
        self.memory_cache = CacheManager()
        self.db_cache = DatabaseCache()
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache (memory first, then database)"""
        # Try memory cache first
        value = self.memory_cache.get(key)
        if value is not None:
            return value
        
        # Try database cache
        value = self.db_cache.get(key)
        if value is not None:
            # Store in memory cache for faster access
            self.memory_cache.set(key, value, ttl=300)  # 5 minutes in memory
            return value
        
        return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in both memory and database cache"""
        memory_success = self.memory_cache.set(key, value, ttl=min(ttl or 300, 300))
        db_success = self.db_cache.set(key, value, ttl)
        return memory_success and db_success
    
    def delete(self, key: str) -> bool:
        """Delete key from both caches"""
        memory_success = self.memory_cache.delete(key)
        db_success = self.db_cache.delete(key)
        return memory_success or db_success
    
    def exists(self, key: str) -> bool:
        """Check if key exists in either cache"""
        return self.memory_cache.exists(key) or self.db_cache.exists(key)
    
    def clear(self) -> bool:
        """Clear both caches"""
        memory_success = self.memory_cache.clear()
        # Database cache clear would be: CacheEntry.query.delete()
        return memory_success

# Global cache instance
cache = HybridCache()

# Cache decorators
def cached(ttl: int = 300, key_prefix: str = "", cache_instance: Optional[HybridCache] = None):
    """Decorator to cache function results"""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_obj = cache_instance or cache
            
            # Generate cache key
            key_data = {
                'func': func.__name__,
                'args': args,
                'kwargs': kwargs
            }
            cache_key = f"{key_prefix}{hashlib.md5(json.dumps(key_data, sort_keys=True, default=str).encode()).hexdigest()}"
            
            # Try to get from cache
            cached_result = cache_obj.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache_obj.set(cache_key, result, ttl)
            
            return result
        return wrapper
    return decorator

def cache_view(ttl: int = 300, key_func: Optional[Callable] = None):
    """Decorator to cache Flask view results"""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key for view
            if key_func:
                cache_key = key_func(request, *args, **kwargs)
            else:
                cache_key = f"view:{func.__name__}:{request.url}:{hashlib.md5(str(request.args.to_dict()).encode()).hexdigest()}"
            
            # Only cache GET requests
            if request.method != 'GET':
                return func(*args, **kwargs)
            
            # Try to get from cache
            cached_response = cache.get(cache_key)
            if cached_response is not None:
                return cached_response
            
            # Execute view and cache result
            response = func(*args, **kwargs)
            
            # Only cache successful responses
            if hasattr(response, 'status_code') and response.status_code == 200:
                cache.set(cache_key, response, ttl)
            
            return response
        return wrapper
    return decorator

# Cache utilities
class CacheUtils:
    """Utility functions for cache management"""
    
    @staticmethod
    def invalidate_pattern(pattern: str) -> int:
        """Invalidate cache keys matching pattern"""
        keys = cache.memory_cache.get_keys(pattern)
        count = 0
        for key in keys:
            if cache.delete(key):
                count += 1
        return count
    
    @staticmethod
    def warm_cache(data_loaders: Dict[str, Callable]):
        """Warm cache with predefined data"""
        for key, loader in data_loaders.items():
            try:
                data = loader()
                cache.set(key, data, ttl=3600)  # 1 hour
                logger.info(f"Warmed cache key: {key}")
            except Exception as e:
                logger.error(f"Failed to warm cache key {key}: {e}")
    
    @staticmethod
    def get_cache_info() -> Dict[str, Any]:
        """Get comprehensive cache information"""
        memory_stats = cache.memory_cache.get_stats()
        
        # Get database cache stats
        try:
            db_total = CacheEntry.query.count()
            db_expired = CacheEntry.query.filter(
                CacheEntry.expires_at < datetime.utcnow()
            ).count()
            db_active = db_total - db_expired
        except Exception:
            db_total = db_expired = db_active = 0
        
        return {
            'memory_cache': memory_stats,
            'database_cache': {
                'total_entries': db_total,
                'active_entries': db_active,
                'expired_entries': db_expired
            },
            'timestamp': datetime.utcnow().isoformat()
        }

# Initialize cache
def initialize_cache():
    """Initialize caching system"""
    logger.info("Initializing cache system...")
    
    # Clear expired database entries
    expired_count = cache.db_cache.clear_expired()
    logger.info(f"Cleared {expired_count} expired cache entries")
    
    # Warm essential cache data
    essential_data = {
        'system_config': lambda: {'version': '1.0.0', 'features': ['invoicing', 'crm']},
        'user_stats': lambda: {'total_users': 0, 'active_users': 0},
    }
    
    CacheUtils.warm_cache(essential_data)
    
    logger.info("Cache system initialized")

# Global cache instance for easy access
def get_cache() -> HybridCache:
    """Get global cache instance"""
    return cache

if __name__ == "__main__":
    # Test cache functionality
    initialize_cache()
    
    # Test basic operations
    cache.set('test_key', {'data': 'test_value'}, ttl=60)
    value = cache.get('test_key')
    print(f"Cached value: {value}")
    
    # Test cache statistics
    cache_info = CacheUtils.get_cache_info()
    print(f"Cache info: {cache_info}")