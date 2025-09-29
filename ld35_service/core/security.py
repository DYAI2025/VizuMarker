from fastapi import HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import os
from typing import Optional
import jwt
from datetime import datetime, timedelta

# Initialize security schemes
security = HTTPBearer(auto_error=False)

# Get secret key from environment
SECRET_KEY = os.getenv("SECRET_KEY", "your-default-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
AUTH_DISABLED = os.getenv("DISABLE_AUTH", "false").lower() in {"1", "true", "yes"}

def verify_token(credentials: HTTPAuthorizationCredentials = None) -> Optional[dict]:
    """
    Verify the JWT token from the Authorization header
    """
    if AUTH_DISABLED:
        # Return a synthetic payload so downstream checks succeed in local mode
        return {"sub": "dev-user", "scopes": ["local"], "auth": "disabled"}

    if not credentials:
        # No credentials supplied and auth is required
        return None
    
    token = credentials.credentials
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """
    Create a JWT access token
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def authenticate_user(token: str) -> Optional[dict]:
    """
    Authenticate user based on token
    In a real implementation, you would validate against a user database
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
        return payload
    except jwt.InvalidTokenError:
        return None

# CORS configuration is handled in main.py via middleware
