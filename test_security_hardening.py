"""
Security Hardening Tests - Phase 11
Comprehensive tests for CORS, input validation, and SQL injection prevention
"""

import pytest
from src.security_hardening import (
    CORSPolicy,
    InputValidator,
    SQLInjectionPrevention,
    SessionManager,
    check_security_compliance,
    get_cors_policy,
    get_session_manager,
)


class TestCORSPolicy:
    """Test CORS policy enforcement"""

    def test_cors_allowed_origin(self):
        """Test that whitelisted origins are allowed"""
        cors = CORSPolicy()
        assert cors.is_origin_allowed("http://localhost:8501") == True

    def test_cors_blocked_origin(self):
        """Test that non-whitelisted origins are blocked"""
        cors = CORSPolicy()
        assert cors.is_origin_allowed("http://evil.com") == False

    def test_cors_empty_origin(self):
        """Test that empty origin is blocked"""
        cors = CORSPolicy()
        assert cors.is_origin_allowed("") == False

    def test_cors_headers_generation(self):
        """Test CORS headers are correctly generated"""
        cors = CORSPolicy()
        headers = cors.get_cors_headers("http://localhost:8501")
        assert headers["Access-Control-Allow-Origin"] == "http://localhost:8501"
        assert "Content-Type" in headers["Access-Control-Allow-Headers"]

    def test_cors_headers_blocked(self):
        """Test no headers for blocked origins"""
        cors = CORSPolicy()
        headers = cors.get_cors_headers("http://evil.com")
        assert headers == {}

    def test_cors_add_origin(self):
        """Test dynamically adding allowed origin"""
        cors = CORSPolicy()
        cors.add_allowed_origin("http://new-origin.com")
        assert cors.is_origin_allowed("http://new-origin.com") == True

    def test_cors_remove_origin(self):
        """Test dynamically removing allowed origin"""
        cors = CORSPolicy()
        cors.add_allowed_origin("http://temp.com")
        cors.remove_allowed_origin("http://temp.com")
        assert cors.is_origin_allowed("http://temp.com") == False


class TestInputValidator:
    """Test input validation and sanitization"""

    def test_validate_query_valid(self):
        """Test valid query passes validation"""
        assert InputValidator.validate_query("What is machine learning?") == True

    def test_validate_query_empty(self):
        """Test empty query fails validation"""
        assert InputValidator.validate_query("") == False

    def test_validate_query_too_long(self):
        """Test query exceeding max length fails"""
        long_query = "a" * 10000
        assert InputValidator.validate_query(long_query) == False

    def test_validate_filename_valid(self):
        """Test valid filename passes validation"""
        assert InputValidator.validate_filename("document.pdf") == True
        assert InputValidator.validate_filename("my_file_2024.txt") == True

    def test_validate_filename_path_traversal(self):
        """Test path traversal attempts are blocked"""
        assert InputValidator.validate_filename("../../../etc/passwd") == False
        assert InputValidator.validate_filename("..\\windows\\system32") == False

    def test_validate_filename_invalid_chars(self):
        """Test filenames with invalid characters are blocked"""
        assert InputValidator.validate_filename("<script>.pdf") == False
        assert InputValidator.validate_filename("file;drop.txt") == False

    def test_validate_email_valid(self):
        """Test valid email addresses"""
        assert InputValidator.validate_email("user@example.com") == True
        assert InputValidator.validate_email("test.name+tag@domain.co.uk") == True

    def test_validate_email_invalid(self):
        """Test invalid email addresses"""
        assert InputValidator.validate_email("invalid.email") == False
        assert InputValidator.validate_email("@example.com") == False

    def test_validate_password_strong(self):
        """Test strong passwords pass validation"""
        assert InputValidator.validate_password("SecurePass123!") == True

    def test_validate_password_weak(self):
        """Test weak passwords fail validation"""
        assert InputValidator.validate_password("weak") == False  # Too short
        assert InputValidator.validate_password("123456789") == False  # No letters
        assert InputValidator.validate_password("abcdefgh") == False  # No special char

    def test_sanitize_string_html_escape(self):
        """Test HTML escaping in sanitization"""
        input_str = "<script>alert('xss')</script>"
        output = InputValidator.sanitize_string(input_str)
        assert "<" not in output
        assert ">" not in output
        assert "&lt;" in output
        assert "&gt;" in output

    def test_sanitize_string_null_bytes(self):
        """Test null byte removal"""
        input_str = "normal\x00string"
        output = InputValidator.sanitize_string(input_str)
        assert "\x00" not in output

    def test_sanitize_string_max_length(self):
        """Test max length enforcement"""
        input_str = "a" * 100
        output = InputValidator.sanitize_string(input_str, max_length=50)
        assert len(output) == 50

    def test_remove_html_tags(self):
        """Test HTML tag removal"""
        input_str = "<p>Hello <b>World</b></p>"
        output = InputValidator.remove_html_tags(input_str)
        assert "<p>" not in output
        assert "<b>" not in output
        assert "Hello World" in output

    def test_remove_script_tags(self):
        """Test script tag removal"""
        input_str = "Before<script>malicious()</script>After"
        output = InputValidator.remove_script_tags(input_str)
        assert "<script>" not in output
        assert "malicious()" not in output
        assert "BeforeAfter" == output

    def test_validate_metadata_dict(self):
        """Test metadata dictionary validation"""
        valid_metadata = {"key1": "value1", "key2": "value2"}
        assert InputValidator.validate_metadata_dict(valid_metadata) == True

        invalid_metadata = "not a dict"
        assert InputValidator.validate_metadata_dict(invalid_metadata) == False


class TestSQLInjectionPrevention:
    """Test SQL injection prevention"""

    def test_sql_injection_union_select(self):
        """Test detection of UNION-based SQL injection"""
        suspicious = "1' UNION SELECT * FROM users--"
        assert SQLInjectionPrevention.is_suspicious(suspicious) == True

    def test_sql_injection_or_condition(self):
        """Test detection of OR-based SQL injection"""
        suspicious = "admin' OR '1'='1"
        assert SQLInjectionPrevention.is_suspicious(suspicious) == True

    def test_sql_injection_drop_table(self):
        """Test detection of DROP TABLE attempts"""
        suspicious = "'; DROP TABLE users;--"
        assert SQLInjectionPrevention.is_suspicious(suspicious) == True

    def test_sql_injection_insert(self):
        """Test detection of INSERT injection"""
        suspicious = "'; INSERT INTO users VALUES(...);--"
        assert SQLInjectionPrevention.is_suspicious(suspicious) == True

    def test_sql_injection_exec(self):
        """Test detection of EXEC injection"""
        suspicious = "'; EXEC xp_cmdshell('dir');--"
        assert SQLInjectionPrevention.is_suspicious(suspicious) == True

    def test_legitimate_query_not_flagged(self):
        """Test legitimate queries are not flagged"""
        legitimate = "What is the union of machine learning?"
        assert SQLInjectionPrevention.is_suspicious(legitimate) == False

    def test_sanitize_like_parameter(self):
        """Test LIKE clause parameter escaping"""
        input_str = "user%_search"
        output = SQLInjectionPrevention.sanitize_like_parameter(input_str)
        assert "\\%" in output
        assert "\\_" in output


class TestSessionManager:
    """Test session management"""

    def test_create_session(self):
        """Test session creation"""
        manager = SessionManager()
        session_id = manager.create_session("user123", "john_doe")
        assert session_id is not None
        assert len(session_id) > 0

    def test_validate_session_valid(self):
        """Test valid session passes validation"""
        manager = SessionManager()
        session_id = manager.create_session("user123", "john_doe")
        assert manager.validate_session(session_id) == True

    def test_validate_session_invalid(self):
        """Test invalid session fails validation"""
        manager = SessionManager()
        assert manager.validate_session("invalid-session-id") == False

    def test_destroy_session(self):
        """Test session destruction"""
        manager = SessionManager()
        session_id = manager.create_session("user123", "john_doe")
        assert manager.destroy_session(session_id) == True
        assert manager.validate_session(session_id) == False

    def test_destroy_nonexistent_session(self):
        """Test destroying non-existent session"""
        manager = SessionManager()
        assert manager.destroy_session("invalid-id") == False

    def test_singleton_instance(self):
        """Test session manager singleton"""
        manager1 = get_session_manager()
        manager2 = get_session_manager()
        assert manager1 is manager2


class TestSecurityCompliance:
    """Test overall security compliance"""

    def test_compliance_clean_query(self):
        """Test clean query passes all checks"""
        results = check_security_compliance("What is artificial intelligence?")
        assert all(results.values()) == True

    def test_compliance_sql_injection(self):
        """Test SQL injection is detected"""
        results = check_security_compliance("'; DROP TABLE users;--")
        assert results["no_sql_injection"] == False

    def test_compliance_xss_attempt(self):
        """Test XSS is detected"""
        results = check_security_compliance("<script>alert('xss')</script>")
        assert results["no_xss"] == False

    def test_compliance_with_filename(self):
        """Test compliance check with filename"""
        results = check_security_compliance("query text", filename="document.pdf")
        assert results["filename_valid"] == True

    def test_compliance_malicious_filename(self):
        """Test malicious filename detection"""
        results = check_security_compliance("query", filename="../../../etc/passwd")
        assert results["filename_valid"] == False


class TestSecurityIntegration:
    """Integration tests for security features"""

    def test_cors_policy_singleton(self):
        """Test CORS policy singleton"""
        cors1 = get_cors_policy()
        cors2 = get_cors_policy()
        assert cors1 is cors2

    def test_defense_in_depth(self):
        """Test defense-in-depth approach"""
        # This query should pass CORS but fail input validation for various reasons
        malicious_query = "test' OR '1'='1"

        # 1. CORS check
        cors = get_cors_policy()
        assert cors.is_origin_allowed("http://localhost:8501") == True

        # 2. Input validation
        assert InputValidator.validate_query(malicious_query) == True  # Valid format

        # 3. SQL injection check
        assert SQLInjectionPrevention.is_suspicious(malicious_query) == True

        # 4. Compliance check
        results = check_security_compliance(malicious_query)
        assert results["no_sql_injection"] == False

    def test_sanitization_pipeline(self):
        """Test complete sanitization pipeline"""
        dirty_input = "normal<script>alert('xss')</script>text"

        # Step 1: Validate
        is_valid = InputValidator.validate_query(dirty_input)

        # Step 2: Sanitize (escapes HTML)
        clean = InputValidator.sanitize_string(dirty_input)

        # Verify HTML is escaped (safe alternative to removal)
        assert "&lt;script&gt;" in clean  # HTML-escaped script tag
        assert "<script>" not in clean  # No raw script tag

        # Step 3: Remove scripts from original
        cleaned = InputValidator.remove_script_tags(dirty_input)

        # Verify scripts are removed
        assert "<script>" not in cleaned
        assert "alert" not in cleaned
        assert "normaltext" == cleaned


# ==================== SUMMARY ====================
if __name__ == "__main__":
    """Run all security tests"""
    import logging

    logging.basicConfig(level=logging.INFO)
    print("\n" + "="*70)
    print("SECURITY HARDENING TEST SUITE")
    print("Testing: CORS, Input Validation, SQL Injection Prevention, Sessions")
    print("="*70 + "\n")

    pytest.main([__file__, "-v", "-s", "--tb=short"])
