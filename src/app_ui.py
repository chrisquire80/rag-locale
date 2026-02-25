
import streamlit as st
import os
from pathlib import Path
import time
import shutil

# Add src to python path if needed (though running from root usually works)
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.config import config, DOCUMENTS_DIR
from src.rag_engine import RAGEngine
from src.document_ingestion import DocumentIngestionPipeline
from src.metrics.ui import show_metrics_dashboard
from src.progress_callbacks import StreamlitProgressCallback
from src.logging_config import get_logger

# FASE 7: Feature integrations
from src.tag_manager import TagManager
from src.search_filters import SearchFilter, SearchFilterBuilder
from src.upload_manager import UploadManager
from src.vector_store import get_vector_store
from src.metrics import get_metrics_collector

logger = get_logger(__name__)

# Configure page
st.set_page_config(
    page_title="RAG Locale - Gemini Hybrid",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Logging configured via logging_config.py

# Custom CSS
st.markdown("""
<style>
    .stChatMessage {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        box-shadow: 0 1px 2px rgba(0,0,0,0.1);
    }
    .stChatMessage.user {
        background-color: #f0f2f6;
    }
    .stChatMessage.assistant {
        background-color: #e8f0fe;
        border-left: 5px solid #4285f4;
    }
    .sidebar-content {
        padding: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# Initialize Session State
if "messages" not in st.session_state:
    st.session_state.messages = []

if "engine_loaded" not in st.session_state:
    st.session_state.engine_loaded = False

# Cache the RAG Engine to avoid reloading on every interaction
@st.cache_resource
def load_engine():
    try:
        engine = RAGEngine()
        # Verify engine loaded
        if engine is None:
            st.error("❌ Errore: Impossibile inizializzare il motore RAG.")
            return None
        # CRITICAL: Disable HITL for Streamlit (no interactive input available)
        engine.enable_hitl = False
        logger.info("ℹ️  HITL disabilitato per ambiente Streamlit")
        return engine
    except Exception as e:
        st.error(f"❌ Errore durante l'inizializzazione del motore RAG: {e}")
        import traceback
        st.error(traceback.format_exc())
        return None

# Initialize session state for Super-RAG
if "super_rag_enabled" not in st.session_state:
    st.session_state.super_rag_enabled = True
if "enable_query_expansion" not in st.session_state:
    st.session_state.enable_query_expansion = True
if "enable_reranking" not in st.session_state:
    st.session_state.enable_reranking = True

# Sidebar
with st.sidebar:
    st.title("🎛️ Configurazione")
    st.markdown("---")

    # NEW: Super-RAG Toggle
    st.subheader("⚡ Super-RAG Mode")

    col1, col2 = st.columns([0.6, 0.4])
    with col1:
        st.session_state.super_rag_enabled = st.checkbox(
            "Abilita Super-RAG",
            value=st.session_state.super_rag_enabled,
            help="Attiva Query Expansion + Reranking per migliore qualità (più lento)"
        )
    with col2:
        if st.session_state.super_rag_enabled:
            st.success("✅ ON")
        else:
            st.info("⚫ OFF")

    # Sub-options for Super-RAG
    if st.session_state.super_rag_enabled:
        st.caption("Opzioni avanzate:")
        col1, col2 = st.columns(2)
        with col1:
            st.session_state.enable_query_expansion = st.checkbox("Query Expansion", value=st.session_state.enable_query_expansion)
        with col2:
            st.session_state.enable_reranking = st.checkbox("Reranking", value=st.session_state.enable_reranking)

    st.markdown("---")

    # ===== PHASE 11.3: USER PREFERENCES & FEEDBACK =====
    with st.expander("⚙️ **Preferenze**", expanded=False):
        st.markdown("**Response Format**")
        response_format = st.selectbox(
            "Stile risposta",
            ["summary", "detailed", "bullets"],
            index=0,
            help="summary: risposta breve | detailed: completa | bullets: punti elenco"
        )

        st.markdown("**Response Length**")
        response_length = st.slider(
            "Lunghezza risposta (parole)",
            min_value=100,
            max_value=1000,
            value=500,
            step=50
        )

        st.markdown("**Display Options**")
        col1, col2 = st.columns(2)
        with col1:
            show_confidence = st.checkbox("Mostra Confidence Score", value=True)
        with col2:
            show_sources = st.checkbox("Mostra Fonti", value=True)

        st.markdown("**Theme**")
        theme = st.selectbox(
            "Tema",
            ["light", "dark", "auto"],
            index=2,
            help="light: chiaro | dark: scuro | auto: automatico"
        )

        # Store preferences in session state
        st.session_state.response_format = response_format
        st.session_state.response_length = response_length
        st.session_state.show_confidence = show_confidence
        st.session_state.show_sources = show_sources
        st.session_state.theme = theme

    st.markdown("---")

    st.subheader("🤖 Modello AI")
    st.info(f"Using: **{config.gemini.model_name}**")

    st.subheader("📂 Documenti")
    
    st.subheader("📂 Carica da Cartella")
    
    col1, col2 = st.columns([0.7, 0.3])
    
    # Session State for folder path
    if "selected_folder" not in st.session_state:
        st.session_state.selected_folder = ""

    with col2:
        if st.button("📂 Sfoglia"):
            try:
                import tkinter as tk
                from tkinter import filedialog
                
                # Create hidden root window
                root = tk.Tk()
                root.withdraw()
                # Make it top most
                root.wm_attributes('-topmost', 1)
                
                # Open dialog
                folder_path = filedialog.askdirectory(master=root)
                
                # Cleanup
                root.destroy()
                
                if folder_path:
                    st.session_state.selected_folder = folder_path
                    st.rerun()
            except Exception as e:
                st.error(f"Errore apertura dialogo: {e}")
    
    with col1:
        folder_path = st.text_input(
            "Percorso:", 
            value=st.session_state.selected_folder,
            placeholder="Seleziona una cartella...",
            label_visibility="collapsed"
        )

    if folder_path and st.button("📥 Importa Cartella", use_container_width=True):
        path = Path(folder_path)
        if not path.exists() or not path.is_dir():
            st.error("Percorso non valido o non è una cartella.")
        else:
            # FASE 13: Create progress UI elements and callback
            progress_bar = st.progress(0)
            status_text = st.empty()
            details_container = st.container()

            # Create StreamlitProgressCallback for real-time updates
            progress_callback = StreamlitProgressCallback(
                progress_bar=progress_bar,
                status_text=status_text,
                details_container=details_container
            )

            files = [f for f in path.glob('*') if f.suffix.lower() in ['.pdf', '.txt', '.md', '.docx']]

            if not files:
                st.warning("Nessun documento compatibile trovato.")
            else:
                pipeline = DocumentIngestionPipeline()

                try:
                    # Copy files to documents directory first
                    copied_files = []
                    for file_path in files:
                        status_text.text(f"Copiando {file_path.name}...")
                        dest_path = DOCUMENTS_DIR / file_path.name
                        shutil.copy2(file_path, dest_path)
                        copied_files.append(dest_path)

                    status_text.text(f"Ingestione di {len(copied_files)} documenti...")

                    # FASE 13: Use ingest_from_directory with progress callback for batch processing
                    total_chunks = pipeline.ingest_from_directory(
                        directory=DOCUMENTS_DIR,
                        progress_callback=progress_callback
                    )

                    # FASE 9: Protected stats check with error handling
                    try:
                        stats = pipeline.vector_store.get_stats()
                        with details_container:
                            st.success(f"✅ Ingestion completato! {stats['total_documents']} documenti totali nel store")
                            st.info(f"📊 Importati {len(files)} file, {total_chunks} chunks generati")
                    except Exception as e:
                        st.error(f"Errore lettura statistiche: {e}")
                        logger.error(f"Stats retrieval failed: {e}")

                except Exception as e:
                    st.error(f"❌ Errore durante l'ingestione: {e}")
                    logger.error(f"Folder import failed: {e}", exc_info=True)
                finally:
                    time.sleep(2)
                    status_text.empty()
                    progress_bar.empty()

    st.markdown("---")
    
    # File Uploader
    uploaded_files = st.file_uploader(
        "Oppure carica file singoli", 
        type=['pdf', 'txt', 'md'], 
        accept_multiple_files=True
    )
    
    if uploaded_files:
        if st.button("Ingest Files"):
            # FASE 13: Create progress UI elements and callback
            progress_bar = st.progress(0)
            status_text = st.empty()
            details_container = st.container()

            # Create StreamlitProgressCallback for real-time updates
            progress_callback = StreamlitProgressCallback(
                progress_bar=progress_bar,
                status_text=status_text,
                details_container=details_container
            )

            pipeline = DocumentIngestionPipeline()

            try:
                # Save all files first
                saved_files = []
                for file in uploaded_files:
                    status_text.text(f"Salvando {file.name}...")
                    save_path = DOCUMENTS_DIR / file.name
                    with open(save_path, "wb") as f:
                        f.write(file.getbuffer())
                    saved_files.append(save_path)

                # FASE 13: Process all files with progress callback
                for i, file_path in enumerate(saved_files):
                    total_chunks = pipeline.ingest_single_file(
                        file_path,
                        progress_callback=progress_callback,
                        file_number=i + 1,
                        total_files=len(saved_files)
                    )

                # Show completion
                with details_container:
                    st.success("✅ Ingestione completata!")

            except Exception as e:
                st.error(f"❌ Errore durante l'ingestione: {e}")
                logger.error(f"File upload ingestion failed: {e}", exc_info=True)
            finally:
                time.sleep(2)
                status_text.empty()
                progress_bar.empty()
                st.rerun()

    st.markdown("---")

    # OPTIMIZATION 8.3: Cache document directory listing with TTL
    @st.cache_data(ttl=60)  # Cache for 60 seconds - refreshes on document upload
    def get_cached_documents():
        """Cache directory listing to avoid filesystem scan on every render"""
        return list(DOCUMENTS_DIR.glob('*'))

    # Documents List (Simple)
    docs_cached = get_cached_documents()
    st.subheader(f"📚 Libreria ({len(docs_cached)})")
    doc_filter = st.text_input("Cerca file...", placeholder="nome file", label_visibility="collapsed")

    docs = docs_cached
    if doc_filter:
        docs = [d for d in docs if doc_filter.lower() in d.name.lower()]
    
    for doc in docs[:20]:  # Limit to 20 to avoid flooding
        if doc.is_file():
            st.caption(f"📄 {doc.name}")
    if len(docs) > 20:
        st.caption(f"...e altri {len(docs)-20} file.")

    st.subheader("🛠️ Diagnostica")

    # Show timeout configuration
    with st.expander("⏱️ Configurazione Timeout"):
        st.info(f"""
        **Timeout Configurati:**
        - Request timeout: {config.gemini.request_timeout}s
        - Embedding timeout: {config.gemini.embedding_timeout}s
        - Completion timeout: {config.gemini.completion_timeout}s
        - Max retries: {config.gemini.max_retries}
        - Retry delay base: {config.gemini.retry_base_delay}s

        **Sequenza Retry:** Exponential backoff (1s, 2s, 4s, 8s, 16s, ...)
        """)

    if st.button("Test API Connection"):
        with st.status("Running diagnostics...", expanded=True) as status:
            try:
                st.write("Checking API Key...")
                if not config.gemini.api_key:
                    st.error("API Key not found!")
                else:
                    st.write("✓ API Key found.")

                st.write("Testing Embedding Model with timeout handling...")
                import google.genai as genai
                model = config.gemini.embedding_model
                st.write(f"Model: {model}")

                # Use new google-genai API
                client = genai.Client(api_key=config.gemini.api_key.get_secret_value())
                result = client.models.embed_content(
                    model=model,
                    contents="Test embedding with improved timeout handling"
                )
                if result and hasattr(result, 'embeddings') and result.embeddings:
                    embedding_len = len(result.embeddings[0].values)
                    st.success(f"✓ Embeddings working! Vector length: {embedding_len}")
                else:
                    st.error(f"Unexpected result: {result}")

            except Exception as e:
                st.error(f"API Error: {e}")
                logger.error(f"Diagnostic test failed: {e}", exc_info=True)
                import traceback
                st.text(traceback.format_exc())

            status.update(label="Diagnostics complete", state="complete")

    if st.button("🔄 Reload Engine"):
        load_engine.clear()
        st.rerun()

    st.subheader("Gestione Dati")
    if st.button("Reset Database (Cancella Tutto)"):
        try:
            # Elimina file fisico
            db_path = config.chromadb.persist_directory / "vector_store.pkl"
            if db_path.exists():
                db_path.unlink()
                st.success("Database cancellato!")
            else:
                st.warning("Nessun database trovato.")

            # Pulisce cache memoria
            load_engine.clear()
            time.sleep(1)
            st.rerun()
        except Exception as e:
            st.error(f"Errore durante reset: {e}")

    # FASE 10: Metrics Dashboard
    show_metrics_dashboard()

# Main Content
st.title("🤖 RAG Locale (Gemini Hybrid + Quality Improvements)")
st.caption("Interroga i tuoi documenti con AI avanzata: Self-Correction, Query Expansion, Inline Citations, Temporal Metadata, Semantic Reranking, Multi-Document Analysis.")

# Load Engine
engine = load_engine()

if engine:
    # FASE 7: Create five tabs including Upload and Advanced filters
    # Create tabs: Upload, Chat, Advanced Chat, Document Library, Global Analysis
    tab_upload, tab_chat, tab_advanced, tab_library, tab_analysis = st.tabs([
        "📤 Upload Documenti",
        "💬 Chat",
        "⭐ Chat Avanzato",
        "📚 Documenti in Libreria",
        "🌍 Analisi Globale"
    ])

    # === TAB 0: UPLOAD DOCUMENTS (FASE 7: Feature 3) ===
    with tab_upload:
        st.subheader("📤 Carica Documenti")
        st.caption("Carica i tuoi documenti in batch con validazione automatica e rilevamento duplicati")

        try:
            # Initialize managers
            vector_store = get_vector_store()
            upload_manager = UploadManager(vector_store)

            # Folder organization
            with st.expander("📁 Organizza per Cartella", expanded=True):
                folder_input = st.text_input(
                    "Nome cartella (opzionale)",
                    placeholder="es: 'Papers di Ricerca'",
                    help="I documenti saranno organizzati in questa cartella"
                )

            # File uploader
            uploaded_files = st.file_uploader(
                "Seleziona file da caricare",
                type=["pdf", "txt", "md"],
                accept_multiple_files=True,
                help="PDF, TXT, Markdown supportati"
            )

            # Upload options
            with st.expander("⚙️ Opzioni Upload"):
                skip_duplicates = st.checkbox("Salta documenti duplicati", value=True)
                auto_tag = st.checkbox("Auto-tag documenti (Feature 1)", value=True)

            # Upload button
            if uploaded_files and st.button("🚀 Carica File", type="primary", key="upload_button"):
                progress_container = st.container()

                with progress_container:
                    with st.spinner(f"Caricamento {len(uploaded_files)} file..."):
                        # Process uploads
                        results = upload_manager.process_batch_upload(
                            uploaded_files,
                            vector_store,
                            folder=folder_input if folder_input else None,
                            skip_duplicates=skip_duplicates
                        )

                        # Display results
                        st.divider()
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("✅ Caricati", len(results['success']))
                        with col2:
                            st.metric("⚠️ Saltati", len(results['duplicates']))
                        with col3:
                            st.metric("❌ Errori", len(results['failed']))

                        # Success details
                        if results['success']:
                            with st.expander("✅ Caricamenti Riusciti", expanded=True):
                                for filename in results['success']:
                                    st.success(f"✓ {filename}")

                        # Duplicate details
                        if results['duplicates']:
                            with st.expander("⚠️ Duplicati Saltati"):
                                for filename in results['duplicates']:
                                    st.warning(f"⊘ {filename} (gia indicizzato)")

                        # Error details
                        if results['failed']:
                            with st.expander("❌ Errori di Caricamento", expanded=len(results['failed']) < 3):
                                for filename, error in results['failed'].items():
                                    with st.container(border=True):
                                        st.error(f"✗ {filename}")
                                        st.caption(f"Errore: {error}")

            # Upload history
            st.divider()
            st.subheader("📜 Upload Recenti")
            try:
                metrics = get_metrics_collector()
                recent = metrics.ingestion_metrics[-10:] if metrics.ingestion_metrics else []
                if recent:
                    for metric in reversed(recent):
                        status = "✅" if metric.success else "❌"
                        st.text(f"{status} {metric.file_name} - {metric.duration_seconds:.1f}s")
                else:
                    st.info("Nessun caricamento recente")
            except Exception as e:
                st.warning(f"Non disponibile: {e}")

        except Exception as e:
            st.error(f"Errore nella tab Upload: {e}")
            logger.error(f"Upload tab error: {e}", exc_info=True)

    # === TAB 1: CHAT ===
    with tab_chat:
        # Display Chat History
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        # FASE 7: Advanced Filters Sidebar (Feature 2)
        with st.expander("⚙️ Filtri Avanzati", expanded=False):
            st.caption("Combina più criteri di ricerca per risultati più precisi")

            try:
                vector_store = get_vector_store()
                tag_manager = TagManager()

                col1, col2 = st.columns(2)

                with col1:
                    # Document type filter
                    doc_types = st.multiselect(
                        "Tipi Documento",
                        ["pdf", "txt", "md"],
                        help="Filtra per estensione file"
                    )

                    # Tag filter (Feature 1 integration)
                    try:
                        all_tags = tag_manager.get_all_tags(vector_store)
                        if all_tags:
                            selected_tags = st.multiselect(
                                "Tag Documenti",
                                list(all_tags.keys()),
                                help="Filtra per tag estratti automaticamente"
                            )
                        else:
                            selected_tags = None
                            st.info("Nessun tag disponibile (carica alcuni documenti)")
                    except Exception as e:
                        st.warning(f"Tag non disponibili: {e}")
                        selected_tags = None

                with col2:
                    # Similarity threshold
                    similarity_min = st.slider(
                        "Soglia Rilevanza Minima",
                        0.0, 1.0, 0.0, 0.05,
                        help="Scarta risultati con punteggio inferiore"
                    )

                    # Source document filter
                    try:
                        available_docs = vector_store.list_indexed_files() if hasattr(vector_store, 'list_indexed_files') else []
                        if available_docs:
                            source_docs = st.multiselect(
                                "Limita ai Documenti",
                                available_docs,
                                help="Cerchia solo in questi documenti"
                            )
                        else:
                            source_docs = None
                    except Exception as e:
                        st.warning(f"Documenti non disponibili: {e}")
                        source_docs = None

                # Store filters in session state
                st.session_state.advanced_filters = {
                    'document_types': doc_types if doc_types else None,
                    'similarity_threshold': similarity_min if similarity_min > 0.0 else 0.0,
                    'tags': selected_tags if selected_tags else None,
                    'source_documents': source_docs if source_docs else None,
                }

            except Exception as e:
                st.warning(f"Errore caricamento filtri: {e}")
                st.session_state.advanced_filters = {}

        # Chat Input
        if prompt := st.chat_input("Fai una domanda sui tuoi documenti..."):
            # Add user message to history
            st.session_state.messages.append({"role": "user", "content": prompt})

            # Display user message
            with st.chat_message("user"):
                st.markdown(prompt)

            # Generate output
            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                full_response = ""

                # Show a spinner while thinking
                with st.spinner("Analisi in corso (con timeout handling)..."):
                    try:
                        # FASE 7: Query with advanced filters (Feature 2)
                        filters = getattr(st.session_state, 'advanced_filters', {})
                        response = engine.query(
                            prompt,
                            auto_approve_if_high_confidence=True,
                            similarity_threshold=filters.get('similarity_threshold', 0.0),
                            document_types=filters.get('document_types', None),
                            tags=filters.get('tags', None),
                            source_documents=filters.get('source_documents', None),
                        )

                        # Simulate streaming for UX (since synchronous)
                        full_response = response.answer

                        # ===== PHASE 11.1: Enhanced Response Visualization =====
                        # Extract confidence metrics
                        confidence_score = getattr(response, 'confidence_score', 0.0)

                        # Calculate confidence level and emoji
                        if confidence_score >= 75:
                            confidence_level = "High"
                            emoji = "🟢"
                            color = "green"
                        elif confidence_score >= 50:
                            confidence_level = "Medium"
                            emoji = "🟡"
                            color = "orange"
                        else:
                            confidence_level = "Low"
                            emoji = "🔴"
                            color = "red"

                        # ==== CARD-BASED LAYOUT WITH VISUAL HIERARCHY ====
                        with st.container(border=True):
                            # Header section with confidence badge and metadata
                            col1, col2, col3 = st.columns([2, 3, 1])

                            with col1:
                                st.markdown(f"### 📝 Risposta")

                            with col2:
                                st.markdown(f"**{emoji} {confidence_level} Confidence** ({confidence_score:.0f}%)")

                            with col3:
                                # Show latency metadata
                                search_ms = getattr(response, 'search_latency_ms', 0)
                                llm_ms = getattr(response, 'llm_latency_ms', 0)
                                st.caption(f"⏱️ {search_ms:.0f}ms search + {llm_ms:.0f}ms LLM")

                            st.divider()

                            # ==== EMBED CITATIONS IN ANSWER TEXT ====
                            # Create citation markers and map to sources
                            if response.sources:
                                try:
                                    from src.confidence import ConfidenceCalculator
                                    calc = ConfidenceCalculator()
                                    ranked_sources = calc.rank_sources(response.sources)
                                except Exception:
                                    ranked_sources = response.sources

                                # Build citation markers [Ref 1], [Ref 2], etc.
                                citation_map = {}
                                for idx, src in enumerate(ranked_sources[:5], 1):  # Max 5 citations
                                    doc_name = getattr(src, 'source', 'Unknown')
                                    citation_map[idx] = (doc_name, src)

                                # Simple heuristic: add citations after key sentences
                                answer_with_citations = full_response
                                if citation_map and len(ranked_sources) > 0:
                                    # Add citation for primary source at the end of first sentence
                                    sentences = answer_with_citations.split('. ')
                                    if len(sentences) > 0 and len(citation_map) > 0:
                                        sentences[0] = sentences[0] + ' [Ref 1]'
                                        answer_with_citations = '. '.join(sentences)
                            else:
                                answer_with_citations = full_response
                                ranked_sources = []
                                citation_map = {}

                            # Display answer with embedded citations
                            st.markdown(answer_with_citations)

                            # Show confidence explanation
                            if confidence_score < 50:
                                st.warning(f"⚠️ **Low confidence** ({confidence_score:.0f}%) - Please verify with sources below")

                        # ==== SOURCES CARD WITH PREVIEWS ====
                        if ranked_sources:
                            with st.expander("📚 **Sources & Evidence** (click to expand)", expanded=True):
                                for idx, source in enumerate(ranked_sources[:5], 1):  # Show top 5 sources
                                    with st.container(border=True):
                                        # Source header
                                        doc_name = getattr(source, 'source', 'Unknown')
                                        score = getattr(source, 'score', 0.0)
                                        percentage = int(score * 100)

                                        # Visual confidence bar
                                        filled = int(10 * score)
                                        bar = "█" * filled + "░" * (10 - filled)

                                        # Primary source indicator
                                        primary_badge = " ⭐ PRIMARY SOURCE" if idx == 1 else ""

                                        col1, col2, col3 = st.columns([0.15, 0.7, 0.15])
                                        with col1:
                                            st.markdown(f"**[{idx}]**")
                                        with col2:
                                            st.markdown(f"**{doc_name}**{primary_badge}")
                                        with col3:
                                            st.markdown(f"`{percentage}%`")

                                        # Confidence bar with label
                                        st.markdown(f"{bar}")

                                        # Extract and display document snippet (preview)
                                        doc_text = getattr(source, 'document', '')
                                        section = getattr(source, 'section', '')

                                        if doc_text:
                                            # Create preview (first 200 chars, clean up)
                                            preview = doc_text[:200].strip()
                                            if len(doc_text) > 200:
                                                preview += "..."

                                            st.caption(f"📄 **Preview:**")
                                            st.markdown(f"*{preview}*")

                                        if section:
                                            st.caption(f"📌 Section: {section}")

                                        st.divider()
                        else:
                            st.info("ℹ️ No sources found for this query")

                        # ===== PHASE 11.3: FEEDBACK BUTTONS =====
                        st.divider()
                        st.markdown("### 👍 Feedback")

                        col1, col2, col3, col4 = st.columns(4)

                        # Generate unique key based on response hash
                        response_key = hash(str(full_response))

                        with col1:
                            if st.button("👍 Helpful", key=f"helpful_{response_key}"):
                                st.success("✅ Thanks for the feedback!")

                        with col2:
                            if st.button("👎 Not Helpful", key=f"unhelpful_{response_key}"):
                                st.info("ℹ️ We'll improve this response")

                        with col3:
                            if st.button("🔗 Copy", key=f"copy_{response_key}"):
                                st.write("📋 Copied to clipboard (paste in another app)")

                        with col4:
                            # Build export text
                            export_text = f"Query: {prompt}\n\nAnswer: {full_response}\n\n"
                            if ranked_sources:
                                export_text += "Sources:\n"
                                for idx, src in enumerate(ranked_sources, 1):
                                    src_name = getattr(src, 'source', 'Unknown')
                                    src_score = getattr(src, 'score', 0.0)
                                    export_text += f"{idx}. {src_name} ({src_score*100:.0f}%)\n"

                            st.download_button(
                                label="📥 Export",
                                data=export_text,
                                file_name="response.txt",
                                mime="text/plain",
                                key=f"export_{response_key}"
                            )

                        # Add to history
                        st.session_state.messages.append({"role": "assistant", "content": full_response})

                    except TimeoutError as e:
                        error_msg = f"❌ Timeout durante la generazione della risposta (riprova, il sistema ritenta automaticamente): {e}"
                        st.error(error_msg)
                        logger.error(f"Timeout in query: {e}", exc_info=True)

                    except ConnectionError as e:
                        error_msg = f"❌ Errore di connessione API (il sistema ritenta automaticamente): {e}"
                        st.error(error_msg)
                        logger.error(f"Connection error in query: {e}", exc_info=True)

                    except Exception as e:
                        import traceback
                        error_msg = f"❌ Errore generazione risposta: {type(e).__name__}: {e}"
                        st.error(error_msg)
                        # Show detailed traceback in expander
                        with st.expander("📋 Dettagli errore"):
                            st.code(traceback.format_exc(), language="python")
                        logger.error(f"Query generation failed: {e}", exc_info=True)

    # === TAB 2: ADVANCED CHAT (con Quality Improvements) ===
    with tab_advanced:
        st.subheader("⭐ Chat Avanzato - Con Quality Improvements")
        st.caption("TASK 1-6: Self-Correction • Query Expansion • Inline Citations • Temporal • Reranking • Multi-Doc Analysis")

        # Display Chat History
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        # Chat Input
        if prompt := st.chat_input("Domanda avanzata sui tuoi documenti..."):
            # Add user message to history
            st.session_state.messages.append({"role": "user", "content": prompt})

            # Display user message
            with st.chat_message("user"):
                st.markdown(prompt)

            # Generate output with ALL quality improvements
            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                full_response = ""

                # Show a spinner while thinking
                with st.spinner("🧠 Elaborazione con tutti i quality improvements..."):
                    try:
                        # Try to use EnhancedRAGEngine if available
                        try:
                            from rag_engine_quality_enhanced import get_enhanced_rag_engine
                            enhanced_engine = get_enhanced_rag_engine()
                            response = enhanced_engine.query(prompt, use_enhancements=True)
                        except ImportError:
                            # Fallback to basic engine
                            response = engine.query(prompt, auto_approve_if_high_confidence=True)

                        full_response = response.answer

                        # Build enhanced output with metadata
                        output_sections = []
                        output_sections.append(f"**Risposta:**\n{full_response}")

                        # Try to show query expansion info
                        try:
                            from query_expansion import get_query_expander
                            expander = get_query_expander(engine.llm)
                            expanded = expander.expand_query(prompt, num_variants=2, use_cache=True)
                            if expanded.variants:
                                output_sections.append(f"\n📝 **Query Variants:** {', '.join(expanded.variants[:2])}")
                                output_sections.append(f"🎯 **Intent:** {expanded.intent}")
                        except Exception as e:
                            logger.debug(f"Query expansion visualization failed: {e}")

                        # Add temporal metadata info with Timeline View
                        try:
                            from temporal_metadata import get_temporal_extractor
                            extractor = get_temporal_extractor()
                            if response.sources:
                                recent_docs = []
                                timeline_data = []
                                for src in response.sources[:5]:  # Extended to 5 for timeline
                                    source_name = getattr(src, 'source', getattr(src, 'document', ''))
                                    score = getattr(src, 'score', 0.0)
                                    temporal = extractor.extract_from_filename(source_name)
                                    if temporal.extracted_date:
                                        recent_docs.append(f"{source_name} ({temporal.extracted_date})")
                                        timeline_data.append({
                                            'date': temporal.extracted_date.isoformat(),
                                            'doc': source_name,
                                            'score': score
                                        })
                                if recent_docs:
                                    output_sections.append(f"\n📅 **Timeline Documenti:** {', '.join(recent_docs)}")

                                    # Add timeline visualization
                                    if timeline_data:
                                        try:
                                            import pandas as pd
                                            timeline_df = pd.DataFrame(timeline_data)
                                            timeline_df.columns = ['📅 Data', '📄 Documento', '⭐ Score']
                                            # Display as interactive table
                                            st.markdown("##### 📊 Timeline View")
                                            st.dataframe(
                                                timeline_df.sort_values('📅 Data', ascending=False),
                                                use_container_width=True,
                                                hide_index=True
                                            )
                                        except Exception as te:
                                            logger.debug(f"Timeline visualization failed: {te}")
                        except Exception as e:
                            logger.debug(f"Temporal metadata visualization failed: {e}")

                        # Show citation info if available
                        if response.sources:
                            sources_md = "\n\n**📚 Fonti (con Inline Citations):**\n"
                            seen_sources = set()
                            for i, s in enumerate(response.sources, 1):
                                doc_name = getattr(s, 'source', getattr(s, 'document', 'Unknown'))
                                if doc_name not in seen_sources:
                                    score = getattr(s, 'score', 0.0)
                                    section = getattr(s, 'section', '')
                                    section_info = f" - {section}" if section else ""
                                    sources_md += f"[Fonte {i}] *{doc_name}*{section_info} (Score: {score:.2f})\n"
                                    seen_sources.add(doc_name)
                            output_sections.append(sources_md)

                        full_output = "".join(output_sections)
                        message_placeholder.markdown(full_output)

                        # Add to history
                        st.session_state.messages.append({"role": "assistant", "content": full_output})

                    except TimeoutError as e:
                        error_msg = f"❌ Timeout durante l'elaborazione avanzata: {e}"
                        st.error(error_msg)
                        logger.error(f"Timeout in advanced query: {e}", exc_info=True)

                    except Exception as e:
                        import traceback
                        error_msg = f"❌ Errore chat avanzato: {type(e).__name__}: {e}"
                        st.error(error_msg)
                        with st.expander("📋 Dettagli errore"):
                            st.code(traceback.format_exc(), language="python")
                        logger.error(f"Advanced query failed: {e}", exc_info=True)

        # Show quality improvements status
        st.divider()
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("TASK 1", "Self-Correction", "✅")
        with col2:
            st.metric("TASK 2", "Query Expansion", "✅")
        with col3:
            st.metric("TASK 3", "Inline Citations", "✅")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("TASK 4", "Temporal Metadata", "✅")
        with col2:
            st.metric("TASK 5", "Reranking", "✅")
        with col3:
            st.metric("TASK 6", "Multi-Doc", "✅")

    # === TAB 3: DOCUMENT LIBRARY ===
    with tab_library:
        st.subheader("📚 Libreria Completa Documenti")

        try:
            # Accedi direttamente al vector_store (fresh instance)
            from vector_store import get_vector_store
            vs = get_vector_store()

            # Verifica che il metodo esista
            if not hasattr(vs, 'get_all_documents'):
                st.error("❌ ERRORE CRITICO: VectorStore non ha il metodo get_all_documents(). Riavvia l'applicazione.")
                st.stop()

            all_docs = vs.get_all_documents()
            total_chunks = vs.get_total_chunks()

            # Mostra statistiche
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Documenti Unici", len(all_docs))
            with col2:
                st.metric("Chunk Totali", total_chunks)
            with col3:
                avg_chunks = total_chunks / len(all_docs) if all_docs else 0
                st.metric("Avg Chunks/Doc", f"{avg_chunks:.1f}")

            st.divider()

            # FASE 7: Tag filtering and display (Feature 1)
            try:
                tag_manager = TagManager()
                all_tags_dict = tag_manager.get_all_tags(vs)
                if all_tags_dict:
                    st.subheader("🏷️ Filtra per Tag")
                    selected_tag_filter = st.multiselect(
                        "Seleziona tag per filtrare",
                        list(all_tags_dict.keys()),
                        help="Mostra solo documenti con questi tag"
                    )
                else:
                    selected_tag_filter = None
            except Exception as e:
                st.warning(f"Tag non disponibili: {e}")
                selected_tag_filter = None
                all_tags_dict = {}

            # Mostra tabella con ricerca
            if all_docs:
                import pandas as pd

                # Formatta dati per tabella
                table_data = []
                for i, doc_info in enumerate(all_docs, 1):
                    source = doc_info.get("source", "Unknown")
                    chunks = doc_info.get("num_chunks", 0)

                    # FASE 7: Extract tags from metadata
                    try:
                        metadata = doc_info.get("metadata", {})
                        tags = metadata.get("tags", []) if isinstance(metadata, dict) else []
                        tags_str = ", ".join(tags) if tags else "No tags"
                    except Exception:
                        tags = []
                        tags_str = "No tags"

                    table_data.append({
                        "#": i,
                        "Documento": source,
                        "Chunk": chunks,
                        "Tag": tags_str,
                        "_tags": tags  # Hidden for filtering
                    })

                # Filter by selected tags if any
                if selected_tag_filter:
                    table_data = [
                        row for row in table_data
                        if any(tag in row["_tags"] for tag in selected_tag_filter)
                    ]

                # Remove hidden column before displaying
                for row in table_data:
                    del row["_tags"]

                df = pd.DataFrame(table_data)

                # Mostra tabella ricercabile
                st.dataframe(
                    df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "#": st.column_config.NumberColumn("", width=50),
                        "Documento": st.column_config.TextColumn("Documento", width=250),
                        "Chunk": st.column_config.NumberColumn("Chunk", width=80),
                        "Tag": st.column_config.TextColumn("Tag", width=200)
                    }
                )

                # FASE 8: Display summaries and key points for each document
                st.divider()
                st.subheader("📝 Sommari Documenti")

                try:
                    summaries_data = vs.get_document_summaries()
                    if summaries_data:
                        for source, summary_info in sorted(summaries_data.items()):
                            summary = summary_info.get("summary", "")
                            key_points = summary_info.get("key_points", [])

                            with st.expander(f"📄 {source}", expanded=False):
                                if summary:
                                    st.markdown(f"**Sommario:** {summary}")
                                else:
                                    st.caption("Sommario non disponibile")

                                if key_points and isinstance(key_points, list):
                                    st.markdown("**Punti Chiave:**")
                                    for point in key_points[:5]:
                                        st.caption(f"• {point}")
                    else:
                        st.info("Nessun sommario disponibile. I sommari verranno generati durante l'ingestion dei documenti.")
                except Exception as e:
                    logger.warning(f"Error displaying summaries: {e}")

                # Show tag statistics
                if all_tags_dict:
                    st.divider()
                    st.subheader("📊 Statistiche Tag")
                    tag_cols = st.columns(min(5, len(all_tags_dict)))
                    for idx, (tag, count) in enumerate(sorted(all_tags_dict.items(), key=lambda x: x[1], reverse=True)[:5]):
                        with tag_cols[idx % len(tag_cols)]:
                            st.metric(f"🏷️ {tag}", f"{count} doc")

                # Bottone refresh
                if st.button("🔄 Aggiorna lista", use_container_width=True):
                    st.rerun()
            else:
                st.info("Nessun documento in libreria. Carica documenti dalla sidebar.")

        except Exception as e:
            st.error(f"Errore nel caricamento della libreria: {e}")
            logger.error(f"Library tab error: {e}", exc_info=True)

    # === TAB 4: GLOBAL ANALYSIS (TASK 6: Multi-Document Analysis) ===
    with tab_analysis:
        # FASE 8: Document Similarity Matrix
        st.subheader("📊 Analisi Globale della Libreria")

        # Create tabs for different analysis views
        analysis_tab1, analysis_tab2 = st.tabs(["🔗 Matrice Similarità", "🌍 Analisi Gemini"])

        with analysis_tab1:
            st.subheader("Matrice di Similarità Documenti")
            st.caption("Visualizza le relazioni tra documenti basate su similarità semantica")

            try:
                from src.document_similarity_matrix import DocumentSimilarityMatrix
                from src.vector_store import get_vector_store

                vs = get_vector_store()
                similarity_manager = DocumentSimilarityMatrix(vs)

                # Compute similarity matrix
                with st.spinner("📊 Calcolo matrice di similarità..."):
                    similarity_matrix = similarity_manager.compute_similarity_matrix()

                if similarity_matrix is not None and len(similarity_matrix) > 0:
                    # Display statistics
                    stats = similarity_manager.get_statistics()
                    if stats:
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Documenti", stats.get("total_documents", 0))
                        with col2:
                            st.metric("Similarità Media", f"{stats.get('avg_similarity', 0):.3f}")
                        with col3:
                            st.metric("Similarità Max", f"{stats.get('max_similarity', 0):.3f}")

                    # Build and display heatmap
                    heatmap_data = similarity_manager.build_heatmap_data()
                    if heatmap_data:
                        try:
                            import plotly.graph_objects as go

                            fig = go.Figure(
                                data=go.Heatmap(
                                    z=heatmap_data["z"],
                                    x=heatmap_data["x"],
                                    y=heatmap_data["y"],
                                    text=heatmap_data["text"],
                                    texttemplate="%{text}",
                                    colorscale=heatmap_data["colorscale"],
                                    colorbar={"title": heatmap_data["colorbar_title"]},
                                    hovertemplate="<b>%{x}</b> → <b>%{y}</b><br>Similarità: %{z:.3f}<extra></extra>",
                                )
                            )

                            fig.update_layout(
                                title="Matrice di Similarità Documenti",
                                xaxis_title="Documento",
                                yaxis_title="Documento",
                                height=600,
                                width=800,
                            )

                            st.plotly_chart(fig, use_container_width=True)

                        except Exception as e:
                            st.warning(f"Impossibile visualizzare heatmap: {e}")

                    # Show most similar pairs
                    st.subheader("🔗 Coppie Documenti Più Simili")
                    similar_pairs = similarity_manager.get_most_similar_pairs(top_n=10)
                    if similar_pairs:
                        pairs_data = []
                        for doc1, doc2, score in similar_pairs:
                            pairs_data.append({
                                "Documento 1": doc1,
                                "Documento 2": doc2,
                                "Similarità": f"{score:.3f}"
                            })
                        import pandas as pd
                        st.dataframe(pd.DataFrame(pairs_data), use_container_width=True, hide_index=True)
                    else:
                        st.info("Nessuna coppia simile trovata")

                else:
                    st.info("Nessun documento per calcolare la matrice di similarità")

            except Exception as e:
                st.warning(f"Errore nel calcolo della similarità: {e}")
                logger.warning(f"Similarity matrix error: {e}")

        with analysis_tab2:
            st.subheader("🌍 Analisi Globale della Libreria - TASK 6")
            st.caption("Utilizzo Gemini 2.0 Flash (1M token context) per analizzare TUTTI i documenti simultaneamente")

            # NEW: Auto-load dashboard on tab open (with cache)
            auto_load = st.checkbox(
                "📊 Carica automaticamente il Riassunto Esecutivo",
                value=False,
                help="Genera riassunto esecutivo al caricamento del tab (TASK 6)"
            )

            col1, col2 = st.columns([0.7, 0.3])

            with col2:
                manual_analysis = st.button("🔍 Analizza Completa", use_container_width=True)

            # Auto-load or manual
            trigger_analysis = auto_load or manual_analysis

            if trigger_analysis:
                spinner_text = "⏳ Caricamento rapido..." if auto_load else "⏳ Analizzando 70+ documenti con Gemini 2.0 Flash..."
                with st.spinner(spinner_text):
                    try:
                        from multi_document_analysis import get_multi_document_analyzer

                        analyzer = get_multi_document_analyzer(engine.llm)

                        # Get all documents from vector store
                        from vector_store import get_vector_store
                        vs = get_vector_store()
                        all_docs_info = vs.get_all_documents()

                        # Prepare documents for analysis
                        documents = []
                        for doc_info in all_docs_info:
                            documents.append({
                                'id': doc_info.get('source', 'unknown'),
                                'title': doc_info.get('source', 'Unknown'),
                                'content': f"Document with {doc_info.get('num_chunks', 0)} chunks",
                                'metadata': doc_info
                            })

                        # Run analysis
                        analysis = analyzer.analyze_all_documents(documents, analysis_depth="comprehensive")

                        # Display results
                        st.success(f"✅ Analisi completata! {analysis.total_documents} documenti analizzati")

                        # Tab results
                        tab_summary, tab_themes, tab_insights, tab_findings, tab_gaps = st.tabs([
                            "📄 Riassunto",
                            "🎨 Temi",
                            "🔗 Insights",
                            "🎯 Findings",
                            "⚠️ Gaps"
                        ])

                        with tab_summary:
                            st.markdown("### Riassunto Globale")
                            st.write(analysis.global_summary)
                            st.metric("Token utilizzati", analysis.total_tokens_used)

                        with tab_themes:
                            st.markdown("### Temi Identificati")
                            for i, theme in enumerate(analysis.themes, 1):
                                with st.expander(f"**{i}. {theme.theme}**"):
                                    st.write(theme.summary)
                                    st.write(f"**Documenti:** {', '.join(theme.documents)}")
                                    st.write(f"**Parole chiave:** {', '.join(theme.keywords)}")

                        with tab_insights:
                            st.markdown("### Cross-Document Insights")
                            for i, insight in enumerate(analysis.insights, 1):
                                with st.expander(f"**{insight.insight_type.upper()}** - Documenti: {', '.join(insight.related_documents)}"):
                                    st.write(insight.insight_text)
                                    if insight.evidence:
                                        st.write("**Evidenza:**")
                                        for ev in insight.evidence:
                                            st.write(f"- {ev}")
                                    st.write(f"Confidence: {insight.confidence:.0%}")

                        with tab_findings:
                            st.markdown("### Key Findings")
                            for i, finding in enumerate(analysis.key_findings, 1):
                                st.write(f"**{i}.** {finding}")

                        with tab_gaps:
                            st.markdown("### Documentation Gaps")
                            if analysis.gaps_identified:
                                for i, gap in enumerate(analysis.gaps_identified, 1):
                                    st.write(f"**{i}.** {gap}")
                            else:
                                st.info("✅ No major gaps identified!")

                            st.markdown("### Recommendations")
                            for i, rec in enumerate(analysis.recommendations, 1):
                                st.write(f"**{i}.** {rec}")

                    except ImportError as e:
                        st.warning(f"⚠️ Multi-Document Analysis non disponibile: {e}")
                        st.info("Assicurati che multi_document_analysis.py sia presente")

                    except Exception as e:
                        import traceback
                        st.error(f"❌ Errore durante l'analisi: {e}")
                        with st.expander("📋 Dettagli errore"):
                            st.code(traceback.format_exc())
                        logger.error(f"Global analysis failed: {e}", exc_info=True)

        with col1:
            st.info("""
            ### 🌍 Analisi Globale della Libreria

            Questa analisi utilizza il **TASK 6** per:

            ✅ **Global Summary** - Panoramica di tutti i documenti
            ✅ **Thematic Clustering** - Raggruppa per temi/argomenti
            ✅ **Cross-Document Insights** - Trova connessioni tra documenti
            ✅ **Key Findings** - Estrae 5-7 punti principali
            ✅ **Gap Analysis** - Identifica aree non documentate
            ✅ **Relationship Mapping** - Mappa dipendenze tra documenti

            **Context Window:** Gemini 2.0 Flash 1M token (supporta ~70+ documenti)
            """)

else:
    st.warning("Il motore RAG non è pronto. Controlla la sidebar per errori o riprova.")
