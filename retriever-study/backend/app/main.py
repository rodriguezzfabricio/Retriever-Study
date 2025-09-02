from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import sqlite3
from datetime import datetime
import os

# Import our own modules
from app.data.local_db import db
from app.core.embeddings import embed_text, cosine_similarity, summarize_text
from app.core.toxicity import get_toxicity_score
from app.core.auth import oauth_flow, get_current_user, AuthError, verify_token, create_access_token
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
from slowapi.errors import RateLimitExceeded

# Initialize structured logging for production
import structlog
logger = structlog.get_logger()

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

class Group(GroupCreate):
    groupId: str
    ownerId: str
    members: List[str] = Field(default_factory=list)
    embedding: List[float] | None = None

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

class GoogleAuthCallback(BaseModel):
    """
    Model for handling Google OAuth callback data.
    
    Why this model exists:
    - Validates that callback contains required 'code' parameter
    - Optional 'state' parameter for CSRF protection
    - Ensures data types are correct before processing
    - Auto-generates API documentation
    """
    code: str = Field(
        ..., 
        description="Authorization code from Google OAuth flow",
        min_length=1,  # Ensure code is not empty
        max_length=2048  # Reasonable limit for OAuth codes
    )
    state: Optional[str] = Field(
        None, 
        description="CSRF protection parameter (optional but recommended)",
        max_length=256
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

class AuthError(BaseModel):
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
    title="Retriever Study API",
    description="Production-ready API for finding and managing study groups with OAuth authentication.",
    version="1.0.0"
)

# ========== PRODUCTION SECURITY SETUP ==========
# Order matters! See SECURITY_IMPLEMENTATION_GUIDE.md for detailed explanation

# 1. FIRST: Initialize rate limiter (must be first)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 2. SECOND: Request size validation middleware (block huge requests early)
@app.middleware("http")
async def request_size_middleware(request: Request, call_next):
    """Validate request size to prevent memory exhaustion attacks"""
    await validate_request_size(request)
    response = await call_next(request)
    return response

# 3. THIRD: Security headers middleware (modify final response)
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

# Environment-based origin configuration
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

if ENVIRONMENT == "production":
    # Production: Only allow your actual domain
    allowed_origins = [
        "https://yourdomain.com",
        "https://www.yourdomain.com"
    ]
else:
    # Development: Allow local development servers
    allowed_origins = [
        "http://localhost:3000",  # React development server
        "http://127.0.0.1:3000",  # Alternative localhost format
        "http://localhost:3001",  # Backup port if 3000 is busy
    ]

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
# These endpoints handle the complete OAuth 2.0 flow with Google

@limiter.limit("10/minute")
@app.get("/auth/google")
async def google_oauth_start(request: Request):
    """
    Start Google OAuth 2.0 authentication flow.
    
    Production Flow:
    1. Generate secure authorization URL with CSRF protection
    2. Redirect user to Google for authorization
    3. Google will redirect back to our callback URL with authorization code
    
    Security Features:
    - State parameter for CSRF protection
    - Specific scopes (email, profile, openid only)
    - Secure redirect URI validation
    
    Response: Redirect URL that frontend should navigate to
    """
    try:
        # Generate CSRF protection state parameter
        import secrets
        state = secrets.token_urlsafe(32)  # Cryptographically secure random string
        
        # Generate Google OAuth URL
        auth_url = oauth_flow.get_authorization_url(state=state)
        
        # In production, you might want to store the state in Redis/database
        # For now, we'll rely on frontend to handle state validation
        
        return {
            "auth_url": auth_url,
            "state": state  # Frontend should include this in callback
        }
        
    except Exception as e:
        print(f"OAuth start error: {e}")  # Log for debugging
        raise HTTPException(
            status_code=500,
            detail="Failed to initialize authentication. Please try again."
        )

@limiter.limit("5/minute")
@app.post("/auth/google/callback", response_model=TokenResponse)
async def google_oauth_callback(request: Request, callback_data: GoogleAuthCallback):
    """
    Handle Google OAuth callback and create user session.
    
    This is the most critical endpoint in our auth system:
    1. Validates authorization code with Google
    2. Retrieves user information from Google
    3. Enforces @umbc.edu email requirement
    4. Creates or updates user in our database
    5. Generates JWT tokens for our application
    6. Returns tokens + user info to frontend
    
    Security Considerations:
    - Authorization code is single-use (Google invalidates after exchange)
    - Email domain validation prevents unauthorized access
    - Database transaction ensures data consistency
    - JWT tokens have proper expiration times
    """
    try:
        # Step 1: Exchange authorization code for user data + tokens
        auth_result = await oauth_flow.handle_callback(
            code=callback_data.code,
            state=callback_data.state
        )
        
        # Step 2: Create or update user in our database
        google_user = auth_result["user"]
        
        user_record = db.create_or_update_oauth_user(
            google_id=google_user["id"],
            name=google_user["name"],
            email=google_user["email"], 
            picture_url=google_user.get("picture")
        )
        
        # Step 3: Update last login timestamp for analytics
        db.update_last_login(user_record["userId"])
        
        # Step 4: Format user profile for frontend
        user_profile = {
            "id": user_record["userId"],
            "name": user_record["name"],
            "email": user_record["email"],
            "picture": user_record.get("picture_url"),
            "courses": user_record.get("courses", []),
            "bio": user_record.get("bio", ""),
            "created_at": user_record.get("created_at")
        }
        
        # Step 5: Return complete authentication response
        return TokenResponse(
            access_token=auth_result["access_token"],
            refresh_token=auth_result["refresh_token"],
            expires_in=auth_result["expires_in"],
            user=user_profile
        )
        
    except AuthError as e:
        # OAuth-specific errors (domain restriction, Google API failures)
        raise HTTPException(
            status_code=e.status_code,
            detail=e.message
        )
    except Exception as e:
        print(f"OAuth callback error: {e}")  # Detailed logging for debugging
        raise HTTPException(
            status_code=500,
            detail="Authentication failed. Please try again."
        )

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
        print(f"Token refresh error: {e}")
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
        user_record = db.get_user_by_google_id(current_user["user_id"])
        
        if not user_record:
            raise HTTPException(
                status_code=404,
                detail="User profile not found"
            )
        
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
        print(f"Get profile error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve user profile"
        )

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
        print(f"Logout error: {e}")
        # Don't fail logout even if database update fails
        return {"message": "Logged out (with warnings)"}

# ========== APPLICATION ENDPOINTS ==========
# Original endpoints with authentication protection added

@limiter.limit("1000/minute")
@app.get("/health")
async def health_check(request: Request):
    """Basic health check to confirm the API is running."""
    return {"status": "ok", "version": app.version}

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
            logger.warning("Suspicious user bio detected", 
                         user=current_user["user_id"], 
                         bio_sample=user_updates.bio[:100])
        
        # Update user information with sanitized data
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
        user_embedding = embed_text(embedding_text)
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
        print(f"Profile update error: {e}")
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
        
        # Sanitize tags array
        sanitized_tags = [sanitize_string(tag, max_length=50) for tag in group_data.tags[:10]]  # Limit to 10 tags
        
        # Log suspicious input attempts
        if detect_suspicious_input(group_data.title):
            logger.warning("Suspicious group title detected", 
                         user=current_user["user_id"], 
                         title_sample=group_data.title[:100])
        
        # Create group with sanitized data
        created_group_dict = db.create_group(
            course_code=group_data.courseCode,  # This comes from enum/dropdown, should be safe
            title=sanitized_title,
            description=sanitized_description,
            tags=sanitized_tags,
            time_prefs=group_data.timePrefs,  # This comes from predefined options
            location=sanitized_location,
            owner_id=current_user["user_id"]  # From JWT token - secure!
        )
        
        # Validate text before AI embedding generation
        validated_embedding_text = f"Title: {sanitized_title}. Description: {sanitized_description}. Tags: {' '.join(sanitized_tags)}."
        validated_embedding_text = validate_ai_input(
            validated_embedding_text,
            max_length=2000,
            user_id=current_user["user_id"]
        )
        
        # Generate AI embedding for group matching
        group_embedding = embed_text(validated_embedding_text)
        
        # Store embedding in database
        db.update_group_embedding(created_group_dict['groupId'], group_embedding)
        
        # Return complete group object
        created_group_dict['embedding'] = group_embedding
        return Group(**created_group_dict)
        
    except Exception as e:
        print(f"Group creation error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to create study group"
        )

@limiter.limit("200/minute")
@app.get("/groups", response_model=List[Group])
async def get_groups(request: Request, courseCode: str):
    """
    Retrieves all groups for a specific course.
    """
    groups_data = db.get_groups_by_course(courseCode)
    return [Group(**group) for group in groups_data]

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
        updated_group = db.join_group(groupId, current_user["user_id"])
        
        if not updated_group:
            raise HTTPException(
                status_code=404, 
                detail="Study group not found or no longer available"
            )
        
        return Group(**updated_group)
        
    except Exception as e:
        print(f"Group join error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to join study group"
        )

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
            user_embedding = embed_text(user_text)
            db.update_user_embedding(user["userId"], user_embedding)
        
        # Get all available study groups
        all_groups = db.get_all_groups()
        
        # Calculate AI similarity scores
        group_similarities = []
        for group in all_groups:
            if group.get('embedding'):  # Only groups with AI embeddings
                # Cosine similarity: measures how "similar" user and group interests are
                similarity_score = cosine_similarity(user_embedding, group['embedding'])
                group_similarities.append((similarity_score, group))
        
        # Sort by AI similarity (best matches first)
        group_similarities.sort(key=lambda x: x[0], reverse=True)
        
        # Return top recommended groups
        recommended_groups = [group for _, group in group_similarities[:limit]]
        
        return [Group(**group) for group in recommended_groups]
        
    except Exception as e:
        print(f"Recommendations error: {e}")
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
    query_embedding = embed_text(validated_query)

    # 2. Get all groups with embeddings
    all_groups = db.get_all_groups()

    # 3. Calculate similarities between query and groups
    group_similarities = []
    for group in all_groups:
        if group.get('embedding'):  # Skip groups without embeddings
            similarity = cosine_similarity(query_embedding, group['embedding'])
            group_similarities.append((similarity, group))

    # 4. Sort by similarity (highest first) and return top N
    group_similarities.sort(key=lambda x: x[0], reverse=True)
    top_groups = [group for _, group in group_similarities[:limit]]

    return [Group(**group) for group in top_groups]

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
    return [Message(**msg) for msg in messages_data]

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

@app.on_event("shutdown")
def shutdown_event():
    """Close the database connection when the app shuts down."""
    db.close()
