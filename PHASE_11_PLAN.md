# FASE 11: USER EXPERIENCE - PROGRESS TRACKING - PLAN

**Status**: Planning
**Objective**: Enhance ingestion UI with detailed progress reporting
**Estimated Time**: 1-2 hours
**Target**: Real-time progress, partial success reporting, retry UI

---

## Overview

FASE 11 improves the ingestion experience by:
1. **Real-time Progress**: Show which files are being processed
2. **Detailed Status**: Display chunks extracted, embeddings generated
3. **Partial Success**: Show what succeeded vs what failed
4. **Retry Interface**: Allow user to retry failed files
5. **Time Estimates**: Predict remaining time based on rate

---

## 11.1: Progress Callback System

**File**: `src/progress_callbacks.py` (NEW)

```python
"""Progress callbacks for real-time UI updates"""

from typing import Callable, Optional
from dataclasses import dataclass

@dataclass
class ProgressUpdate:
    """Progress update structure"""
    current_file: str
    file_number: int
    total_files: int
    current_chunk: int
    total_chunks: int
    status: str  # "processing", "embedding", "saving", "done", "failed"
    error: Optional[str] = None
    elapsed_seconds: float = 0
    estimated_remaining_seconds: float = 0

class ProgressCallback:
    """Base callback interface"""
    def on_file_start(self, filename: str, file_number: int, total: int):
        pass

    def on_chunk_processing(self, chunk_number: int, total: int):
        pass

    def on_embedding_start(self, chunk_count: int):
        pass

    def on_embedding_complete(self, chunks_done: int, total: int):
        pass

    def on_file_complete(self, filename: str, chunks: int, success: bool, error: str = None):
        pass

    def on_batch_complete(self, total_files: int, successful: int, failed: int, total_chunks: int):
        pass

class StreamlitProgressCallback(ProgressCallback):
    """Streamlit-specific progress callback"""

    def __init__(self, progress_bar, status_text, details_container):
        self.progress_bar = progress_bar
        self.status_text = status_text
        self.details_container = details_container
        self.start_time = time.time()

    def on_file_start(self, filename: str, file_number: int, total: int):
        pct = (file_number - 1) / total
        self.progress_bar.progress(pct)
        self.status_text.text(f"Processing {file_number}/{total}: {filename}")

    def on_chunk_processing(self, chunk_number: int, total: int):
        self.details_container.write(f"  Extracting chunk {chunk_number}/{total}...")

    def on_embedding_start(self, chunk_count: int):
        self.details_container.write(f"  Generating {chunk_count} embeddings...")

    def on_file_complete(self, filename: str, chunks: int, success: bool, error: str = None):
        if success:
            elapsed = time.time() - self.start_time
            self.details_container.success(f"✓ {filename}: {chunks} chunks ({elapsed:.1f}s)")
        else:
            self.details_container.error(f"✗ {filename}: {error}")

    def on_batch_complete(self, total_files: int, successful: int, failed: int, total_chunks: int):
        self.progress_bar.progress(1.0)
        self.status_text.text(f"Complete: {successful}/{total_files} files, {total_chunks} total chunks")
```

---

## 11.2: Enhanced Ingestion Pipeline

**Modified** `src/document_ingestion.py`:

Add progress callback support:

```python
def ingest_single_file(self, file_path: Path, max_retries: int = 3,
                      progress_callback: Optional[ProgressCallback] = None) -> int:
    """Ingest with progress reporting"""

    if progress_callback:
        progress_callback.on_file_start(file_path.name, ...)

    chunks = self.processor.process_file(file_path)
    if progress_callback:
        progress_callback.on_chunk_processing(len(chunks), ...)

    # Add documents
    if progress_callback:
        progress_callback.on_embedding_start(len(chunks))

    count_added, failed_docs = self.vector_store.add_documents(...)

    if progress_callback:
        progress_callback.on_file_complete(
            file_path.name,
            count_added,
            success=True
        )

    return count_added
```

---

## 11.3: Enhanced Streamlit UI

**Modified** `src/app_ui.py`:

Improve ingestion progress display:

```python
if folder_path and st.button("Import Folder"):
    # Create progress containers
    progress_bar = st.progress(0)
    status_text = st.empty()
    details_container = st.container()

    # Gather files
    files = [f for f in path.glob('*') if f.suffix.lower() in ['.pdf', '.txt', '.md']]

    if not files:
        st.warning("No compatible documents found")
    else:
        pipeline = DocumentIngestionPipeline()
        callback = StreamlitProgressCallback(progress_bar, status_text, details_container)

        results = {
            "successful": 0,
            "failed": 0,
            "total_chunks": 0
        }

        for i, file_path in enumerate(files):
            try:
                count = pipeline.ingest_single_file(file_path, progress_callback=callback)
                results["successful"] += 1
                results["total_chunks"] += count
            except Exception as e:
                results["failed"] += 1
                callback.on_file_complete(file_path.name, 0, False, str(e))

        # Final summary
        with details_container:
            st.markdown(f"""
            ## Ingestion Complete
            - **Successful**: {results['successful']}/{len(files)}
            - **Failed**: {results['failed']}/{len(files)}
            - **Total Chunks**: {results['total_chunks']}
            """)

            if results["failed"] > 0:
                st.warning(f"Some files failed. See details above.")
                if st.button("Retry Failed Files"):
                    # Implement retry logic
                    pass
```

---

## 11.4: Partial Success Summary

Add detailed breakdown:

```python
def show_ingestion_summary(results):
    """Display detailed ingestion results"""
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Successful", results["successful"])
    with col2:
        st.metric("Failed", results["failed"])
    with col3:
        st.metric("Total Chunks", results["total_chunks"])

    if results["failed_files"]:
        st.subheader("Failed Files")
        for filename, error in results["failed_files"]:
            st.error(f"**{filename}**: {error}")

    if results["file_metrics"]:
        st.subheader("Processing Time")
        for filename, metrics in results["file_metrics"]:
            st.write(f"{filename}: {metrics['time']:.1f}s ({metrics['chunks']} chunks)")
```

---

## 11.5: Time Estimation

Add ETA calculation:

```python
class TimeEstimator:
    """Estimate remaining time based on progress"""

    def __init__(self):
        self.file_times = []

    def record_file(self, filename: str, duration: float):
        self.file_times.append(duration)

    def estimate_remaining(self, files_remaining: int) -> float:
        """Estimate remaining time in seconds"""
        if not self.file_times:
            return 0

        avg_time = sum(self.file_times) / len(self.file_times)
        return avg_time * files_remaining

    def get_eta_string(self, remaining_seconds: float) -> str:
        """Format ETA as human-readable string"""
        if remaining_seconds < 60:
            return f"{remaining_seconds:.0f}s"
        elif remaining_seconds < 3600:
            return f"{remaining_seconds/60:.1f}m"
        else:
            return f"{remaining_seconds/3600:.1f}h"
```

---

## 11.6: Retry Interface

Add ability to retry failed files:

```python
class IngestionRetryManager:
    """Manage retry of failed files"""

    def __init__(self):
        self.failed_files = []

    def add_failed(self, filename: str, error: str):
        self.failed_files.append({"filename": filename, "error": error})

    def get_failed_files(self) -> List[Path]:
        """Return paths of failed files for retry"""
        return [Path(DOCUMENTS_DIR) / f["filename"] for f in self.failed_files]

    def show_retry_ui(self):
        """Display retry interface in Streamlit"""
        if self.failed_files:
            st.warning(f"Warning: {len(self.failed_files)} files failed")
            for failed in self.failed_files:
                st.write(f"- {failed['filename']}: {failed['error']}")

            if st.button("Retry Failed Files"):
                st.info("Retrying failed files...")
                pipeline = DocumentIngestionPipeline()
                successful = 0
                for file_path in self.get_failed_files():
                    try:
                        pipeline.ingest_single_file(file_path)
                        successful += 1
                    except Exception as e:
                        st.error(f"Still failed: {e}")
                st.success(f"Retried: {successful} files succeeded")
```

---

## Implementation Sequence

1. **Create progress_callbacks.py** - Base callback system
2. **Modify document_ingestion.py** - Accept and use callbacks
3. **Modify app_ui.py** - Integrate progress display
4. **Add time estimation** - Show ETA
5. **Add retry interface** - Allow user to retry failures
6. **Test** - Verify UI improvements

---

## Success Criteria

- ✅ Progress bar shows 0-100% during ingestion
- ✅ Current file name displayed
- ✅ Chunk count shown (X/Y)
- ✅ Success/failure breakdown shown
- ✅ Failed files listed with error reasons
- ✅ Estimated time remaining displayed
- ✅ Retry button available for failed files
- ✅ Metrics integrated with progress tracking
- ✅ No performance degradation
- ✅ Works with Streamlit streaming

---

## Files to Create/Modify

| File | Type | Action |
|------|------|--------|
| `src/progress_callbacks.py` | Code | CREATE |
| `src/document_ingestion.py` | Code | MODIFY (add callbacks) |
| `src/app_ui.py` | Code | MODIFY (use callbacks) |

---

This is the FASE 11 plan. Ready to implement.
