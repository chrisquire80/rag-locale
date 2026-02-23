"""
Streamlit Application Entry Point

Launches the RAG LOCALE interactive UI with structured logging configured.
Auto-initializes JSON logging and metrics collection.

Usage:
    streamlit run src/app_streamlit.py
"""

import sys
from pathlib import Path

# Initialize structured logging FIRST (before any other imports)
from src.logging_config import get_logger, configure_logging

# Configure logging early
configure_logging(level="INFO", log_file="logs/streamlit.jsonl", console=True)
logger = get_logger(__name__)

logger.info("Streamlit application starting")

# Now import other modules
import streamlit as st
from src.config import config, print_config
from src.rag_engine import RAGEngine
from src.memory_service import get_memory_service

logger.info("All modules imported successfully")


def main():
    """Main Streamlit application"""
    # Page config
    st.set_page_config(
        page_title="RAG LOCALE",
        page_icon="🚀",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Title
    st.title("🚀 RAG LOCALE - Sistema Aziendale")
    st.markdown(
        """
        **Zero-Cloud • Sovranità Dato • GDPR Compliant**

        Interroga i tuoi documenti con IA locale.
        """
    )

    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configurazione")
        logger.info("Sidebar rendered")

        # System info
        with st.expander("📊 System Info"):
            st.metric("Log Level", config.log_level)
            st.metric("Environment", config.environment)

    # Main content area
    col1, col2 = st.columns([2, 1])

    with col1:
        st.header("📝 Query Documents")
        query = st.text_input(
            "Enter your question:",
            placeholder="What is this document about?",
            key="query_input"
        )

        if query:
            logger.info("Query received", query=query[:100])  # Log first 100 chars

            with st.spinner("Processing..."):
                try:
                    rag_engine = RAGEngine()
                    response = rag_engine.query(query)

                    logger.info(
                        "Query completed",
                        query_length=len(query),
                        documents_found=len(response.sources),
                        latency_ms=int(
                            (response.latency_ms if hasattr(response, 'latency_ms') else 0)
                        ),
                    )

                    # Display response
                    st.success("✅ Query completed")
                    st.markdown("### Response")
                    st.write(response.answer if hasattr(response, 'answer') else str(response))

                    # Display sources
                    if hasattr(response, 'sources') and response.sources:
                        st.markdown("### 📚 Sources")
                        for i, source in enumerate(response.sources, 1):
                            st.write(f"**{i}. {source.file_name}**")

                except Exception as e:
                    logger.error(
                        "Query failed",
                        error=str(e),
                        query=query[:50],
                    )
                    st.error(f"❌ Error: {e}")

    with col2:
        st.header("📊 Metrics")
        memory_svc = get_memory_service()

        # Show recent stats
        stats = memory_svc.get_stats()
        st.metric("Total Queries", stats.get("total_interactions", 0))
        st.metric("Anomalies Found", stats.get("total_anomalies", 0))

        if stats.get("anomaly_rate"):
            st.metric("Anomaly Rate", f"{stats['anomaly_rate']:.1%}")

    logger.info("Streamlit render complete")


if __name__ == "__main__":
    logger.info("=== Streamlit App Started ===")
    main()
    logger.info("=== Streamlit App Finished ===")
