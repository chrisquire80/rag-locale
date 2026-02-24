"""
Structured Logging Configuration

Provides JSON-formatted structured logging for production monitoring.
Logs are machine-parsable and include timestamp, level, module, message, and context.
"""

import json
import sys
from datetime import datetime
from typing import Any
from pathlib import Path

class JSONFormatter(logging.Formatter):
    """
    Custom formatter that outputs JSON instead of plain text.

    Makes logs:
    - Machine-parsable for log aggregation systems
    - Structured with consistent fields
    - Easily filterable in ELK, Datadog, CloudWatch, etc.
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        Convert log record to JSON format.

        Fields:
        - timestamp: ISO 8601 format
        - level: DEBUG, INFO, WARNING, ERROR, CRITICAL
        - module: Source module name
        - function: Function name
        - line: Line number
        - message: Log message
        - exception: Exception details if present
        - extra: Additional context fields
        """
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
        }

        # Add exception details if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields (custom context)
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        return json.dumps(log_data, ensure_ascii=False)

class StructuredLogger:
    """
    Wrapper around Python logging with structured context support.

    Usage:
        logger = StructuredLogger(__name__)
        logger.info("User logged in", user_id=123, session_id="abc")
        # Output: {"timestamp": "...", "level": "INFO", "message": "User logged in", "user_id": 123, ...}
    """

    def __init__(self, name: str, log_level: str = "INFO"):
        """
        Initialize structured logger.

        Args:
            name: Logger name (typically __name__)
            log_level: Default logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, log_level))

    def _log(self, level: int, message: str, **extra_fields):
        """
        Internal method to log with extra fields.

        Args:
            level: Logging level (logging.INFO, etc.)
            message: Log message
            **extra_fields: Additional context to include in JSON
        """
        record = self.logger.makeRecord(
            self.logger.name,
            level,
            "(unknown file)",
            0,
            message,
            (),
            None
        )

        # Attach extra fields to record
        if extra_fields:
            record.extra_fields = extra_fields

        self.logger.handle(record)

    def debug(self, message: str, **extra_fields):
        """Log debug message with optional context"""
        self._log(logging.DEBUG, message, **extra_fields)

    def info(self, message: str, **extra_fields):
        """Log info message with optional context"""
        self._log(logging.INFO, message, **extra_fields)

    def warning(self, message: str, **extra_fields):
        """Log warning message with optional context"""
        self._log(logging.WARNING, message, **extra_fields)

    def error(self, message: str, **extra_fields):
        """Log error message with optional context"""
        self._log(logging.ERROR, message, **extra_fields)

    def critical(self, message: str, **extra_fields):
        """Log critical message with optional context"""
        self._log(logging.CRITICAL, message, **extra_fields)

def configure_json_logging(
    log_level: str = "INFO",
    log_file: Path = None,
    include_console: bool = True
) -> logging.Logger:
    """
    Configure root logger with JSON formatting.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path for file handler
        include_console: Whether to include console output

    Returns:
        Configured root logger
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Console handler
    if include_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, log_level))
        console_formatter = JSONFormatter()
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(getattr(logging, log_level))
        file_formatter = JSONFormatter()
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

    return root_logger

def get_structured_logger(name: str) -> StructuredLogger:
    """
    Get a structured logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        StructuredLogger instance
    """
    return StructuredLogger(name)

# Example usage and log output documentation:
"""
Example:
    logger = get_structured_logger(__name__)
    logger.info("Processing query", query="What is AI?", user_id=123)

Output (formatted):
{
    "timestamp": "2026-02-23T10:30:45.123Z",
    "level": "INFO",
    "module": "rag_engine",
    "function": "query",
    "line": 157,
    "message": "Processing query",
    "query": "What is AI?",
    "user_id": 123
}

For monitoring/analytics:
- Parse JSON to extract fields
- Filter by level, module, or specific field values
- Aggregate metrics (errors per module, latency by operation)
- Create alerts on critical errors
- Build dashboards in ELK, Datadog, CloudWatch, etc.
"""
