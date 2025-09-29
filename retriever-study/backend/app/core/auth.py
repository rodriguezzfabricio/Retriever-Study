"""Production-grade Google OAuth 2.0 + JWT Authentication System."""
import asyncio
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any

from dotenv import load_dotenv
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests
import structlog

logger = structlog.get_logger()


def _load_environment() -> None:
    """Ensure development env files populate os.environ before first access."""
    project_root = Path(__file__).resolve().parents[2]
    for filename in (".env", ".env.development", ".env.local"):
        env_path = project_root / filename
        if env_path.exists():
            load_dotenv(env_path, override=False)


_load_environment()

# ========== CONFIGURATION ==========
# These MUST be environment variables in production for security
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("JWT_SECRET_KEY environment variable must be set")
ALGORITHM = "HS256"  # Industry standard for JWT signing
ACCESS_TOKEN_EXPIRE_MINUTES = 10080  # 7 days  # Short-lived for security
REFRESH_TOKEN_EXPIRE_DAYS = 7     # Longer for user convenience

# Google OAuth credentials - get these from Google Cloud Console
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET") 
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")
if not GOOGLE_REDIRECT_URI:
    raise ValueError("GOOGLE_REDIRECT_URI environment variable must be set")

# Google API endpoints - these are standard OAuth 2.0 URLs
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

# FastAPI security scheme - automatically extracts "Bearer <token>" from headers
security = HTTPBearer()

# ========== CUSTOM EXCEPTIONS ==========
class AuthError(Exception):
    """
    Custom authentication error for better error handling
    
    Why custom exception?
    - Different auth errors need different HTTP status codes
    - Security: Control exactly what error info is exposed to client
    - Debugging: Can log detailed errors server-side while showing generic message to user
    """
    def __init__(self, message: str, status_code: int = 401):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

# ========== JWT TOKEN FUNCTIONS ==========
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a signed JWT access token with a 7-day expiration.
    
    The payload includes the internal user ID (`sub`) and email,
    adhering to the new secure authentication standard.
    """
    payload = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        # Set default expiration to 7 days as per requirements
        expire = datetime.utcnow() + timedelta(days=7)
    
    payload.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access",
    })
    
    # Ensure 'sub' (subject) claim is present for user identification
    if "sub" not in payload:
        raise ValueError("Payload for access token must contain 'sub' (user ID) claim.")
        
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str) -> Dict[str, Any]:
    """
    Verify JWT token signature and decode payload
    
    Security checks performed:
    1. Signature validation (prevents tampering)
    2. Expiration check (prevents replay attacks)
    3. Algorithm verification (prevents algorithm substitution attacks)
    """
    try:
        payload = jwt.decode(
            token, 
            SECRET_KEY, 
            algorithms=[ALGORITHM],
            options={
                "require": ["exp", "iat", "sub"],  # Required claims
                "verify_aud": False,  # Not using audience
                "verify_iss": False   # Not using issuer
            }
        )
        return payload
    except JWTError as e:
        # Log the actual error for debugging, but don't expose to client
        logger.error(f"JWT verification failed: {e}")
        raise AuthError("Invalid or expired token")

# ========== GOOGLE OAUTH FUNCTIONS ==========

def _verify_google_token_sync(id_token: str, client_id: str) -> Dict[str, Any]:
    """
    Synchronous Google token verification - runs in thread pool.

    CRITICAL: This must run in a thread pool to avoid blocking the async event loop.
    The Google auth library uses synchronous HTTP requests.
    """
    request_adapter = google_requests.Request()
    return google_id_token.verify_oauth2_token(
        id_token,
        request_adapter,
        client_id,
        clock_skew_in_seconds=120,
    )

async def verify_google_id_token(id_token: str) -> Dict[str, Any]:
    """
    Verify Google-issued ID tokens using google-auth (Production-Grade Async).

    CRITICAL FIX: Google's auth library is synchronous, so we run it in a thread pool
    to prevent blocking FastAPI's async event loop. This is essential for production.

    Security steps:
    1. Fetch Google's public keys and verify the JWT signature.
    2. Validate the token audience matches our client id.
    3. Enforce allowed issuers from Google.
    4. Allow minor clock skew for local development machines.
    """
    if not id_token:
        raise AuthError("No ID token provided", 400)

    if not GOOGLE_CLIENT_ID:
        raise AuthError("Google OAuth is not configured", 500)

    try:
        # Run synchronous Google API call in thread pool (production-grade async pattern)
        user_info = await asyncio.get_event_loop().run_in_executor(
            None,  # Use default thread pool
            _verify_google_token_sync,
            id_token,
            GOOGLE_CLIENT_ID
        )

        issuer = user_info.get("iss")
        if issuer not in {"accounts.google.com", "https://accounts.google.com"}:
            raise AuthError("Invalid token issuer.", 401)

        return user_info
    except AuthError:
        raise
    except OSError as e:
        print(f"Google ID token network error: {e!r}")
        raise AuthError("Unable to reach Google token service. Please try again.", 503)
    except Exception as e:
        # Log the detailed error for debugging
        print(f"Google ID token verification failed: {e}")
        # Return a generic error to the client for security
        raise AuthError("Invalid or expired Google token", 401)


def validate_umbc_email(email: str) -> bool:
    """
    Validate university email domain
    
    Business rule: Only UMBC students/faculty can use the app
    Security: Prevents random Google users from accessing our system
    """
    if not email:
        return False
    return email.lower().strip().endswith("@umbc.edu")

# ========== FASTAPI DEPENDENCIES ==========
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """
    FastAPI dependency to get current authenticated user
    
    How FastAPI dependencies work:
    1. security = HTTPBearer() extracts "Authorization: Bearer <token>" header
    2. This function gets called automatically for protected endpoints  
    3. If token is valid, returns user info
    4. If token is invalid, raises HTTP 401 error
    
    Usage in endpoints:
    @app.get("/protected")
    async def protected_endpoint(current_user = Depends(get_current_user)):
        return {"user_id": current_user["user_id"]}
    """
    try:
        token = credentials.credentials
        payload = verify_token(token)
        
        # Verify this is an access token (not refresh token)
        if payload.get("type") != "access":
            raise AuthError("Invalid token type")
        
        # Extract user information from token
        user_id = payload.get("sub")  # 'sub' is standard JWT claim for subject
        if not user_id:
            raise AuthError("Token missing user identifier")
        
        return {
            "user_id": user_id,
            "email": payload.get("email"),
            "name": payload.get("name"),
            "picture": payload.get("picture")
        }
        
    except AuthError:
        # Convert our custom exception to FastAPI HTTP exception
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},  # Tells client how to authenticate
        )
