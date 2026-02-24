"""
Streamlit UI for metrics and monitoring
Displays system performance metrics in sidebar with charts and alerts
"""

import streamlit as st
import plotly.graph_objects as go
from pathlib import Path
from src.metrics.dashboard import MetricsAnalyzer
from src.metrics.charts import MetricsCharts
from src.metrics.alerts import MetricsAlerts, AlertSeverity
from src.metrics.query_analytics import QueryAnalyzer


def show_metrics_dashboard():
    """Display metrics dashboard in Streamlit sidebar"""
    with st.sidebar:
        st.markdown("---")
        st.subheader("📊 Metrics & Performance")

        metrics_file = Path("logs/metrics.jsonl")

        if not metrics_file.exists():
            st.info("No metrics data yet. Start ingesting documents to collect metrics.")
            return

        try:
            analyzer = MetricsAnalyzer(metrics_file)
            charts = get_metrics_charts()
            alerts_system = get_metrics_alerts()

            # Time range selector
            time_range = st.selectbox(
                "Time Range",
                ["All", "Last 24h", "Last 7d"],
                key="metrics_time_range"
            )

            hours_map = {
                "All": None,
                "Last 24h": 24,
                "Last 7d": 7 * 24
            }
            hours = hours_map[time_range]

            # Create tabs for different views
            tab1, tab2, tab3, tab4, tab5 = st.tabs(["Metrics", "Charts", "Alerts", "Trends", "Query Analytics"])

            # ===== TAB 1: METRICS SUMMARY =====
            with tab1:
                st.subheader("Performance Metrics")

                # Ingestion metrics
                col1, col2 = st.columns(2)

                with col1:
                    st.subheader("Ingestion")
                    ing = analyzer.ingestion_summary(hours)

                    if ing.get("total_files", 0) > 0:
                        st.metric(
                            "Files",
                            ing.get("total_files", 0),
                            f"Success: {ing.get('successful', 0)}"
                        )
                        st.metric(
                            "Total Chunks",
                            ing.get("total_chunks", 0),
                            f"{ing.get('avg_chunks_per_second', 0):.1f}/s"
                        )
                        st.metric(
                            "Success Rate",
                            f"{ing.get('success_rate', 0)*100:.1f}%"
                        )
                        st.metric(
                            "Time (s)",
                            f"{ing.get('total_time_seconds', 0):.1f}"
                        )
                    else:
                        st.info("No ingestion data yet")

                # Query metrics
                with col2:
                    st.subheader("Queries")
                    qry = analyzer.query_summary(hours)

                    if qry.get("total_queries", 0) > 0:
                        st.metric(
                            "Total Queries",
                            qry.get("total_queries", 0)
                        )
                        st.metric(
                            "Avg Latency",
                            f"{qry.get('avg_latency_ms', 0):.0f}ms",
                            f"P95: {qry.get('p95_latency_ms', 'N/A')}ms"
                        )
                        st.metric(
                            "Cache Hit Rate",
                            f"{qry.get('cache_hit_rate', 0)*100:.1f}%"
                        )
                        st.metric(
                            "Docs Found",
                            f"{qry.get('avg_documents_found', 0):.1f}",
                            "avg per query"
                        )
                    else:
                        st.info("No query data yet")

                # API metrics
                st.subheader("API Calls")
                api = analyzer.api_summary(hours)

                if api.get("total_calls", 0) > 0:
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric(
                            "Total Calls",
                            api.get("total_calls", 0)
                        )
                        st.metric(
                            "Errors",
                            api.get("errors", 0)
                        )
                    with col2:
                        st.metric(
                            "Success Rate",
                            f"{api.get('success_rate', 0)*100:.1f}%"
                        )
                        st.metric(
                            "Avg Latency",
                            f"{api.get('avg_latency_ms', 0):.0f}ms"
                        )
                else:
                    st.info("No API data yet")

                # Detailed report
                if st.button("Show Detailed Report"):
                    with st.expander("Full Metrics Report", expanded=True):
                        # Capture print output
                        import io
                        import sys

                        old_stdout = sys.stdout
                        sys.stdout = io.StringIO()

                        analyzer.print_report(hours)

                        output = sys.stdout.getvalue()
                        sys.stdout = old_stdout

                        st.code(output, language="text")

                # Slowest operations
                if st.checkbox("Show Slowest Operations"):
                    col1, col2 = st.columns(2)

                    with col1:
                        st.markdown("**Slowest Files**")
                        slowest_files = analyzer.get_slowest_files(5)
                        if slowest_files:
                            for i, f in enumerate(slowest_files, 1):
                                st.write(
                                    f"{i}. {f['file']} - "
                                    f"{f['time_seconds']:.1f}s "
                                    f"({f['chunks']} chunks)"
                                )
                        else:
                            st.info("No data")

                    with col2:
                        st.markdown("**Slowest Queries**")
                        slowest_queries = analyzer.get_slowest_queries(5)
                        if slowest_queries:
                            for i, q in enumerate(slowest_queries, 1):
                                st.write(
                                    f"{i}. {q['query']}... - "
                                    f"{q['latency_ms']:.0f}ms"
                                )
                        else:
                            st.info("No data")

            # ===== TAB 2: CHARTS =====
            with tab2:
                st.subheader("Real-Time Charts")

                # Chart selection
                chart_type = st.selectbox(
                    "Select Chart",
                    ["Ingestion Rate", "Query Latency", "Latency Trend", "Cache Hit Rate", "Success Rate"],
                    key="chart_select"
                )

                try:
                    if chart_type == "Ingestion Rate":
                        st.plotly_chart(
                            charts.chart_ingestion_rate(hours or 24),
                            use_container_width=True
                        )
                    elif chart_type == "Query Latency":
                        st.plotly_chart(
                            charts.chart_query_latency(hours or 24),
                            use_container_width=True
                        )
                    elif chart_type == "Latency Trend":
                        st.plotly_chart(
                            charts.chart_query_latency_trend(hours or 24),
                            use_container_width=True
                        )
                    elif chart_type == "Cache Hit Rate":
                        st.plotly_chart(
                            charts.chart_cache_hit_rate(hours or 24),
                            use_container_width=True
                        )
                    elif chart_type == "Success Rate":
                        st.plotly_chart(
                            charts.chart_success_rate(hours or 24),
                            use_container_width=True
                        )

                    st.info("Charts update automatically as new metrics are collected")

                except Exception as e:
                    st.error(f"Error rendering chart: {e}")

            # ===== TAB 3: ALERTS =====
            with tab3:
                st.subheader("Performance Alerts")

                # Run alert checks
                try:
                    active_alerts = alerts_system.check_all(hours or 24)
                    alert_summary = alerts_system.get_alert_summary()

                    # Alert summary cards
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total Alerts", alert_summary["total_alerts"])
                    with col2:
                        st.metric("Critical", alert_summary["critical"], delta_color="inverse")
                    with col3:
                        st.metric("Warning", alert_summary["warning"])
                    with col4:
                        st.metric("Info", alert_summary["info"])

                    st.markdown("---")

                    # Display alerts by severity
                    if active_alerts:
                        # Critical alerts
                        critical_alerts = alerts_system.get_alerts_by_severity(AlertSeverity.CRITICAL)
                        if critical_alerts:
                            st.error("Critical Alerts")
                            for alert in critical_alerts:
                                st.error(f"🔴 {alert.message}\n\n{alert.description}")

                        # Warnings
                        warning_alerts = alerts_system.get_alerts_by_severity(AlertSeverity.WARNING)
                        if warning_alerts:
                            st.warning("Warnings")
                            for alert in warning_alerts:
                                st.warning(f"🟡 {alert.message}\n\n{alert.description}")

                        # Info
                        info_alerts = alerts_system.get_alerts_by_severity(AlertSeverity.INFO)
                        if info_alerts:
                            st.info("Informational Alerts")
                            for alert in info_alerts:
                                st.info(f"ℹ️ {alert.message}\n\n{alert.description}")
                    else:
                        st.success("No alerts detected - system operating normally!")

                except Exception as e:
                    st.error(f"Error checking alerts: {e}")

            # ===== TAB 4: TRENDS =====
            with tab4:
                st.subheader("Historical Trends")

                trend_period = st.selectbox(
                    "Aggregation Period",
                    ["Hourly", "Daily", "Weekly"],
                    key="trend_period"
                )

                try:
                    # Display trend analysis
                    col1, col2 = st.columns(2)

                    with col1:
                        st.markdown("**Ingestion Metrics Trend**")
                        ing = analyzer.ingestion_summary(hours)
                        if ing.get("total_files", 0) > 0:
                            st.write(f"Average Rate: {ing.get('avg_chunks_per_second', 0):.2f} chunks/s")
                            st.write(f"Success Rate: {ing.get('success_rate', 0)*100:.1f}%")
                            st.write(f"Total Size: {ing.get('total_size_mb', 0):.1f} MB")
                        else:
                            st.info("No ingestion data")

                    with col2:
                        st.markdown("**Query Metrics Trend**")
                        qry = analyzer.query_summary(hours)
                        if qry.get("total_queries", 0) > 0:
                            st.write(f"Average Latency: {qry.get('avg_latency_ms', 0):.0f}ms")
                            st.write(f"P95 Latency: {qry.get('p95_latency_ms', 'N/A')}ms")
                            st.write(f"Cache Hit Rate: {qry.get('cache_hit_rate', 0)*100:.1f}%")
                        else:
                            st.info("No query data")

                    st.markdown("---")

                    # Performance recommendations
                    st.markdown("**Performance Insights**")
                    insights = []

                    ing = analyzer.ingestion_summary(hours)
                    qry = analyzer.query_summary(hours)

                    if ing.get("avg_chunks_per_second", 0) < 2:
                        insights.append("⚠️ Ingestion rate is slow, consider optimizing chunk extraction")

                    if qry.get("avg_latency_ms", 0) > 500:
                        insights.append("⚠️ Query latency is high, consider optimizing embedding search")

                    if qry.get("cache_hit_rate", 0) < 0.5:
                        insights.append("⚠️ Cache hit rate is low, consider enabling caching")

                    if ing.get("success_rate", 0) < 0.95:
                        insights.append("⚠️ Ingestion success rate is low, check for problematic PDFs")

                    if insights:
                        for insight in insights:
                            st.info(insight)
                    else:
                        st.success("System performance is optimal!")

                except Exception as e:
                    st.error(f"Error generating trends: {e}")

            # ===== TAB 5: QUERY ANALYTICS =====
            with tab5:
                st.subheader("Query Analytics")

                try:
                    query_analyzer = QueryAnalyzer(metrics_file)

                    # Time range selector
                    qa_time_range = st.selectbox(
                        "Analytics Time Range",
                        ["Last 24h", "Last 7d", "All"],
                        key="qa_time_range"
                    )

                    qa_hours_map = {
                        "Last 24h": 24,
                        "Last 7d": 7 * 24,
                        "All": None
                    }
                    qa_hours = qa_hours_map[qa_time_range]

                    # Query Volume Trend
                    st.markdown("**Query Volume Trend**")
                    volume_data = query_analyzer.get_query_volume_trend(hours=qa_hours or 24)

                    if volume_data['timestamps']:
                        fig_volume = go.Figure()
                        fig_volume.add_trace(go.Scatter(
                            x=volume_data['timestamps'],
                            y=volume_data['volumes'],
                            mode='lines+markers',
                            name='Queries/hour',
                            fill='tozeroy'
                        ))
                        fig_volume.update_layout(
                            title="Hourly Query Volume",
                            xaxis_title="Time",
                            yaxis_title="Number of Queries",
                            hovermode='x unified'
                        )
                        st.plotly_chart(fig_volume, use_container_width=True)
                        st.metric("Total Queries", volume_data['total_queries'])
                        st.metric("Avg per Hour", f"{volume_data['avg_per_hour']:.1f}")
                    else:
                        st.info("No query data available for selected period")

                    st.markdown("---")

                    # Latency Breakdown
                    st.markdown("**Performance Breakdown**")
                    latency_breakdown = query_analyzer.get_latency_breakdown(hours=qa_hours or 24)

                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric(
                            "Avg Search",
                            f"{latency_breakdown['search']['avg']:.0f}ms"
                        )
                    with col2:
                        st.metric(
                            "Avg LLM",
                            f"{latency_breakdown['llm']['avg']:.0f}ms"
                        )
                    with col3:
                        st.metric(
                            "P95 Search",
                            f"{latency_breakdown['search']['p95']:.0f}ms"
                        )
                    with col4:
                        st.metric(
                            "P95 LLM",
                            f"{latency_breakdown['llm']['p95']:.0f}ms"
                        )

                    st.markdown("---")

                    # Slowest Queries
                    st.markdown("**Slowest Queries**")
                    slow_queries = query_analyzer.get_slowest_queries(top_n=10, hours=qa_hours or 24)

                    if slow_queries:
                        for idx, q in enumerate(slow_queries, 1):
                            col1, col2 = st.columns([3, 1])
                            with col1:
                                st.write(f"**{idx}. {q['query'][:80]}...**")
                            with col2:
                                st.write(f"{q['total_ms']:.0f}ms")
                            st.caption(f"Search: {q['search_ms']:.0f}ms | LLM: {q['llm_ms']:.0f}ms | {q['timestamp']}")
                    else:
                        st.info("No slow queries found")

                    st.markdown("---")

                    # Cache Effectiveness
                    st.markdown("**Cache Effectiveness**")
                    cache_data = query_analyzer.get_cache_effectiveness(hours=qa_hours or 24)

                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Cache Hit Rate", f"{cache_data['overall_hit_rate']:.1f}%")
                        st.metric("Total Cache Hits", cache_data['total_cache_hits'])
                    with col2:
                        st.metric("Total Queries", cache_data['total_queries'])

                    if cache_data['timestamps']:
                        fig_cache = go.Figure()
                        fig_cache.add_trace(go.Scatter(
                            x=cache_data['timestamps'],
                            y=cache_data['hit_rates'],
                            mode='lines+markers',
                            name='Hit Rate %',
                            fill='tozeroy'
                        ))
                        fig_cache.update_layout(
                            title="Cache Hit Rate Trend",
                            xaxis_title="Hour",
                            yaxis_title="Hit Rate (%)",
                            yaxis_range=[0, 100],
                            hovermode='x unified'
                        )
                        st.plotly_chart(fig_cache, use_container_width=True)

                    st.markdown("---")

                    # Query Success Rate
                    st.markdown("**Query Success Rate**")
                    success_data = query_analyzer.get_query_success_stats(hours=qa_hours or 24)

                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Success Rate", f"{success_data['overall_success_rate']:.1f}%")
                    with col2:
                        st.metric("Successful", success_data['successful_queries'])
                    with col3:
                        st.metric("Failed", success_data['failed_queries'])

                    if success_data['timestamps']:
                        fig_success = go.Figure()
                        fig_success.add_trace(go.Scatter(
                            x=success_data['timestamps'],
                            y=success_data['success_rates'],
                            mode='lines+markers',
                            name='Success Rate %',
                            fill='tozeroy'
                        ))
                        fig_success.update_layout(
                            title="Query Success Rate Trend",
                            xaxis_title="Hour",
                            yaxis_title="Success Rate (%)",
                            yaxis_range=[0, 100],
                            hovermode='x unified'
                        )
                        st.plotly_chart(fig_success, use_container_width=True)

                except Exception as e:
                    st.error(f"Error generating query analytics: {e}")
                    import traceback
                    st.error(traceback.format_exc())

        except Exception as e:
            st.error(f"Error loading metrics: {e}")


def get_metrics_summary_html() -> str:
    """Get HTML summary of metrics (for displays)"""
    metrics_file = Path("logs/metrics.jsonl")

    if not metrics_file.exists():
        return "<p>No metrics available</p>"

    try:
        analyzer = MetricsAnalyzer(metrics_file)
        ing = analyzer.ingestion_summary()
        qry = analyzer.query_summary()
        api = analyzer.api_summary()

        html = f"""
        <div style="font-size: 12px; color: #666;">
            <p><b>Ingestion:</b> {ing.get('total_files', 0)} files, {ing.get('total_chunks', 0)} chunks</p>
            <p><b>Queries:</b> {qry.get('total_queries', 0)} queries, avg latency {qry.get('avg_latency_ms', 0):.0f}ms</p>
            <p><b>API:</b> {api.get('total_calls', 0)} calls, success rate {api.get('success_rate', 0)*100:.1f}%</p>
        </div>
        """
        return html
    except Exception as e:
        return f"<p>Error: {e}</p>"


if __name__ == "__main__":
    st.set_page_config(page_title="Metrics", layout="wide")
    st.title("System Metrics")
    show_metrics_dashboard()
