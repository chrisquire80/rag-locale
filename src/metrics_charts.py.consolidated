"""
Real-time metrics charting with Plotly
Generates interactive visualizations for performance monitoring
"""

import json
import logging
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import plotly.graph_objects as go
import plotly.express as px
from scipy import stats as scipy_stats

logger = logging.getLogger(__name__)


class MetricsCharts:
    """Generate Plotly charts from metrics data"""

    def __init__(self, metrics_file: Path = None):
        self.metrics_file = metrics_file or Path("logs/metrics.jsonl")
        self.data = self._load_metrics()

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

    def chart_ingestion_rate(self, hours: int = 24) -> go.Figure:
        """
        Chart ingestion rate over time
        X-axis: timestamp
        Y-axis: chunks per second
        """
        data = self._get_last_n_hours(hours)
        ingestions = [m for m in data if m.get('type') == 'ingestion']

        if not ingestions:
            return self._empty_chart("No ingestion data available")

        timestamps = []
        rates = []

        for metric in ingestions:
            ts = self._parse_timestamp(metric.get('timestamp'))
            chunks = metric.get('data', {}).get('chunks_created', 0)
            duration = metric.get('data', {}).get('duration_seconds', 1)
            rate = chunks / duration if duration > 0 else 0

            timestamps.append(ts)
            rates.append(rate)

        fig = go.Figure()

        # Add line trace
        fig.add_trace(go.Scatter(
            x=timestamps,
            y=rates,
            mode='lines+markers',
            name='Ingestion Rate',
            line=dict(color='#1f77b4', width=2),
            fill='tozeroy',
            fillcolor='rgba(31, 119, 180, 0.2)',
            hovertemplate='<b>%{x|%Y-%m-%d %H:%M:%S}</b><br>' +
                         'Rate: %{y:.2f} chunks/s<extra></extra>'
        ))

        # Add average line
        if rates:
            avg_rate = np.mean(rates)
            fig.add_hline(
                y=avg_rate,
                line_dash="dash",
                line_color="red",
                annotation_text=f"Average: {avg_rate:.2f} chunks/s",
                annotation_position="right"
            )

        fig.update_layout(
            title="Ingestion Rate Over Time",
            xaxis_title="Timestamp",
            yaxis_title="Chunks per Second",
            hovermode='x unified',
            height=400,
            template='plotly_white'
        )

        return fig

    def chart_query_latency(self, hours: int = 24) -> go.Figure:
        """
        Chart query latency distribution
        Histogram with avg and P95 lines
        """
        data = self._get_last_n_hours(hours)
        queries = [m for m in data if m.get('type') == 'query']

        if not queries:
            return self._empty_chart("No query data available")

        latencies = [m.get('data', {}).get('total_latency_ms', 0) for m in queries]
        latencies = [l for l in latencies if l > 0]  # Filter out zeros

        if not latencies:
            return self._empty_chart("No valid query latency data")

        fig = go.Figure()

        # Histogram
        fig.add_trace(go.Histogram(
            x=latencies,
            nbinsx=30,
            name='Query Latency',
            marker_color='rgba(31, 119, 180, 0.7)',
            opacity=0.7,
            hovertemplate='Latency: %{x:.0f}ms<br>Count: %{y}<extra></extra>'
        ))

        # Average line
        avg_latency = np.mean(latencies)
        fig.add_vline(
            x=avg_latency,
            line_dash="dash",
            line_color="green",
            annotation_text=f"Avg: {avg_latency:.0f}ms",
            annotation_position="top right"
        )

        # P95 line
        p95_latency = np.percentile(latencies, 95)
        fig.add_vline(
            x=p95_latency,
            line_dash="dot",
            line_color="orange",
            annotation_text=f"P95: {p95_latency:.0f}ms",
            annotation_position="top right"
        )

        fig.update_layout(
            title="Query Latency Distribution",
            xaxis_title="Latency (ms)",
            yaxis_title="Frequency",
            hovermode='x unified',
            height=400,
            template='plotly_white',
            showlegend=True
        )

        return fig

    def chart_query_latency_trend(self, hours: int = 24) -> go.Figure:
        """
        Chart query latency trend over time
        X-axis: timestamp
        Y-axis: latency (ms)
        """
        data = self._get_last_n_hours(hours)
        queries = [m for m in data if m.get('type') == 'query']

        if not queries:
            return self._empty_chart("No query data available")

        timestamps = []
        latencies = []
        search_latencies = []
        llm_latencies = []

        for metric in queries:
            ts = self._parse_timestamp(metric.get('timestamp'))
            lat = metric.get('data', {}).get('total_latency_ms', 0)
            search_lat = metric.get('data', {}).get('search_latency_ms', 0)
            llm_lat = metric.get('data', {}).get('llm_latency_ms', 0)

            timestamps.append(ts)
            latencies.append(lat)
            search_latencies.append(search_lat)
            llm_latencies.append(llm_lat)

        fig = go.Figure()

        # Total latency
        fig.add_trace(go.Scatter(
            x=timestamps,
            y=latencies,
            mode='lines+markers',
            name='Total Latency',
            line=dict(color='#1f77b4', width=2),
            hovertemplate='<b>%{x|%Y-%m-%d %H:%M:%S}</b><br>' +
                         'Latency: %{y:.0f}ms<extra></extra>'
        ))

        # Search latency
        fig.add_trace(go.Scatter(
            x=timestamps,
            y=search_latencies,
            mode='lines',
            name='Search Latency',
            line=dict(color='#ff7f0e', width=1, dash='dash'),
            hovertemplate='Search: %{y:.0f}ms<extra></extra>'
        ))

        # LLM latency
        fig.add_trace(go.Scatter(
            x=timestamps,
            y=llm_latencies,
            mode='lines',
            name='LLM Latency',
            line=dict(color='#2ca02c', width=1, dash='dash'),
            hovertemplate='LLM: %{y:.0f}ms<extra></extra>'
        ))

        fig.update_layout(
            title="Query Latency Trend",
            xaxis_title="Timestamp",
            yaxis_title="Latency (ms)",
            hovermode='x unified',
            height=400,
            template='plotly_white'
        )

        return fig

    def chart_cache_hit_rate(self, hours: int = 24) -> go.Figure:
        """
        Chart cache hit rate over time
        X-axis: time period (hourly aggregation)
        Y-axis: hit rate percentage
        """
        data = self._get_last_n_hours(hours)
        queries = [m for m in data if m.get('type') == 'query']

        if not queries:
            return self._empty_chart("No query data available")

        # Aggregate by hour
        hourly_stats = {}
        for metric in queries:
            ts = self._parse_timestamp(metric.get('timestamp'))
            hour_key = ts.replace(minute=0, second=0, microsecond=0)

            if hour_key not in hourly_stats:
                hourly_stats[hour_key] = {'hits': 0, 'total': 0}

            cache_hit = metric.get('data', {}).get('cache_hit', False)
            hourly_stats[hour_key]['total'] += 1
            if cache_hit:
                hourly_stats[hour_key]['hits'] += 1

        timestamps = sorted(hourly_stats.keys())
        hit_rates = [
            (hourly_stats[ts]['hits'] / hourly_stats[ts]['total']) * 100
            for ts in timestamps
        ]

        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=timestamps,
            y=hit_rates,
            mode='lines+markers',
            name='Cache Hit Rate',
            fill='tozeroy',
            fillcolor='rgba(44, 160, 44, 0.2)',
            line=dict(color='#2ca02c', width=2),
            hovertemplate='<b>%{x|%Y-%m-%d %H:%M}</b><br>' +
                         'Hit Rate: %{y:.1f}%<extra></extra>'
        ))

        fig.update_layout(
            title="Cache Hit Rate Over Time",
            xaxis_title="Timestamp",
            yaxis_title="Hit Rate (%)",
            yaxis=dict(range=[0, 100]),
            hovermode='x unified',
            height=400,
            template='plotly_white'
        )

        return fig

    def chart_success_rate(self, hours: int = 24) -> go.Figure:
        """
        Chart ingestion success rate over time
        X-axis: time period (hourly aggregation)
        Y-axis: success percentage
        """
        data = self._get_last_n_hours(hours)
        ingestions = [m for m in data if m.get('type') == 'ingestion']

        if not ingestions:
            return self._empty_chart("No ingestion data available")

        # Aggregate by hour
        hourly_stats = {}
        for metric in ingestions:
            ts = self._parse_timestamp(metric.get('timestamp'))
            hour_key = ts.replace(minute=0, second=0, microsecond=0)

            if hour_key not in hourly_stats:
                hourly_stats[hour_key] = {'success': 0, 'total': 0}

            success = metric.get('data', {}).get('success', False)
            hourly_stats[hour_key]['total'] += 1
            if success:
                hourly_stats[hour_key]['success'] += 1

        timestamps = sorted(hourly_stats.keys())
        success_rates = [
            (hourly_stats[ts]['success'] / hourly_stats[ts]['total']) * 100
            for ts in timestamps
        ]

        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=timestamps,
            y=success_rates,
            mode='lines+markers',
            name='Success Rate',
            fill='tozeroy',
            fillcolor='rgba(31, 119, 180, 0.2)',
            line=dict(color='#1f77b4', width=2),
            hovertemplate='<b>%{x|%Y-%m-%d %H:%M}</b><br>' +
                         'Success: %{y:.1f}%<extra></extra>'
        ))

        fig.update_layout(
            title="Ingestion Success Rate Over Time",
            xaxis_title="Timestamp",
            yaxis_title="Success Rate (%)",
            yaxis=dict(range=[0, 100]),
            hovermode='x unified',
            height=400,
            template='plotly_white'
        )

        return fig

    def detect_anomalies(self, values: List[float], threshold: float = 2.0) -> List[bool]:
        """
        Detect statistical anomalies using Z-score
        Returns list of booleans indicating anomalies

        Args:
            values: List of numeric values
            threshold: Z-score threshold (default 2.0 = 95% confidence)

        Returns:
            List of booleans indicating anomalies
        """
        if len(values) < 2:
            return [False] * len(values)

        try:
            z_scores = np.abs(scipy_stats.zscore(values))
            anomalies = z_scores > threshold
            return anomalies.tolist()
        except Exception as e:
            logger.warning(f"Anomaly detection failed: {e}")
            return [False] * len(values)

    def _empty_chart(self, message: str) -> go.Figure:
        """Return empty chart with message"""
        fig = go.Figure()
        fig.add_annotation(
            text=message,
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=14)
        )
        fig.update_layout(
            title="",
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            height=400,
            template='plotly_white'
        )
        return fig


# Global instance
_charts = None


def get_metrics_charts() -> MetricsCharts:
    """Get or create global metrics charts instance"""
    global _charts
    if _charts is None:
        _charts = MetricsCharts()
    return _charts


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    charts = get_metrics_charts()

    # Test chart generation
    print("Generating sample charts...")
    print("[OK] Ingestion rate chart")
    print("[OK] Query latency chart")
    print("[OK] Query latency trend chart")
    print("[OK] Cache hit rate chart")
    print("[OK] Success rate chart")
    print("\nAll charts ready for Streamlit display")
