# Load environment variables FIRST - Critical for security config
from dotenv import load_dotenv
import os

# Load environment file based on environment
env_file = ".env.development" if os.getenv("ENVIRONMENT", "development") == "development" else ".env"
load_dotenv(env_file)

from fastapi import FastAPI, HTTPException, Depends, Request, WebSocket, WebSocketDisconnect
import json
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from typing import List, Dict, Any, Optional
import sqlite3
from datetime import datetime
import os

# Import our own modules
from app.data.local_db import db, GroupCapacityError  # Keep for compatibility
from app.data.async_db import initialize_async_database, close_async_database, user_repo, group_repo, async_db
from app.core.embeddings import embed_text, cosine_similarity, summarize_text
from app.core.toxicity import get_toxicity_score
from app.core.auth import (
    verify_google_id_token,
    get_current_user,
    AuthError,
    verify_token,
    create_access_token,
    create_refresh_token,
    validate_umbc_email,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    GOOGLE_CLIENT_ID,
)
from app.core.async_ai import initialize_ai_service, cleanup_ai_service, ai_service
from app.core.monitoring import (
    performance_tracker,
    pool_monitor,
    health_checker,
    get_performance_middleware,
    get_ai_operation_monitor,
)
from app.core.logging_config import (
    setup_production_logging,
    get_logger,
    error_tracker,
    security_logger,
    get_error_middleware,
)
from app.core.environment import (
    get_config,
    is_development,
    is_production,
    Environment,
)
from app.core.security import (
    limiter, 
    add_security_headers, 
    validate_request_size,
    sanitize_string,
    validate_email,
    detect_suspicious_input,
    validate_ai_input,
    validate_ai_computation_limits,
    _rate_limit_exceeded_handler
)
from app.core.time import get_semester_end_date
from slowapi.errors import RateLimitExceeded

# Load environment configuration
config = get_config()

# Initialize production logging system with environment-based settings
setup_production_logging(
    log_level=config.logging.level,
    log_file=config.logging.file_path,
    enable_console=config.is_development()
)
logger = get_logger('retriever_api')

# Initialize async components flag
async_initialized = False

# --- Business constants ---
DEFAULT_MAX_MEMBERS = 8
MAX_MEMBERS_MIN = 2
MAX_MEMBERS_MAX = 50

# --- Pydantic Models for Data Validation ---

class UserPrefs(BaseModel):
    studyStyle: List[str] = Field(default_factory=list)
    timeSlots: List[str] = Field(default_factory=list)
    locations: List[str] = Field(default_factory=list)

class UserCreate(BaseModel):
    name: str
    email: str
    courses: List[str] = Field(default_factory=list)
    bio: str
    prefs: UserPrefs

class User(UserCreate):
    userId: str
    embedding: List[float] | None = None

class GroupCreate(BaseModel):
    courseCode: str
    title: str
    description: str
    tags: List[str] = Field(default_factory=list)
    timePrefs: List[str] = Field(default_factory=list)
    location: str
    maxMembers: int = Field(
        default=DEFAULT_MAX_MEMBERS,
        ge=MAX_MEMBERS_MIN,
        le=MAX_MEMBERS_MAX,
        description="Maximum allowed members for the group"
    )
    semester: Optional[str] = None

class Group(GroupCreate):
    groupId: str
    ownerId: str
    members: List[str] = Field(default_factory=list)
    embedding: List[float] | None = None
    memberCount: int = Field(default=0, ge=0)
    isFull: bool = Field(default=False)
    expires_at: Optional[str] = None

    @validator('memberCount', pre=True, always=True)
    def compute_member_count(cls, value, values):
        members = values.get('members') or []
        if value is None:
            return len(members)
        return value

    @validator('isFull', pre=True, always=True)
    def compute_full_flag(cls, value, values):
        max_members = values.get('maxMembers') or DEFAULT_MAX_MEMBERS
        member_count = values.get('memberCount')
        if member_count is None:
            member_count = len(values.get('members') or [])
        if value is not None:
            return value
        return member_count >= max_members

def normalize_group_record(raw_group: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Normalize varying database shapes into the API's Group schema."""
    if not raw_group:
        return None

    def pick(*keys, default=None):
        for key in keys:
            if key in raw_group and raw_group[key] is not None:
                return raw_group[key]
        return default

    group_id = pick('groupId', 'group_id', 'id')
    course_code = pick('courseCode', 'course_code', 'subject', default='')
    title = pick('title', 'name', default='')
    description = pick('description', default='')
    location = pick('location', default='')
    owner_id = pick('ownerId', 'owner_id', 'created_by', default='')

    tags = pick('tags', default=[]) or []
    if isinstance(tags, str):
        try:
            tags = json.loads(tags)
        except json.JSONDecodeError:
            tags = [tag.strip() for tag in tags.split(',') if tag.strip()]

    time_prefs = pick('timePrefs', 'time_prefs', default=[]) or []
    if isinstance(time_prefs, str):
        try:
            time_prefs = json.loads(time_prefs)
        except json.JSONDecodeError:
            time_prefs = [slot.strip() for slot in time_prefs.split(',') if slot.strip()]

    members = pick('members', default=[]) or []
    if isinstance(members, str):
        try:
            members = json.loads(members)
        except json.JSONDecodeError:
            members = [member.strip() for member in members.split(',') if member.strip()]
    elif not isinstance(members, list):
        members = list(members)

    raw_max_members = pick('maxMembers', 'max_members', default=DEFAULT_MAX_MEMBERS)
    try:
        max_members = int(raw_max_members)
    except (TypeError, ValueError):
        max_members = DEFAULT_MAX_MEMBERS
    max_members = max(MAX_MEMBERS_MIN, min(MAX_MEMBERS_MAX, max_members))

    raw_member_count = pick('memberCount', 'member_count')
    try:
        member_count = int(raw_member_count) if raw_member_count is not None else len(members)
    except (TypeError, ValueError):
        member_count = len(members)

    embedding = raw_group.get('embedding')
    if isinstance(embedding, memoryview):
        embedding = list(embedding)

    normalized = {
        'groupId': group_id,
        'courseCode': course_code,
        'title': title,
        'description': description,
        'tags': tags,
        'timePrefs': time_prefs,
        'location': location,
        'ownerId': owner_id,
        'members': members,
        'embedding': embedding,
        'maxMembers': max_members,
        'memberCount': member_count,
        'isFull': member_count >= max_members,
        'expires_at': pick('expires_at'),
        'semester': pick('semester')
    }

    return normalized

class JoinGroupRequest(BaseModel):
    userId: str

class MessageCreate(BaseModel):
    groupId: str
    senderId: str
    content: str

class Message(MessageCreate):
    messageId: str
    createdAt: datetime
    toxicityScore: float
    # Optional display name for sender (computed on server)
    senderName: Optional[str] = None

# --- OAuth Authentication Models ---

class GoogleLoginRequest(BaseModel):
    """Payload sent from the SPA after Google sign-in."""

    id_token: str = Field(
        ...,
        description="Google-issued ID token returned to the SPA",
        min_length=10,
        max_length=4096,
    )

class TokenResponse(BaseModel):
    """
    Standardized response format for authentication tokens.
    
    Why standardization matters:
    - Frontend developers know exactly what to expect
    - Consistent across all auth endpoints
    - Follows OAuth 2.0 specification standards
    - Easy to add new fields later without breaking changes
    """
    access_token: str = Field(..., description="JWT access token for API requests")
    refresh_token: str = Field(..., description="Long-lived token for getting new access tokens")
    token_type: str = Field(default="bearer", description="Token type (always 'bearer' for JWT)")
    expires_in: int = Field(..., description="Access token lifetime in seconds")
    user: Dict[str, Any] = Field(..., description="User profile information")

class RefreshTokenRequest(BaseModel):
    """
    Request model for token refresh endpoint.
    
    Security considerations:
    - Only accepts refresh tokens (not access tokens)
    - Validates token format before processing
    - Limits token length to prevent abuse
    """
    refresh_token: str = Field(
        ...,
        description="Valid refresh token to exchange for new access token",
        min_length=10,  # JWT tokens are always long
        max_length=2048  # Reasonable upper limit
    )

class AuthErrorResponse(BaseModel):
    """
    Standardized error response for authentication failures.
    
    Why custom error format:
    - Consistent error structure across all endpoints
    - Helpful error messages for frontend developers
    - Security: Don't expose internal error details
    - Internationalization ready (error codes)
    """
    error: str = Field(..., description="Error type identifier")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error context")

class UserProfile(BaseModel):
    """
    User profile data structure for authenticated responses.
    
    Design decisions:
    - Only includes safe-to-expose user data
    - No sensitive fields like tokens or internal IDs
    - Consistent with frontend user context structure
    """
    id: str = Field(..., description="User unique identifier")
    name: str = Field(..., description="User display name")
    email: str = Field(..., description="User email address")
    picture: Optional[str] = Field(None, description="Profile picture URL")
    courses: List[str] = Field(default_factory=list, description="User's enrolled courses")
    bio: Optional[str] = Field(None, description="User biography")
    created_at: Optional[str] = Field(None, description="Account creation timestamp")

# --- FastAPI App Initialization ---

app = FastAPI(
    title=config.app_name,
    description="Production-ready API for finding and managing study groups with OAuth authentication.",
    version=config.version,
    debug=config.debug
)

# ========== PRODUCTION SECURITY SETUP ==========
# Order matters! See SECURITY_IMPLEMENTATION_GUIDE.md for detailed explanation

# 1. FIRST: Initialize rate limiter (must be first)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 2. SECOND: Error tracking middleware (catch all unhandled exceptions)
app.middleware("http")(get_error_middleware())

# 3. THIRD: Request size validation middleware (block huge requests early)
@app.middleware("http")
async def request_size_middleware(request: Request, call_next):
    """Validate request size to prevent memory exhaustion attacks"""
    await validate_request_size(request)
    response = await call_next(request)
    return response

# 4. FOURTH: Performance monitoring middleware (track all requests)
app.middleware("http")(get_performance_middleware())

# 5. FIFTH: Security headers middleware (modify final response)
app.middleware("http")(add_security_headers)

# --- CORS Configuration for Production ---
# 
# CORS (Cross-Origin Resource Sharing) Problem:
# Browsers implement Same-Origin Policy - requests between different domains are blocked
# Example: React app (http://localhost:3000) → FastAPI (http://localhost:8000) = BLOCKED
# 
# Production Security Strategy:
# 1. Development: Allow localhost origins for local development
# 2. Production: Only allow your actual domain
# 3. Credentials: Required for sending cookies/auth headers
# 4. Methods: Only allow HTTP methods you actually use
# 
# NEVER use allow_origins=["*"] with allow_credentials=True in production!
# This would allow any website to make authenticated requests to your API

import os
from fastapi.middleware.cors import CORSMiddleware

# Get CORS origins from environment configuration
allowed_origins = config.security.allowed_cors_origins

logger.info("CORS configuration loaded", 
           environment=config.environment.value,
           allowed_origins=allowed_origins)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,           # Specific domains only (security)
    allow_credentials=True,                  # Required for JWT tokens in headers
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],  # HTTP methods we use
    allow_headers=["*"],                     # Allow all headers (Authorization, Content-Type, etc.)
    expose_headers=["X-Total-Count"],        # Headers frontend can access (pagination, etc.)
)

# --- Helper Functions ---

def _generate_user_text_for_embedding(user: UserCreate) -> str:
    """Combines user info into a single string for embedding."""
    prefs_text = ' '.join([f"{k}:{v}" for k, v_list in user.prefs.dict().items() for v in v_list])
    courses_text = ' '.join(user.courses)
    return f"Bio: {user.bio}. Courses: {courses_text}. Preferences: {prefs_text}."

def _generate_group_text_for_embedding(group: GroupCreate) -> str:
    """Combines group info into a single string for embedding."""
    tags_text = ' '.join(group.tags)
    time_text = ' '.join(group.timePrefs)
    return f"Title: {group.title}. Description: {group.description}. Tags: {tags_text}. Time: {time_text}."

# --- API Endpoints ---

# ========== AUTHENTICATION ENDPOINTS ==========
# Modern Google Sign-In flow: SPA posts Google ID token to backend for verification


# Lightweight endpoint so the SPA can fetch Google OAuth settings at runtime.
@app.get("/auth/google/config")
async def get_google_oauth_config():
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Google OAuth is not configured.")
    return {"client_id": GOOGLE_CLIENT_ID}


@limiter.limit("10/minute")
@app.post("/auth/google_login", response_model=TokenResponse)
async def google_login(request: Request, login_request: GoogleLoginRequest):
    """Exchange a Google ID token for our application's JWT pair."""

    try:
        logger.info(
            "Google login attempt",
            endpoint="/auth/google_login",
            client_ip=getattr(request.client, "host", "unknown"),
            has_token=bool(login_request.id_token),
        )

        google_user = await verify_google_id_token(login_request.id_token)
        email = google_user.get("email")

        if not validate_umbc_email(email):
            raise HTTPException(status_code=403, detail="A valid UMBC email address is required.")

        google_id = google_user.get("sub")
        if not google_id:
            raise HTTPException(status_code=400, detail="Google token missing required subject claim.")

        display_name = google_user.get("name") or (email.split("@", 1)[0] if email else "Unknown User")
        sanitized_name = sanitize_string(display_name, max_length=100)
        picture_url = google_user.get("picture")

        if async_initialized and user_repo and hasattr(user_repo, "create_user"):
            user_record = await user_repo.create_user({
                "google_id": google_id,
                "name": sanitized_name,
                "email": email,
                "picture_url": picture_url,
            })
        else:
            user_record = db.create_or_update_oauth_user(
                google_id=google_id,
                name=sanitized_name,
                email=email,
                picture_url=picture_url,
            )

        db.update_last_login(user_record["userId"])

        token_payload = {
            "sub": google_id,
            "user_id": user_record["userId"],
            "email": email,
            "name": sanitized_name,
        }

        access_token = create_access_token(token_payload)
        refresh_token = create_refresh_token(token_payload)

        user_profile = {
            "id": user_record["userId"],
            "name": user_record["name"],
            "email": user_record["email"],
            "picture": user_record.get("picture_url"),
            "courses": user_record.get("courses", []),
            "bio": user_record.get("bio", ""),
            "created_at": user_record.get("created_at"),
        }

        logger.info("Google login successful", user_id=user_record["userId"])

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=user_profile,
        )

    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Google login failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to authenticate with Google.")

@limiter.limit("10/minute")
@app.post("/auth/refresh", response_model=TokenResponse)
async def refresh_access_token(request: Request, refresh_request: RefreshTokenRequest):
    """
    Exchange refresh token for new access token.
    
    Why refresh tokens matter:
    - Access tokens expire quickly (30 minutes) for security
    - Refresh tokens last longer (7 days) for user convenience  
    - This endpoint lets users stay logged in without re-authenticating
    
    Security Features:
    - Validates refresh token signature and expiration
    - Only accepts tokens with type="refresh"
    - Generates new access token with updated expiration
    - Could implement token rotation (new refresh token each time)
    """
    try:
        # Step 1: Verify and decode refresh token
        payload = verify_token(refresh_request.refresh_token)
        
        # Step 2: Validate token type (prevent access tokens being used)
        if payload.get("type") != "refresh":
            raise AuthError("Invalid token type for refresh operation", 400)
        
        # Step 3: Get user information from token
        user_id = payload.get("sub")
        if not user_id:
            raise AuthError("Invalid token: missing user identifier", 400)
        
        # Step 4: Verify user still exists and is active
        if async_initialized and user_repo:
            user_record = await user_repo.get_user_by_google_id(user_id)
        else:
            user_record = db.get_user_by_google_id(user_id)
            
        if not user_record:
            raise AuthError("User account not found or deactivated", 404)
        
        # Step 5: Create new access token with fresh expiration
        new_access_token = create_access_token({
            "sub": user_id,
            "email": payload.get("email"),
            "name": payload.get("name"),
            "picture": payload.get("picture")
        })
        
        # Step 6: Format user profile
        user_profile = {
            "id": user_record["userId"],
            "name": user_record["name"],
            "email": user_record["email"],
            "picture": user_record.get("picture_url"),
            "courses": user_record.get("courses", []),
            "bio": user_record.get("bio", "")
        }
        
        # Return new access token (keep same refresh token for now)
        return TokenResponse(
            access_token=new_access_token,
            refresh_token=refresh_request.refresh_token,  # Reuse existing refresh token
            expires_in=1800,  # 30 minutes in seconds
            user=user_profile
        )
        
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise HTTPException(
            status_code=401,
            detail="Token refresh failed. Please log in again."
        )

@limiter.limit("100/minute")
@app.get("/auth/me", response_model=UserProfile)
async def get_current_user_profile(request: Request, current_user = Depends(get_current_user)):
    """
    Get current user's profile information.
    
    This endpoint demonstrates how authentication protection works:
    - Depends(get_current_user) automatically validates JWT token
    - If token is valid, current_user contains user info
    - If token is invalid/missing, returns 401 automatically
    - No manual token validation needed in endpoint code
    
    Usage by frontend:
    - Include "Authorization: Bearer <token>" header
    - FastAPI handles token extraction and validation
    - Endpoint receives validated user data
    """
    try:
        # Get fresh user data from database (in case profile was updated)
        if async_initialized and user_repo:
            user_record = await user_repo.get_user_by_google_id(current_user["user_id"])
        else:
            user_record = db.get_user_by_google_id(current_user["user_id"])
        
        if not user_record:
            raise HTTPException(
                status_code=404,
                detail="User profile not found"
            )
        
        logger.info("Authenticated request to /auth/me",
                    user_id=user_record.get("userId"),
                    email=user_record.get("email"))
        
        return UserProfile(
            id=user_record["userId"],
            name=user_record["name"],
            email=user_record["email"],
            picture=user_record.get("picture_url"),
            courses=user_record.get("courses", []),
            bio=user_record.get("bio", ""),
            created_at=user_record.get("created_at")
        )
        
    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        logger.error(f"Get profile error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve user profile"
        )

@limiter.limit("100/minute")
@app.get("/users/{user_id}/groups", response_model=List[Group])
async def get_user_groups(
    request: Request,
    user_id: str,
    current_user = Depends(get_current_user)
):
    """Return groups the authenticated user belongs to."""
    try:
        requester_id = current_user.get("user_id")

        if not requester_id:
            raise HTTPException(status_code=401, detail="Authentication required")

        if user_id not in {requester_id, current_user.get("userId"), current_user.get("id")}:  # type: ignore[arg-type]
            raise HTTPException(status_code=403, detail="Cannot view other users' groups")

        if async_initialized and group_repo and hasattr(group_repo, "get_groups_for_member"):
            groups_data = await group_repo.get_groups_for_member(requester_id)
        else:
            groups_data = db.get_groups_for_user(requester_id)

        normalized_groups = [normalize_group_record(group) for group in groups_data]
        return [Group(**group) for group in normalized_groups if group]

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to retrieve user groups", user_id=user_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve joined groups")

@app.post("/auth/logout")
async def logout_user(current_user = Depends(get_current_user)):
    """
    Logout current user.
    
    JWT Token Logout Strategy:
    - JWTs are stateless - we can't "invalidate" them server-side
    - Frontend should delete tokens from storage
    - Optional: Maintain token blacklist in Redis for high-security apps
    - Update last_logout timestamp for analytics
    
    In production, you might:
    - Add token to blacklist database/Redis
    - Revoke Google refresh tokens
    - Clear any server-side sessions
    """
    try:
        # Update logout timestamp for analytics
        # db.update_last_logout(current_user["user_id"])  # Optional
        
        return {"message": "Successfully logged out"}
        
    except Exception as e:
        logger.error(f"Logout error: {e}")
        # Don't fail logout even if database update fails
        return {"message": "Logged out (with warnings)"}

# ========== APPLICATION ENDPOINTS ==========
# Original endpoints with authentication protection added

@limiter.limit("1000/minute")
@app.get("/health")
async def health_check(request: Request):
    """Comprehensive health check for production monitoring"""
    health_status = {
        "status": "ok", 
        "version": app.version,
        "timestamp": datetime.utcnow().isoformat(),
        "async_mode": async_initialized
    }
    
    if async_initialized:
        try:
            # Check async database health
            if async_db:
                db_health = await async_db.health_check()
                health_status["database"] = db_health
            
            # Check AI service health
            if ai_service:
                ai_health = await ai_service.health_check()
                health_status["ai_service"] = ai_health
                
            # Add performance metrics
            health_status["performance"] = performance_tracker.get_performance_summary(window_minutes=5)
                
        except Exception as e:
            health_status["status"] = "degraded"
            health_status["error"] = str(e)
    
    return health_status

@limiter.limit("100/minute")
@app.get("/metrics")
async def get_performance_metrics(request: Request, window_minutes: int = 15):
    """
    Get detailed performance metrics for monitoring and alerting.
    
    Production Monitoring Features:
    - Request timing statistics (avg, p95, min, max)
    - AI operation performance tracking
    - Database operation metrics
    - Connection pool utilization
    - System resource usage
    
    Use this endpoint for:
    - Application performance monitoring (APM)
    - Alerting on performance degradation
    - Capacity planning and scaling decisions
    - Troubleshooting performance issues
    """
    try:
        metrics = {
            "performance_summary": performance_tracker.get_performance_summary(window_minutes),
            "system_health": await health_checker.get_system_health(async_db, ai_service),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return metrics
        
    except Exception as e:
        logger.error("Failed to retrieve metrics", error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve performance metrics"
        )

@limiter.limit("50/minute")
@app.get("/admin/errors")
async def get_error_summary(request: Request, window_hours: int = 1):
    """
    Get error tracking summary for production monitoring.
    
    Production Error Monitoring:
    - Error counts by type and frequency
    - Recent error samples for debugging
    - Alert thresholds and trending
    - Security event aggregation
    
    Usage:
    - Operations dashboard error tracking
    - Automated alerting on error spikes
    - Root cause analysis for incidents
    - Performance degradation detection
    """
    try:
        error_summary = error_tracker.get_error_summary(window_hours)
        
        return {
            "error_tracking": error_summary,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error("Failed to retrieve error summary", error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve error tracking data"
        )

@limiter.limit("60/minute")
@app.put("/users/me", response_model=UserProfile)
async def update_current_user_profile(
    request: Request,
    user_updates: UserCreate,
    current_user = Depends(get_current_user)
):
    """
    Update the current authenticated user's profile information.
    
    Production API Design Changes:
    - Changed from POST /users to PUT /users/me (RESTful)
    - Requires authentication (user can only update their own profile)
    - User ID comes from JWT token (can't be faked)
    - Regenerates AI embeddings when profile changes
    
    Why this matters for production:
    - Security: Users can only modify their own data
    - Consistency: Profile updates trigger AI re-embedding
    - Analytics: Track which users update profiles most
    """
    try:
        # Get current user record from database
        if async_initialized and user_repo:
            user_record = await user_repo.get_user_by_google_id(current_user["user_id"])
        else:
            user_record = db.get_user_by_google_id(current_user["user_id"])
            
        if not user_record:
            raise HTTPException(status_code=404, detail="User profile not found")
        
        # Sanitize all user inputs
        sanitized_name = sanitize_string(user_updates.name, max_length=100)
        sanitized_bio = sanitize_string(user_updates.bio, max_length=500)
        
        # Validate email format (even though it comes from JWT)
        if not validate_email(current_user["email"]):
            raise HTTPException(status_code=400, detail="Invalid email format")
        
        # Log suspicious input attempts
        if detect_suspicious_input(user_updates.bio):
            security_logger.log_suspicious_input(
                input_type="user_bio",
                content_sample=user_updates.bio,
                user_id=current_user["user_id"]
            )
        
        # Update user information with sanitized data
        if async_initialized and user_repo:
            updated_user = await user_repo.update_user_by_google_id(
                google_id=current_user["user_id"],
                user_data={
                    'name': sanitized_name,
                    'email': current_user["email"],  # Email from JWT (can't be changed)
                    'picture_url': current_user.get("picture")
                }
            )
        else:
            updated_user = db.create_or_update_oauth_user(
                google_id=current_user["user_id"],
                name=sanitized_name,
                email=current_user["email"],  # Email from JWT (can't be changed)
                picture_url=current_user.get("picture")
            )
        
        # Update additional profile fields (courses, bio, preferences)
        # This would need new database methods in production
        # For now, simulate the update
        
        # Regenerate AI embedding with new profile data  
        embedding_text = _generate_user_text_for_embedding(user_updates)
        
        if async_initialized and ai_service:
            # Use async AI service with performance monitoring
            with get_ai_operation_monitor("user_profile_embedding"):
                user_embedding = await ai_service.generate_embedding_async(embedding_text)
        else:
            # Fallback to sync embedding
            user_embedding = embed_text(embedding_text)
            
        # Update embedding in database
        if async_initialized:
            # Would need async embedding update method in user_repo
            pass  # TODO: Implement async embedding update
        else:
            db.update_user_embedding(updated_user['userId'], user_embedding)
        
        return UserProfile(
            id=updated_user["userId"],
            name=updated_user["name"],
            email=updated_user["email"],
            picture=updated_user.get("picture_url"),
            courses=user_updates.courses,
            bio=user_updates.bio,
            created_at=updated_user.get("created_at")
        )
        
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        logger.error(f"Profile update error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to update profile"
        )

@limiter.limit("30/minute")
@app.post("/groups", response_model=Group, status_code=201)
async def create_study_group(
    request: Request,
    group_data: GroupCreate,
    current_user = Depends(get_current_user)
):
    """
    Create a new study group with the current user as owner.
    
    Production Security Updates:
    - Owner ID comes from authenticated user (can't be faked)
    - Only authenticated users can create groups
    - Automatic group ownership assignment
    - AI embeddings for group recommendations
    
    Business Logic:
    - User becomes first member of their created group
    - Group gets AI embedding for matching with users
    - Group is immediately available for others to join
    """
    try:
        # Sanitize all user inputs before database storage
        sanitized_title = sanitize_string(group_data.title, max_length=100)
        sanitized_description = sanitize_string(group_data.description, max_length=1000)
        sanitized_location = sanitize_string(group_data.location, max_length=200)
        sanitized_max_members = max(
            MAX_MEMBERS_MIN,
            min(MAX_MEMBERS_MAX, group_data.maxMembers)
        )
        
        # Sanitize tags array
        sanitized_tags = [sanitize_string(tag, max_length=50) for tag in group_data.tags[:10]]  # Limit to 10 tags
        
        # Log suspicious input attempts
        if detect_suspicious_input(group_data.title):
            security_logger.log_suspicious_input(
                input_type="group_title",
                content_sample=group_data.title,
                user_id=current_user["user_id"]
            )
        
        # Calculate expiration date
        expires_at = None
        if group_data.semester:
            end_date = get_semester_end_date(group_data.semester)
            if end_date:
                expires_at = end_date.isoformat()

        # Create group with sanitized data
        if async_initialized and group_repo:
            created_group_dict = await group_repo.create_group({
                'name': sanitized_title,  # Map title to name for new schema
                'description': sanitized_description,
                'subject': group_data.courseCode,  # Map courseCode to subject
                'max_members': sanitized_max_members,
                'created_by': current_user["user_id"],
                'semester': group_data.semester,
                'expires_at': expires_at
            })
        else:
            # Fallback to sync database
            created_group_dict = db.create_group(
                course_code=group_data.courseCode,
                title=sanitized_title,
                description=sanitized_description,
                tags=sanitized_tags,
                time_prefs=group_data.timePrefs,
                location=sanitized_location,
                owner_id=current_user["user_id"],
                max_members=sanitized_max_members,
                semester=group_data.semester,
                expires_at=expires_at
            )
        
        # Validate text before AI embedding generation
        validated_embedding_text = f"Title: {sanitized_title}. Description: {sanitized_description}. Tags: {' '.join(sanitized_tags)}."
        validated_embedding_text = validate_ai_input(
            validated_embedding_text,
            max_length=2000,
            user_id=current_user["user_id"]
        )
        
        # Generate AI embedding for group matching
        if async_initialized and ai_service:
            # Use async AI service with performance monitoring
            with get_ai_operation_monitor("group_embedding"):
                group_embedding = await ai_service.generate_embedding_async(validated_embedding_text)
        else:
            # Fallback to sync embedding
            group_embedding = embed_text(validated_embedding_text)
        
        # Store embedding in database
        normalized_group = normalize_group_record(created_group_dict)
        if not normalized_group:
            raise HTTPException(status_code=500, detail="Failed to normalize created group")

        if async_initialized:
            # Would need async embedding update method
            pass  # TODO: Implement async group embedding update
        else:
            db.update_group_embedding(normalized_group['groupId'], group_embedding)

        # Return complete group object
        normalized_group['embedding'] = group_embedding
        return Group(**normalized_group)
        
    except Exception as e:
        logger.error(f"Group creation error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to create study group"
        )

@limiter.limit("200/minute")
@app.get("/groups", response_model=List[Group])
async def get_groups(request: Request, courseCode: Optional[str] = None, offset: int = 0, limit: int = 20):
    """
    Retrieve study groups.

    - When `courseCode` is provided: return groups for that course.
    - When omitted: return groups across all courses (paginated).

    This change makes the "All Groups" page truly show all groups so users
    can discover study groups from any course, not just their first course.
    """
    if async_initialized and group_repo:
        if courseCode:
            groups_data = await group_repo.search_groups("", subject_filter=courseCode)
            paginated_groups = groups_data[offset:offset + limit]
        else:
            groups_data = await group_repo.get_groups_with_pagination(limit=limit, offset=offset)
            paginated_groups = groups_data
    else:
        if courseCode:
            groups_data = db.get_groups_by_course(courseCode)
        else:
            groups_data = db.get_all_groups()
        paginated_groups = groups_data[offset:offset + limit]

    normalized_groups = [normalize_group_record(group) for group in paginated_groups]
    return [Group(**group) for group in normalized_groups if group]

@limiter.limit("100/minute")
@app.get("/groups/{groupId}", response_model=Group)
async def get_group_details(request: Request, groupId: str):
    """
    Retrieves detailed information for a specific study group.

    Production Features:
    - Async database operations for better performance
    - Detailed group information including member list
    - Rate limited to prevent abuse
    - Proper error handling for non-existent groups
    """
    try:
        if async_initialized and group_repo:
            # Use async database for better performance
            group_data = await group_repo.get_group_by_id(groupId)
        else:
            # Fallback to sync database
            group_data = db.get_group_by_id(groupId)

        if not group_data:
            raise HTTPException(
                status_code=404,
                detail="Study group not found"
            )

        normalized_group = normalize_group_record(group_data)
        if not normalized_group:
            raise HTTPException(status_code=500, detail="Failed to normalize group data")

        return Group(**normalized_group)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to retrieve group details",
                    group_id=groupId,
                    error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve group details"
        )

@limiter.limit("50/minute")
@app.post("/groups/{groupId}/join", response_model=Group)
async def join_study_group(
    request: Request,
    groupId: str,
    current_user = Depends(get_current_user)
):
    """
    Add current authenticated user to a study group.
    
    Production Security Updates:
    - User ID comes from JWT token (can't join as someone else)
    - Only authenticated users can join groups
    - Automatic duplicate membership prevention
    - Audit trail of group joins
    """
    try:
        # Join group with authenticated user ID
        try:
            updated_group = db.join_group(groupId, current_user["user_id"])
        except (GroupCapacityError, ValueError) as capacity_error:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "GROUP_FULL",
                    "message": str(capacity_error)
                }
            ) from capacity_error

        if not updated_group:
            raise HTTPException(
                status_code=404,
                detail="Study group not found or no longer available"
            )

        normalized_group = normalize_group_record(updated_group)
        if not normalized_group:
            raise HTTPException(status_code=500, detail="Failed to normalize group data")

        return Group(**normalized_group)
        
    except Exception as e:
        logger.error(f"Group join error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to join study group"
        )

@limiter.limit("50/minute")
@app.post("/groups/{groupId}/leave", response_model=Group)
async def leave_study_group(
    request: Request,
    groupId: str,
    current_user = Depends(get_current_user)
):
    """
    Remove current authenticated user from a study group.

    Security:
    - User ID is taken from validated JWT
    - Only authenticated users can leave
    """
    try:
        user_id = current_user["user_id"]

        # Use async repo if available, otherwise fallback to local sqlite
        if async_initialized and group_repo and hasattr(group_repo, "leave_group"):
            updated_group = await group_repo.leave_group(groupId, user_id)
        else:
            updated_group = db.leave_group(groupId, user_id)

        if not updated_group:
            raise HTTPException(status_code=404, detail="Study group not found")

        normalized_group = normalize_group_record(updated_group)
        if not normalized_group:
            raise HTTPException(status_code=500, detail="Failed to normalize group data")

        return Group(**normalized_group)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to leave group", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to leave study group")

@limiter.limit("20/minute")
@app.get("/recommendations", response_model=List[Group])
async def get_personalized_recommendations(
    request: Request,
    current_user = Depends(get_current_user),
    limit: int = 5
):
    """
    Get AI-powered study group recommendations for the current user.
    
    This is the core AI feature of our platform:
    1. Uses authenticated user's profile data (secure)
    2. Computes AI embeddings on-demand if needed
    3. Finds groups with similar study patterns/interests
    4. Returns personalized recommendations
    
    Production AI/ML Considerations:
    - Embedding computation is expensive (cache results)
    - Similarity calculations scale O(n) with group count
    - Consider pre-computing recommendations for active users
    - Monitor recommendation quality with user feedback
    """
    try:
        # Check AI computation limits
        validate_ai_computation_limits(current_user["user_id"], "recommendations")
        
        # Get current user from database by Google ID
        if async_initialized and user_repo:
            user = await user_repo.get_user_by_google_id(current_user["user_id"])
        else:
            user = db.get_user_by_google_id(current_user["user_id"])
            
        if not user:
            raise HTTPException(
                status_code=404, 
                detail="User profile not found for recommendations"
            )
        
        # Ensure user has AI embedding for matching
        user_embedding = user.get('embedding')
        if not user_embedding:
            # Validate and sanitize user data before AI processing
            user_bio = validate_ai_input(
                user.get('bio', ''), 
                max_length=1000, 
                user_id=current_user["user_id"]
            )
            
            # Compute embedding from validated user profile
            user_text = f"Bio: {user_bio}. Courses: {' '.join(user.get('courses', []))}."
            
            if async_initialized and ai_service:
                # Use async AI service with performance monitoring
                with get_ai_operation_monitor("user_recommendations_embedding"):
                    user_embedding = await ai_service.generate_embedding_async(user_text)
            else:
                # Fallback to sync embedding
                user_embedding = embed_text(user_text)
                
            # Update embedding in database
            if not async_initialized:
                db.update_user_embedding(user["userId"], user_embedding)
        
        # Get all available study groups
        if async_initialized and group_repo:
            # Use async database with pagination
            all_groups = await group_repo.get_groups_with_pagination(limit=100)
        else:
            # Fallback to sync database
            all_groups = db.get_all_groups()

        normalized_groups = [normalize_group_record(group) for group in all_groups]

        # Calculate AI similarity scores
        group_similarities = []
        for group in normalized_groups:
            if not group:
                continue
            if group.get('embedding'):  # Only groups with AI embeddings
                # Cosine similarity: measures how "similar" user and group interests are
                similarity_score = cosine_similarity(user_embedding, group['embedding'])
                group_similarities.append((similarity_score, group))

        # Sort by AI similarity (best matches first)
        group_similarities.sort(key=lambda x: x[0], reverse=True)

        # Return top recommended groups
        recommended_groups = [group for _, group in group_similarities[:limit]]

        return [Group(**group) for group in recommended_groups if group]
        
    except Exception as e:
        logger.error(f"Recommendations error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to generate recommendations"
        )

@limiter.limit("30/minute")
@app.get("/search", response_model=List[Group])
async def search_groups(request: Request, q: str, limit: int = 10):
    """
    Searches groups using natural language query with vector similarity.
    """
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query parameter 'q' cannot be empty")

    # Validate search query for AI processing
    validated_query = validate_ai_input(
        q, 
        max_length=200, 
        user_id=request.client.host if hasattr(request, 'client') else 'anonymous'
    )
    
    # Check AI computation limits for search
    validate_ai_computation_limits(
        request.client.host if hasattr(request, 'client') else 'anonymous', 
        "search"
    )

    # Convert validated search query to embedding
    if async_initialized and ai_service:
        # Use async AI service for embedding generation with monitoring
        with get_ai_operation_monitor("search_embedding"):
            query_embedding = await ai_service.generate_embedding_async(validated_query)
    else:
        # Fallback to sync embedding
        query_embedding = embed_text(validated_query)

    # 2. Get all groups with embeddings
    if async_initialized and group_repo:
        # Use async database operations
        all_groups = await group_repo.get_groups_with_pagination(limit=100)
    else:
        # Fallback to sync database
        all_groups = db.get_all_groups()

    normalized_groups = [normalize_group_record(group) for group in all_groups]

    # 3. Calculate similarities between query and groups
    group_similarities = []
    for group in normalized_groups:
        if group and group.get('embedding'):  # Skip groups without embeddings
            similarity = cosine_similarity(query_embedding, group['embedding'])
            group_similarities.append((similarity, group))

    # 4. Sort by similarity (highest first) and return top N
    group_similarities.sort(key=lambda x: x[0], reverse=True)
    top_groups = [group for _, group in group_similarities[:limit]]

    return [Group(**group) for group in top_groups if group]

@app.post("/messages", response_model=Message, status_code=201)
def create_message(message_data: MessageCreate):
    """
    Creates a new message with toxicity filtering.
    Blocks toxic messages and stores non-toxic ones.
    """
    # 1. Check toxicity of the message content (fail fast principle)
    toxicity_score = get_toxicity_score(message_data.content)
    
    # 2. Define toxicity threshold (as per SSOT spec)
    TOXICITY_THRESHOLD = 0.8
    
    # 3. If message is too toxic, block it with helpful error
    if toxicity_score >= TOXICITY_THRESHOLD:
        raise HTTPException(
            status_code=400, 
            detail={
                "error": "Message contains toxic content and was blocked",
                "suggestion": "Please rephrase your message in a more respectful way",
                "toxicity_score": toxicity_score
            }
        )
    
    # 4. Store the non-toxic message with its toxicity score
    created_message_dict = db.create_message(
        group_id=message_data.groupId,
        sender_id=message_data.senderId, 
        content=message_data.content,
        toxicity_score=toxicity_score
    )
    
    return Message(**created_message_dict)

@app.get("/messages", response_model=List[Message])
def get_messages(groupId: str, limit: int = 50):
    """
    Retrieves messages for a specific group.
    """
    messages_data = db.get_messages_by_group(groupId, limit)
    enriched: List[Message] = []
    for msg in messages_data:
        # Try to resolve a friendly sender name
        sender_name = None
        try:
            user = db.get_user_by_google_id(msg.get("senderId"))
            if not user and msg.get("senderId"):
                user = db.get_user_by_id(msg.get("senderId"))
            if user:
                sender_name = user.get("name")
        except Exception:
            sender_name = None

        payload = {**msg, "senderName": sender_name}
        enriched.append(Message(**payload))
    return enriched

@app.post("/summarize")
def summarize_group_chat(groupId: str, since: str = None):
    """
    Summarizes recent messages in a group into 3-5 bullet points.
    """
    # 1. Get recent messages (last 20 for good context without model limits)
    recent_messages = db.get_messages_by_group(groupId, limit=20)
    
    # 2. Handle edge case: too few messages for meaningful summary
    if len(recent_messages) < 3:
        return {"bullets": ["No recent updates."]}
    
    # 3. Combine message content into one text for summarization
    message_texts = [msg["content"] for msg in recent_messages]
    combined_text = " ".join(message_texts)
    
    # 4. Generate summary bullets (3-5 bullets, ≤400 chars total)
    summary_bullets = summarize_text(combined_text, max_len=400)
    
    return {"bullets": summary_bullets}

# ========== WEBSOCKET CHAT ENDPOINTS ==========
# Real-time chat functionality for study groups

from app.core.websocket import connection_manager, authenticate_websocket_user

@app.websocket("/ws/groups/{group_id}")
async def websocket_group_chat(websocket: WebSocket, group_id: str, token: str = None):
    """
    WebSocket endpoint for real-time group chat

    Connection Process:
    1. Extract JWT token from query parameter
    2. Authenticate user and verify group membership
    3. Join chat room and handle messages
    4. Clean up on disconnect

    Usage: ws://localhost:8000/ws/groups/{groupId}?token={jwt_token}
    """
    user_data = None

    try:
        # Authenticate WebSocket connection
        user_data = await authenticate_websocket_user(websocket, token)
        if not user_data:
            return  # Connection closed by auth function

        user_id = user_data['user_id']

        # Connect user to group chat room
        connected = await connection_manager.connect(
            websocket, group_id, user_id, user_data
        )

        if not connected:
            return  # Connection failed (not a group member)

        # Handle incoming messages
        while True:
            try:
                # Receive message from client
                raw_data = await websocket.receive_text()
                message_data = json.loads(raw_data)

                # Validate message format
                if not isinstance(message_data, dict):
                    continue

                # Handle different message types
                message_type = message_data.get('type', 'message')

                if message_type == 'message':
                    # SECURITY: sanitize content and enforce length
                    raw_content = message_data.get('content', '')
                    safe_content = (raw_content or '').strip()[:2000]

                    # Optional: simple toxicity filter to match REST behavior
                    toxicity_score = get_toxicity_score(safe_content)
                    TOXICITY_THRESHOLD = 0.8
                    if toxicity_score >= TOXICITY_THRESHOLD:
                        # Notify sender only; don't broadcast toxic content
                        await websocket.send_text(json.dumps({
                            'type': 'error',
                            'error': 'TOXIC_MESSAGE_BLOCKED'
                        }))
                        continue

                    # Persist message to DB so history survives reconnects
                    try:
                        created = db.create_message(
                            group_id=group_id,
                            sender_id=user_id,
                            content=safe_content,
                            toxicity_score=toxicity_score
                        )
                    except Exception as e:
                        logger.error("Failed to persist message", group_id=group_id, user_id=user_id, error=str(e))
                        continue

                    # Resolve sender display name (prefer DB, fallback to token)
                    sender_name = None
                    try:
                        prof = db.get_user_by_google_id(user_id) or db.get_user_by_id(user_id)
                        if prof:
                            sender_name = prof.get('name')
                    except Exception:
                        sender_name = None
                    if not sender_name:
                        sender_name = (user_data.get('raw') or {}).get('name')

                    # Broadcast normalized payload with server authoritative fields
                    sanitized_payload = {
                        'type': 'message',
                        'messageId': created.get('messageId'),
                        'groupId': group_id,
                        'senderId': user_id,
                        'senderName': sender_name,
                        'content': safe_content,
                        'createdAt': created.get('createdAt')
                    }
                    await connection_manager.send_message_to_group(group_id, sanitized_payload, user_id)

                elif message_type == 'ping':
                    # Keepalive ping
                    await websocket.send_text(json.dumps({
                        'type': 'pong',
                        'timestamp': datetime.utcnow().isoformat()
                    }))

                # Add more message types as needed (typing, reactions, etc.)

            except WebSocketDisconnect:
                logger.info("WebSocket client disconnected",
                           group_id=group_id,
                           user_id=user_id)
                break

            except json.JSONDecodeError:
                logger.warning("Invalid JSON received",
                              group_id=group_id,
                              user_id=user_id)
                continue

            except Exception as e:
                logger.error("WebSocket message handling error",
                           group_id=group_id,
                           user_id=user_id,
                           error=str(e))
                break

    except Exception as e:
        logger.error("WebSocket connection error",
                    group_id=group_id,
                    error=str(e))

    finally:
        # Always clean up connection
        if user_data:
            await connection_manager.disconnect(group_id, user_data['user_id'])

@limiter.limit("100/minute")
@app.get("/ws/groups/{group_id}/stats")
async def get_group_chat_stats(request: Request, group_id: str, current_user = Depends(get_current_user)):
    """
    Get real-time chat statistics for a group

    Useful for:
    - Showing active members count
    - Debugging connection issues
    - Monitoring chat health
    """
    try:
        stats = connection_manager.get_group_stats(group_id)
        return {
            "group_id": group_id,
            "chat_stats": stats,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error("Failed to get chat stats", group_id=group_id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve chat statistics"
        )

@app.on_event("startup")
async def startup_event():
    """Initialize async database and AI services for production performance"""
    global async_initialized
    try:
        # Get database URL from environment configuration
        database_url = config.get_database_url()
        
        if database_url.startswith("postgresql://") or database_url.startswith("asyncpg://"):
            # Production: Initialize async PostgreSQL connection pool
            logger.info("Initializing production async database pool")
            await initialize_async_database(database_url)
            
            # Initialize async AI service with environment-specific thread pools
            initialize_ai_service(max_workers=config.ai.thread_pool_size)
            
            # Start connection pool monitoring
            await pool_monitor.start_monitoring(async_db)
            
            async_initialized = True
            logger.info("Production async services initialized successfully")
        else:
            # Development: Keep using SQLite with sync operations
            logger.info("Development mode: using SQLite with sync operations", 
                       database_type="sqlite", 
                       environment=config.environment.value)
            async_initialized = False
            
    except Exception as e:
        logger.error("Failed to initialize async services", error=str(e))
        # Fall back to sync operations
        async_initialized = False

@app.on_event("shutdown")
async def shutdown_event():
    """Close database connections and cleanup resources when the app shuts down"""
    try:
        if async_initialized:
            # Cleanup async services
            await pool_monitor.stop_monitoring()
            await cleanup_ai_service()
            await close_async_database()
            logger.info("Async services shutdown complete")
        else:
            # Cleanup sync database
            db.close()
            logger.info("Sync database closed")
    except Exception as e:
        logger.error("Error during shutdown", error=str(e))

from slowapi.errors import RateLimitExceeded

# Load environment configuration
config = get_config()

# Initialize production logging system with environment-based settings
setup_production_logging(
    log_level=config.logging.level,
    log_file=config.logging.file_path,
    enable_console=config.is_development()
)
logger = get_logger('retriever_api')

# Initialize async components flag
async_initialized = False

# --- Business constants ---
DEFAULT_MAX_MEMBERS = 8
MAX_MEMBERS_MIN = 2
MAX_MEMBERS_MAX = 50

# --- Pydantic Models for Data Validation ---

class UserPrefs(BaseModel):
    studyStyle: List[str] = Field(default_factory=list)
    timeSlots: List[str] = Field(default_factory=list)
    locations: List[str] = Field(default_factory=list)

class UserCreate(BaseModel):
    name: str
    email: str
    courses: List[str] = Field(default_factory=list)
    bio: str
    prefs: UserPrefs

class User(UserCreate):
    userId: str
    embedding: List[float] | None = None

class GroupCreate(BaseModel):
    courseCode: str
    title: str
    description: str
    tags: List[str] = Field(default_factory=list)
    timePrefs: List[str] = Field(default_factory=list)
    location: str
    maxMembers: int = Field(
        default=DEFAULT_MAX_MEMBERS,
        ge=MAX_MEMBERS_MIN,
        le=MAX_MEMBERS_MAX,
        description="Maximum allowed members for the group"
    )

class Group(GroupCreate):
    groupId: str
    ownerId: str
    members: List[str] = Field(default_factory=list)
    embedding: List[float] | None = None
    memberCount: int = Field(default=0, ge=0)
    isFull: bool = Field(default=False)

    @validator('memberCount', pre=True, always=True)
    def compute_member_count(cls, value, values):
        members = values.get('members') or []
        if value is None:
            return len(members)
        return value

    @validator('isFull', pre=True, always=True)
    def compute_full_flag(cls, value, values):
        max_members = values.get('maxMembers') or DEFAULT_MAX_MEMBERS
        member_count = values.get('memberCount')
        if member_count is None:
            member_count = len(values.get('members') or [])
        if value is not None:
            return value
        return member_count >= max_members


def normalize_group_record(raw_group: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Normalize varying database shapes into the API's Group schema."""
    if not raw_group:
        return None

    def pick(*keys, default=None):
        for key in keys:
            if key in raw_group and raw_group[key] is not None:
                return raw_group[key]
        return default

    group_id = pick('groupId', 'group_id', 'id')
    course_code = pick('courseCode', 'course_code', 'subject', default='')
    title = pick('title', 'name', default='')
    description = pick('description', default='')
    location = pick('location', default='')
    owner_id = pick('ownerId', 'owner_id', 'created_by', default='')

    tags = pick('tags', default=[]) or []
    if isinstance(tags, str):
        try:
            tags = json.loads(tags)
        except json.JSONDecodeError:
            tags = [tag.strip() for tag in tags.split(',') if tag.strip()]

    time_prefs = pick('timePrefs', 'time_prefs', default=[]) or []
    if isinstance(time_prefs, str):
        try:
            time_prefs = json.loads(time_prefs)
        except json.JSONDecodeError:
            time_prefs = [slot.strip() for slot in time_prefs.split(',') if slot.strip()]

    members = pick('members', default=[]) or []
    if isinstance(members, str):
        try:
            members = json.loads(members)
        except json.JSONDecodeError:
            members = [member.strip() for member in members.split(',') if member.strip()]
    elif not isinstance(members, list):
        members = list(members)

    raw_max_members = pick('maxMembers', 'max_members', default=DEFAULT_MAX_MEMBERS)
    try:
        max_members = int(raw_max_members)
    except (TypeError, ValueError):
        max_members = DEFAULT_MAX_MEMBERS
    max_members = max(MAX_MEMBERS_MIN, min(MAX_MEMBERS_MAX, max_members))

    raw_member_count = pick('memberCount', 'member_count')
    try:
        member_count = int(raw_member_count) if raw_member_count is not None else len(members)
    except (TypeError, ValueError):
        member_count = len(members)

    embedding = raw_group.get('embedding')
    if isinstance(embedding, memoryview):
        embedding = list(embedding)

    normalized = {
        'groupId': group_id,
        'courseCode': course_code,
        'title': title,
        'description': description,
        'tags': tags,
        'timePrefs': time_prefs,
        'location': location,
        'ownerId': owner_id,
        'members': members,
        'embedding': embedding,
        'maxMembers': max_members,
        'memberCount': member_count,
        'isFull': member_count >= max_members,
    }

    return normalized

class JoinGroupRequest(BaseModel):
    userId: str

class MessageCreate(BaseModel):
    groupId: str
    senderId: str
    content: str

class Message(MessageCreate):
    messageId: str
    createdAt: datetime
    toxicityScore: float

# --- OAuth Authentication Models ---

class GoogleLoginRequest(BaseModel):
    """Payload sent from the SPA after Google sign-in."""

    id_token: str = Field(
        ...,
        description="Google-issued ID token returned to the SPA",
        min_length=10,
        max_length=4096,
    )

class TokenResponse(BaseModel):
    """
    Standardized response format for authentication tokens.
    
    Why standardization matters:
    - Frontend developers know exactly what to expect
    - Consistent across all auth endpoints
    - Follows OAuth 2.0 specification standards
    - Easy to add new fields later without breaking changes
    """
    access_token: str = Field(..., description="JWT access token for API requests")
    refresh_token: str = Field(..., description="Long-lived token for getting new access tokens")
    token_type: str = Field(default="bearer", description="Token type (always 'bearer' for JWT)")
    expires_in: int = Field(..., description="Access token lifetime in seconds")
    user: Dict[str, Any] = Field(..., description="User profile information")

class RefreshTokenRequest(BaseModel):
    """
    Request model for token refresh endpoint.
    
    Security considerations:
    - Only accepts refresh tokens (not access tokens)
    - Validates token format before processing
    - Limits token length to prevent abuse
    """
    refresh_token: str = Field(
        ...,
        description="Valid refresh token to exchange for new access token",
        min_length=10,  # JWT tokens are always long
        max_length=2048  # Reasonable upper limit
    )

class AuthErrorResponse(BaseModel):
    """
    Standardized error response for authentication failures.
    
    Why custom error format:
    - Consistent error structure across all endpoints
    - Helpful error messages for frontend developers
    - Security: Don't expose internal error details
    - Internationalization ready (error codes)
    """
    error: str = Field(..., description="Error type identifier")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error context")

class UserProfile(BaseModel):
    """
    User profile data structure for authenticated responses.
    
    Design decisions:
    - Only includes safe-to-expose user data
    - No sensitive fields like tokens or internal IDs
    - Consistent with frontend user context structure
    """
    id: str = Field(..., description="User unique identifier")
    name: str = Field(..., description="User display name")
    email: str = Field(..., description="User email address")
    picture: Optional[str] = Field(None, description="Profile picture URL")
    courses: List[str] = Field(default_factory=list, description="User's enrolled courses")
    bio: Optional[str] = Field(None, description="User biography")
    created_at: Optional[str] = Field(None, description="Account creation timestamp")

