"""
Document Upload Manager
Handles batch uploads, validation, duplicate detection, and folder organization.
"""

import logging
import io
import re
from typing import Optional
from pathlib import Path
import time

logger = logging.getLogger(__name__)

class UploadManager:
    """Manages document uploads with validation and deduplication."""

    # File size limits (in MB)
    MAX_FILE_SIZE_MB = {
        'pdf': 100,
        'txt': 50,
        'md': 50,
        'docx': 50,
    }

    # Allowed file types
    ALLOWED_TYPES = ['pdf', 'txt', 'md', 'docx']

    def __init__(self, vector_store=None):
        """
        Initialize UploadManager.

        Args:
            vector_store: Optional ChromaVectorStore instance for duplicate detection
        """
        self.vector_store = vector_store
        self.upload_history: list[Dict] = []

    def validate_file(self, file_obj) -> tuple[bool, Optional[str]]:
        """
        Validate a file for upload.

        Args:
            file_obj: Streamlit UploadedFile object or similar

        Returns:
            Tuple of (is_valid, error_message)
            - is_valid: True if file passes validation
            - error_message: Error description if validation fails, None otherwise
        """
        try:
            # Check if file exists and has content
            if not file_obj or not hasattr(file_obj, 'name'):
                return False, "Invalid file object"

            filename = file_obj.name
            file_size_bytes = len(file_obj.getvalue()) if hasattr(file_obj, 'getvalue') else file_obj.size

            # Extract file extension
            extension = Path(filename).suffix.lower().lstrip('.')

            # Check file type
            if extension not in self.ALLOWED_TYPES:
                return False, f"Unsupported file type: .{extension}. Allowed: {', '.join(self.ALLOWED_TYPES)}"

            # Check file size
            max_size_mb = self.MAX_FILE_SIZE_MB.get(extension, 50)
            max_size_bytes = max_size_mb * 1024 * 1024
            if file_size_bytes > max_size_bytes:
                return False, f"File too large: {file_size_bytes / (1024*1024):.1f}MB > {max_size_mb}MB limit"

            # Check minimum file size (not empty)
            if file_size_bytes < 100:
                return False, "File is too small (empty or invalid)"

            # PDF-specific validation
            if extension == 'pdf':
                try:
                    import pypdf
                    pdf_bytes = file_obj.getvalue() if hasattr(file_obj, 'getvalue') else file_obj.read()
                    pdf_reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
                    if len(pdf_reader.pages) == 0:
                        return False, "PDF has no pages"
                except Exception as e:
                    return False, f"Invalid PDF: {str(e)[:50]}"

            return True, None

        except Exception as e:
            logger.warning(f"File validation error: {e}")
            return False, f"Validation failed: {str(e)[:50]}"

    def check_duplicate(self, filename: str, vector_store=None) -> bool:
        """
        Check if a document with this filename is already indexed.

        Args:
            filename: Document filename to check
            vector_store: Optional ChromaVectorStore instance

        Returns:
            True if document already exists, False otherwise
        """
        try:
            store = vector_store or self.vector_store
            if not store:
                return False

            # Query vector store for this document
            indexed_files = store.list_indexed_files() if hasattr(store, 'list_indexed_files') else []

            # Normalize filenames for comparison
            filename_normalized = filename.lower()
            for indexed_file in indexed_files:
                if indexed_file.lower() == filename_normalized:
                    logger.info(f"Duplicate detected: {filename}")
                    return True

            return False

        except Exception as e:
            logger.warning(f"Duplicate detection failed: {e}")
            # If we can't check, assume not duplicate (safer than blocking)
            return False

    def create_folder_path(self, folder: str, filename: str) -> str:
        """
        Create organized folder path for document metadata.

        Args:
            folder: Folder name (e.g., "Research Papers")
            filename: Original filename

        Returns:
            Formatted path (e.g., "Research Papers/paper.pdf")
        """
        if not folder or not folder.strip():
            return filename

        # Normalize folder name: lowercase, remove special chars
        folder_normalized = re.sub(r'[^a-z0-9\s\-_]', '', folder.lower()).strip()
        folder_normalized = re.sub(r'\s+', '-', folder_normalized)

        return f"{folder_normalized}/{filename}"

    def process_batch_upload(
        self,
        files: List,
        vector_store,
        folder: Optional[str] = None,
        skip_duplicates: bool = True,
        callback=None
    ) -> Dict:
        """
        Process batch upload of multiple files.

        Args:
            files: List of Streamlit UploadedFile objects
            vector_store: ChromaVectorStore instance
            folder: Optional folder name for organization
            skip_duplicates: Whether to skip duplicate documents
            callback: Optional ProgressCallback for progress updates

        Returns:
            Dictionary with:
            - 'success': List of successfully uploaded filenames
            - 'duplicates': List of skipped duplicate filenames
            - 'failed': Dict of {filename: error_message} for failed uploads
        """
        results = {
            'success': [],
            'duplicates': [],
            'failed': {},
        }

        if not files:
            return results

        total_files = len(files)
        logger.info(f"Processing batch upload: {total_files} files")

        for file_index, file_obj in enumerate(files, 1):
            try:
                filename = file_obj.name

                # Progress update
                if callback and hasattr(callback, 'on_file_start'):
                    callback.on_file_start(filename, file_index, total_files)

                # Validate file
                is_valid, error = self.validate_file(file_obj)
                if not is_valid:
                    results['failed'][filename] = error or "Validation failed"
                    logger.warning(f"Validation failed for {filename}: {error}")
                    if callback and hasattr(callback, 'on_file_complete'):
                        callback.on_file_complete(
                            filename=filename,
                            chunks_added=0,
                            success=False,
                            error=error
                        )
                    continue

                # Check for duplicates
                if skip_duplicates and self.check_duplicate(filename, vector_store):
                    results['duplicates'].append(filename)
                    logger.info(f"Skipping duplicate: {filename}")
                    if callback and hasattr(callback, 'on_file_complete'):
                        callback.on_file_complete(
                            filename=filename,
                            chunks_added=0,
                            success=False,
                            error="Already indexed"
                        )
                    continue

                # Record successful upload
                results['success'].append(filename)
                logger.info(f"✓ Marked for ingestion: {filename}")

                if callback and hasattr(callback, 'on_file_complete'):
                    callback.on_file_complete(
                        filename=filename,
                        chunks_added=0,
                        success=True
                    )

                # Track in history
                self.upload_history.append({
                    'filename': filename,
                    'timestamp': time.time(),
                    'folder': folder,
                    'size_bytes': len(file_obj.getvalue()) if hasattr(file_obj, 'getvalue') else 0,
                    'success': True,
                })

            except Exception as e:
                error_msg = f"Processing error: {str(e)[:50]}"
                results['failed'][file_obj.name if hasattr(file_obj, 'name') else 'unknown'] = error_msg
                logger.error(f"Error processing {file_obj.name if hasattr(file_obj, 'name') else 'file'}: {e}")

        logger.info(
            f"Batch upload completed: {len(results['success'])} success, "
            f"{len(results['duplicates'])} duplicates, {len(results['failed'])} failed"
        )

        return results

    def get_upload_history(self, limit: int = 10) -> list[Dict]:
        """
        Get recent upload history.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of upload history entries (most recent first)
        """
        # Sort by timestamp descending
        sorted_history = sorted(
            self.upload_history,
            key=lambda x: x.get('timestamp', 0),
            reverse=True
        )
        return sorted_history[:limit]

    def clear_history(self):
        """Clear upload history."""
        self.upload_history = []

    def get_storage_stats(self) -> Dict:
        """
        Get upload storage statistics.

        Returns:
            Dictionary with:
            - 'total_files': Total files uploaded
            - 'total_size_mb': Total size in MB
            - 'success_count': Number of successful uploads
            - 'failure_count': Number of failed uploads
        """
        total_size = sum(entry.get('size_bytes', 0) for entry in self.upload_history)
        success_count = sum(1 for entry in self.upload_history if entry.get('success', False))

        return {
            'total_files': len(self.upload_history),
            'total_size_mb': total_size / (1024 * 1024),
            'success_count': success_count,
            'failure_count': len(self.upload_history) - success_count,
        }
