"""
Topic UI Renderer - Visualizza documenti raggruppati per argomento
Supporta: Sidebar filters, Topic tab, Cards view, Tree view, Search
"""

import streamlit as st
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class TopicUIRenderer:
    """Renderizza l'UI per visualizzare documenti per argomento"""

    # ========================================================================
    # 1. SIDEBAR FILTER - Filtri per argomento nella sidebar
    # ========================================================================

    @staticmethod
    def render_topic_filter_sidebar(grouped_docs: Dict[str, Dict], stats: Dict) -> Optional[str]:
        """
        Aggiunge filtri per argomento nella sidebar

        Args:
            grouped_docs: Documenti raggruppati per topic
            stats: Statistiche sui topic

        Returns:
            Topic selezionato o None
        """
        st.sidebar.markdown("---")
        st.sidebar.subheader("📂 Filtra per Argomento")

        # Mostra statistiche
        col1, col2 = st.sidebar.columns(2)
        with col1:
            st.metric("Argomenti", stats['total_topics'])
        with col2:
            st.metric("Documenti", stats['total_documents'])

        # Opzione "Tutti"
        topics_list = ["Tutti gli argomenti"] + [t['name'] for t in stats['topics']]

        selected_topic = st.sidebar.selectbox(
            "Scegli argomento:",
            topics_list,
            key="selected_topic_filter"
        )

        # Mostra topic con conteggio
        with st.sidebar.expander("Dettagli argomenti", expanded=False):
            for topic_info in sorted(stats['topics'], key=lambda x: x['count'], reverse=True):
                col_name, col_count = st.columns([3, 1])
                with col_name:
                    st.text(topic_info['name'])
                with col_count:
                    st.text(f"{topic_info['count']} ({topic_info['percentage']}%)")

        return selected_topic if selected_topic != "Tutti gli argomenti" else None

    # ========================================================================
    # 2. TOPIC TAB - Tab dedicato per visualizzare per argomento
    # ========================================================================

    @staticmethod
    def render_topics_tab(grouped_docs: Dict[str, Dict], stats: Dict):
        """
        Renderizza un tab dedicato per visualizzare documenti per argomento

        Args:
            grouped_docs: Documenti raggruppati per topic
            stats: Statistiche sui topic
        """
        st.subheader("📚 Documenti per Argomento")

        # Statistiche riassuntive
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Totale Argomenti", stats['total_topics'])
        with col2:
            st.metric("Totale Documenti", stats['total_documents'])
        with col3:
            if stats['total_documents'] > 0:
                avg_docs = round(stats['total_documents'] / stats['total_topics'], 1)
                st.metric("Media Doc/Argomento", avg_docs)

        st.markdown("---")

        # Visualizza topic in ordine di frequenza
        for topic_key, topic_data in grouped_docs.items():
            topic_name = topic_data['display_name']
            doc_count = topic_data['count']

            # Calcola percentuale
            percentage = round((doc_count / stats['total_documents']) * 100, 1) if stats['total_documents'] > 0 else 0

            with st.expander(f"📌 {topic_name} ({doc_count} documenti - {percentage}%)", expanded=False):
                # Progress bar
                st.progress(percentage / 100, text=f"{percentage}%")

                # Lista documenti
                for doc in topic_data['documents']:
                    doc_name = doc.get('metadata', {}).get('filename', doc.get('id', 'Documento'))
                    doc_size = doc.get('metadata', {}).get('size', 0)

                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"📄 {doc_name}")
                    with col2:
                        if doc_size > 0:
                            size_kb = round(doc_size / 1024, 1)
                            st.caption(f"{size_kb} KB")

    # ========================================================================
    # 3. HIERARCHICAL VIEW - Vista ad albero dei topic
    # ========================================================================

    @staticmethod
    def render_topics_tree(grouped_docs: Dict[str, Dict], stats: Dict, max_depth: int = 2):
        """
        Renderizza una vista ad albero dei topic e documenti

        Args:
            grouped_docs: Documenti raggruppati per topic
            stats: Statistiche sui topic
            max_depth: Profondità massima dell'albero
        """
        st.subheader("🌳 Vista Gerarchica")

        # Root node
        st.write(f"**RAG LOCALE**")
        with st.container(border=True):
            st.write(f"Total: {stats['total_documents']} documenti | {stats['total_topics']} argomenti")

        # Topic nodes
        for i, (topic_key, topic_data) in enumerate(grouped_docs.items()):
            topic_name = topic_data['display_name']
            doc_count = topic_data['count']

            col_indent, col_content = st.columns([0.5, 9.5])
            with col_content:
                with st.expander(f"📂 {topic_name} ({doc_count})", expanded=i < 3):
                    # Document nodes
                    for doc in topic_data['documents'][:10]:  # Max 10 per topic
                        doc_name = doc.get('metadata', {}).get('filename', doc.get('id'))
                        st.write(f"&nbsp;&nbsp;&nbsp;&nbsp;📄 {doc_name}")

                    if len(topic_data['documents']) > 10:
                        st.caption(f"... e {len(topic_data['documents']) - 10} altri documenti")

    # ========================================================================
    # 4. CARDS VIEW - Visualizza topic come cards
    # ========================================================================

    @staticmethod
    def render_topics_cards(grouped_docs: Dict[str, Dict], stats: Dict, cols: int = 3):
        """
        Renderizza topic come cards (grid view)

        Args:
            grouped_docs: Documenti raggruppati per topic
            stats: Statistiche sui topic
            cols: Numero di colonne
        """
        st.subheader("🎴 Vista a Card")

        # Create grid
        columns = st.columns(cols)

        for i, (topic_key, topic_data) in enumerate(grouped_docs.items()):
            col = columns[i % cols]

            with col:
                topic_name = topic_data['display_name']
                doc_count = topic_data['count']
                percentage = round((doc_count / stats['total_documents']) * 100, 1) if stats['total_documents'] > 0 else 0

                with st.container(border=True):
                    st.subheader(f"📌 {topic_name}")

                    # Statistiche
                    st.metric("Documenti", doc_count)
                    st.progress(percentage / 100)
                    st.caption(f"{percentage}% del totale")

                    # Link ai documenti
                    if st.button("Visualizza", key=f"view_topic_{topic_key}"):
                        st.session_state.selected_topic = topic_name

    # ========================================================================
    # 5. SEARCH IN TOPICS - Ricerca all'interno dei topic
    # ========================================================================

    @staticmethod
    def render_topic_search(grouped_docs: Dict[str, Dict]) -> List[Dict]:
        """
        Renderizza un'interfaccia di ricerca all'interno dei topic

        Args:
            grouped_docs: Documenti raggruppati per topic

        Returns:
            Lista di documenti che matchano la ricerca
        """
        st.subheader("🔍 Ricerca in Argomenti")

        search_query = st.text_input("Cerca documenti per nome o argomento:", placeholder="Es: Machine Learning, AI...")

        if search_query:
            results = []
            search_lower = search_query.lower()

            for topic_key, topic_data in grouped_docs.items():
                topic_name = topic_data['display_name'].lower()

                # Ricerca nel nome argomento
                if search_lower in topic_name:
                    results.extend(topic_data['documents'])
                else:
                    # Ricerca nei nomi dei documenti
                    for doc in topic_data['documents']:
                        doc_name = doc.get('metadata', {}).get('filename', doc.get('id', '')).lower()
                        if search_lower in doc_name:
                            results.append(doc)

            # Mostra risultati
            if results:
                st.success(f"Trovati {len(results)} risultati")
                for doc in results:
                    doc_name = doc.get('metadata', {}).get('filename', doc.get('id'))
                    st.write(f"📄 {doc_name}")
            else:
                st.info("Nessun risultato trovato")

            return results
        return []

    # ========================================================================
    # 6. DISTRIBUTION CHART - Grafico della distribuzione topic
    # ========================================================================

    @staticmethod
    def render_topic_distribution_chart(stats: Dict):
        """
        Renderizza un grafico della distribuzione topic

        Args:
            stats: Statistiche sui topic
        """
        st.subheader("📊 Distribuzione Argomenti")

        try:
            import plotly.graph_objects as go

            # Prepara dati
            topic_names = [t['name'] for t in stats['topics']]
            topic_counts = [t['count'] for t in stats['topics']]

            # Pie chart
            fig = go.Figure(data=[go.Pie(
                labels=topic_names,
                values=topic_counts,
                hole=0.3,
                marker=dict(line=dict(color="#0e1117", width=2))
            )])

            fig.update_layout(
                template="plotly_dark",
                paper_bgcolor="#0e1117",
                font=dict(family="Inter", color="#e6edf3"),
                height=400,
                showlegend=True
            )

            st.plotly_chart(fig, use_container_width=True)

        except Exception as e:
            logger.error(f"Errore creazione chart: {e}")
            # Fallback: tabella
            st.dataframe({
                'Argomento': topic_names,
                'Documenti': topic_counts,
                'Percentuale': [f"{(c/sum(topic_counts)*100):.1f}%" for c in topic_counts]
            })

    # ========================================================================
    # 7. TOPIC DETAILS - Dettagli completi di un topic
    # ========================================================================

    @staticmethod
    def render_topic_details(topic_name: str, topic_data: Dict):
        """
        Renderizza i dettagli completi di un singolo topic

        Args:
            topic_name: Nome del topic
            topic_data: Dati del topic
        """
        st.subheader(f"📌 Dettagli: {topic_name}")

        # Informazioni principali
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Documenti", topic_data['count'])
        with col2:
            st.metric("Cartella", "documenti")
        with col3:
            st.metric("Ultimo aggiornamento", "Oggi")

        st.markdown("---")

        # Lista documenti
        st.write(f"**Documenti in {topic_name}:**")
        for i, doc in enumerate(topic_data['documents'], 1):
            doc_name = doc.get('metadata', {}).get('filename', doc.get('id'))
            doc_size = doc.get('metadata', {}).get('size', 0)

            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                st.write(f"{i}. {doc_name}")
            with col2:
                if doc_size > 0:
                    st.caption(f"{round(doc_size/1024, 1)} KB")
            with col3:
                if st.button("Visualizza", key=f"view_doc_{doc['id']}"):
                    st.session_state.selected_document = doc

    # ========================================================================
    # 8. HELPER: Filtra documenti per topic selezionato
    # ========================================================================

    @staticmethod
    def filter_documents_by_topic(documents: List[Dict], grouped_docs: Dict[str, Dict],
                                 selected_topic: Optional[str]) -> List[Dict]:
        """
        Filtra documenti in base al topic selezionato

        Args:
            documents: Tutti i documenti
            grouped_docs: Documenti raggruppati
            selected_topic: Topic selezionato

        Returns:
            Lista filtrata di documenti
        """
        if not selected_topic:
            return documents

        for topic_key, topic_data in grouped_docs.items():
            if topic_data['display_name'] == selected_topic:
                return topic_data['documents']

        return documents
