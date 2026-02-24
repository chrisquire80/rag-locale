"""
Configurazione centralizzata per RAG Locale
Ambiente: HP ProBook 440 G11 (16GB RAM, CPU-only)
"""

import logging
from pathlib import Path
from typing import Literal
from pydantic_settings import BaseSettings
from pydantic import Field, SecretStr

logger = logging.getLogger(__name__)

# Percorsi assoluti per robustezza
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
VECTOR_DB_DIR = DATA_DIR / "vector_db"
DOCUMENTS_DIR = DATA_DIR / "documents"
LOGS_DIR = PROJECT_ROOT / "logs"

# Crea directory se non esistono
for dir_path in [DATA_DIR, VECTOR_DB_DIR, DOCUMENTS_DIR, LOGS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

class GeminiConfig(BaseSettings):
    """Configurazione Google Gemini (Hybrid RAG)"""

    # API Key (da variabile d'ambiente GEMINI_API_KEY o .env)
    api_key: SecretStr = Field(..., description="Google Gemini API Key")

    # Modelli
    model_name: str = Field(default="gemini-2.0-flash", description="Modello Chat veloce")
    embedding_model: str = Field(default="models/gemini-embedding-001", description="Modello Embeddings")

    # Configurazione generazione
    max_tokens: int = Field(default=2048)
    temperature: float = Field(default=0.3)

    # Timeouts e Retry (FIXED: Aumentati per ReadTimeoutError e ConnectionResetError)
    request_timeout: int = Field(default=300, description="Timeout richiesta API in secondi (300s = 5 min)")
    embedding_timeout: int = Field(default=300, description="Timeout specifico embedding (300s = 5 min)")
    completion_timeout: int = Field(default=300, description="Timeout specifico completion (300s = 5 min)")
    max_retries: int = Field(default=5, description="Numero massimo retry per timeout/connection errors")
    retry_base_delay: float = Field(default=1.0, description="Delay base per exponential backoff (secondi)")

    class Config:
        env_prefix = "GEMINI_"
        extra = "ignore"
        env_file = ".env"
        env_file_encoding = "utf-8"

class ChromaDBConfig(BaseSettings):
    """Configurazione ChromaDB Vector Store"""

    # Modalità di funzionamento
    mode: Literal["persistent", "ephemeral"] = Field(
        default="persistent",
        description="persistent = disk-based (obbligatorio in produzione)"
    )

    # Percorso di storage
    persist_directory: Path = Field(default=VECTOR_DB_DIR)

    # Configurazione HNSW
    # NOTA: I valori sono ottimizzati per CPU non-dedicata su laptop
    hnsw_space: str = Field(
        default="cosine",
        description="Metrica similarità"
    )
    hnsw_construction_ef: int = Field(
        default=200,
        description="Qualità indice (alto = più accurato ma lento). Per laptop: 200"
    )
    hnsw_m: int = Field(
        default=16,
        description="Numero connessioni per nodo (16-48 tipico)"
    )

    # Chunking
    chunk_size: int = Field(
        default=1000,
        description="Dimensione chunk in token (balance precision vs context)"
    )
    chunk_overlap: int = Field(
        default=100,
        description="Overlap tra chunk per mantener continuità"
    )

    class Config:
        env_prefix = "CHROMADB_"
        extra = "ignore"

class RAGConfig(BaseSettings):
    """Configurazione RAG Engine"""

    # Retrieval
    similarity_top_k: int = Field(
        default=5,
        description="Numero di chunk recuperati dalla query"
    )

    # HITL (Human-in-the-Loop)
    enable_hitl: bool = Field(
        default=False,
        description="Richiede validazione umana prima di generare risposta (disabilitato per Streamlit)"
    )

    hitl_score_threshold: float = Field(
        default=0.7,
        description="Score similarità minima per auto-approve (senza HITL)"
    )

    # System Prompt
    system_prompt: str = Field(
        default="""Sei un assistente IA specializzato in documentazione IT aziendale.

ISTRUZIONI PRINCIPALI:
1. Rispondi SOLO basandoti sui documenti forniti nel contesto.
2. Se una parola ha molteplici significati (es. "Factorial" = HR platform vs funzione matematica),
   dai PRIORITA' al contesto dei documenti recuperati. Se il 90% dei documenti parla di "Factorial HR",
   rispondi su quello anche se il termine è ambiguo.
3. Se hai dubbi su quale interpretazione sia corretta, ANALIZZA i documenti forniti e scegli
   quella che ha il supporto maggiore nei dati.
4. Se non trovi informazioni pertinenti in NESSUNO dei significati, solo allora dichiara
   che non hai dati sufficienti.

FORMATO RISPOSTA:
- Usa linguaggio tecnico preciso
- Cita ESPLICITAMENTE i documenti fonte
- Se un concetto ha molteplici interpretazioni, menzionalo brevemente:
  "Nel contesto dei vostri documenti, Factorial si riferisce a [INTERPRETAZIONE],
  come documentato in [FONTE]."

AMBIGUITY RESOLUTION:
- Non rifiutare una risposta solo perché esiste ambiguita' semantica
- Usa il contesto dei documenti per risolvere l'ambiguita'
- Spiega la scelta se pertinente all'utente"""
    )

    # Metadata filtering per granularità
    enable_metadata_filter: bool = Field(default=True)

    class Config:
        env_prefix = "RAG_"
        extra = "ignore"

class PerformanceConfig(BaseSettings):
    """Centralizzazione di tutti i parametri di performance e tuning"""

    # ===== SIMILARITY & CLUSTERING THRESHOLDS =====
    semantic_similarity_threshold: float = Field(
        default=0.85,
        description="Soglia cosine similarity per semantic query clustering e deduplication"
    )
    dedup_similarity_threshold: float = Field(
        default=0.85,
        description="Soglia similarity per context deduplication"
    )

    # ===== CACHE CONFIGURATION =====
    cache_ttl_seconds: int = Field(
        default=7200,
        description="Cache time-to-live in secondi (7200s = 2 ore)"
    )
    cache_max_size: int = Field(
        default=1000,
        description="Numero massimo di entry nel cache"
    )
    query_expansion_cache_size: int = Field(
        default=500,
        description="Size della query expansion cache"
    )

    # ===== RETRIEVAL PARAMETERS =====
    top_k_default: int = Field(
        default=5,
        description="Numero di documenti da recuperare di default"
    )
    top_k_max: int = Field(
        default=20,
        description="Numero massimo di documenti che si possono recuperare"
    )
    chunk_size_default: int = Field(
        default=512,
        description="Dimensione default chunk per document splitting"
    )
    max_context_tokens: int = Field(
        default=2000,
        description="Numero massimo di token per il contesto LLM"
    )

    # ===== BATCH PROCESSING =====
    reranking_batch_size: int = Field(
        default=10,
        description="Batch size per reranking operations"
    )
    embedding_batch_size: int = Field(
        default=32,
        description="Batch size per embedding generation"
    )

    # ===== LLM GENERATION =====
    llm_temperature: float = Field(
        default=0.7,
        description="Temperature per LLM generation (0=deterministic, 1=creative)"
    )
    llm_temperature_summary: float = Field(
        default=0.3,
        description="Temperature per document summarization (basso = preciso)"
    )
    llm_max_output_tokens: int = Field(
        default=2048,
        description="Max output tokens per LLM response"
    )

    # ===== QUERY EXPANSION =====
    query_variants_count: int = Field(
        default=3,
        description="Numero di varianti query da generare"
    )

    # ===== DEDUPLICATION =====
    context_dedup_enabled: bool = Field(
        default=True,
        description="Abilita context deduplication per ridurre token usage"
    )
    dedup_target_reduction_percent: float = Field(
        default=20.0,
        description="Target % di riduzione tramite deduplication (15-25%)"
    )

    # ===== EVALUATION & QUALITY =====
    quality_eval_enabled: bool = Field(
        default=True,
        description="Abilita quality evaluation tramite LLM-as-Judge"
    )
    quality_threshold_accept: float = Field(
        default=0.5,
        description="Soglia quality per accettare risposta"
    )

    class Config:
        env_prefix = "PERF_"
        extra = "ignore"

class AppConfig(BaseSettings):
    """Configurazione applicazione principale"""

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")
    log_file: Path = Field(default=LOGS_DIR / "rag.log")

    # Performance monitoring
    enable_monitoring: bool = Field(default=True)
    memory_warning_threshold_pct: int = Field(default=85)

    # Documenti da ingestire
    document_extensions: list[str] = Field(
        default=[".pdf", ".txt", ".md", ".docx"],
        description="Estensioni file supportate"
    )

    # Database
    gemini: GeminiConfig = Field(default_factory=GeminiConfig)
    chromadb: ChromaDBConfig = Field(default_factory=ChromaDBConfig)
    rag: RAGConfig = Field(default_factory=RAGConfig)
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)

    class Config:
        env_file = ".env"
        env_nested_delimiter = "__"
        extra = "ignore"

# Istanza globale di configurazione
config = AppConfig()

# Utility: Stampa configurazione attiva
def print_config() -> None:
    """Debug: mostra configurazione caricata"""
    logger.info("\n" + "="*60)
    logger.info("CONFIGURAZIONE RAG LOCALE - HP ProBook 440 G11")
    logger.info("="*60)
    logger.info(f"\nGemini (Hybrid RAG):")
    # logger.info(f"   API Key: {config.gemini.api_key.get_secret_value()[:5]}...")
    logger.info(f"   Model: {config.gemini.model_name}")
    logger.info(f"   Max Tokens: {config.gemini.max_tokens}")
    logger.info(f"   Embedding: {config.gemini.embedding_model}")

    logger.info(f"\nChromeDB:")
    logger.info(f"   Mode: {config.chromadb.mode}")
    logger.info(f"   Path: {config.chromadb.persist_directory}")
    logger.info(f"   HNSW ef: {config.chromadb.hnsw_construction_ef}")
    logger.info(f"   Chunk Size: {config.chromadb.chunk_size} tokens")

    logger.info(f"\nRAG Engine:")
    logger.info(f"   Top-K: {config.rag.similarity_top_k}")
    logger.info(f"   HITL: {'ENABLED' if config.rag.enable_hitl else 'DISABLED'}")
    logger.info(f"   HITL Threshold: {config.rag.hitl_score_threshold}")

    logger.info(f"\nPaths:")
    logger.info(f"   Documents: {DOCUMENTS_DIR}")
    logger.info(f"   Vector DB: {VECTOR_DB_DIR}")
    logger.info(f"   Logs: {LOGS_DIR}")
    logger.info("\n" + "="*60 + "\n")

if __name__ == "__main__":
    print_config()

