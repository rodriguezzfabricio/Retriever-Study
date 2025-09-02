"""
Production-grade Google OAuth 2.0 + JWT Authentication System

Key Design Decisions:
1. JWT tokens for stateless authentication (scales well with Lambda)
2. Google OAuth for secure, passwordless authentication  
3. Domain restriction to @umbc.edu for university access control
4. Separate access/refresh tokens for security + UX
5. Custom error handling for security and debugging
"""
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
import httpx

# ========== CONFIGURATION ==========
# These MUST be environment variables in production for security
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-change-in-production")
ALGORITHM = "HS256"  # Industry standard for JWT signing
ACCESS_TOKEN_EXPIRE_MINUTES = 30  # Short-lived for security
REFRESH_TOKEN_EXPIRE_DAYS = 7     # Longer for user convenience

# Google OAuth credentials - get these from Google Cloud Console
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET") 
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:3000/auth/callback")

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
    Create a signed JWT access token
    
    How JWT works:
    1. Take user data (payload)
    2. Add expiration timestamp  
    3. Sign with secret key using HMAC-SHA256
    4. Result: three base64 parts separated by dots (header.payload.signature)
    
    Why we include 'type': Prevents refresh tokens being used as access tokens
    """
    payload = data.copy()  # Don't modify original data
    
    # Set expiration time
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # Add JWT standard claims
    payload.update({
        "exp": expire,      # Expiration time (standard JWT claim)
        "type": "access",   # Custom claim to differentiate token types
        "iat": datetime.utcnow()  # Issued at time
    })
    
    # Sign and return token
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(data: dict) -> str:
    """
    Create a long-lived refresh token
    
    Refresh tokens:
    - Only used to get new access tokens
    - Longer expiration for user convenience
    - Should be stored securely (httpOnly cookie in production)
    """
    payload = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    
    payload.update({
        "exp": expire,
        "type": "refresh",  # Prevents misuse as access token
        "iat": datetime.utcnow()
    })
    
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
            algorithms=[ALGORITHM]  # Explicitly specify allowed algorithms
        )
        return payload
    except JWTError as e:
        # Log the actual error for debugging, but don't expose to client
        print(f"JWT verification failed: {e}")
        raise AuthError("Invalid or expired token")

# ========== GOOGLE OAUTH FUNCTIONS ==========
async def exchange_code_for_tokens(code: str) -> Dict[str, Any]:
    """
    Exchange OAuth authorization code for access tokens
    
    OAuth 2.0 Authorization Code Flow Step:
    Client → Google: "User authorized, here's the code"
    Google → Client: "Here's the access token for that user"
    
    Why this is secure:
    - Code is single-use and expires quickly
    - Client secret proves we're the legitimate app
    - Exchange happens server-to-server (code never exposed to browser)
    """
    async with httpx.AsyncClient() as client:
        # Prepare token exchange request
        token_data = {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,  # Proves we're the real app
            "code": code,                           # Authorization code from callback
            "grant_type": "authorization_code",     # OAuth 2.0 flow type
            "redirect_uri": GOOGLE_REDIRECT_URI,    # Must match what we registered
        }
        
        response = await client.post(GOOGLE_TOKEN_URL, data=token_data)
        
        if response.status_code != 200:
            print(f"Google token exchange failed: {response.text}")
            raise AuthError("Failed to authenticate with Google", 400)
        
        return response.json()

async def get_google_user_info(access_token: str) -> Dict[str, Any]:
    """
    Get user profile information from Google
    
    Why we need this:
    - OAuth gives us permission to access user data
    - We use this to get email, name, profile picture
    - Email validation happens here (must be @umbc.edu)
    """
    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = await client.get(GOOGLE_USERINFO_URL, headers=headers)
        
        if response.status_code != 200:
            print(f"Google userinfo failed: {response.status_code}")
            raise AuthError("Failed to fetch user information")
        
        return response.json()

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

# ========== OAUTH FLOW HANDLER ==========
class GoogleOAuthFlow:
    """
    Handles complete Google OAuth 2.0 flow
    
    OAuth Flow Steps:
    1. get_authorization_url() → Redirect user to Google
    2. User authorizes our app on Google  
    3. Google redirects back with code
    4. handle_callback() → Exchange code for user info + our JWT tokens
    """
    
    def __init__(self):
        # Fail fast if OAuth not configured
        if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
            raise ValueError(
                "Google OAuth not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables"
            )
    
    def get_authorization_url(self, state: str = None) -> str:
        """
        Generate Google OAuth authorization URL
        
        Parameters explanation:
        - scope: What permissions we're requesting (email, profile, openid)
        - response_type=code: We want authorization code (not implicit flow)
        - access_type=offline: We want refresh tokens
        - prompt=consent: Force consent screen (ensures we get refresh token)
        - state: CSRF protection parameter (optional but recommended)
        """
        base_url = "https://accounts.google.com/o/oauth2/auth"
        
        params = {
            "client_id": GOOGLE_CLIENT_ID,
            "redirect_uri": GOOGLE_REDIRECT_URI,
            "scope": "openid email profile",  # Standard OpenID Connect scopes
            "response_type": "code",           # Authorization code flow
            "access_type": "offline",          # Get refresh tokens
            "prompt": "consent"                # Force consent screen
        }
        
        if state:
            params["state"] = state  # CSRF protection
        
        # Build query string manually (more control than urllib)
        query_params = "&".join([f"{key}={value}" for key, value in params.items()])
        return f"{base_url}?{query_params}"
    
    async def handle_callback(self, code: str, state: str = None) -> Dict[str, Any]:
        """
        Handle OAuth callback and return JWT tokens + user info
        
        This is the core of our auth system:
        1. Exchange code for Google access token
        2. Use Google token to get user info
        3. Validate user email domain
        4. Create our own JWT tokens
        5. Return everything frontend needs
        """
        try:
            # Step 1: Exchange authorization code for Google tokens
            google_tokens = await exchange_code_for_tokens(code)
            google_access_token = google_tokens.get("access_token")
            
            if not google_access_token:
                raise AuthError("No access token received from Google")
            
            # Step 2: Get user information from Google
            user_info = await get_google_user_info(google_access_token)
            
            # Step 3: Validate university email requirement
            email = user_info.get("email", "").strip()
            if not validate_umbc_email(email):
                raise AuthError("Only @umbc.edu email addresses are permitted", 403)
            
            # Step 4: Create our application's JWT tokens
            user_payload = {
                "sub": user_info.get("id"),        # Google user ID
                "email": email,
                "name": user_info.get("name", ""),
                "picture": user_info.get("picture", "")
            }
            
            access_token = create_access_token(user_payload)
            refresh_token = create_refresh_token(user_payload)
            
            # Step 5: Return complete authentication response
            return {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # Seconds
                "user": {
                    "id": user_info.get("id"),
                    "email": email,
                    "name": user_info.get("name", ""),
                    "picture": user_info.get("picture", "")
                }
            }
            
        except AuthError:
            raise  # Re-raise auth errors as-is
        except Exception as e:
            print(f"OAuth callback error: {e}")
            raise AuthError("Authentication failed", 500)

# Initialize the OAuth handler
oauth_flow = GoogleOAuthFlow()