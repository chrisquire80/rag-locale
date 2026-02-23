"""
Shared utilities for metrics modules
Centralizes duplicated _load_metrics and _parse_timestamp logic
"""

import json
import logging
from pathlib import Path
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

def load_metrics(metrics_file: Path = None) -> list[Dict]:
    """
    Load metrics from JSONL file.

    Centralizes duplicate logic from metrics_alerts.py, metrics_charts.py, metrics_dashboard.py

    Args:
        metrics_file: Path to metrics.jsonl file (defaults to logs/metrics.jsonl)

    Returns:
        List of metric dictionaries parsed from JSONL
    """
    if metrics_file is None:
        metrics_file = Path("logs/metrics.jsonl")

    data = []
    if metrics_file.exists():
        try:
            with open(metrics_file) as f:
                for line in f:
                    if line.strip():
                        try:
                            data.append(json.loads(line))
                        except json.JSONDecodeError as e:
                            logger.warning(f"Failed to parse metric line: {e}")
        except Exception as e:
            logger.error(f"Failed to load metrics: {e}")
    return data

def parse_timestamp(ts_str: str) -> datetime:
    """
    Parse ISO format timestamp.

    Centralizes duplicate logic from metrics_alerts.py and other modules

    Args:
        ts_str: ISO format timestamp string

    Returns:
        Parsed datetime object, or current time if parsing fails
    """
    if not ts_str:
        return datetime.now()
    try:
        return datetime.fromisoformat(ts_str)
    except (ValueError, TypeError):
        return datetime.now()

def get_last_n_hours_metrics(data: list[Dict], hours: int = 24) -> list[Dict]:
    """
    Filter metrics to last N hours.

    Args:
        data: List of metric dictionaries
        hours: Number of hours to include (default 24)

    Returns:
        Filtered list with only metrics from last N hours
    """
    cutoff = datetime.now() - timedelta(hours=hours)
    return [
        m for m in data
        if parse_timestamp(m.get('timestamp')) > cutoff
    ]
