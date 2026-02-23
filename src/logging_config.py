"""
Centralized Logging Configuration

Auto-initializes structured JSON logging on import.
Ensures all modules use the same logging format across the application.

Usage:
    # Import at top of module - auto-configures logging
    from src.logging_config import get_logger
    logger = get_logger(__name__)

    # All logs automatically use structured JSON format
    logger.info("Query processed", query_id=123, latency_ms=1500)
    # Output: {"timestamp": "...", "level": "INFO", "module": "...", "query_id": 123, ...}
"""

import logging
import json
import sys
from datetime import datetime
from pathlib import Path


class JSONFormatter(logging.Formatter):
    """Custom formatter that outputs structured JSON logs"""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON"""
        log_obj = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "module": record.name,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
        }

        # Add exception info if present
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        # Add any extra fields from LogRecord
        if hasattr(record, 'extra_fields'):
            log_obj.update(record.extra_fields)

        # Return as compact JSON (no pretty-printing)
        return json.dumps(log_obj, default=str)


def configure_logging(
    level: str = "INFO",
    log_file: str = "logs/app.jsonl",
    console: bool = True,
) -> None:
    """
    Configure root logger with JSON formatting

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (JSONL format)
        console: Also output to console
    """
    root_logger = logging.getLogger()

    # Set root level
    log_level = getattr(logging, level.upper(), logging.INFO)
    root_logger.setLevel(log_level)

    # Remove any existing handlers (avoid duplicates)
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create formatter
    formatter = JSONFormatter()

    # Console handler
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # File handler (JSONL format)
    try:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_path, encoding='utf-8')
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except Exception as e:
        if console:
            print(f"[WARNING] Could not create log file {log_file}: {e}")


def get_logger(name: str) -> logging.Logger:
    """
    Get logger for a module with structured logging support

    Args:
        name: Module name (typically __name__)

    Returns:
        Configured logger instance

    Usage:
        logger = get_logger(__name__)
        logger.info("Event", field1=value1, field2=value2)
    """
    return logging.getLogger(name)


# Auto-configure on import (unless running tests)
import os
if os.getenv('PYTEST_CURRENT_TEST') is None:
    _log_level = os.getenv('LOG_LEVEL', 'INFO')
    _log_file = os.getenv('LOG_FILE', 'logs/app.jsonl')
    _console = os.getenv('LOG_CONSOLE', 'true').lower() != 'false'

    configure_logging(level=_log_level, log_file=_log_file, console=_console)

    # Log initialization
    _init_logger = get_logger(__name__)
    _init_logger.info(
        "Logging configured",
        level=_log_level,
        log_file=_log_file,
        format="json"
    )
