"""
PARWA Knowledge Ingest Pipeline (Day 3)

Full pipeline for knowledge base ingestion:
  - File content ingestion (PDF, DOCX, TXT, MD, CSV)
  - URL auto-ingest (scrape, chunk, embed, store)
  - Progress tracking with job management

BC-001: All operations scoped to company_id.
BC-008: Graceful degradation — never crashes.
"""

import asyncio
import hashlib
import logging
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("parwa.knowledge.ingest")


def _import_chunker():
    """Lazy import for DocumentChunker.

    Uses importlib.util to load the module directly from its file path,
    bypassing the package ``__init__.py`` which triggers heavy
    database model imports.
    """
    import importlib.util
    import os

    # If the package is already imported, use it directly
    import sys
    if "app.shared.knowledge_base.chunker" in sys.modules:
        return sys.modules["app.shared.knowledge_base.chunker"].DocumentChunker

    # Load the module directly from file to avoid __init__.py chain
    _here = os.path.dirname(os.path.abspath(__file__))
    _chunker_path = os.path.join(
        _here, "..", "..", "shared", "knowledge_base", "chunker.py"
    )
    _chunker_path = os.path.normpath(_chunker_path)

    spec = importlib.util.spec_from_file_location(
        "app.shared.knowledge_base.chunker", _chunker_path
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load DocumentChunker from {_chunker_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["app.shared.knowledge_base.chunker"] = module
    spec.loader.exec_module(module)
    return module.DocumentChunker


def _import_embedding_service():
    """Lazy import for EmbeddingService."""
    from app.services.embedding_service import EmbeddingService
    return EmbeddingService


def _import_vector_store():
    """Lazy import for get_vector_store.

    Uses importlib.util to load the module directly from its file path,
    bypassing the package ``__init__.py`` which triggers heavy
    database model imports.
    """
    import importlib.util
    import os

    # If the package is already imported, use it directly
    import sys
    if "app.shared.knowledge_base.vector_search" in sys.modules:
        return sys.modules["app.shared.knowledge_base.vector_search"].get_vector_store

    # Load the module directly from file to avoid __init__.py chain
    _here = os.path.dirname(os.path.abspath(__file__))
    _vs_path = os.path.join(
        _here, "..", "..", "shared", "knowledge_base", "vector_search.py"
    )
    _vs_path = os.path.normpath(_vs_path)

    spec = importlib.util.spec_from_file_location(
        "app.shared.knowledge_base.vector_search", _vs_path
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load vector_search from {_vs_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["app.shared.knowledge_base.vector_search"] = module
    spec.loader.exec_module(module)
    return module.get_vector_store


# ── Constants ───────────────────────────────────────────────────────────

_URL_FETCH_TIMEOUT = 30.0
_URL_MAX_CONTENT_LENGTH = 5_000_000  # 5 MB — reject oversized pages
_USER_AGENT = "PARWA-KnowledgeIngest/1.0"
_JOB_TTL_SECONDS = 86400  # 24 hours — stale jobs are pruned

# Supported file extensions for text extraction
_TEXT_EXTENSIONS = frozenset({".txt", ".md", ".csv", ".json", ".html", ".htm"})
_DOCUMENT_EXTENSIONS = frozenset({".pdf", ".docx", ".doc", ".xlsx", ".pptx"})

# Regex for stripping HTML tags
_HTML_TAG_RE = re.compile(r"<[^>]+>")
# Collapse excessive whitespace left after tag removal
_WHITESPACE_RE = re.compile(r"\s+")


# ── Data Models ─────────────────────────────────────────────────────────


class IngestStatus(str, Enum):
    """Lifecycle states for an ingest job."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class IngestSource(str, Enum):
    """Origin of the ingested content."""

    FILE = "file"
    URL = "url"


@dataclass
class IngestJob:
    """Tracks the progress of a single ingest operation.

    Attributes:
        job_id: Unique identifier for this ingest job.
        company_id: Tenant that owns this job (BC-001).
        source: Origin of the content (file or URL).
        status: Current lifecycle state.
        progress: Percentage complete (0–100).
        total_chunks: Total number of chunks to process.
        processed_chunks: Number of chunks processed so far.
        error_message: Human-readable error if the job failed.
        document_id: Optional document identifier.
        source_url: The URL being ingested (for URL jobs).
        filename: Original filename (for file jobs).
        created_at: Epoch timestamp when the job was created.
        updated_at: Epoch timestamp when the job was last updated.
    """

    job_id: str
    company_id: str
    source: IngestSource
    status: IngestStatus = IngestStatus.PENDING
    progress: float = 0.0
    total_chunks: int = 0
    processed_chunks: int = 0
    error_message: Optional[str] = None
    document_id: Optional[str] = None
    source_url: Optional[str] = None
    filename: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


# ── Service ─────────────────────────────────────────────────────────────


class KnowledgeIngestService:
    """Full-pipeline knowledge base ingestion with progress tracking.

    Orchestrates:
      1. Text extraction (file content or URL scraping)
      2. Chunking via :class:`DocumentChunker`
      3. Embedding via :class:`EmbeddingService`
      4. Storage via the active :class:`VectorStore`

    All operations are scoped to ``company_id`` (BC-001) and never
    crash the caller (BC-008).

    Usage::

        svc = KnowledgeIngestService()
        job = svc.ingest_file_content("co-123", "doc-456", b"...", "faq.md")
        job = svc.ingest_url("co-123", "https://example.com/help")
        status = svc.get_job_status(job.job_id)
    """

    def __init__(self) -> None:
        self._chunker: Any = None  # Lazy-initialized on first use
        # Thread-safe job storage: job_id -> IngestJob
        self._jobs: Dict[str, IngestJob] = {}
        self._lock = threading.Lock()

    @property
    def chunker(self) -> Any:
        """Lazily-initialized DocumentChunker instance."""
        if self._chunker is None:
            ChunkerCls = _import_chunker()
            self._chunker = ChunkerCls()
        return self._chunker

    # ── Public API: File Ingest ──────────────────────────────────────

    def ingest_file_content(
        self,
        company_id: str,
        document_id: str,
        content: bytes,
        filename: str,
    ) -> IngestJob:
        """Ingest raw file content with progress tracking.

        Accepts raw bytes and a filename.  The filename extension is
        used to detect the content type.  Text-based formats (TXT, MD,
        CSV, JSON, HTML) are decoded directly.  Binary formats (PDF,
        DOCX, etc.) require optional dependencies; if unavailable the
        job fails gracefully with a clear error message (BC-008).

        The actual processing runs asynchronously in a background task
        so the caller receives an :class:`IngestJob` immediately.

        Args:
            company_id: Tenant identifier (BC-001).
            document_id: Document UUID for storage.
            content: Raw file bytes.
            filename: Original filename (used for type detection and metadata).

        Returns:
            An :class:`IngestJob` whose ``job_id`` can be used to poll progress.
        """
        if not company_id or not company_id.strip():
            raise ValueError(
                "SECURITY (BC-001): company_id is required for ingest operations"
            )

        job = IngestJob(
            job_id=self._generate_job_id(),
            company_id=company_id,
            source=IngestSource.FILE,
            document_id=document_id,
            filename=filename,
        )
        self._register_job(job)

        logger.info(
            "ingest_file_content: job created, company_id=%s, document_id=%s, "
            "filename=%s, job_id=%s, content_size=%d",
            company_id,
            document_id,
            filename,
            job.job_id,
            len(content),
        )

        # Fire-and-forget background processing
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(
                self._process_ingest(job.job_id, content=content, filename=filename)
            )
        except RuntimeError:
            # No running event loop — run in a new thread
            thread = threading.Thread(
                target=self._run_ingest_sync,
                args=(job.job_id, content, filename),
                daemon=True,
            )
            thread.start()

        return job

    # ── Public API: URL Ingest ───────────────────────────────────────

    def ingest_url(
        self,
        company_id: str,
        url: str,
        document_id: Optional[str] = None,
    ) -> IngestJob:
        """Ingest content from a URL with progress tracking.

        Fetches the URL via ``httpx``, extracts text content by
        stripping HTML tags, then chunks, embeds, and stores the
        result.  If ``document_id`` is not provided, one is generated
        from the URL hash.

        Args:
            company_id: Tenant identifier (BC-001).
            url: The URL to scrape and ingest.
            document_id: Optional document UUID; auto-generated if omitted.

        Returns:
            An :class:`IngestJob` whose ``job_id`` can be used to poll progress.
        """
        if not company_id or not company_id.strip():
            raise ValueError(
                "SECURITY (BC-001): company_id is required for ingest operations"
            )
        if not url or not url.strip():
            raise ValueError("URL must not be empty")

        # Auto-generate document_id from URL if not provided
        if not document_id:
            document_id = self._url_to_document_id(url, company_id)

        job = IngestJob(
            job_id=self._generate_job_id(),
            company_id=company_id,
            source=IngestSource.URL,
            document_id=document_id,
            source_url=url,
        )
        self._register_job(job)

        logger.info(
            "ingest_url: job created, company_id=%s, url=%s, "
            "document_id=%s, job_id=%s",
            company_id,
            url,
            document_id,
            job.job_id,
        )

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(
                self._process_ingest(job.job_id, url=url)
            )
        except RuntimeError:
            thread = threading.Thread(
                target=self._run_ingest_sync,
                args=(job.job_id, None, None, url),
                daemon=True,
            )
            thread.start()

        return job

    # ── Public API: Job Status ───────────────────────────────────────

    def get_job_status(self, job_id: str) -> Optional[IngestJob]:
        """Retrieve the current status of an ingest job.

        Args:
            job_id: The unique identifier returned by ``ingest_file_content``
                    or ``ingest_url``.

        Returns:
            The :class:`IngestJob` if found, otherwise ``None``.
        """
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(self, company_id: str) -> List[IngestJob]:
        """List all ingest jobs for a given tenant.

        Results are ordered by creation time (newest first).

        Args:
            company_id: Tenant identifier (BC-001).

        Returns:
            List of :class:`IngestJob` instances for the company.
        """
        with self._lock:
            company_jobs = [
                job for job in self._jobs.values()
                if job.company_id == company_id
            ]
        # Sort newest first
        company_jobs.sort(key=lambda j: j.created_at, reverse=True)
        return company_jobs

    # ── Internal: Processing Pipeline ────────────────────────────────

    async def _process_ingest(
        self,
        job_id: str,
        content: Optional[bytes] = None,
        filename: Optional[str] = None,
        url: Optional[str] = None,
    ) -> None:
        """Execute the full ingest pipeline for a job.

        Steps:
          1. Extract text (from file bytes or URL)
          2. Chunk the text
          3. Generate embeddings for each chunk
          4. Store chunks + embeddings in the vector store
          5. Update job progress throughout

        BC-008: Every step is wrapped in error handling so the job
        transitions to FAILED with a descriptive message rather than
        crashing.
        """
        job = self._get_job(job_id)
        if job is None:
            logger.error("_process_ingest: job %s not found", job_id)
            return

        try:
            self._update_job(job_id, status=IngestStatus.PROCESSING, progress=0.0)

            # ── Step 1: Extract text ───────────────────────────────
            text: Optional[str] = None

            if url:
                text = await self._fetch_url_text(url)
                if not text:
                    self._update_job(
                        job_id,
                        status=IngestStatus.FAILED,
                        error_message=f"Failed to extract text from URL: {url}",
                    )
                    return
            elif content is not None:
                text = self._extract_text_from_bytes(content, filename or "")
                if not text:
                    self._update_job(
                        job_id,
                        status=IngestStatus.FAILED,
                        error_message=f"Failed to extract text from file: {filename}",
                    )
                    return
            else:
                self._update_job(
                    job_id,
                    status=IngestStatus.FAILED,
                    error_message="No content or URL provided for ingestion",
                )
                return

            self._update_job(job_id, progress=10.0)

            # ── Step 2: Chunk the text ─────────────────────────────
            chunks = self._chunk_text(text, filename or url or "unknown")
            total_chunks = len(chunks)

            if total_chunks == 0:
                self._update_job(
                    job_id,
                    status=IngestStatus.COMPLETED,
                    progress=100.0,
                    total_chunks=0,
                    processed_chunks=0,
                )
                logger.info(
                    "_process_ingest: no chunks produced, job_id=%s", job_id
                )
                return

            self._update_job(
                job_id,
                progress=20.0,
                total_chunks=total_chunks,
            )

            # ── Step 3: Generate embeddings ────────────────────────
            EmbeddingSvc = _import_embedding_service()
            embedding_svc = EmbeddingSvc(company_id=job.company_id)
            processed = 0
            stored_chunks: List[Dict[str, Any]] = []

            # Process in batches for efficiency
            batch_size = embedding_svc.max_batch_size
            for batch_start in range(0, total_chunks, batch_size):
                batch_end = min(batch_start + batch_size, total_chunks)
                batch = chunks[batch_start:batch_end]
                batch_texts = [c["content"] for c in batch]

                # Generate embeddings for the batch
                embeddings = embedding_svc.generate_embeddings_batch(batch_texts)

                for i, chunk_data in enumerate(batch):
                    embedding = embeddings[i] if i < len(embeddings) else None

                    chunk_id = (
                        f"{job.document_id}_{chunk_data['chunk_index']}"
                    )
                    stored_chunks.append({
                        "chunk_id": chunk_id,
                        "content": chunk_data["content"],
                        "chunk_index": chunk_data["chunk_index"],
                        "embedding": embedding,
                        "metadata": chunk_data.get("metadata", {}),
                    })
                    processed += 1

                # Update progress: 20–90% range for embedding
                progress = 20.0 + (processed / total_chunks) * 70.0
                self._update_job(
                    job_id,
                    progress=min(progress, 90.0),
                    processed_chunks=processed,
                )

            # ── Step 4: Store in vector store ──────────────────────
            _get_vector_store = _import_vector_store()
            vector_store = _get_vector_store()
            success = vector_store.add_document(
                document_id=job.document_id or job.job_id,
                chunks=stored_chunks,
                company_id=job.company_id,
                metadata={
                    "source": job.source.value,
                    "filename": job.filename,
                    "source_url": job.source_url,
                    "job_id": job.job_id,
                },
            )

            if not success:
                logger.warning(
                    "_process_ingest: vector store add_document returned False, "
                    "job_id=%s, company_id=%s",
                    job_id,
                    job.company_id,
                )

            self._update_job(
                job_id,
                status=IngestStatus.COMPLETED,
                progress=100.0,
                processed_chunks=processed,
            )

            logger.info(
                "_process_ingest: completed, job_id=%s, company_id=%s, "
                "total_chunks=%d, document_id=%s",
                job_id,
                job.company_id,
                total_chunks,
                job.document_id,
            )

        except Exception as exc:
            # BC-008: Never crash — mark the job as failed
            error_msg = str(exc)[:500]
            self._update_job(
                job_id,
                status=IngestStatus.FAILED,
                error_message=error_msg,
            )
            logger.error(
                "_process_ingest: FAILED, job_id=%s, company_id=%s, error=%s",
                job_id,
                job.company_id,
                error_msg,
                exc_info=True,
            )

    # ── Internal: Text Extraction ────────────────────────────────────

    async def _fetch_url_text(self, url: str) -> Optional[str]:
        """Fetch a URL and extract its text content.

        Uses ``httpx`` for the HTTP request, then strips HTML tags
        with a simple regex-based approach (BC-008: never crashes).

        Args:
            url: The URL to fetch.

        Returns:
            Extracted text content, or ``None`` on failure.
        """
        try:
            async with httpx.AsyncClient(
                timeout=_URL_FETCH_TIMEOUT,
                follow_redirects=True,
                headers={"User-Agent": _USER_AGENT},
            ) as client:
                response = await client.get(url)

                if response.status_code != 200:
                    logger.warning(
                        "_fetch_url_text: HTTP %d for %s",
                        response.status_code,
                        url,
                    )
                    return None

                # Reject oversized responses
                if len(response.content) > _URL_MAX_CONTENT_LENGTH:
                    logger.warning(
                        "_fetch_url_text: content too large (%d bytes) for %s",
                        len(response.content),
                        url,
                    )
                    return None

                # Decode response body
                text = response.text

                # Strip HTML tags if the content appears to be HTML
                if self._looks_like_html(text):
                    text = self._strip_html(text)

                return text

        except httpx.TimeoutException:
            logger.warning(
                "_fetch_url_text: request timed out for %s", url
            )
            return None
        except httpx.HTTPError as exc:
            logger.warning(
                "_fetch_url_text: HTTP error for %s: %s", url, str(exc)
            )
            return None
        except Exception as exc:
            logger.error(
                "_fetch_url_text: unexpected error for %s: %s",
                url,
                str(exc),
                exc_info=True,
            )
            return None

    def _extract_text_from_bytes(
        self, content: bytes, filename: str
    ) -> Optional[str]:
        """Extract text content from raw file bytes.

        Supports:
          - Text-based formats (TXT, MD, CSV, JSON, HTML) — decoded as UTF-8
          - PDF — requires ``PyPDF2`` or ``pypdf`` (graceful fallback)
          - DOCX — requires ``python-docx`` (graceful fallback)

        BC-008: Returns ``None`` on any failure rather than raising.

        Args:
            content: Raw file bytes.
            filename: Filename (used for type detection).

        Returns:
            Extracted text, or ``None`` if extraction fails.
        """
        ext = self._get_extension(filename).lower()

        try:
            # ── Text-based formats ─────────────────────────────────
            if ext in _TEXT_EXTENSIONS:
                text = content.decode("utf-8", errors="replace")
                # Strip HTML if applicable
                if ext in {".html", ".htm"} and self._looks_like_html(text):
                    text = self._strip_html(text)
                return text

            # ── PDF ────────────────────────────────────────────────
            if ext == ".pdf":
                return self._extract_pdf_text(content)

            # ── DOCX ───────────────────────────────────────────────
            if ext in {".docx", ".doc"}:
                return self._extract_docx_text(content)

            # ── Unknown format — attempt UTF-8 decode ──────────────
            logger.warning(
                "_extract_text_from_bytes: unknown extension '%s' for '%s', "
                "attempting UTF-8 decode",
                ext,
                filename,
            )
            return content.decode("utf-8", errors="replace")

        except Exception as exc:
            logger.error(
                "_extract_text_from_bytes: failed for '%s': %s",
                filename,
                str(exc),
            )
            return None

    # ── Internal: Document Parsers ───────────────────────────────────

    @staticmethod
    def _extract_pdf_text(content: bytes) -> Optional[str]:
        """Extract text from PDF bytes.

        Tries ``pypdf`` first, then ``PyPDF2`` as a fallback.
        Returns ``None`` if neither library is available (BC-008).
        """
        import io

        try:
            try:
                from pypdf import PdfReader
            except ImportError:
                from PyPDF2 import PdfReader  # type: ignore[no-redef]

            reader = PdfReader(io.BytesIO(content))
            pages: List[str] = []
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    pages.append(page_text)
            return "\n\n".join(pages) if pages else None

        except ImportError:
            logger.warning(
                "_extract_pdf_text: pypdf/PyPDF2 not installed, "
                "cannot extract PDF text"
            )
            return None
        except Exception as exc:
            logger.warning("_extract_pdf_text: extraction failed: %s", str(exc))
            return None

    @staticmethod
    def _extract_docx_text(content: bytes) -> Optional[str]:
        """Extract text from DOCX bytes.

        Requires ``python-docx``.  Returns ``None`` if unavailable (BC-008).
        """
        import io

        try:
            from docx import Document  # type: ignore[import-untyped]

            doc = Document(io.BytesIO(content))
            paragraphs = [p.text for p in doc.paragraphs if p.text]
            return "\n\n".join(paragraphs) if paragraphs else None

        except ImportError:
            logger.warning(
                "_extract_docx_text: python-docx not installed, "
                "cannot extract DOCX text"
            )
            return None
        except Exception as exc:
            logger.warning("_extract_docx_text: extraction failed: %s", str(exc))
            return None

    # ── Internal: Chunking Helper ────────────────────────────────────

    def _chunk_text(
        self, text: str, source_name: str
    ) -> List[Dict[str, Any]]:
        """Chunk text using the DocumentChunker.

        Chooses ``chunk_markdown`` for markdown content, otherwise
        ``chunk_text`` for plain text.

        Args:
            text: The full text content to chunk.
            source_name: Source identifier for metadata.

        Returns:
            List of chunk dicts from :class:`DocumentChunker`.
        """
        # Use markdown-aware chunking for .md files
        if source_name.lower().endswith(".md"):
            return self.chunker.chunk_markdown(text)
        return self.chunker.chunk_text(text, filename=source_name)

    # ── Internal: HTML Utilities ─────────────────────────────────────

    @staticmethod
    def _looks_like_html(text: str) -> bool:
        """Heuristic check: does the text contain HTML tags?"""
        return "<" in text and ">" in text and ("<html" in text.lower() or "<body" in text.lower() or "<p" in text.lower() or "<div" in text.lower())

    @staticmethod
    def _strip_html(html: str) -> str:
        """Strip HTML tags and normalize whitespace.

        Simple regex-based approach.  For complex HTML, a proper
        parser (e.g. BeautifulSoup) would be better, but this keeps
        the dependency footprint minimal.

        Args:
            html: Raw HTML string.

        Returns:
            Cleaned plain-text string.
        """
        # Remove <script> and <style> blocks entirely
        cleaned = re.sub(r"<script[^>]*>[\s\S]*?</script>", "", html, flags=re.IGNORECASE)
        cleaned = re.sub(r"<style[^>]*>[\s\S]*?</style>", "", cleaned, flags=re.IGNORECASE)
        # Remove all remaining HTML tags
        cleaned = _HTML_TAG_RE.sub(" ", cleaned)
        # Decode common HTML entities
        cleaned = cleaned.replace("&amp;", "&")
        cleaned = cleaned.replace("&lt;", "<")
        cleaned = cleaned.replace("&gt;", ">")
        cleaned = cleaned.replace("&quot;", '"')
        cleaned = cleaned.replace("&#39;", "'")
        cleaned = cleaned.replace("&nbsp;", " ")
        # Collapse whitespace
        cleaned = _WHITESPACE_RE.sub(" ", cleaned)
        return cleaned.strip()

    # ── Internal: Job Management ─────────────────────────────────────

    def _register_job(self, job: IngestJob) -> None:
        """Add a new job to the tracker (thread-safe)."""
        with self._lock:
            self._jobs[job.job_id] = job
        # Prune stale jobs opportunistically
        self._prune_stale_jobs()

    def _get_job(self, job_id: str) -> Optional[IngestJob]:
        """Retrieve a job by ID (thread-safe)."""
        with self._lock:
            return self._jobs.get(job_id)

    def _update_job(self, job_id: str, **kwargs: Any) -> None:
        """Update mutable fields on a job (thread-safe).

        Args:
            job_id: The job to update.
            **kwargs: Fields to set on the IngestJob.
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                logger.warning("_update_job: job %s not found", job_id)
                return
            for key, value in kwargs.items():
                if hasattr(job, key):
                    setattr(job, key, value)
            job.updated_at = time.time()

    def _prune_stale_jobs(self) -> None:
        """Remove jobs older than the TTL to prevent memory leaks."""
        cutoff = time.time() - _JOB_TTL_SECONDS
        with self._lock:
            stale_ids = [
                jid for jid, job in self._jobs.items()
                if job.updated_at < cutoff
            ]
            for jid in stale_ids:
                del self._jobs[jid]
        if stale_ids:
            logger.debug(
                "_prune_stale_jobs: removed %d stale jobs", len(stale_ids)
            )

    # ── Internal: Helpers ────────────────────────────────────────────

    @staticmethod
    def _generate_job_id() -> str:
        """Generate a unique job identifier."""
        return f"ingest_{uuid.uuid4().hex[:16]}"

    @staticmethod
    def _url_to_document_id(url: str, company_id: str) -> str:
        """Derive a deterministic document ID from a URL and company.

        Uses SHA-256 hashing to produce a stable, unique ID for the
        same URL+company combination.
        """
        raw = f"{company_id}:{url}".encode("utf-8")
        digest = hashlib.sha256(raw).hexdigest()[:32]
        return f"doc_url_{digest}"

    @staticmethod
    def _get_extension(filename: str) -> str:
        """Extract the file extension from a filename.

        Returns a lowercase extension including the dot (e.g. ``".pdf"``).
        Returns ``""`` if no extension is found.
        """
        if not filename:
            return ""
        dot_pos = filename.rfind(".")
        if dot_pos == -1 or dot_pos == len(filename) - 1:
            return ""
        return filename[dot_pos:]

    # ── Internal: Sync Runner ────────────────────────────────────────

    def _run_ingest_sync(
        self,
        job_id: str,
        content: Optional[bytes] = None,
        filename: Optional[str] = None,
        url: Optional[str] = None,
    ) -> None:
        """Run the async ingest pipeline in a synchronous context.

        Creates a new event loop for the thread if one doesn't exist.
        Used when there is no running event loop available (e.g. when
        the caller is not inside ``asyncio``).
        """
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                self._process_ingest(
                    job_id, content=content, filename=filename, url=url
                )
            )
        except Exception as exc:
            # Last-resort BC-008 handler
            logger.error(
                "_run_ingest_sync: unhandled error, job_id=%s: %s",
                job_id,
                str(exc),
                exc_info=True,
            )
            self._update_job(
                job_id,
                status=IngestStatus.FAILED,
                error_message=f"Unhandled error: {str(exc)[:500]}",
            )
        finally:
            try:
                loop.close()
            except Exception:
                pass
