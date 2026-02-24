"""
Document Topic Analyzer - Estrae argomenti e raggruppa documenti
Supporta: LLM-based extraction, Keyword extraction, Vector clustering, Caching
"""

import os
import json
import logging
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from datetime import datetime
import hashlib

logger = logging.getLogger(__name__)

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    numpy = None

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.cluster import KMeans
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.info("sklearn non disponibile - clustering disabilitato (fallback: keyword extraction)")

# Path per cache dei topic
TOPICS_CACHE_DIR = Path("data/topics_cache")
TOPICS_CACHE_DIR.mkdir(parents=True, exist_ok=True)


class DocumentTopicAnalyzer:
    """Analizza documenti ed estrae argomenti con supporto per caching e clustering"""

    def __init__(self, llm_service=None, cache_enabled=True):
        """
        Inizializza l'analizzatore di topic

        Args:
            llm_service: Servizio LLM per estrazione topic basata su AI
            cache_enabled: Se True, usa cache per i topic estratti
        """
        self.llm_service = llm_service
        self.cache_enabled = cache_enabled
        self.topics_cache = {}
        self._load_cache()

    def _get_cache_key(self, document: Dict) -> str:
        """Genera una chiave unica per il cache basata sul contenuto del documento"""
        content = document.get('text', document.get('content', ''))[:500]
        return hashlib.md5(content.encode()).hexdigest()

    def _load_cache(self):
        """Carica il cache dei topic da file"""
        cache_file = TOPICS_CACHE_DIR / "topics_cache.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    self.topics_cache = json.load(f)
                logger.info(f"Cache caricato: {len(self.topics_cache)} topic in memoria")
            except Exception as e:
                logger.warning(f"Errore caricamento cache: {e}")
                self.topics_cache = {}

    def _save_cache(self):
        """Salva il cache dei topic su file"""
        if not self.cache_enabled:
            return

        try:
            cache_file = TOPICS_CACHE_DIR / "topics_cache.json"
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.topics_cache, f, ensure_ascii=False, indent=2)
            logger.info(f"Cache salvato: {len(self.topics_cache)} topic")
        except Exception as e:
            logger.error(f"Errore salvataggio cache: {e}")

    # ========================================================================
    # 1. ESTRAZIONE ARGOMENTI - LLM BASED (Approccio 1)
    # ========================================================================

    def extract_topics_llm(self, documents: List[Dict], batch_size: int = 10) -> Dict[str, List[str]]:
        """
        Estrae argomenti usando LLM (Gemini)

        Args:
            documents: Lista di documenti da analizzare
            batch_size: Numero di documenti da elaborare per batch

        Returns:
            Dict con {document_id: [topic1, topic2, ...]}
        """
        if not self.llm_service:
            logger.warning("LLM service non disponibile, usando keyword extraction")
            return self.extract_topics_keywords(documents)

        topics = {}
        processed = 0

        for doc in documents:
            cache_key = self._get_cache_key(doc)

            # Verifica cache
            if cache_key in self.topics_cache:
                topics[doc['id']] = self.topics_cache[cache_key]
                continue

            try:
                content = doc.get('text', doc.get('content', ''))[:1000]
                filename = doc.get('metadata', {}).get('filename', doc.get('id', ''))

                prompt = f"""Analizza questo documento e identifica 3-5 argomenti principali.

Filename: {filename}
Contenuto: {content}

Rispondi SOLO con gli argomenti separati da virgola, esempio:
Machine Learning, AI, Data Science, Python

Argomenti:"""

                # Try different methods to get response from LLM service
                try:
                    # Try generate method (standard)
                    if hasattr(self.llm_service, 'generate'):
                        response = self.llm_service.generate(prompt)
                    # Try generate_response method
                    elif hasattr(self.llm_service, 'generate_response'):
                        response = self.llm_service.generate_response(prompt)
                    # Try query method
                    elif hasattr(self.llm_service, 'query'):
                        response = self.llm_service.query(prompt)
                    # Fallback: use keyword extraction
                    else:
                        logger.warning(f"LLM service non ha metodi riconosciuti, usando keyword extraction")
                        return self.extract_topics_keywords([doc])
                except AttributeError:
                    logger.warning(f"LLM service metodo non trovato, usando keyword extraction")
                    return self.extract_topics_keywords([doc])

                # Parse response
                extracted_topics = [t.strip() for t in response.split(',') if t.strip()]
                extracted_topics = extracted_topics[:5]  # Max 5 topic

                topics[doc['id']] = extracted_topics
                self.topics_cache[cache_key] = extracted_topics

                processed += 1
                if processed % batch_size == 0:
                    logger.info(f"Elaborati {processed}/{len(documents)} documenti")
                    self._save_cache()

            except Exception as e:
                logger.error(f"Errore estrazione topic per {doc.get('id')}: {e}")
                topics[doc['id']] = ["Non classificato"]

        self._save_cache()
        return topics

    # ========================================================================
    # 2. ESTRAZIONE ARGOMENTI - KEYWORD BASED (Approccio 2)
    # ========================================================================

    def extract_topics_keywords(self, documents: List[Dict], top_n: int = 4) -> Dict[str, List[str]]:
        """
        Estrae argomenti analizzando le parole chiave principali

        Args:
            documents: Lista di documenti
            top_n: Numero massimo di topic da estrarre

        Returns:
            Dict con {document_id: [topic1, topic2, ...]}
        """
        topics = {}

        # Keywords comuni da escludere
        stop_topics = {
            'il', 'lo', 'la', 'i', 'gli', 'le', 'un', 'una', 'uno', 'dei', 'delle',
            'di', 'da', 'per', 'con', 'su', 'in', 'a', 'è', 'sono', 'che', 'non',
            'file', 'documento', 'text', 'document', 'content', 'data', 'system'
        }

        for doc in documents:
            try:
                content = doc.get('text', doc.get('content', ''))
                filename = doc.get('metadata', {}).get('filename', '')

                # Estrai parole chiave da filename
                filename_words = [w.lower() for w in filename.replace('.', ' ').split('_')
                                 if len(w) > 3 and w.lower() not in stop_topics]

                # Estrai parole più frequenti dal contenuto
                words = [w.lower() for w in content.split() if len(w) > 4]
                word_freq = {}
                for word in words:
                    if word not in stop_topics:
                        word_freq[word] = word_freq.get(word, 0) + 1

                # Top keywords
                top_keywords = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:top_n]
                extracted = filename_words + [w[0] for w in top_keywords]

                # Capitalizza e rimuovi duplicati
                final_topics = list(dict.fromkeys([w.capitalize() for w in extracted[:top_n]]))
                topics[doc['id']] = final_topics if final_topics else ["Vario"]

            except Exception as e:
                logger.error(f"Errore keyword extraction per {doc.get('id')}: {e}")
                topics[doc['id']] = ["Vario"]

        return topics

    # ========================================================================
    # 3. CLUSTERING VETTORIALE (Approccio 3)
    # ========================================================================

    def extract_topics_clustering(self, documents: List[Dict], n_clusters: int = 8) -> Dict[str, List[str]]:
        """
        Estrae argomenti usando clustering vettoriale (TF-IDF + KMeans)
        Fallback a keyword extraction se sklearn non disponibile

        Args:
            documents: Lista di documenti
            n_clusters: Numero di cluster (argomenti)

        Returns:
            Dict con {document_id: [cluster_topic]}
        """
        if not SKLEARN_AVAILABLE:
            logger.warning("sklearn non disponibile, usando keyword extraction al posto del clustering")
            return self.extract_topics_keywords(documents)

        if len(documents) < n_clusters:
            n_clusters = max(2, len(documents) // 2)

        try:
            # Prepara testi
            texts = [doc.get('text', doc.get('content', ''))[:500] for doc in documents]

            # TF-IDF vectorization
            vectorizer = TfidfVectorizer(max_features=100, stop_words='english')
            tfidf_matrix = vectorizer.fit_transform(texts)

            # KMeans clustering
            kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            labels = kmeans.fit_predict(tfidf_matrix)

            # Estrai top terms per cluster
            order_centroids = kmeans.cluster_centers_.argsort()[:, ::-1]
            terms = vectorizer.get_feature_names_out()

            cluster_topics = {}
            for i in range(n_clusters):
                top_terms = [terms[ind].capitalize() for ind in order_centroids[i, :3]]
                cluster_topics[i] = top_terms

            # Assegna topic ai documenti
            topics = {}
            for doc, label in zip(documents, labels):
                topics[doc['id']] = cluster_topics[label]

            logger.info(f"Clustering completato: {n_clusters} cluster creati")
            return topics

        except Exception as e:
            logger.error(f"Errore clustering: {e}")
            return {doc['id']: ["Vario"] for doc in documents}

    # ========================================================================
    # 4. APPROCCIO IBRIDO (Combina LLM + Keywords + Clustering)
    # ========================================================================

    def extract_topics_hybrid(self, documents: List[Dict]) -> Dict[str, List[str]]:
        """
        Approccio ibrido: Combina LLM, keywords e clustering

        Args:
            documents: Lista di documenti

        Returns:
            Dict con {document_id: [topic1, topic2, ...]}
        """
        logger.info("Avvio estrazione topic IBRIDA...")

        # 1. Prova con LLM se disponibile
        if self.llm_service:
            logger.info("Fase 1: Estrazione LLM in corso...")
            topics = self.extract_topics_llm(documents)
        else:
            # 2. Fallback: Keywords
            logger.info("Fase 1: LLM non disponibile, usando keywords...")
            topics = self.extract_topics_keywords(documents)

        # 3. Supplementa con clustering per similarità
        logger.info("Fase 2: Clustering per identificare argomenti correlati...")
        clustering_topics = self.extract_topics_clustering(documents)

        # 4. Unisci i risultati
        final_topics = {}
        for doc in documents:
            doc_id = doc['id']
            llm_topics = topics.get(doc_id, [])
            cluster_topics = clustering_topics.get(doc_id, [])

            # Combina senza duplicati
            combined = list(dict.fromkeys(llm_topics + cluster_topics))
            final_topics[doc_id] = combined[:5]  # Max 5

        logger.info("Estrazione topic ibrida completata")
        return final_topics

    # ========================================================================
    # 5. RAGGRUPPAMENTO PER ARGOMENTO
    # ========================================================================

    def group_documents_by_topic(self, documents: List[Dict], topics: Dict[str, List[str]]) -> Dict[str, List[Dict]]:
        """
        Raggruppa documenti per argomento

        Args:
            documents: Lista di documenti
            topics: Dict con topic per ogni documento

        Returns:
            Dict con {topic: [doc1, doc2, ...]}
        """
        grouped = {}
        topic_doc_count = {}

        for doc in documents:
            doc_id = doc['id']
            doc_topics = topics.get(doc_id, ['Non classificato'])

            for topic in doc_topics:
                topic_key = topic.lower()
                if topic_key not in grouped:
                    grouped[topic_key] = {
                        'display_name': topic,
                        'documents': [],
                        'count': 0
                    }

                grouped[topic_key]['documents'].append(doc)
                grouped[topic_key]['count'] += 1
                topic_doc_count[topic_key] = grouped[topic_key]['count']

        # Ordina per numero di documenti
        sorted_grouped = dict(sorted(grouped.items(),
                                    key=lambda x: x[1]['count'],
                                    reverse=True))

        logger.info(f"Raggruppamento completato: {len(sorted_grouped)} argomenti identificati")
        return sorted_grouped

    # ========================================================================
    # 6. STATISTICHE TOPIC
    # ========================================================================

    def get_topic_statistics(self, grouped_docs: Dict[str, Dict]) -> Dict:
        """
        Calcola statistiche sui topic

        Args:
            grouped_docs: Documenti raggruppati per topic

        Returns:
            Dict con statistiche
        """
        stats = {
            'total_topics': len(grouped_docs),
            'total_documents': sum(g['count'] for g in grouped_docs.values()),
            'topics': [],
            'distribution': {}
        }

        for topic_key, topic_data in grouped_docs.items():
            count = topic_data['count']
            display_name = topic_data['display_name']

            stats['topics'].append({
                'name': display_name,
                'count': count,
                'percentage': 0  # Calcolato dopo
            })
            stats['distribution'][display_name] = count

        # Calcola percentuali
        total = stats['total_documents']
        if total > 0:
            for topic in stats['topics']:
                topic['percentage'] = round((topic['count'] / total) * 100, 1)

        return stats

    # ========================================================================
    # 7. METODO PRINCIPALE - WORKFLOW COMPLETO
    # ========================================================================

    def analyze_documents(self, documents: List[Dict], method: str = "hybrid") -> Tuple[Dict, Dict, Dict]:
        """
        Workflow completo: Estrai topic, raggruppa, calcola statistiche

        Args:
            documents: Lista di documenti
            method: "llm", "keywords", "clustering", o "hybrid"

        Returns:
            Tuple: (topics_dict, grouped_docs, statistics)
        """
        logger.info(f"Inizio analisi {len(documents)} documenti con metodo: {method}")

        # Estrai topic in base al metodo
        if method == "llm":
            topics = self.extract_topics_llm(documents)
        elif method == "keywords":
            topics = self.extract_topics_keywords(documents)
        elif method == "clustering":
            topics = self.extract_topics_clustering(documents)
        else:  # hybrid
            topics = self.extract_topics_hybrid(documents)

        # Raggruppa documenti
        grouped = self.group_documents_by_topic(documents, topics)

        # Calcola statistiche
        stats = self.get_topic_statistics(grouped)

        logger.info(f"Analisi completata: {stats['total_topics']} argomenti, "
                   f"{stats['total_documents']} documenti")

        return topics, grouped, stats


# Singleton per l'accesso globale
_analyzer_instance = None

def get_topic_analyzer(llm_service=None, cache_enabled=True):
    """Restituisce istanza singleton dell'analizzatore"""
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = DocumentTopicAnalyzer(llm_service, cache_enabled)
    return _analyzer_instance
