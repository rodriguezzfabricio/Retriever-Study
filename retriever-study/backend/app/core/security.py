"""
Production Security Configuration Module

This module implements multiple security layers for production deployment:
1. Rate limiting - prevents API abuse and DDoS attacks
2. Request size limits - prevents memory exhaustion  
3. Security headers - protects against common web attacks
4. Input validation - sanitizes user input
5. Environment validation - ensures proper configuration

Key Learning: Security is implemented in layers - if one fails, others protect you.
"""

from datetime import datetime
import time
import os
import re
import hashlib
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import structlog

# Initialize structured logging for production
logger = structlog.get_logger()

# ========== RATE LIMITING CONFIGURATION ==========
# 
# Why Rate Limiting is Critical:
# - Prevents brute force attacks on authentication endpoints
# - Stops API abuse that could crash your server
# - Protects against DDoS attacks
# - Ensures fair usage among users
# 
# Rate Limit Strategy:
# - Stricter limits for auth endpoints (expensive operations)
# - Generous limits for normal API usage
# - IP-based limiting (could be enhanced with user-based limits)

def get_rate_limit_key(request: Request) -> str:
    """
    Determine rate limit key for request.
    
    Production Enhancement Ideas:
    - Use user ID for authenticated requests (per-user limits)
    - Use IP address for unauthenticated requests
    - Different limits for different user tiers
    - Whitelist internal services
    """
    # For now, use IP address for all rate limiting
    return get_remote_address(request)

# Initialize rate limiter with Redis backend (production) or memory (development)
REDIS_URL = os.getenv("REDIS_URL")
if REDIS_URL:
    # Production: Use Redis for distributed rate limiting
    import redis
    redis_client = redis.from_url(REDIS_URL)
    limiter = Limiter(key_func=get_rate_limit_key, storage_uri=REDIS_URL)
    logger.info("Rate limiting configured with Redis backend")
else:
    # Development: Use in-memory storage
    limiter = Limiter(key_func=get_rate_limit_key)
    logger.info("Rate limiting configured with memory backend (development only)")

# ========== SECURITY HEADERS ==========
#
# Security Headers Explanation:
# These headers tell browsers how to behave when loading our API responses
# Critical for preventing XSS, clickjacking, and other web attacks

SECURITY_HEADERS = {
    # Prevent MIME type sniffing attacks
    "X-Content-Type-Options": "nosniff",
    
    # Prevent clickjacking attacks (iframe embedding)
    "X-Frame-Options": "DENY",
    
    # Enable XSS protection in browsers
    "X-XSS-Protection": "1; mode=block",
    
    # Only load resources over HTTPS in production
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains" if os.getenv("ENVIRONMENT") == "production" else None,
    
    # Control which referrer information is sent
    "Referrer-Policy": "strict-origin-when-cross-origin",
    
    # Prevent Flash/PDF from loading
    "X-Permitted-Cross-Domain-Policies": "none"
}

# ========== INPUT VALIDATION & SANITIZATION ==========

def sanitize_string(input_string: str, max_length: int = 1000) -> str:
    """
    Sanitize user input to prevent injection attacks.
    
    Security Measures:
    - Remove potential HTML/script tags
    - Limit string length to prevent DoS
    - Remove control characters
    - Preserve Unicode for international users
    
    Why This Matters:
    - Prevents XSS attacks in user-generated content
    - Stops SQL injection attempts
    - Prevents log injection attacks
    - Maintains data quality
    """
    if not input_string:
        return ""
    
    # Truncate to maximum length
    sanitized = input_string[:max_length]
    
    # Remove HTML tags and script elements
    sanitized = re.sub(r'<[^>]*>', '', sanitized)
    
    # Remove control characters but preserve normal whitespace
    sanitized = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', sanitized)
    
    # Remove potential SQL injection patterns (basic protection)
    dangerous_patterns = [
        r'(?i)(union\s+select)',
        r'(?i)(drop\s+table)',
        r'(?i)(insert\s+into)',
        r'(?i)(delete\s+from)',
        r'(?i)(update\s+.+\s+set)'
    ]
    
    for pattern in dangerous_patterns:
        sanitized = re.sub(pattern, '', sanitized)
    
    return sanitized.strip()

def validate_email(email: str) -> bool:
    """
    Validate email format with production-grade regex.
    
    Why Custom Validation:
    - Pydantic validation is good but this adds extra security layer
    - Prevents obvious injection attempts
    - Enforces business rules (like @umbc.edu domain)
    """
    if not email or len(email) > 254:  # RFC 5321 limit
        return False
    
    # RFC-compliant email regex (simplified for readability)
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if not re.match(email_pattern, email):
        return False
    
    # Business rule: must be UMBC email
    return email.lower().endswith('@umbc.edu')

# ========== REQUEST SIZE LIMITS ==========

MAX_REQUEST_SIZE = 1024 * 1024  # 1MB limit for API requests

async def validate_request_size(request: Request):
    """
    Prevent memory exhaustion attacks by limiting request size.
    
    Why This Matters:
    - Prevents attackers from sending huge payloads
    - Protects server memory and bandwidth
    - Stops potential DoS attacks
    - Ensures consistent response times
    """
    content_length = request.headers.get('content-length')
    
    if content_length:
        content_length = int(content_length)
        if content_length > MAX_REQUEST_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Request too large. Maximum size is {MAX_REQUEST_SIZE} bytes"
            )

# ========== ENVIRONMENT VALIDATION ==========

def validate_production_environment():
    """
    Ensure all required environment variables are configured for production.
    
    Production Checklist:
    - OAuth credentials configured
    - JWT secret is cryptographically secure
    - Database connection is configured
    - Logging and monitoring are enabled
    
    Why Fail Fast:
    - Better to crash at startup than fail silently in production
    - Prevents security vulnerabilities from misconfigurations
    - Makes deployment issues obvious immediately
    """
    required_vars = [
        "JWT_SECRET_KEY",
        "GOOGLE_CLIENT_ID", 
        "GOOGLE_CLIENT_SECRET"
    ]
    
    missing_vars = []
    weak_configs = []
    
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            missing_vars.append(var)
        elif var == "JWT_SECRET_KEY" and len(value) < 32:
            weak_configs.append(f"{var} is too short (minimum 32 characters)")
    
    if missing_vars:
        error_msg = f"Missing required environment variables: {', '.join(missing_vars)}"
        logger.error("Environment validation failed", missing_vars=missing_vars)
        raise ValueError(error_msg)
    
    if weak_configs:
        error_msg = f"Weak security configurations: {', '.join(weak_configs)}"
        logger.warning("Security configuration warnings", warnings=weak_configs)
        # Don't fail for warnings, but log them prominently
    
    # Additional production checks
    if os.getenv("ENVIRONMENT") == "production":
        if os.getenv("JWT_SECRET_KEY") == "dev-secret-change-in-production":
            raise ValueError("Production environment detected but JWT_SECRET_KEY is still using development default!")
        
        if not os.getenv("SENTRY_DSN"):
            logger.warning("SENTRY_DSN not configured - error tracking disabled")
    
    logger.info("Environment validation passed")

# ========== SECURITY MIDDLEWARE ==========

async def add_security_headers(request: Request, call_next):
    """
    Add security headers to all responses.
    
    This middleware runs for every request and adds security headers
    that protect against various web attacks.
    """
    start_time = time.time()
    
    # Process the request
    response = await call_next(request)
    
    # Add security headers to response
    for header_name, header_value in SECURITY_HEADERS.items():
        if header_value:  # Skip None values
            response.headers[header_name] = header_value
    
    # Add performance timing header (useful for monitoring)
    duration = time.time() - start_time
    response.headers["X-Response-Time"] = f"{duration:.3f}s"
    
    return response

# ========== ATTACK DETECTION ==========

SUSPICIOUS_PATTERNS = [
    # SQL Injection patterns
    r'(?i)(union\s+select|drop\s+table|insert\s+into)',
    
    # XSS patterns  
    r'(?i)(<script|javascript:|on\w+\s*=)',
    
    # Path traversal
    r'(\.\./|\.\.\\)',
    
    # Command injection
    r'(?i)(;|\||&|\$\(|\`)',
]

def detect_suspicious_input(input_text: str) -> Optional[str]:
    """
    Detect potentially malicious input patterns.
    
    Returns the type of attack detected, or None if input appears safe.
    This is used for logging and monitoring suspicious activity.
    """
    if not input_text:
        return None
    
    for i, pattern in enumerate(SUSPICIOUS_PATTERNS):
        if re.search(pattern, input_text):
            attack_types = ["sql_injection", "xss", "path_traversal", "command_injection"]
            return attack_types[i % len(attack_types)]
    
    return None

# ========== AI ABUSE PROTECTION ==========

def validate_ai_input(text: str, max_length: int = 2000, user_id: str = None) -> str:
    """
    Comprehensive AI input validation to prevent abuse.
    
    Protects against:
    - Computation DoS (huge text → expensive embedding)
    - Model poisoning (repetitive patterns)
    - Data extraction attempts
    """
    if not text or not isinstance(text, str):
        return ""
    
    # 1. Length validation (prevent expensive computation)
    if len(text) > max_length:
        raise HTTPException(
            status_code=400, 
            detail=f"Input too long for AI processing. Maximum {max_length} characters."
        )
    
    # 2. Repetition detection (prevent model confusion)
    words = text.split()
    if len(words) > 10:
        word_freq = {}
        for word in words:
            if len(word) > 2:  # Only check meaningful words
                word_freq[word.lower()] = word_freq.get(word.lower(), 0) + 1
        
        # Check for excessive repetition
        max_repetitions = max(word_freq.values()) if word_freq else 0
        if max_repetitions > len(words) * 0.3:  # >30% repetition
            logger.warning("AI input repetition detected", 
                         user=user_id, 
                         repetition_ratio=max_repetitions/len(words))
            raise HTTPException(
                status_code=400, 
                detail="Input contains excessive repetition"
            )
    
    # 3. Content validation (detect suspicious patterns)
    suspicious_type = detect_suspicious_input(text)
    if suspicious_type:
        logger.warning("Suspicious AI input detected", 
                     user=user_id, 
                     attack_type=suspicious_type,
                     input_sample=text[:100])
        raise HTTPException(
            status_code=400, 
            detail="Invalid input content detected"
        )
    
    # 4. Standard sanitization
    return sanitize_string(text, max_length)

def validate_ai_computation_limits(
    operation_type: str,
    input_text: str,
    user_id: Optional[str] = None,
    max_length: int = 10000,
    max_repetition_ratio: float = 0.7
) -> None:
    """
    Validate AI computation requests to prevent abuse and resource exhaustion.
    
    Senior Engineer Teaching Points:
    1. Input Validation: Always validate before expensive operations
    2. Resource Protection: Set hard limits on computation resources
    3. Abuse Detection: Look for patterns that indicate malicious use
    4. Fail Fast: Reject invalid requests immediately
    5. Logging: Track security events for monitoring
    """
    
    # Input length validation (prevents memory exhaustion)
    if len(input_text) > max_length:
        logger.warning(
            "AI input length exceeded",
            operation=operation_type,
            length=len(input_text),
            max_length=max_length,
            user_id=user_id,
            timestamp=datetime.utcnow()  # Now properly imported!
        )
        raise HTTPException(
            status_code=413,
            detail=f"Input too long. Maximum {max_length} characters allowed."
        )
    
    # ...existing code...

# Initialize environment validation on module import
try:
    validate_production_environment()
except ValueError as e:
    logger.error("Security configuration failed", error=str(e))
    # In production, you might want to exit here
    # For development, we'll just log the error
    if os.getenv("ENVIRONMENT") == "production":
        raise
