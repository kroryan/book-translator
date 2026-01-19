"""
API Middleware
==============
Rate limiting, authentication, and request handling middleware.
"""
import time
import hashlib
from functools import wraps
from collections import defaultdict
from typing import Callable, Optional
from flask import request, jsonify, g

from book_translator.config import config
from book_translator.utils.logging import get_logger


class RateLimiter:
    """
    Simple in-memory rate limiter.
    
    Uses a sliding window approach for rate limiting.
    """
    
    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.requests: dict = defaultdict(list)
        self.logger = get_logger().api_logger
    
    def _get_client_id(self) -> str:
        """Get unique client identifier."""
        # Use X-Forwarded-For if behind proxy
        forwarded = request.headers.get('X-Forwarded-For')
        if forwarded:
            ip = forwarded.split(',')[0].strip()
        else:
            ip = request.remote_addr or 'unknown'
        
        # Include API key if present
        api_key = request.headers.get('X-API-Key', '')
        
        return hashlib.sha256(f"{ip}:{api_key}".encode()).hexdigest()[:16]
    
    def _cleanup_old_requests(self, client_id: str, window_start: float) -> None:
        """Remove requests outside the current window."""
        self.requests[client_id] = [
            ts for ts in self.requests[client_id]
            if ts > window_start
        ]
    
    def is_allowed(self) -> tuple[bool, dict]:
        """
        Check if request is allowed.
        
        Returns:
            Tuple of (allowed, info_dict)
        """
        client_id = self._get_client_id()
        current_time = time.time()
        window_start = current_time - 60  # 1 minute window
        
        self._cleanup_old_requests(client_id, window_start)
        
        request_count = len(self.requests[client_id])
        remaining = max(0, self.requests_per_minute - request_count)
        
        if request_count >= self.requests_per_minute:
            retry_after = int(self.requests[client_id][0] - window_start + 1)
            return False, {
                'limit': self.requests_per_minute,
                'remaining': 0,
                'reset': retry_after
            }
        
        self.requests[client_id].append(current_time)
        
        return True, {
            'limit': self.requests_per_minute,
            'remaining': remaining - 1,
            'reset': 60
        }


class APIKeyAuth:
    """
    Simple API key authentication.
    
    API keys are loaded from configuration.
    """
    
    def __init__(self):
        self.logger = get_logger().api_logger
        self._load_keys()
    
    def _load_keys(self) -> None:
        """Load API keys from config."""
        # In production, load from environment or secure storage
        # For now, check if API key auth is enabled
        self.enabled = bool(config.security.api_key)
        self.valid_keys = set()
        
        if config.security.api_key:
            self.valid_keys.add(config.security.api_key)
    
    def validate(self, api_key: str) -> bool:
        """Validate an API key."""
        if not self.enabled:
            return True
        
        return api_key in self.valid_keys


# Global instances
_rate_limiter: Optional[RateLimiter] = None
_api_key_auth: Optional[APIKeyAuth] = None


def get_rate_limiter() -> RateLimiter:
    """Get rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter(config.security.rate_limit_per_minute)
    return _rate_limiter


def get_api_key_auth() -> APIKeyAuth:
    """Get API key auth instance."""
    global _api_key_auth
    if _api_key_auth is None:
        _api_key_auth = APIKeyAuth()
    return _api_key_auth


def rate_limit(f: Callable) -> Callable:
    """Rate limiting decorator."""
    @wraps(f)
    def decorated(*args, **kwargs):
        limiter = get_rate_limiter()
        allowed, info = limiter.is_allowed()
        
        # Add rate limit headers
        g.rate_limit_info = info
        
        if not allowed:
            return jsonify({
                'error': 'Rate limit exceeded',
                'retry_after': info['reset']
            }), 429
        
        return f(*args, **kwargs)
    
    return decorated


def require_api_key(f: Callable) -> Callable:
    """API key authentication decorator."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = get_api_key_auth()
        
        if not auth.enabled:
            return f(*args, **kwargs)
        
        api_key = request.headers.get('X-API-Key')
        
        if not api_key:
            return jsonify({'error': 'API key required'}), 401
        
        if not auth.validate(api_key):
            return jsonify({'error': 'Invalid API key'}), 403
        
        return f(*args, **kwargs)
    
    return decorated


def add_rate_limit_headers(response):
    """Add rate limit headers to response."""
    if hasattr(g, 'rate_limit_info'):
        info = g.rate_limit_info
        response.headers['X-RateLimit-Limit'] = str(info['limit'])
        response.headers['X-RateLimit-Remaining'] = str(info['remaining'])
        response.headers['X-RateLimit-Reset'] = str(info['reset'])
    return response
