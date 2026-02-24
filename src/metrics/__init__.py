"""
Metrics package for RAG LOCALE
Unified metrics collection, alerting, visualization, and UI
"""

# Core metrics data structures and collection
from .core import (
    IngestionMetrics,
    QueryMetrics,
    APIMetrics,
    MetricsCollector,
    get_metrics_collector
)

# Shared utilities
from ._loader import (
    load_metrics,
    parse_timestamp,
    get_last_n_hours_metrics
)

# Analysis and reporting
try:
    from .dashboard import MetricsAnalyzer
except ImportError:
    MetricsAnalyzer = None

# Visualization
try:
    from .charts import MetricsCharts
except ImportError:
    MetricsCharts = None

# Alerting
try:
    from .alerts import MetricsAlerts, Alert, AlertType, AlertSeverity
except ImportError:
    MetricsAlerts = None
    Alert = None
    AlertType = None
    AlertSeverity = None

# UI
try:
    from .ui import show_metrics_dashboard
except ImportError:
    show_metrics_dashboard = None


__all__ = [
    # Core
    "IngestionMetrics",
    "QueryMetrics",
    "APIMetrics",
    "MetricsCollector",
    "get_metrics_collector",
    # Utilities
    "load_metrics",
    "parse_timestamp",
    "get_last_n_hours_metrics",
    # Optional modules
    "MetricsAnalyzer",
    "MetricsCharts",
    "MetricsAlerts",
    "Alert",
    "AlertType",
    "AlertSeverity",
    "show_metrics_dashboard",
]
