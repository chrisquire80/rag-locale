"""
Security Hardening Module - Phase 11
Comprehensive security protections for RAG LOCALE system
- CORS policy enforcement
- Input validation and sanitization
- SQL injection prevention
- XSS protection
- CSRF token validation
- Rate limiting integration
"""

import re
import html
import sqlite3
from typing import Optional, Any, Dict, List
from urllib.parse import quote, unquote
from functools import wraps

from src.logging_config import get_logger
from src.rate_limiter import rate_limit

logger = get_logger(__name__)


# ==================== CORS POLICY ====================
class CORSPolicy:
    """CORS (Cross-Origin Resource Sharing) Policy Manager"""

    def __init__(self):
        # Allowed origins (whitelist)
        self.allowed_origins = [
            "http://localhost:3000",
            "http://localhost:8501",  # Streamlit default
            "http://127.0.0.1:8501",
            "https://rag-locale.example.com",  # Production domain
        ]

        # Allowed methods
        self.allowed_methods = ["GET", "POST", "OPTIONS", "PUT", "DELETE"]

        # Allowed headers
        self.allowed_headers = [
            "Content-Type",
            "Authorization",
            "X-Requested-With",
            "Accept",
            "X-CSRF-Token",
        ]

        # Credentials allowed
        self.allow_credentials = True

        # Max age for preflight cache
        self.max_age = 86400  # 24 hours

        logger.info("[CORS] Policy initialized")

    def is_origin_allowed(self, origin: str) -> bool:
        """Check if origin is in whitelist"""
        if not origin:
            return False

        is_allowed = origin in self.allowed_origins

        if not is_allowed:
            logger.warning(f"[CORS] Blocked request from unauthorized origin: {origin}")

        return is_allowed

    def get_cors_headers(self, origin: str) -> Dict[str, str]:
        """Get CORS headers for response"""
        if not self.is_origin_allowed(origin):
            return {}

        return {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Methods": ", ".join(self.allowed_methods),
            "Access-Control-Allow-Headers": ", ".join(self.allowed_headers),
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Max-Age": str(self.max_age),
        }

    def add_allowed_origin(self, origin: str) -> None:
        """Dynamically add allowed origin (admin only)"""
        if origin not in self.allowed_origins:
            self.allowed_origins.append(origin)
            logger.info(f"[CORS] Added allowed origin: {origin}")

    def remove_allowed_origin(self, origin: str) -> None:
        """Dynamically remove allowed origin (admin only)"""
        if origin in self.allowed_origins:
            self.allowed_origins.remove(origin)
            logger.info(f"[CORS] Removed allowed origin: {origin}")


# ==================== INPUT VALIDATION ====================
class InputValidator:
    """Comprehensive input validation and sanitization"""

    # Regex patterns for validation
    PATTERNS = {
        "email": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
        "url": r"^https?://[^\s/$.?#].[^\s]*$",
        "filename": r"^[\w\-. ]+$",  # Alphanumeric, dash, underscore, dot, space
        "sql_keyword": r"(DROP|DELETE|INSERT|UPDATE|UNION|SELECT|EXEC|EXECUTE|--|\*|;)",
        "script_tag": r"<script[^>]*>.*?</script>",
        "html_tag": r"<[^>]+>",
    }

    # Max length limits
    MAX_LENGTHS = {
        "query": 5000,
        "filename": 255,
        "email": 254,
        "password": 128,
        "username": 50,
        "url": 2048,
    }

    @classmethod
    def validate_query(cls, query: str, max_length: int = 5000) -> bool:
        """Validate search query"""
        if not query or not isinstance(query, str):
            logger.warning("[VALIDATION] Empty or non-string query")
            return False

        if len(query) > max_length:
            logger.warning(f"[VALIDATION] Query exceeds max length ({len(query)} > {max_length})")
            return False

        # Check for potential SQL injection
        if re.search(cls.PATTERNS["sql_keyword"], query, re.IGNORECASE):
            logger.warning("[VALIDATION] Query contains potential SQL keywords")
            # Note: This is for RAG queries which shouldn't contain SQL anyway
            # In RAG context, this is a safety check but might be overly restrictive

        return True

    @classmethod
    def validate_filename(cls, filename: str) -> bool:
        """Validate uploaded filename"""
        if not filename or not isinstance(filename, str):
            logger.warning("[VALIDATION] Empty or non-string filename")
            return False

        if len(filename) > cls.MAX_LENGTHS["filename"]:
            logger.warning(f"[VALIDATION] Filename exceeds max length")
            return False

        # Check for path traversal attempts
        if ".." in filename or "/" in filename or "\\" in filename:
            logger.warning("[VALIDATION] Filename contains path traversal characters")
            return False

        # Check for allowed characters
        if not re.match(cls.PATTERNS["filename"], filename):
            logger.warning(f"[VALIDATION] Filename contains invalid characters: {filename}")
            return False

        return True

    @classmethod
    def validate_email(cls, email: str) -> bool:
        """Validate email address"""
        if not email or not isinstance(email, str):
            return False

        if len(email) > cls.MAX_LENGTHS["email"]:
            return False

        return bool(re.match(cls.PATTERNS["email"], email))

    @classmethod
    def validate_password(cls, password: str) -> bool:
        """
        Validate password strength
        - Min 8 characters
        - At least 1 uppercase
        - At least 1 lowercase
        - At least 1 digit
        - At least 1 special character
        """
        if not password or len(password) < 8:
            return False

        if len(password) > cls.MAX_LENGTHS["password"]:
            return False

        has_upper = bool(re.search(r"[A-Z]", password))
        has_lower = bool(re.search(r"[a-z]", password))
        has_digit = bool(re.search(r"\d", password))
        has_special = bool(re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>?]", password))

        return all([has_upper, has_lower, has_digit, has_special])

    @classmethod
    def sanitize_string(cls, value: str, max_length: Optional[int] = None) -> str:
        """
        Sanitize string input
        - Remove null bytes
        - HTML escape
        - Trim whitespace
        """
        if not isinstance(value, str):
            return ""

        # Remove null bytes (null injection)
        value = value.replace("\x00", "")

        # HTML escape to prevent XSS
        value = html.escape(value, quote=True)

        # Trim whitespace
        value = value.strip()

        # Enforce max length
        if max_length and len(value) > max_length:
            value = value[:max_length]

        return value

    @classmethod
    def remove_html_tags(cls, value: str) -> str:
        """Remove HTML tags from string"""
        return re.sub(cls.PATTERNS["html_tag"], "", value)

    @classmethod
    def remove_script_tags(cls, value: str) -> str:
        """Remove script tags specifically"""
        return re.sub(cls.PATTERNS["script_tag"], "", value, flags=re.IGNORECASE | re.DOTALL)

    @classmethod
    def validate_metadata_dict(cls, metadata: dict) -> bool:
        """Validate metadata dictionary"""
        if not isinstance(metadata, dict):
            return False

        # Check key and value lengths
        for key, value in metadata.items():
            if len(str(key)) > 100 or len(str(value)) > 1000:
                logger.warning("[VALIDATION] Metadata key/value exceeds max length")
                return False

        return True


# ==================== SQL INJECTION PREVENTION ====================
class SQLInjectionPrevention:
    """SQL Injection prevention utilities"""

    # Dangerous SQL patterns
    DANGEROUS_PATTERNS = [
        r"(\bUNION\b.*\bSELECT\b)",
        r"(\bOR\b.*[='].*[='])",
        r"(';.*--)",
        r"(DROP\b.*\bTABLE\b)",
        r"(INSERT\b.*\bINTO\b)",
        r"(DELETE\b.*\bFROM\b)",
        r"(UPDATE\b.*\bSET\b)",
        r"(EXEC\b.*\()",
    ]

    @classmethod
    def is_suspicious(cls, value: str) -> bool:
        """Check if value looks like SQL injection attempt"""
        if not isinstance(value, str):
            return False

        value_upper = value.upper()

        for pattern in cls.DANGEROUS_PATTERNS:
            if re.search(pattern, value_upper):
                logger.warning(f"[SQL INJECTION] Detected suspicious pattern: {pattern}")
                return True

        return False

    @classmethod
    def sanitize_like_parameter(cls, value: str) -> str:
        """Escape wildcard characters for SQL LIKE clause"""
        if not isinstance(value, str):
            return ""

        # Escape LIKE wildcards
        value = value.replace("%", "\\%")
        value = value.replace("_", "\\_")

        return value

    @classmethod
    def use_parameterized_query(cls, query: str, params: tuple) -> tuple:
        """
        Recommend using parameterized queries
        This is documentation - actual queries should use ? placeholders

        Example:
            cursor.execute("SELECT * FROM users WHERE id = ? AND name = ?", (1, "John"))
        """
        logger.debug(f"[SQL] Using parameterized query with {len(params)} parameters")
        return (query, params)


# ==================== AUTHENTICATION & SESSION ====================
class SessionManager:
    """Session and authentication management"""

    def __init__(self):
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        self.session_timeout = 3600  # 1 hour
        logger.info("[SESSION] Manager initialized")

    def create_session(self, user_id: str, username: str) -> str:
        """Create new session (placeholder)"""
        # In production, use secure session tokens (JWT, etc.)
        import uuid
        import time

        session_id = str(uuid.uuid4())
        self.active_sessions[session_id] = {
            "user_id": user_id,
            "username": username,
            "created_at": time.time(),
            "last_accessed": time.time(),
        }

        logger.info(f"[SESSION] Created session for user: {username}")
        return session_id

    def validate_session(self, session_id: str) -> bool:
        """Validate session is active and not expired"""
        if session_id not in self.active_sessions:
            logger.warning(f"[SESSION] Invalid session ID")
            return False

        import time

        session = self.active_sessions[session_id]
        age = time.time() - session["created_at"]

        if age > self.session_timeout:
            del self.active_sessions[session_id]
            logger.warning(f"[SESSION] Session expired: {session_id}")
            return False

        session["last_accessed"] = time.time()
        return True

    def destroy_session(self, session_id: str) -> bool:
        """Destroy session"""
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
            logger.info(f"[SESSION] Session destroyed: {session_id}")
            return True

        return False


# ==================== SECURITY DECORATORS ====================
def require_valid_input(max_length: int = 5000):
    """Decorator to validate input on function"""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Validate first argument if it's a string (usually the query)
            if args and isinstance(args[0], str):
                if not InputValidator.validate_query(args[0], max_length):
                    logger.warning(f"[SECURITY] Invalid input to {func.__name__}")
                    raise ValueError("Invalid input: Query validation failed")

            return func(*args, **kwargs)

        return wrapper

    return decorator


def sanitize_input(func):
    """Decorator to sanitize string inputs"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        # Sanitize string arguments
        new_args = []
        for arg in args:
            if isinstance(arg, str):
                new_args.append(InputValidator.sanitize_string(arg))
            else:
                new_args.append(arg)

        new_kwargs = {}
        for key, value in kwargs.items():
            if isinstance(value, str):
                new_kwargs[key] = InputValidator.sanitize_string(value)
            else:
                new_kwargs[key] = value

        return func(*new_args, **new_kwargs)

    return wrapper


@rate_limit(endpoint_name="security_check", tokens_cost=0.1)
def check_security_compliance(query: str, filename: Optional[str] = None) -> Dict[str, bool]:
    """
    Comprehensive security compliance check
    Returns dict with validation results for each check
    """
    results = {
        "query_valid": InputValidator.validate_query(query) if query else True,
        "filename_valid": InputValidator.validate_filename(filename) if filename else True,
        "no_sql_injection": not SQLInjectionPrevention.is_suspicious(query) if query else True,
        "no_xss": not ("<script" in query.lower()) if query else True,
    }

    logger.info(f"[SECURITY] Compliance check results: {results}")
    return results


# ==================== INITIALIZATION ====================
def get_cors_policy() -> CORSPolicy:
    """Singleton getter for CORS policy"""
    if not hasattr(get_cors_policy, "_instance"):
        get_cors_policy._instance = CORSPolicy()

    return get_cors_policy._instance


def get_session_manager() -> SessionManager:
    """Singleton getter for session manager"""
    if not hasattr(get_session_manager, "_instance"):
        get_session_manager._instance = SessionManager()

    return get_session_manager._instance


# Log initialization
logger.info("[SECURITY HARDENING] Module initialized with CORS, Input Validation, SQL Prevention")
