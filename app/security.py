# app/security.py
"""
Security utilities: password hashing (Argon2 primary, bcrypt fallback) and JWT helpers.
This file uses passlib.CryptContext with argon2 as first scheme. Existing bcrypt hashes
will still verify. You can re-hash on login to migrate users to argon2.
"""

from passlib.context import CryptContext
from datetime import datetime, timedelta
import jwt
from typing import Optional
from .config import JWT_SECRET, JWT_ALGORITHM, JWT_EXP_DELTA

# CryptContext: argon2 first (preferred), keep bcrypt for legacy verification.
# passlib will add scheme metadata to stored hashes, so verification chooses correct backend.
pwd_context = CryptContext(
    schemes=["argon2", "bcrypt"],
    deprecated="auto",
    # optional argon2 params can be tuned here, but passlib defaults are safe
)

# ---------------- Password helpers ----------------
def hash_password(password: str) -> str:
    """
    Hash password using the CryptContext (argon2 preferred).
    Returns the encoded hash string (includes scheme marker).
    """
    if password is None:
        password = ""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plaintext password against stored hash.
    Returns True/False.
    """
    if plain_password is None:
        plain_password = ""
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False

def password_needs_rehash(hashed_password: str) -> bool:
    """
    Use this to detect if a stored hash should be upgraded to the current preferred scheme.
    Example usage: after successful login, if password_needs_rehash(user.password_hash): 
    compute new_hash = hash_password(plain_password) and persist it for the user.
    """
    try:
        return pwd_context.needs_update(hashed_password)
    except Exception:
        return False

# ---------------- JWT helpers ----------------
def create_access_token(subject: str, expires_delta: Optional[int] = None) -> str:
    """
    Create a signed JWT for 'subject' (typically user email or user id).
    """
    expire = datetime.utcnow() + timedelta(seconds=(expires_delta if expires_delta is not None else JWT_EXP_DELTA))
    payload = {"sub": subject, "exp": expire}
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return token

def decode_access_token(token: str) -> Optional[dict]:
    """
    Decode and verify the JWT. Returns the payload or None if invalid/expired.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except Exception:
        return None
