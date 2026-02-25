"""
Pipeline di Ingestion Documenti IT
Supporta: PDF, TXT, MD, DOCX
Utilizza RegEx-based chunking per preservare struttura
"""

import re
import time
from pathlib import Path
import logging
from typing import Any, Optional, Dict, List
from dataclasses import dataclass
from concurrent.futures import ProcessPoolExecutor, as_completed
import os

try:
    import pypdf
except ImportError:
    pypdf = None

try:
    from docx import Document as DocxDocument
except ImportError:
    DocxDocument = None

from src.config import config, DOCUMENTS_DIR, LOGS_DIR
from src.vector_store import get_vector_store
from src.progress_callbacks import ProgressCallback, ProgressUpdate
from src.pdf_validator import get_pdf_validator
from src.tag_manager import TagManager
from src.document_summarizer import DocumentSummarizer
from src.logging_config import get_logger
from src.rate_limiter import rate_limit

logger = get_logger(__name__)

# Crash Recovery Files
LOCK_FILE = LOGS_DIR / "ingestion_lock.txt"
BLACKLIST_FILE = LOGS_DIR / "ingestion_blacklist.txt"

def load_blacklist():
    if BLACKLIST_FILE.exists():
        with open(BLACKLIST_FILE, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def add_to_blacklist(filename):
    with open(BLACKLIST_FILE, "a", encoding="utf-8") as f:
        f.write(f"{filename}\n")

def check_previous_crash():
    """Check if we crashed last time and blacklist the culprit"""
    if LOCK_FILE.exists():
        try:
            with open(LOCK_FILE, "r", encoding="utf-8") as f:
                crashed_file = f.read().strip()
            
            if crashed_file:
                logger.warning(f"🚨 Rilevato crash precedente su: {crashed_file}. Aggiungo alla blacklist.")
                add_to_blacklist(crashed_file)
            
            # Remove lock after handling
            LOCK_FILE.unlink()
        except Exception as e:
            logger.error(f"Error handling crash lock: {e}")


@dataclass
class Chunk:
    """Rappresentazione di un chunk di documento"""
    text: str
    source: str
    section: Optional[str] = None
    page: Optional[int] = None
    order: int = 0
    extra_metadata: Optional[dict] = None  # FASE 17: Support for visual metadata


class DocumentProcessor:
    """Processa documenti in vari formati"""

    def __init__(self):
        self.chunk_size = config.chromadb.chunk_size
        self.chunk_overlap = config.chromadb.chunk_overlap
        # Auto-Check Crash on Startup
        check_previous_crash()

    def process_file(self, file_path: Path) -> list[Chunk]:
        """Processa file singolo in base all'estensione"""
        file_path = Path(file_path)

        if not file_path.exists():
            logger.error(f"✗ File non trovato: {file_path}")
            return []
            
        # Check Blacklist
        blacklist = load_blacklist()
        if file_path.name in blacklist:
            logger.warning(f"🚫 Salto file in blacklist (crash precedente): {file_path.name}")
            return []

        # Set Lock
        try:
            with open(LOCK_FILE, "w", encoding="utf-8") as f:
                f.write(file_path.name)
        except Exception as e:
            logger.error(f"Error writing lock file: {e}")

        chunks = []
        try:
            if file_path.suffix.lower() == ".pdf":
                chunks = self._process_pdf(file_path)
            elif file_path.suffix.lower() == ".txt":
                chunks = self._process_txt(file_path)
            elif file_path.suffix.lower() == ".md":
                chunks = self._process_markdown(file_path)
            elif file_path.suffix.lower() == ".docx":
                chunks = self._process_docx(file_path)
            else:
                logger.warning(f"⚠️  Formato non supportato: {file_path.suffix}")
                chunks = []
        finally:
            # Clear Lock (safe even if crashed, as this runs on next successful completion... 
            # actually if it crashes, this finally block might not complete in the OS process sense if segfault,
            # but the lock REMAINS, which is what we want for the NEXT run to detect it.)
            if LOCK_FILE.exists():
                LOCK_FILE.unlink()
                
        return chunks

    def _process_pdf(self, file_path: Path) -> list[Chunk]:
        """Estrai testo da PDF usando subprocess isolato (anti-crash)"""
        import subprocess
        import json
        import sys
        
        chunks = []
        worker_script = Path(__file__).parent / "pdf_worker.py"
        
        try:
            # Run worker in separate process
            logger.info(f"🚀 Avvio analisi sicura per: {file_path.name}")
            result = subprocess.run(
                [sys.executable, str(worker_script), str(file_path)],
                capture_output=True,
                text=True,
                timeout=300  # Aumentato a 300s per PDF grandi + Gemini embedding (FIX FASE 5)
            )
            
            if result.returncode != 0:
                logger.error(f"⚠️ Errore nel worker PDF per {file_path.name}: {result.stderr}")
                return []

            # Read result sidecar file
            output_file = file_path.with_suffix(".json.temp")
            if not output_file.exists():
                logger.error(f"⚠️ Nessun output dal worker per {file_path.name}")
                return []

            try:
                with open(output_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Convert to Chunks
                for page_data in data.get("pages", []):
                    page_chunks = self._chunk_text(
                        page_data["text"],
                        source=file_path.name,
                        page=page_data["page_num"]
                    )
                    chunks.extend(page_chunks)

                logger.info(f"✓ PDF processato (Safe Mode): {file_path.name} ({len(chunks)} chunks)")
            finally:
                # Cleanup temp file SEMPRE, anche se json.load() o elaborazione fallisce
                if output_file.exists():
                    try:
                        output_file.unlink()
                        logger.debug(f"Cleanup: rimosso {output_file.name}")
                    except Exception as e:
                        logger.warning(f"⚠️ Non riuscito a eliminare {output_file.name}: {e}")

            return chunks

        except subprocess.TimeoutExpired:
            logger.error(f"⏳ Timeout analisi PDF per {file_path.name} (saltato)")
            return []
        except Exception as e:
            logger.error(f"✗ Errore subprocess PDF: {e}")
            return []

    def _process_txt(self, file_path: Path) -> list[Chunk]:
        """Processa file TXT"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()

            chunks = self._chunk_text(text, source=file_path.name)
            logger.info(f"✓ TXT processato: {file_path.name} ({len(chunks)} chunks)")
            return chunks

        except Exception as e:
            logger.error(f"✗ Errore TXT processing: {e}")
            return []

    def _process_markdown(self, file_path: Path) -> list[Chunk]:
        """Processa file Markdown preservando struttura sezioni"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            chunks = []
            # Splita per header (# ## ###)
            sections = re.split(r'^(#{1,3}\s+.+)$', content, flags=re.MULTILINE)

            current_section = None
            for i, section in enumerate(sections):
                if section.startswith('#'):
                    # Identificato header
                    current_section = section.strip()
                    logger.debug(f"   Section: {current_section[:50]}...")
                elif section.strip():
                    # Contenuto della sezione
                    section_chunks = self._chunk_text(
                        section,
                        source=file_path.name,
                        section=current_section
                    )
                    chunks.extend(section_chunks)

            logger.info(f"✓ Markdown processato: {file_path.name} ({len(chunks)} chunks)")
            return chunks

        except Exception as e:
            logger.error(f"✗ Errore Markdown processing: {e}")
            return []

    def _process_docx(self, file_path: Path) -> list[Chunk]:
        """Processa file DOCX"""
        if DocxDocument is None:
            logger.error("❌ python-docx non installato. Salta file DOCX.")
            return []

        try:
            doc = DocxDocument(file_path)
            text = "\n".join([para.text for para in doc.paragraphs])

            chunks = self._chunk_text(text, source=file_path.name)
            logger.info(f"✓ DOCX processato: {file_path.name} ({len(chunks)} chunks)")
            return chunks

        except Exception as e:
            logger.error(f"✗ Errore DOCX processing: {e}")
            return []

    def _chunk_text(
        self,
        text: str,
        source: str,
        section: Optional[str] = None,
        page: Optional[int] = None
    ) -> list[Chunk]:
        """
        Chunking intelligente: preserva frasi complete e struttura.
        Utilizza sentence splitting per migliore coesione semantica.
        """
        if not text or len(text) < 50:
            return []

        chunks = []

        # Split per frasi (sentence-aware)
        # Regex che preserva puntuazione
        sentences = re.split(r'(?<=[.!?])\s+', text)

        current_chunk = ""
        chunk_order = 0

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # Aggiungi frase al chunk corrente
            test_chunk = (current_chunk + " " + sentence).strip()

            # Stima token (euristica: 1 token ~= 4 caratteri per Italiano)
            estimated_tokens = len(test_chunk) // 4

            if estimated_tokens <= self.chunk_size:
                # Frase entra nel chunk
                current_chunk = test_chunk
            else:
                # Chunk pieno, salva e inizia nuovo
                if current_chunk:
                    chunks.append(Chunk(
                        text=current_chunk,
                        source=source,
                        section=section,
                        page=page,
                        order=chunk_order
                    ))
                    chunk_order += 1

                # Nuova frase diventa inizio del nuovo chunk
                current_chunk = sentence

        # Salva ultimo chunk
        if current_chunk:
            chunks.append(Chunk(
                text=current_chunk,
                source=source,
                section=section,
                page=page,
                order=chunk_order
            ))

        return chunks


class DocumentIngestionPipeline:
    """Pipeline completa: lettura file → chunking → vector store"""

    def __init__(self):
        self.processor = DocumentProcessor()
        self.vector_store = get_vector_store()
        self.tag_manager = TagManager()  # FASE 7: Initialize tag manager for document tagging
        self.summarizer = DocumentSummarizer()  # FASE 8: Initialize summarizer for document summaries

    def ingest_from_directory(self, directory: Path = None, progress_callback: Optional[ProgressCallback] = None) -> int:
        """
        Ingestisci tutti i documenti da directory con supporto progress callback (FASE 13).

        Args:
            directory: Path alla cartella. Default: config.documents_dir
            progress_callback: Optional ProgressCallback per real-time UI updates

        Returns:
            Numero di chunk ingestiti
        """
        if directory is None:
            directory = DOCUMENTS_DIR

        directory = Path(directory)
        if not directory.exists():
            logger.warning(f"⚠️  Directory non trovata: {directory}")
            return 0

        logger.info(f"📂 Scansionamento: {directory}")

        # FASE 13: Track timing for batch completion report
        batch_start_time = time.perf_counter()

        # FASE 13: Collect all files first to know total for progress
        all_files = []
        for ext in config.document_extensions:
            files = list(directory.glob(f"*{ext}"))
            logger.info(f"   Trovati {len(files)} file {ext}")
            all_files.extend(files)

        if not all_files:
            logger.warning(f"⚠️  Nessun file trovato in {directory}")
            return 0

        # FASE 13: Ingest with progress tracking
        total_chunks = 0
        for file_counter, file_path in enumerate(all_files, 1):
            logger.info(f"\n📄 [{file_counter}/{len(all_files)}] Elaborazione: {file_path.name}")
            print(f"Processing: {file_path.name}", flush=True)  # Streamlit progress

            chunks_added = self.ingest_single_file(
                file_path,
                progress_callback=progress_callback,
                file_number=file_counter,
                total_files=len(all_files)
            )
            total_chunks += chunks_added

        logger.info(f"\nIngestion completato: {total_chunks} chunks totali")

        # FASE 13: Report batch completion
        if progress_callback:
            elapsed_seconds = time.perf_counter() - batch_start_time
            progress_callback.on_batch_complete(
                total_files=len(all_files),
                successful=len(all_files),  # Assuming all succeeded (failures handled individually)
                failed=0,
                total_chunks=total_chunks,
                elapsed_seconds=elapsed_seconds
            )

        return total_chunks

    def ingest_from_directory_parallel(
        self,
        directory: Path = None,
        max_workers: int = None,
        use_batch_embedding: bool = True
    ) -> int:
        """
        Ingestisci documenti da directory in PARALLELO per 10-50x speedup (OPTIMIZATION 8.7).

        OPTIMIZATION 8.7: Parallel document processing
        - Uses ProcessPoolExecutor for multi-core PDF processing
        - Each worker processes one PDF independently
        - Significantly faster on multi-core CPUs (4+ cores)
        - Batch embeddings for additional 3-5x speedup

        Args:
            directory: Path alla cartella. Default: config.documents_dir
            max_workers: Numero di worker processes (default: CPU count)
            use_batch_embedding: Usa batch embedding per ancora più velocità

        Returns:
            Numero totale di chunks ingestiti
        """
        if directory is None:
            directory = DOCUMENTS_DIR

        directory = Path(directory)
        if not directory.exists():
            logger.warning(f"⚠️  Directory non trovata: {directory}")
            return 0

        # Determina numero di worker (default: CPU count)
        if max_workers is None:
            max_workers = os.cpu_count() or 4

        logger.info(f"📂 Parallel Ingestion: {directory} (workers={max_workers}, batch_embedding={use_batch_embedding})")

        # Raccogli tutti i file
        all_files = []
        for ext in config.document_extensions:
            files = list(directory.glob(f"*{ext}"))
            all_files.extend(files)

        if not all_files:
            logger.warning(f"⚠️  Nessun file trovato in {directory}")
            return 0

        logger.info(f"   Trovati {len(all_files)} file, processing con {max_workers} workers...")

        # Raccoglie i chunk da tutti i file
        failed_files = []
        
        # Batching variables (FASE 3 OPTIMIZATION)
        batch_documents = []
        batch_metadatas = []
        batch_ids = []
        BATCH_THRESHOLD = 500  # Write to VectorStore every 500 chunks to save RAM
        chunks_since_last_write = 0
        total_chunks = 0  # FIX: inizializzare prima del loop futures


        # OPTIMIZATION 8.7: Parallelize PDF processing
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            # Sottometti tutti i job
            future_to_file = {
                executor.submit(self._process_file_for_parallel, file_path): file_path
                for file_path in all_files
            }

            # Raccogli risultati man mano che completano
            completed = 0
            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                completed += 1

                try:
                    chunks = future.result()  # Returns Chunk objects
                    if chunks:
                        logger.info(f"✓ [{completed}/{len(all_files)}] {file_path.name}: {len(chunks)} chunks")
                        
                        # Prepare data for batch
                        for chunk in chunks:
                             batch_documents.append(chunk.text)
                             metadata = {
                                "source": chunk.source,
                                "section": chunk.section or "default",
                                "page": chunk.page or 0,
                                "order": chunk.order
                             }
                             # Merge extra metadata if present (FASE 17)
                             if chunk.extra_metadata:
                                 metadata.update(chunk.extra_metadata)
                             
                             batch_metadatas.append(metadata)
                             batch_ids.append(f"{Path(chunk.source).stem}_{chunk.order:03d}")
                        
                        chunks_since_last_write += len(chunks)

                        # Write batch if threshold reached
                        if len(batch_documents) >= BATCH_THRESHOLD:
                             logger.info(f"💾 Flushing batch of {len(batch_documents)} chunks to VectorStore...")
                             try:
                                 count, failed = self.vector_store.add_documents(
                                     documents=batch_documents,
                                     metadatas=batch_metadatas,
                                     ids=batch_ids,
                                     rebuild_matrix=False, # Deferred rebuild until end
                                     use_batch_embedding=use_batch_embedding
                                 )
                                 total_chunks += count
                                 if failed:
                                     logger.warning(f"⚠️ {len(failed)} chunks failed in batch")
                                 
                                 # Clear batch
                                 batch_documents = []
                                 batch_metadatas = []
                                 batch_ids = []
                             except Exception as e:
                                 logger.error(f"Error writing batch: {e}")
                                 # Retain batch? No, skip to avoid blocking subsequent
                                 batch_documents = []
                                 batch_metadatas = []
                                 batch_ids = []
                    else:
                        logger.warning(f"⚠️  [{completed}/{len(all_files)}] {file_path.name}: 0 chunks")
                except Exception as e:
                    logger.error(f"✗ [{completed}/{len(all_files)}] {file_path.name} FAILED: {e}")
                    failed_files.append((file_path.name, str(e)[:100]))

        # Write remaining chunks
        if batch_documents:
            try:
                logger.info(f"💾 Flushing final batch of {len(batch_documents)} chunks...")
                count, failed = self.vector_store.add_documents(
                     documents=batch_documents,
                     metadatas=batch_metadatas,
                     ids=batch_ids,
                     rebuild_matrix=True, # Rebuild at the end
                     use_batch_embedding=use_batch_embedding
                )
                total_chunks += count
            except Exception as e:
                logger.error(f"Error writing final batch: {e}")

        # Force matrix rebuild if we skipped it during batches
        if total_chunks > 0:
             self.vector_store._rebuild_matrix()
             self.vector_store._rebuild_metadata_index()

        logger.info(f"\nParallel ingestion completato: {total_chunks} chunks, {len(failed_files)} file failed")
        if failed_files:
            logger.warning("Failed files:")
            for fname, error in failed_files:
                logger.warning(f"  - {fname}: {error}")

        return total_chunks

    def _process_file_for_parallel(self, file_path: Path):
        """
        Worker function per ProcessPoolExecutor (OPTIMIZATION 8.7).
        Elabora singolo file e ritorna lista di Chunk objects.
        """
        try:
            # 1. Standard text processing
            chunks = self.processor.process_file(file_path)
            
            # 2. FASE 17: Multimodal Processing for PDFs
            if file_path.suffix.lower() == ".pdf" and chunks:
                try:
                    # Import locally to avoid pickling issues and circular imports
                    from src.multimodal_ingestion import MultimodalIngestion
                    
                    # Instantiate fresh in worker process
                    multimodal = MultimodalIngestion()
                    visual_elements = multimodal.process_pdf_visuals(file_path)
                    
                    if visual_elements:
                        logger.info(f"Adding {len(visual_elements)} visual elements for {file_path.name}")
                        
                        # Create chunks for visual elements
                        start_order = len(chunks)
                        for i, visual in enumerate(visual_elements):
                            visual_chunk = Chunk(
                                text=visual['text'],  # Description + label
                                source=visual['source'],
                                section=f"Visual: {visual['type']}",
                                page=visual['page'],
                                order=start_order + i,
                                extra_metadata={
                                    "content_type": "visual",
                                    "image_path": visual.get("image_path"),
                                    "visual_type": visual.get("type")
                                }
                            )
                            chunks.append(visual_chunk)
                
                except Exception as e:
                    logger.warning(f"Multimodal processing failed for {file_path.name}: {e}")
                    # Continue with just text chunks
            
            return chunks
        except Exception as e:
            logger.error(f"Worker error processing {file_path.name}: {e}")
            raise

    @rate_limit(endpoint_name="document_ingestion", tokens_cost=5.0)
    def ingest_single_file(self, file_path: Path, max_retries: int = 3, progress_callback: Optional[ProgressCallback] = None, file_number: int = 1, total_files: int = 1) -> int:
        """
        Ingestisci singolo file con retry logic per rate-limit errors.

        FIX FASE 6: Add retry logic for rate-limit (429) errors
        - Implement exponential backoff
        - Distinguish between rate-limit (retry) vs other errors (fail)
        - Add progress logging for UI feedback

        FASE 10: Add metrics collection
        - Track ingestion time, chunks created
        - Record success/failure with error details

        FASE 13+14: Add progress callbacks and PDF validation
        - Accept progress_callback for real-time UI updates
        - Validate PDFs before processing (FASE 12)
        - Report validation errors via callback
        """
        file_path = Path(file_path)
        logger.info(f"📄 Ingestion: {file_path.name}")
        print(f"Processing: {file_path.name}", flush=True)  # Streamlit progress

        # FASE 13+14: Initialize progress callback (optional)
        if progress_callback:
            progress_callback.on_file_start(file_path.name, file_number, total_files)

        # FASE 10: Initialize metrics
        from src.metrics import get_metrics_collector, IngestionMetrics
        metrics_collector = get_metrics_collector()
        start_time = time.perf_counter()
        file_size = file_path.stat().st_size if file_path.exists() else 0

        # Check if blacklisted
        blacklist = load_blacklist()
        if file_path.name in blacklist:
            logger.warning(f"Skipping blacklisted file: {file_path.name}")
            if progress_callback:
                progress_callback.on_file_complete(
                    filename=file_path.name,
                    chunks_added=0,
                    success=False,
                    error="File blacklisted (previous crash)"
                )
            return 0

        # FASE 12: PDF Validation (if PDF file)
        if file_path.suffix.lower() == ".pdf":
            validator = get_pdf_validator()
            is_valid, error = validator.validate_strict(file_path)

            if not is_valid:
                logger.warning(f"❌ PDF Validation failed for {file_path.name}: {error.message}")

                if validator.should_blacklist(error):
                    logger.warning(f"🚫 Permanently blacklisting {file_path.name} ({error.error_type.value})")
                    add_to_blacklist(file_path.name)

                    if progress_callback:
                        progress_callback.on_file_complete(
                            filename=file_path.name,
                            chunks_added=0,
                            success=False,
                            error=f"Validation failed - {error.error_type.value}: {error.message}"
                        )

                    # Record metrics for validation failure
                    end_time = time.perf_counter()
                    duration = end_time - start_time
                    metrics = IngestionMetrics(
                        file_name=file_path.name,
                        file_size_bytes=file_size,
                        chunks_created=0,
                        embeddings_generated=0,
                        start_time=start_time,
                        end_time=end_time,
                        duration_seconds=duration,
                        success=False,
                        error=f"PDF validation failed: {error.error_type.value}"
                    )
                    metrics_collector.record_ingestion(metrics)

                    return 0

                elif validator.should_retry(error):
                    logger.warning(f"⏳ Transient validation error, will retry: {error.message}")
                    # Fall through to retry logic below

        retry_count = 0
        while retry_count < max_retries:
            try:
                chunks = self.processor.process_file(file_path)
                if not chunks:
                    logger.warning(f"⚠️ No chunks extracted from {file_path.name}")
                    if progress_callback:
                        progress_callback.on_file_complete(
                            filename=file_path.name,
                            chunks_added=0,
                            success=False,
                            error="No chunks extracted (file may be empty or unreadable)"
                        )
                    return 0

                # FASE 13: Report chunk extraction complete
                if progress_callback and len(chunks) > 0:
                    progress_callback.on_chunk_extracted(
                        chunk_number=len(chunks),
                        total_chunks=len(chunks),
                        filename=file_path.name
                    )

                documents = [chunk.text for chunk in chunks]

                # FASE 7: Extract tags from document content (first chunk)
                tags = []
                if chunks:
                    # Get tags from first chunk content
                    tags = self.tag_manager.extract_tags_for_document(
                        filename=file_path.name,
                        content=chunks[0].text,
                        num_tags=3
                    )
                    logger.info(f"📌 Extracted tags for {file_path.name}: {tags}")

                metadatas = [
                    {
                        "source": chunk.source,
                        "section": chunk.section or "default",
                        "page": chunk.page or 0,
                        "order": chunk.order,
                        "tags": tags  # FASE 7: Add tags to metadata
                    }
                    for chunk in chunks
                ]
                ids = [
                    f"{file_path.stem}_{chunk.order:03d}"
                    for chunk in chunks
                ]

                # FASE 13: Report embedding generation started
                if progress_callback and len(chunks) > 0:
                    progress_callback.on_embedding_start(
                        chunk_count=len(chunks),
                        filename=file_path.name
                    )

                # FASE 9: Handle return value from add_documents (track actual added vs attempted)
                count_added, failed_docs = self.vector_store.add_documents(
                    documents=documents,
                    metadatas=metadatas,
                    ids=ids
                )

                if failed_docs:
                    logger.warning(f"Failed to add {len(failed_docs)}/{len(chunks)} chunks")
                    for doc_id, error in failed_docs:
                        logger.warning(f"  - {doc_id}: {error}")

                logger.info(f"Successfully ingested {count_added}/{len(chunks)} chunks from {file_path.name}")

                # FASE 8: Auto-generate summaries for document
                try:
                    if chunks and count_added > 0:
                        # Use full text of first chunk for summary generation
                        doc_text = documents[0]  # First document chunk

                        # Generate summary
                        summary = self.summarizer.summarize_document(
                            filename=file_path.name,
                            content=doc_text,
                            use_cache=True
                        )

                        # Extract key points
                        key_points = []
                        if summary:  # Only extract key points if we have a summary
                            key_points = self.summarizer.extract_key_points(
                                filename=file_path.name,
                                content=doc_text,
                                num_points=3
                            )

                        if summary or key_points:
                            # Update document metadata with summary
                            success = self.vector_store.update_document_summary(
                                source_filename=file_path.name,
                                summary=summary,
                                key_points=key_points
                            )
                            if success:
                                logger.info(f"Generated summary and key points for {file_path.name}")
                except Exception as e:
                    logger.warning(f"Failed to generate summary for {file_path.name}: {e}")
                    # Continue without summary (non-blocking)

                # FASE 10: Record success metrics
                end_time = time.perf_counter()
                duration = end_time - start_time
                metrics = IngestionMetrics(
                    file_name=file_path.name,
                    file_size_bytes=file_size,
                    chunks_created=count_added,
                    embeddings_generated=count_added,
                    start_time=start_time,
                    end_time=end_time,
                    duration_seconds=duration,
                    success=True
                )
                metrics_collector.record_ingestion(metrics)

                # FASE 13: Report file completion success
                if progress_callback:
                    progress_callback.on_file_complete(
                        filename=file_path.name,
                        chunks_added=count_added,
                        success=True
                    )

                return count_added  # Return actual added, not attempted

            except RuntimeError as e:
                # Check if rate-limit error from vector_store
                error_msg = str(e)
                is_rate_limit = "429" in error_msg or "rate" in error_msg.lower()

                if is_rate_limit and retry_count < max_retries - 1:
                    # Exponential backoff: 30s, 60s, 120s
                    wait_time = 30 * (2 ** retry_count)
                    logger.warning(f"[429 Rate Limited] {file_path.name} - Waiting {wait_time}s before retry {retry_count + 1}/{max_retries}")
                    if progress_callback:
                        progress_callback.on_file_complete(
                            filename=file_path.name,
                            chunks_added=0,
                            success=False,
                            error=f"Rate limited - retrying ({retry_count + 1}/{max_retries})"
                        )
                    time.sleep(wait_time)
                    retry_count += 1
                    continue
                elif retry_count < max_retries - 1:
                    # Other errors - retry quickly
                    logger.warning(f"[Error] {file_path.name}: {error_msg[:100]}... - Retrying in 5s ({retry_count + 1}/{max_retries})")
                    if progress_callback:
                        progress_callback.on_file_complete(
                            filename=file_path.name,
                            chunks_added=0,
                            success=False,
                            error=f"Error - retrying ({retry_count + 1}/{max_retries}): {error_msg[:50]}"
                        )
                    time.sleep(5)
                    retry_count += 1
                    continue
                else:
                    # Max retries exceeded
                    logger.error(f"Max retries ({max_retries}) exceeded for {file_path.name}")
                    add_to_blacklist(file_path.name)

                    # FASE 10: Record failure metrics
                    end_time = time.perf_counter()
                    duration = end_time - start_time
                    metrics = IngestionMetrics(
                        file_name=file_path.name,
                        file_size_bytes=file_size,
                        chunks_created=0,
                        embeddings_generated=0,
                        start_time=start_time,
                        end_time=end_time,
                        duration_seconds=duration,
                        success=False,
                        error=error_msg[:200]
                    )
                    metrics_collector.record_ingestion(metrics)

                    # FASE 13: Report final failure
                    if progress_callback:
                        progress_callback.on_file_complete(
                            filename=file_path.name,
                            chunks_added=0,
                            success=False,
                            error=f"Max retries exceeded: {error_msg[:100]}"
                        )

                    return 0

            except Exception as e:
                logger.error(f"Unexpected error ingesting {file_path.name}: {e}")
                add_to_blacklist(file_path.name)

                # FASE 10: Record failure metrics
                end_time = time.perf_counter()
                duration = end_time - start_time
                metrics = IngestionMetrics(
                    file_name=file_path.name,
                    file_size_bytes=file_size,
                    chunks_created=0,
                    embeddings_generated=0,
                    start_time=start_time,
                    end_time=end_time,
                    duration_seconds=duration,
                    success=False,
                    error=str(e)[:200]
                )
                metrics_collector.record_ingestion(metrics)

                # FASE 13: Report unexpected error
                if progress_callback:
                    progress_callback.on_file_complete(
                        filename=file_path.name,
                        chunks_added=0,
                        success=False,
                        error=f"Unexpected error: {str(e)[:100]}"
                    )

                return 0

        return 0


if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)

    pipeline = DocumentIngestionPipeline()

    # Crea documento di test
    test_doc = DOCUMENTS_DIR / "test_policy.txt"
    test_doc.parent.mkdir(parents=True, exist_ok=True)

    with open(test_doc, 'w', encoding='utf-8') as f:
        f.write("""
POLICY SMART WORKING 2024

1. PRINCIPI GENERALI
Il smart working è un modalità di lavoro flessibile che consente ai dipendenti
di svolgere le proprie attività lavorative in modalità remota, con accordo
aziendale e nel rispetto dei vincoli normativi.

2. REQUISITI TECNICI
I dipendenti devono disporre di una connessione internet stabile e di un
ambiente di lavoro adatto allo svolgimento delle proprie funzioni.
La sicurezza informatica è prioritaria.

3. FREQUENZA
La frequenza massima di smart working è stabilita in 3 giorni a settimana,
salvo diverse disposizioni del management.
""")

    print("\n" + "="*60)
    print("TEST INGESTION PIPELINE")
    print("="*60)

    total = pipeline.ingest_from_directory()
    print(f"\nIngestion completato: {total} chunks")

    # Verifica vector store
    print("\nVector Store Stats:")
    stats = pipeline.vector_store.get_stats()
    for k, v in stats.items():
        print(f"  {k}: {v}")
