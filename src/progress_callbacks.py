"""
Progress callbacks for real-time ingestion UI updates
Decouples backend progress from frontend rendering
"""

import logging
import time
from typing import Optional, Callable
from dataclasses import dataclass
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


@dataclass
class ProgressUpdate:
    """Standard progress update structure"""
    current_file: str
    file_number: int
    total_files: int
    current_chunk: int
    total_chunks: int
    status: str  # "starting", "processing", "embedding", "saving", "done", "failed"
    error: Optional[str] = None
    elapsed_seconds: float = 0
    estimated_remaining_seconds: float = 0

    @property
    def progress_percent(self) -> float:
        """Progress as percentage (0-100)"""
        if self.total_files <= 0:
            return 0
        return (self.file_number - 1 + (self.current_chunk / max(1, self.total_chunks))) / self.total_files * 100

    @property
    def eta_string(self) -> str:
        """Human-readable ETA"""
        if self.estimated_remaining_seconds < 60:
            return f"{self.estimated_remaining_seconds:.0f}s"
        elif self.estimated_remaining_seconds < 3600:
            return f"{self.estimated_remaining_seconds/60:.1f}m"
        else:
            return f"{self.estimated_remaining_seconds/3600:.1f}h"


class ProgressCallback(ABC):
    """Base callback interface for progress updates"""

    @abstractmethod
    def on_file_start(self, filename: str, file_number: int, total_files: int):
        """Called when starting to process a file"""
        pass

    @abstractmethod
    def on_chunk_extracted(self, chunk_number: int, total_chunks: int, filename: str):
        """Called when chunk is extracted from file"""
        pass

    @abstractmethod
    def on_embedding_start(self, chunk_count: int, filename: str):
        """Called when starting to generate embeddings"""
        pass

    @abstractmethod
    def on_embedding_progress(self, completed: int, total: int, filename: str):
        """Called with embedding progress"""
        pass

    @abstractmethod
    def on_file_complete(self, filename: str, chunks_added: int, success: bool, error: Optional[str] = None):
        """Called when file processing complete"""
        pass

    @abstractmethod
    def on_batch_complete(self, total_files: int, successful: int, failed: int, total_chunks: int,
                         elapsed_seconds: float):
        """Called when entire batch complete"""
        pass


class LoggingProgressCallback(ProgressCallback):
    """Progress callback that logs to logger"""

    def on_file_start(self, filename: str, file_number: int, total_files: int):
        logger.info(f"[{file_number}/{total_files}] Starting: {filename}")

    def on_chunk_extracted(self, chunk_number: int, total_chunks: int, filename: str):
        if chunk_number % max(1, total_chunks // 5) == 0:  # Log every 20%
            logger.debug(f"  Chunks: {chunk_number}/{total_chunks}")

    def on_embedding_start(self, chunk_count: int, filename: str):
        logger.debug(f"  Generating {chunk_count} embeddings...")

    def on_embedding_progress(self, completed: int, total: int, filename: str):
        if total > 0 and completed % max(1, total // 5) == 0:  # Log every 20%
            logger.debug(f"  Embeddings: {completed}/{total}")

    def on_file_complete(self, filename: str, chunks_added: int, success: bool, error: Optional[str] = None):
        if success:
            logger.info(f"  ✓ Completed: {chunks_added} chunks")
        else:
            logger.warning(f"  ✗ Failed: {error}")

    def on_batch_complete(self, total_files: int, successful: int, failed: int, total_chunks: int,
                         elapsed_seconds: float):
        logger.info(f"Batch complete: {successful}/{total_files} files, {total_chunks} chunks in {elapsed_seconds:.1f}s")


class PrintProgressCallback(ProgressCallback):
    """Progress callback that prints to stdout"""

    def on_file_start(self, filename: str, file_number: int, total_files: int):
        print(f"\n[{file_number}/{total_files}] {filename}")

    def on_chunk_extracted(self, chunk_number: int, total_chunks: int, filename: str):
        pass  # Too verbose for print

    def on_embedding_start(self, chunk_count: int, filename: str):
        print(f"  Generating {chunk_count} embeddings...", flush=True)

    def on_embedding_progress(self, completed: int, total: int, filename: str):
        pass  # Too verbose for print

    def on_file_complete(self, filename: str, chunks_added: int, success: bool, error: Optional[str] = None):
        if success:
            print(f"  Done: {chunks_added} chunks")
        else:
            print(f"  Error: {error}")

    def on_batch_complete(self, total_files: int, successful: int, failed: int, total_chunks: int,
                         elapsed_seconds: float):
        rate = total_chunks / elapsed_seconds if elapsed_seconds > 0 else 0
        print(f"\n{'='*60}")
        print(f"Complete: {successful}/{total_files} files ({failed} failed)")
        print(f"Total: {total_chunks} chunks in {elapsed_seconds:.1f}s ({rate:.1f} chunks/s)")
        print(f"{'='*60}\n")


class StreamlitProgressCallback(ProgressCallback):
    """Progress callback for Streamlit UI"""

    def __init__(self, progress_bar, status_text, details_container):
        self.progress_bar = progress_bar
        self.status_text = status_text
        self.details_container = details_container
        self.start_time = time.time()
        self.file_times = []  # For ETA calculation
        self.current_file_start = None

    def on_file_start(self, filename: str, file_number: int, total_files: int):
        """Show which file we're processing"""
        pct = (file_number - 1) / total_files if total_files > 0 else 0
        self.progress_bar.progress(pct)

        elapsed = time.time() - self.start_time
        avg_file_time = sum(self.file_times) / len(self.file_times) if self.file_times else 0
        remaining_files = total_files - file_number
        estimated_remaining = avg_file_time * remaining_files

        self.status_text.text(
            f"Processing {file_number}/{total_files}: {filename}\n"
            f"Elapsed: {elapsed:.0f}s | ETA: {estimated_remaining:.0f}s"
        )

        self.current_file_start = time.time()

    def on_chunk_extracted(self, chunk_number: int, total_chunks: int, filename: str):
        """Show chunk extraction progress"""
        pass  # Too verbose for Streamlit

    def on_embedding_start(self, chunk_count: int, filename: str):
        """Show embedding generation start"""
        self.details_container.write(f"  ⚙️ Generating {chunk_count} embeddings...")

    def on_embedding_progress(self, completed: int, total: int, filename: str):
        """Show embedding progress"""
        pass  # Would be too many updates

    def on_file_complete(self, filename: str, chunks_added: int, success: bool, error: Optional[str] = None):
        """Show file completion status"""
        if success:
            elapsed = time.time() - self.current_file_start if self.current_file_start else 0
            self.details_container.success(f"✓ {filename}: {chunks_added} chunks ({elapsed:.1f}s)")
            self.file_times.append(elapsed)  # For ETA calculation
        else:
            self.details_container.error(f"✗ {filename}: {error}")

    def on_batch_complete(self, total_files: int, successful: int, failed: int, total_chunks: int,
                         elapsed_seconds: float):
        """Show final summary"""
        self.progress_bar.progress(1.0)

        with self.details_container:
            st = self._get_streamlit()
            if st:
                st.markdown("---")
                st.subheader("Ingestion Complete")

                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Files", f"{successful}/{total_files}")
                with col2:
                    st.metric("Failed", failed)
                with col3:
                    st.metric("Total Chunks", total_chunks)
                with col4:
                    rate = total_chunks / elapsed_seconds if elapsed_seconds > 0 else 0
                    st.metric("Rate", f"{rate:.1f}/s")

    def _get_streamlit(self):
        """Safely import Streamlit"""
        try:
            import streamlit as st
            return st
        except ImportError:
            return None


class CompositeProgressCallback(ProgressCallback):
    """Composite callback that delegates to multiple callbacks"""

    def __init__(self, *callbacks):
        self.callbacks = callbacks

    def on_file_start(self, filename: str, file_number: int, total_files: int):
        for cb in self.callbacks:
            try:
                cb.on_file_start(filename, file_number, total_files)
            except Exception as e:
                logger.error(f"Error in progress callback: {e}")

    def on_chunk_extracted(self, chunk_number: int, total_chunks: int, filename: str):
        for cb in self.callbacks:
            try:
                cb.on_chunk_extracted(chunk_number, total_chunks, filename)
            except Exception as e:
                logger.error(f"Error in progress callback: {e}")

    def on_embedding_start(self, chunk_count: int, filename: str):
        for cb in self.callbacks:
            try:
                cb.on_embedding_start(chunk_count, filename)
            except Exception as e:
                logger.error(f"Error in progress callback: {e}")

    def on_embedding_progress(self, completed: int, total: int, filename: str):
        for cb in self.callbacks:
            try:
                cb.on_embedding_progress(completed, total, filename)
            except Exception as e:
                logger.error(f"Error in progress callback: {e}")

    def on_file_complete(self, filename: str, chunks_added: int, success: bool, error: Optional[str] = None):
        for cb in self.callbacks:
            try:
                cb.on_file_complete(filename, chunks_added, success, error)
            except Exception as e:
                logger.error(f"Error in progress callback: {e}")

    def on_batch_complete(self, total_files: int, successful: int, failed: int, total_chunks: int,
                         elapsed_seconds: float):
        for cb in self.callbacks:
            try:
                cb.on_batch_complete(total_files, successful, failed, total_chunks, elapsed_seconds)
            except Exception as e:
                logger.error(f"Error in progress callback: {e}")


class NullProgressCallback(ProgressCallback):
    """No-op progress callback (for testing)"""

    def on_file_start(self, filename: str, file_number: int, total_files: int):
        pass

    def on_chunk_extracted(self, chunk_number: int, total_chunks: int, filename: str):
        pass

    def on_embedding_start(self, chunk_count: int, filename: str):
        pass

    def on_embedding_progress(self, completed: int, total: int, filename: str):
        pass

    def on_file_complete(self, filename: str, chunks_added: int, success: bool, error: Optional[str] = None):
        pass

    def on_batch_complete(self, total_files: int, successful: int, failed: int, total_chunks: int,
                         elapsed_seconds: float):
        pass
