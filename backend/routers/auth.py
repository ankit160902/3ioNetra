import asyncio

from fastapi import APIRouter, HTTPException, Header, Depends, status
from typing import Optional, Dict
from models.api_schemas import UserRegisterRequest, UserLoginRequest, AuthResponse, UserResponse
from services.auth_service import get_auth_service

router = APIRouter(prefix="/api/auth", tags=["authentication"])

# ----------------------------------------------------------------------------
# Helper function to verify auth token
# ----------------------------------------------------------------------------

async def get_current_user(authorization: Optional[str] = Header(None)):
    """Extract and verify user from Authorization header"""
    if not authorization:
        return None

    try:
        # Expected format: "Bearer <token>"
        if " " not in authorization:
            return None

        token = authorization.split(" ")[1]
        auth_service = get_auth_service()
        user = await asyncio.to_thread(auth_service.verify_token, token)
        return user
    except Exception:
        return None

# ----------------------------------------------------------------------------
# AUTHENTICATION ENDPOINTS
# ----------------------------------------------------------------------------

@router.post("/register", response_model=AuthResponse)
async def register_user(request: UserRegisterRequest):
    """
    Register a new user account with extended profile.
    """
    auth_service = get_auth_service()
    try:
        result = auth_service.register_user(
            name=request.name,
            email=request.email,
            password=request.password,
            phone=request.phone,
            gender=request.gender,
            dob=request.dob,
            profession=request.profession,
            preferred_deity=request.preferred_deity,
        )
        if not result:
            raise ValueError("Email already registered or database unavailable")
        return AuthResponse(
            user=UserResponse(**result["user"]),
            token=result["token"]
        )
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
    """
    Login an existing user.
    """
    auth_service = get_auth_service()
    try:
        result = auth_service.login_user(request.email, request.password)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        return AuthResponse(
            user=UserResponse(**result["user"]),
            token=result["token"]
        )
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
async def logout_user(authorization: Optional[str] = Header(None)):
    """
    Logout user and invalidate token.
    """
    if not authorization or " " not in authorization:
        return {"message": "Already logged out"}
        
    token = authorization.split(" ")[1]
    auth_service = get_auth_service()
    auth_service.logout_user(token)
    return {"message": "Successfully logged out"}
