"""
Authentication utilities for API.
"""
from fastapi.security import HTTPBearer

# HTTPBearer for authentication
auth_scheme = HTTPBearer(auto_error=False)

