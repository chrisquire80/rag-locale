# Multimodal RAG LOCALE - Streamlit UI Integration Guide

**Status**: ✅ READY FOR IMPLEMENTATION
**Date**: 2026-02-18

---

## 🎨 New UI Tab: "📊 Visual Analytics"

### Tab Location & Structure

```
Streamlit App Tabs:
├─ 💬 Chat (existing)
├─ ⭐ Chat Avanzato (existing - with query variants)
├─ 📚 Documenti in Libreria (existing)
├─ 🌍 Analisi Globale (existing)
└─ 📊 VISUAL ANALYTICS (NEW - Multimodal)
```

### New Tab: "📊 Visual Analytics - Multimodal Search"

```
┌────────────────────────────────────────────┐
│ 📊 Visual Analytics - Multimodal Search    │
├────────────────────────────────────────────┤
│                                            │
│  🔍 Search Query: [________________] 🔎   │
│                                            │
│  ☑ Include Charts    ☑ Include Tables    │
│  ☑ Include Images    ☑ Auto-detect visual│
│                                            │
│  ═════════════════════════════════════════ │
│                                            │
│  Result 1: Chart from Page 12             │
│  ┌─────────────────────────────┐          │
│  │   [Chart preview here]      │ ← NEW   │
│  │   Bar chart: 2024-2025      │          │
│  │   Trend: +150%              │          │
│  │   Data: {chart_data_dict}   │          │
│  └─────────────────────────────┘          │
│                                            │
│  Related text: "As you can see in..."     │
│  [Fonte 1] [Fonte 2]                      │
│                                            │
│  ═════════════════════════════════════════ │
│                                            │
│  Result 2: Table from Page 8              │
│  ┌──────────────────────────────┐         │
│  │ Q1  │ Q2  │ Q3  │ Q4        │         │
│  ├─────┼─────┼─────┼──────────┤         │
│  │ 100 │ 120 │ 145 │ 150      │         │
│  └──────────────────────────────┘         │
│                                            │
│  [Download as CSV] [View Source]         │
│                                            │
│  ═════════════════════════════════════════ │
│                                            │
│  Result 3: Chart from Page 5              │
│  [Similar structure as Result 1]          │
│                                            │
└────────────────────────────────────────────┘
```

---

## 🔧 Implementation Code

### Add to `src/app_ui.py`

**Step 1**: Import multimodal components (add to imports)

```python
from rag_engine_multimodal import get_multimodal_rag_engine
from multimodal_retrieval import VisualQueryAnalyzer
```

**Step 2**: Add Visual Analytics tab (add after existing tabs)

```python
# In main() function, after existing tabs:
with tabs[4]:  # New "📊 Visual Analytics" tab
    st.header("📊 Visual Analytics - Multimodal Search")

    # Get multimodal engine
    multimodal_engine = get_multimodal_rag_engine()

    # Query input with visual options
    col1, col2 = st.columns([4, 1])
    with col1:
        visual_query = st.text_input(
            "🔍 Search Query",
            placeholder="e.g. 'Mostra il trend di crescita'",
            key="visual_query"
        )
    with col2:
        search_btn = st.button("🔎 Search", key="visual_search")

    # Visual filtering options
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        include_charts = st.checkbox("📈 Include Charts", value=True)
    with col2:
        include_tables = st.checkbox("📊 Include Tables", value=True)
    with col3:
        include_images = st.checkbox("🖼️ Include Images", value=True)
    with col4:
        auto_detect = st.checkbox("🤖 Auto-detect", value=True)

    if search_btn and visual_query:
        st.divider()

        # Visual intent detection
        analyzer = VisualQueryAnalyzer()
        intent = analyzer.extract_visual_intent(visual_query)

        with st.spinner("🔍 Performing multimodal search..."):
            # Perform multimodal query
            response = multimodal_engine.query_with_multimodal(
                user_query=visual_query,
                include_visuals=True
            )

        # Display detection info
        col1, col2 = st.columns([1, 3])
        with col1:
            st.info(f"🎯 **Intent Detected**")
        with col2:
            if intent.get('needs_visual'):
                st.success(f"Visual query detected: {', '.join(intent.get('visual_types', []))}")
            else:
                st.info("Text-based query")

        # Display answer
        st.subheader("📝 Answer")
        st.write(response.answer)

        # Display visual results
        if response.sources:
            st.subheader("📊 Retrieved Sources")

            for idx, source in enumerate(response.sources[:5], 1):
                with st.container():
                    col1, col2 = st.columns([3, 1])

                    with col1:
                        st.write(f"**[{idx}] {source.source}** (Score: {source.score:.2%})")

                    with col2:
                        st.caption(f"Page N/A")  # Would come from metadata

                    # Show visual elements if available
                    if hasattr(source, 'visual_elements') and source.visual_elements:
                        for visual in source.visual_elements:
                            st.write(f"📈 **{visual.title}**")
                            st.caption(visual.description)
                            if hasattr(visual, 'visual_data') and visual.visual_data:
                                st.code(visual.visual_data, language="text")

                    # Show text preview
                    st.markdown(f"> {source.document[:300]}...")

                    # Download options
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if hasattr(source, 'visual_elements') and source.visual_elements:
                            st.button(f"📥 Download Data", key=f"download_{idx}")
                    with col2:
                        st.button(f"🔗 View Source", key=f"source_{idx}")
                    with col3:
                        st.button(f"➕ Add Context", key=f"context_{idx}")

                    st.divider()

        # Quality metrics
        st.subheader("📈 Quality Metrics")
        metrics = multimodal_engine.get_quality_metrics()

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Vision Enabled", "✅" if metrics.get('multimodal_vision') else "❌")
        with col2:
            st.metric("Visual Boost", f"{metrics.get('visual_boost_factor', 1.2)}x")
        with col3:
            st.metric("Query Expansion", "✅" if metrics.get('task_2_query_expansion') else "❌")
        with col4:
            st.metric("Reranking", "✅" if metrics.get('task_5_cross_encoder_reranking') else "❌")
```

---

## 📁 Sidebar Integration

### Add Visual Analytics Controls to Sidebar

```python
# In sidebar section (add after existing Super-RAG toggle):

with st.sidebar:
    st.divider()
    st.subheader("📊 Visual Analytics")

    # Vision processing options
    enable_vision = st.checkbox("🎨 Enable Vision Analysis", value=True, key="enable_vision")

    if enable_vision:
        vision_dpi = st.slider(
            "📸 Image Quality (DPI)",
            min_value=150,
            max_value=300,
            value=300,
            step=50,
            help="Higher DPI = better quality but slower processing"
        )

        visual_boost = st.slider(
            "⬆️ Visual Boost Factor",
            min_value=1.0,
            max_value=2.0,
            value=1.2,
            step=0.1,
            help="How much to boost visual-rich results (1.0 = no boost, 2.0 = double)"
        )

        # Advanced options
        with st.expander("⚙️ Advanced Options"):
            batch_size = st.number_input(
                "Batch Size",
                min_value=1,
                max_value=20,
                value=5,
                help="Process N PDFs in parallel"
            )

            cache_vision = st.checkbox(
                "Cache Vision Results",
                value=True,
                help="Reuse analysis for same PDFs"
            )
```

---

## 🚀 Document Ingestion with Vision

### Update Document Upload Section

```python
# In document ingestion section (modify existing upload code):

st.subheader("📤 Upload & Ingest Documents")

# Add vision option to upload
use_vision = st.checkbox(
    "🎨 Process with Vision Analysis",
    value=True,
    key="use_vision_ingest",
    help="Automatically extract charts, tables, and images"
)

uploaded_files = st.file_uploader(
    "Choose PDF files",
    type=["pdf"],
    accept_multiple_files=True,
    key="multimodal_uploader"
)

if uploaded_files:
    progress_bar = st.progress(0)
    status_text = st.empty()

    multimodal_engine = get_multimodal_rag_engine()

    for idx, file in enumerate(uploaded_files):
        # Save uploaded file temporarily
        temp_path = f"temp_{file.name}"
        with open(temp_path, "wb") as f:
            f.write(file.getbuffer())

        # Ingest with or without vision
        if use_vision:
            status_text.text(f"🎨 Processing {file.name} with vision analysis...")
            result = multimodal_engine.ingest_document_with_vision(temp_path)

            # Display result
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Pages", result.get('pages_processed', 0))
            with col2:
                st.metric("Charts Found", result.get('charts_found', 0))
            with col3:
                st.metric("Tables Found", result.get('tables_found', 0))
        else:
            status_text.text(f"📄 Processing {file.name} (text only)...")
            result = multimodal_engine.ingest_document(temp_path)

        # Update progress
        progress_bar.progress((idx + 1) / len(uploaded_files))

        # Cleanup
        import os
        os.remove(temp_path)

    st.success(f"✅ Ingested {len(uploaded_files)} documents with vision analysis!")
    progress_bar.empty()
    status_text.empty()
```

---

## 📊 Visual Dashboard

### New Dashboard Tab for Document Statistics

```python
# In Analisi Globale or new Statistics tab:

def display_visual_statistics():
    """Display visual content statistics"""
    st.subheader("📊 Document Visual Content Statistics")

    multimodal_engine = get_multimodal_rag_engine()

    # Get all documents
    all_docs = multimodal_engine.vector_store.get_all_documents()

    total_charts = 0
    total_tables = 0
    total_images = 0

    # Create statistics dataframe
    stats_data = []
    for doc in all_docs:
        doc_stats = {
            'Document': doc.get('source', 'Unknown'),
            'Pages': doc.get('num_chunks', 0),
            'Charts': doc.get('charts_count', 0),
            'Tables': doc.get('tables_count', 0),
            'Images': doc.get('images_count', 0),
        }
        stats_data.append(doc_stats)
        total_charts += doc_stats['Charts']
        total_tables += doc_stats['Tables']
        total_images += doc_stats['Images']

    # Display overview metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Documents", len(all_docs))
    with col2:
        st.metric("Total Charts", total_charts)
    with col3:
        st.metric("Total Tables", total_tables)
    with col4:
        st.metric("Total Images", total_images)

    # Display detailed table
    import pandas as pd
    df = pd.DataFrame(stats_data)
    st.dataframe(df, use_container_width=True)

    # Display distribution charts
    col1, col2 = st.columns(2)
    with col1:
        st.bar_chart(df.set_index('Document')['Charts'])
    with col2:
        st.bar_chart(df.set_index('Document')['Tables'])
```

---

## 🧪 Testing Integration

### Create Integration Tests

```python
# test_multimodal_ui_integration.py

import pytest
from streamlit.testing.v1 import AppTest
from rag_engine_multimodal import get_multimodal_rag_engine

def test_visual_intent_detection():
    """Test visual intent detection in queries"""
    engine = get_multimodal_rag_engine()

    # Test cases
    visual_queries = [
        "Mostra il grafico dei trend",
        "Visualizza la tabella dei dati",
        "Che cosa vedi nel diagramma?",
    ]

    text_queries = [
        "Qual è il significato di Factorial?",
        "Come funziona la piattaforma?",
    ]

    for query in visual_queries:
        intent = VisualQueryAnalyzer().extract_visual_intent(query)
        assert intent['needs_visual'] == True

    for query in text_queries:
        intent = VisualQueryAnalyzer().extract_visual_intent(query)
        assert intent['needs_visual'] == False


def test_multimodal_retrieval():
    """Test multimodal retrieval"""
    engine = get_multimodal_rag_engine()

    response = engine.query_with_multimodal(
        "Mostra il trend di crescita",
        include_visuals=True
    )

    assert response.answer is not None
    assert len(response.sources) > 0
    assert response.model == "gemini-2.0-flash"


def test_vision_ingestion():
    """Test document ingestion with vision"""
    engine = get_multimodal_rag_engine()

    result = engine.ingest_document_with_vision("test_report.pdf")

    assert result['pages_processed'] > 0
    assert 'visual_elements_indexed' in result
```

---

## 📋 Implementation Checklist

- [ ] Add multimodal imports to `app_ui.py`
- [ ] Create "📊 Visual Analytics" tab
- [ ] Add sidebar Visual Analytics controls
- [ ] Update document upload with vision option
- [ ] Add visual statistics dashboard
- [ ] Create integration tests
- [ ] Test with sample PDFs
- [ ] Verify chart extraction accuracy
- [ ] Verify table extraction accuracy
- [ ] Performance benchmark
- [ ] Deploy to production

---

## 🎯 Success Metrics

- ✅ Visual intent detection accuracy: >90%
- ✅ Chart extraction accuracy: >90%
- ✅ Table extraction accuracy: >95%
- ✅ Query response time: <3s
- ✅ Document ingestion: <25 min for 82 PDFs
- ✅ User satisfaction: +40%

---

## 📞 Troubleshooting UI Issues

### Issue: Charts not displaying
**Solution**: Verify image extraction worked
```python
result = engine.ingest_document_with_vision("file.pdf")
print(f"Charts found: {result['charts_found']}")
```

### Issue: Query slow with vision
**Solution**: Reduce DPI or disable auto-detect
```python
engine.vision_dpi = 150  # Lower quality
# Or use text-only: include_visuals=False
```

### Issue: Memory issues with large documents
**Solution**: Process in batches
```python
# Process one at a time
for file in large_files:
    engine.ingest_document_with_vision(file)
    gc.collect()  # Force garbage collection
```

---

## 🚀 Deployment

### Production Checklist

- [ ] All tests passing (>95% pass rate)
- [ ] Performance benchmarked
- [ ] Error handling comprehensive
- [ ] Documentation complete
- [ ] Security review passed
- [ ] Rate limiting configured
- [ ] Caching configured
- [ ] Monitoring enabled

---

**Status**: ✅ READY FOR IMPLEMENTATION
**Next Step**: Implement Visual Analytics tab in Streamlit
**Timeline**: 2-3 hours for complete implementation

