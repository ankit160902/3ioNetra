import asyncio

from fastapi import APIRouter, HTTPException, Header, Cookie, Depends, Request, status
from fastapi.responses import JSONResponse
from typing import Optional, Dict
from models.api_schemas import UserRegisterRequest, UserLoginRequest, AuthResponse, UserResponse
from services.auth_service import get_auth_service

router = APIRouter(prefix="/api/auth", tags=["authentication"])

# Cookie name for httpOnly auth token (Fix 4)
AUTH_COOKIE_NAME = "auth_token"
AUTH_COOKIE_MAX_AGE = 30 * 24 * 3600  # 30 days (matches backend token expiry)

# ----------------------------------------------------------------------------
# Helper function to verify auth token
# ----------------------------------------------------------------------------

async def get_current_user(
    authorization: Optional[str] = Header(None),
    request: Request = None,
):
    """Extract and verify user from httpOnly cookie (preferred) or Authorization header (fallback).
    Returns None for anonymous access.
    Raises 401 if a token is provided but invalid/expired.
    """
    token = None

    # Priority 1: httpOnly cookie (Fix 4 — XSS-safe)
    if request and request.cookies.get(AUTH_COOKIE_NAME):
        token = request.cookies[AUTH_COOKIE_NAME]

    # Priority 2: Authorization header (backwards compat)
    if not token and authorization:
        if " " not in authorization:
            raise HTTPException(status_code=401, detail="Invalid authorization header")
        token = authorization.split(" ")[1]

    if not token:
        return None

    try:
        auth_service = get_auth_service()
        user = await asyncio.to_thread(auth_service.verify_token, token)
        if user is None:
            raise HTTPException(status_code=401, detail="Token expired or invalid")
        return user
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Authentication failed")

# ----------------------------------------------------------------------------
# AUTHENTICATION ENDPOINTS
# ----------------------------------------------------------------------------

def _set_auth_cookie(response: JSONResponse, token: str) -> JSONResponse:
    """Set httpOnly auth cookie on response (Fix 4)."""
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=False,  # Set to True in production (HTTPS only)
        samesite="lax",
        max_age=AUTH_COOKIE_MAX_AGE,
        path="/",
    )
    return response


@router.post("/register", response_model=AuthResponse)
async def register_user(request: UserRegisterRequest):
    """Register a new user account with extended profile."""
    auth_service = get_auth_service()
    try:
        result = await asyncio.to_thread(
            auth_service.register_user,
            name=request.name,
            email=request.email,
            password=request.password,
            phone=request.phone,
            gender=request.gender,
            dob=request.dob,
            profession=request.profession,
            preferred_deity=request.preferred_deity,
            rashi=request.rashi,
            gotra=request.gotra,
            nakshatra=request.nakshatra,
            temple_visits=request.favorite_temples,
            purchase_history=request.past_purchases,
        )
        if not result:
            raise ValueError("Email already registered or database unavailable")
        auth_data = AuthResponse(
            user=UserResponse(**result["user"]),
            token=result["token"]
        )
        # Fix 4: Set httpOnly cookie AND return token in body (backwards compat)
        response = JSONResponse(content=auth_data.model_dump())
        return _set_auth_cookie(response, result["token"])
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )


@router.post("/login", response_model=AuthResponse)
async def login_user(request: UserLoginRequest):
    """Login an existing user."""
    auth_service = get_auth_service()
    try:
        result = await asyncio.to_thread(auth_service.login_user, request.email, request.password)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        auth_data = AuthResponse(
            user=UserResponse(**result["user"]),
            token=result["token"]
        )
        # Fix 4: Set httpOnly cookie AND return token in body (backwards compat)
        response = JSONResponse(content=auth_data.model_dump())
        return _set_auth_cookie(response, result["token"])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}"
        )

@router.get("/verify", response_model=UserResponse)
async def verify_auth(user: Dict = Depends(get_current_user)):
    """
    Verify authentication token.
    """
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    return UserResponse(**user)

@router.post("/logout")
async def logout_user(authorization: Optional[str] = Header(None), request: Request = None):
    """Logout user, invalidate token, and clear cookie."""
    token = None
    # Check cookie first
    if request and request.cookies.get(AUTH_COOKIE_NAME):
        token = request.cookies[AUTH_COOKIE_NAME]
    # Fallback to header
    if not token and authorization and " " in authorization:
        token = authorization.split(" ")[1]

    if token:
        auth_service = get_auth_service()
        await asyncio.to_thread(auth_service.logout_user, token)

    # Fix 4: Clear httpOnly cookie on logout
    response = JSONResponse(content={"message": "Successfully logged out"})
    response.delete_cookie(AUTH_COOKIE_NAME, path="/")
    return response

@router.get("/product-names")
async def get_product_names():
    """Return list of product names for registration form dropdown."""
    try:
        from services.cache_service import get_cache_service
        cache = get_cache_service()

        # Check cache first (product names are static)
        cached = await cache.get("product_names")
        if cached is not None:
            return cached

        from services.product_service import get_product_service
        svc = get_product_service()
        # get_all_products is async-declared but uses sync PyMongo internally
        products = await asyncio.to_thread(
            lambda: list(svc.collection.find({"is_active": True}, {"name": 1}))
        ) if svc.collection is not None else []
        names = sorted(set(p.get("name", "") for p in products if p.get("name")))

        # Cache for 1 hour
        await cache.set("product_names", names, ttl=3600)
        return names
    except Exception:
        return []
