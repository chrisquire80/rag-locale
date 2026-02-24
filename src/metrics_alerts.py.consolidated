"""
Metrics-based alerting system
Detects performance anomalies and generates alerts
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from enum import Enum
import numpy as np
from scipy import stats as scipy_stats

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertType(Enum):
    """Alert types"""
    INGESTION_RATE_LOW = "ingestion_rate_low"
    QUERY_LATENCY_HIGH = "query_latency_high"
    ERROR_RATE_HIGH = "error_rate_high"
    CACHE_HIT_RATE_LOW = "cache_hit_rate_low"
    ANOMALY_DETECTED = "anomaly_detected"


@dataclass
class Alert:
    """Performance alert"""
    alert_type: AlertType
    severity: AlertSeverity
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    value: Optional[float] = None
    threshold: Optional[float] = None
    description: str = ""

    def __str__(self) -> str:
        """String representation"""
        status = f"[{self.severity.value.upper()}]"
        if self.value is not None and self.threshold is not None:
            return (
                f"{status} {self.message} "
                f"(Current: {self.value:.2f}, Threshold: {self.threshold:.2f})"
            )
        return f"{status} {self.message}"


class MetricsAlerts:
    """Alert system for metrics monitoring"""

    def __init__(self, metrics_file: Path = None):
        self.metrics_file = metrics_file or Path("logs/metrics.jsonl")
        self.data = self._load_metrics()
        self.alerts: List[Alert] = []

        # Configuration thresholds
        self.ingestion_rate_min = 2.0  # chunks/s
        self.query_latency_max = 500.0  # ms
        self.error_rate_max = 0.10  # 10%
        self.cache_hit_rate_min = 0.5  # 50%
        self.anomaly_zscore_threshold = 2.0  # Standard deviations

    def _load_metrics(self) -> List[Dict]:
        """Load metrics from JSONL file"""
        data = []
        if self.metrics_file.exists():
            try:
                with open(self.metrics_file) as f:
                    for line in f:
                        if line.strip():
                            try:
                                data.append(json.loads(line))
                            except json.JSONDecodeError as e:
                                logger.warning(f"Failed to parse metric line: {e}")
            except Exception as e:
                logger.error(f"Failed to load metrics: {e}")
        return data

    def _parse_timestamp(self, ts_str: str) -> datetime:
        """Parse ISO format timestamp"""
        if not ts_str:
            return datetime.now()
        try:
            return datetime.fromisoformat(ts_str)
        except (ValueError, TypeError):
            return datetime.now()

    def _get_last_n_hours(self, hours: int = 24) -> List[Dict]:
        """Get metrics from last N hours"""
        cutoff = datetime.now() - timedelta(hours=hours)
        return [
            m for m in self.data
            if self._parse_timestamp(m.get('timestamp')) > cutoff
        ]

    def check_all(self, hours: int = 24) -> List[Alert]:
        """
        Run all alert checks
        Returns list of alerts generated
        """
        self.alerts = []

        self.check_ingestion_rate(hours)
        self.check_query_latency(hours)
        self.check_error_rate(hours)
        self.check_cache_hit_rate(hours)
        self.check_anomalies(hours)

        return self.alerts

    def check_ingestion_rate(self, hours: int = 24) -> Optional[Alert]:
        """Check if ingestion rate is below threshold"""
        data = self._get_last_n_hours(hours)
        ingestions = [m for m in data if m.get('type') == 'ingestion']

        if not ingestions:
            return None

        rates = []
        for metric in ingestions:
            chunks = metric.get('data', {}).get('chunks_created', 0)
            duration = metric.get('data', {}).get('duration_seconds', 1)
            rate = chunks / duration if duration > 0 else 0
            rates.append(rate)

        avg_rate = np.mean(rates) if rates else 0

        if avg_rate < self.ingestion_rate_min:
            alert = Alert(
                alert_type=AlertType.INGESTION_RATE_LOW,
                severity=AlertSeverity.WARNING,
                message="Ingestion rate below threshold",
                value=avg_rate,
                threshold=self.ingestion_rate_min,
                description=f"Average ingestion rate ({avg_rate:.2f} chunks/s) is below threshold ({self.ingestion_rate_min} chunks/s)"
            )
            self.alerts.append(alert)
            logger.warning(f"Alert: {alert}")
            return alert

        return None

    def check_query_latency(self, hours: int = 24) -> Optional[Alert]:
        """Check if query latency is above threshold"""
        data = self._get_last_n_hours(hours)
        queries = [m for m in data if m.get('type') == 'query']

        if not queries:
            return None

        latencies = [m.get('data', {}).get('total_latency_ms', 0) for m in queries]
        latencies = [l for l in latencies if l > 0]

        if not latencies:
            return None

        avg_latency = np.mean(latencies)

        if avg_latency > self.query_latency_max:
            alert = Alert(
                alert_type=AlertType.QUERY_LATENCY_HIGH,
                severity=AlertSeverity.WARNING,
                message="Query latency above threshold",
                value=avg_latency,
                threshold=self.query_latency_max,
                description=f"Average query latency ({avg_latency:.0f}ms) exceeds threshold ({self.query_latency_max}ms)"
            )
            self.alerts.append(alert)
            logger.warning(f"Alert: {alert}")
            return alert

        return None

    def check_error_rate(self, hours: int = 24) -> Optional[Alert]:
        """Check if error rate is above threshold"""
        data = self._get_last_n_hours(hours)
        ingestions = [m for m in data if m.get('type') == 'ingestion']

        if not ingestions:
            return None

        failures = sum(1 for m in ingestions if not m.get('data', {}).get('success', False))
        error_rate = failures / len(ingestions) if ingestions else 0

        if error_rate > self.error_rate_max:
            alert = Alert(
                alert_type=AlertType.ERROR_RATE_HIGH,
                severity=AlertSeverity.CRITICAL,
                message="Ingestion error rate above threshold",
                value=error_rate * 100,
                threshold=self.error_rate_max * 100,
                description=f"Error rate ({error_rate*100:.1f}%) exceeds threshold ({self.error_rate_max*100:.1f}%)"
            )
            self.alerts.append(alert)
            logger.error(f"Alert: {alert}")
            return alert

        return None

    def check_cache_hit_rate(self, hours: int = 24) -> Optional[Alert]:
        """Check if cache hit rate is below threshold"""
        data = self._get_last_n_hours(hours)
        queries = [m for m in data if m.get('type') == 'query']

        if not queries:
            return None

        hits = sum(1 for m in queries if m.get('data', {}).get('cache_hit', False))
        hit_rate = hits / len(queries) if queries else 0

        if hit_rate < self.cache_hit_rate_min:
            alert = Alert(
                alert_type=AlertType.CACHE_HIT_RATE_LOW,
                severity=AlertSeverity.INFO,
                message="Cache hit rate below threshold",
                value=hit_rate * 100,
                threshold=self.cache_hit_rate_min * 100,
                description=f"Cache hit rate ({hit_rate*100:.1f}%) is below target ({self.cache_hit_rate_min*100:.1f}%)"
            )
            self.alerts.append(alert)
            logger.info(f"Alert: {alert}")
            return alert

        return None

    def check_anomalies(self, hours: int = 24) -> List[Alert]:
        """Detect statistical anomalies in query latencies"""
        data = self._get_last_n_hours(hours)
        queries = [m for m in data if m.get('type') == 'query']

        if not queries or len(queries) < 5:
            return []

        latencies = [m.get('data', {}).get('total_latency_ms', 0) for m in queries]
        latencies = [l for l in latencies if l > 0]

        if not latencies or len(latencies) < 5:
            return []

        try:
            z_scores = np.abs(scipy_stats.zscore(latencies))
            anomalies = z_scores > self.anomaly_zscore_threshold

            anomaly_alerts = []
            for i, is_anomaly in enumerate(anomalies):
                if is_anomaly:
                    query_metric = queries[i]
                    query_text = query_metric.get('data', {}).get('query_text', 'Unknown')[:50]
                    latency = latencies[i]

                    alert = Alert(
                        alert_type=AlertType.ANOMALY_DETECTED,
                        severity=AlertSeverity.WARNING,
                        message="Anomalous query latency detected",
                        value=latency,
                        threshold=np.mean(latencies),
                        description=f"Query '{query_text}...' latency ({latency:.0f}ms) is statistical outlier"
                    )
                    anomaly_alerts.append(alert)
                    self.alerts.append(alert)
                    logger.warning(f"Alert: {alert}")

            return anomaly_alerts

        except Exception as e:
            logger.warning(f"Anomaly detection failed: {e}")
            return []

    def get_active_alerts(self) -> List[Alert]:
        """Get current active alerts"""
        return self.alerts

    def get_alerts_by_severity(self, severity: AlertSeverity) -> List[Alert]:
        """Get alerts filtered by severity"""
        return [a for a in self.alerts if a.severity == severity]

    def clear_alerts(self):
        """Clear all alerts"""
        self.alerts = []

    def get_alert_summary(self) -> Dict:
        """Get summary of current alerts"""
        return {
            "total_alerts": len(self.alerts),
            "critical": len(self.get_alerts_by_severity(AlertSeverity.CRITICAL)),
            "warning": len(self.get_alerts_by_severity(AlertSeverity.WARNING)),
            "info": len(self.get_alerts_by_severity(AlertSeverity.INFO)),
        }


# Global instance
_alerts = None


def get_metrics_alerts() -> MetricsAlerts:
    """Get or create global metrics alerts instance"""
    global _alerts
    if _alerts is None:
        _alerts = MetricsAlerts()
    return _alerts


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    alerts = get_metrics_alerts()

    print("Running alert checks...")
    active_alerts = alerts.check_all(hours=24)

    print(f"\nAlert Summary:")
    summary = alerts.get_alert_summary()
    print(f"  Total Alerts: {summary['total_alerts']}")
    print(f"  Critical: {summary['critical']}")
    print(f"  Warning: {summary['warning']}")
    print(f"  Info: {summary['info']}")

    if active_alerts:
        print(f"\nActive Alerts:")
        for alert in active_alerts:
            # Use ASCII-safe representation
            severity_str = f"[{alert.severity.value.upper()}]"
            print(f"  - {severity_str} {alert.alert_type.value}")
    else:
        print("\nNo alerts detected")
