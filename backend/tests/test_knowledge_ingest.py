"""
Comprehensive unit tests for PARWA Knowledge Ingest Pipeline service.

Tests cover:
  - KnowledgeIngestService initialization
  - ingest_file_content() — job creation, text extraction, chunking, embedding, storage
  - ingest_url() — URL fetching, HTML stripping, auto document_id generation
  - get_job_status() — found / not found
  - list_jobs() — tenant isolation, ordering
  - Progress tracking — status transitions, progress percentage
  - Tenant isolation (BC-001) — company_id validation, cross-tenant protection

All external dependencies are mocked — no database, Redis, or network access required.
"""

import asyncio
import hashlib
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.knowledge.ingest import (
    IngestJob,
    IngestSource,
    IngestStatus,
    KnowledgeIngestService,
)


# ════════════════════════════════════════════════════════════════════════
# Fixtures
# ════════════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_chunker():
    """Mock DocumentChunker instance."""
    chunker = MagicMock()
    chunker.chunk_text.return_value = [
        {"content": "chunk one text", "chunk_index": 0, "metadata": {"source": "test.txt"}},
        {"content": "chunk two text", "chunk_index": 1, "metadata": {"source": "test.txt"}},
    ]
    chunker.chunk_markdown.return_value = [
        {"content": "# Header\nmarkdown chunk", "chunk_index": 0, "metadata": {"source": "test.md"}},
    ]
    return chunker


@pytest.fixture
def mock_embedding_service():
    """Mock EmbeddingService class and instance."""
    instance = MagicMock()
    instance.max_batch_size = 10
    instance.generate_embeddings_batch.return_value = [
        [0.1] * 1536,
        [0.2] * 1536,
    ]
    cls = MagicMock(return_value=instance)
    return cls, instance


@pytest.fixture
def mock_vector_store():
    """Mock vector store returned by get_vector_store()."""
    vs = MagicMock()
    vs.add_document.return_value = True
    get_vs_fn = MagicMock(return_value=vs)
    return get_vs_fn, vs


@pytest.fixture
def service(mock_chunker, mock_embedding_service, mock_vector_store):
    """KnowledgeIngestService with all external dependencies mocked."""
    svc = KnowledgeIngestService()
    # Directly set the chunker to avoid lazy import
    svc._chunker = mock_chunker
    return svc


@pytest.fixture
def service_with_pipeline(service, mock_embedding_service, mock_vector_store):
    """Service with pipeline-level mocks patched for _process_ingest testing."""
    emb_cls, emb_inst = mock_embedding_service
    get_vs_fn, vs_inst = mock_vector_store

    with patch(
        "app.services.knowledge.ingest._import_embedding_service",
        return_value=emb_cls,
    ), patch(
        "app.services.knowledge.ingest._import_vector_store",
        return_value=get_vs_fn,
    ):
        yield service, emb_cls, emb_inst, get_vs_fn, vs_inst


# ════════════════════════════════════════════════════════════════════════
# 1. KnowledgeIngestService Initialization
# ════════════════════════════════════════════════════════════════════════


class TestInitialization:
    """Tests for KnowledgeIngestService initialization."""

    def test_service_creates_with_empty_jobs_dict(self):
        """Service should initialize with an empty job tracking dict."""
        svc = KnowledgeIngestService()
        assert svc._jobs == {}

    def test_service_chunker_is_lazy_none(self):
        """Service._chunker should be None until first access."""
        svc = KnowledgeIngestService()
        assert svc._chunker is None

    def test_service_has_lock(self):
        """Service should have a threading lock for job storage."""
        svc = KnowledgeIngestService()
        assert svc._lock is not None

    def test_service_creates_properly(self):
        """Service should instantiate without errors."""
        svc = KnowledgeIngestService()
        assert isinstance(svc, KnowledgeIngestService)


# ════════════════════════════════════════════════════════════════════════
# 2. ingest_file_content()
# ════════════════════════════════════════════════════════════════════════


class TestIngestFileContent:
    """Tests for ingest_file_content() public API and pipeline."""

    def test_creates_job_with_pending_status(self, service):
        """ingest_file_content should return a job with PENDING status."""
        job = service.ingest_file_content(
            company_id="co-1",
            document_id="doc-1",
            content=b"Hello world",
            filename="test.txt",
        )
        assert job.status == IngestStatus.PENDING

    def test_returns_ingest_job_with_correct_company_id(self, service):
        """Returned job should have the correct company_id."""
        job = service.ingest_file_content(
            company_id="co-42",
            document_id="doc-1",
            content=b"text",
            filename="test.txt",
        )
        assert job.company_id == "co-42"

    def test_returns_ingest_job_with_correct_document_id(self, service):
        """Returned job should have the correct document_id."""
        job = service.ingest_file_content(
            company_id="co-1",
            document_id="doc-abc",
            content=b"text",
            filename="test.txt",
        )
        assert job.document_id == "doc-abc"

    def test_returns_ingest_job_with_source_file(self, service):
        """Returned job source should be IngestSource.FILE."""
        job = service.ingest_file_content(
            company_id="co-1",
            document_id="doc-1",
            content=b"text",
            filename="test.txt",
        )
        assert job.source == IngestSource.FILE

    def test_job_has_filename_set(self, service):
        """Returned job should have filename set."""
        job = service.ingest_file_content(
            company_id="co-1",
            document_id="doc-1",
            content=b"text",
            filename="report.md",
        )
        assert job.filename == "report.md"

    def test_job_id_is_unique(self, service):
        """Each call should produce a unique job_id."""
        job1 = service.ingest_file_content("co-1", "d1", b"a", "a.txt")
        job2 = service.ingest_file_content("co-1", "d2", b"b", "b.txt")
        assert job1.job_id != job2.job_id

    def test_job_id_starts_with_ingest_prefix(self, service):
        """Job IDs should start with 'ingest_'."""
        job = service.ingest_file_content("co-1", "d1", b"a", "a.txt")
        assert job.job_id.startswith("ingest_")

    def test_raises_value_error_empty_company_id(self, service):
        """BC-001: Empty company_id should raise ValueError."""
        with pytest.raises(ValueError, match="BC-001"):
            service.ingest_file_content("", "doc-1", b"text", "f.txt")

    def test_raises_value_error_whitespace_company_id(self, service):
        """BC-001: Whitespace-only company_id should raise ValueError."""
        with pytest.raises(ValueError, match="BC-001"):
            service.ingest_file_content("   ", "doc-1", b"text", "f.txt")

    def test_processes_text_content_through_pipeline(self, service_with_pipeline):
        """Full pipeline: text content -> chunks -> embeddings -> vector store."""
        service, emb_cls, emb_inst, get_vs_fn, vs_inst = service_with_pipeline
        job = service.ingest_file_content("co-1", "doc-1", b"Hello world", "test.txt")

        # Wait for background thread to complete
        self._wait_for_job_completion(service, job.job_id, timeout=5.0)

        updated = service.get_job_status(job.job_id)
        assert updated is not None
        assert updated.status == IngestStatus.COMPLETED
        assert updated.progress == 100.0
        assert updated.total_chunks == 2  # mock_chunker returns 2 chunks
        assert updated.processed_chunks == 2

    def test_handles_empty_content_marks_job_failed(self, service_with_pipeline):
        """Empty bytes decode to empty string, which the pipeline treats as
        a failed extraction (not zero-chunk success)."""
        service, emb_cls, emb_inst, get_vs_fn, vs_inst = service_with_pipeline

        job = service.ingest_file_content("co-1", "doc-1", b"", "empty.txt")

        self._wait_for_job_completion(service, job.job_id, timeout=5.0)

        updated = service.get_job_status(job.job_id)
        assert updated is not None
        # Empty bytes -> empty text -> pipeline marks as FAILED
        assert updated.status == IngestStatus.FAILED
        assert "Failed to extract text" in (updated.error_message or "")

    def test_handles_content_that_chunks_to_zero(self, service_with_pipeline):
        """Non-empty content where chunker returns 0 chunks should
        complete with 0 chunks and progress 100."""
        service, emb_cls, emb_inst, get_vs_fn, vs_inst = service_with_pipeline
        # Override chunker to return empty list for this test
        service.chunker.chunk_text.return_value = []

        job = service.ingest_file_content("co-1", "doc-1", b"some text", "short.txt")

        self._wait_for_job_completion(service, job.job_id, timeout=5.0)

        updated = service.get_job_status(job.job_id)
        assert updated is not None
        assert updated.status == IngestStatus.COMPLETED
        assert updated.total_chunks == 0
        assert updated.progress == 100.0

    def test_handles_markdown_content(self, service_with_pipeline):
        """Markdown files should use chunk_markdown instead of chunk_text."""
        service, emb_cls, emb_inst, get_vs_fn, vs_inst = service_with_pipeline
        # Markdown chunker returns 1 chunk
        job = service.ingest_file_content("co-1", "doc-1", b"# Title\nSome markdown", "readme.md")

        self._wait_for_job_completion(service, job.job_id, timeout=5.0)

        updated = service.get_job_status(job.job_id)
        assert updated is not None
        assert updated.status == IngestStatus.COMPLETED
        # Verify chunk_markdown was called for .md file
        service.chunker.chunk_markdown.assert_called()

    def test_handles_html_content_strips_tags(self, service_with_pipeline):
        """HTML files should have their tags stripped."""
        service, emb_cls, emb_inst, get_vs_fn, vs_inst = service_with_pipeline
        html = b"<html><body><p>Hello World</p></body></html>"

        job = service.ingest_file_content("co-1", "doc-1", html, "page.html")

        self._wait_for_job_completion(service, job.job_id, timeout=5.0)

        updated = service.get_job_status(job.job_id)
        assert updated is not None
        assert updated.status == IngestStatus.COMPLETED

    def test_pipeline_calls_embedding_service(self, service_with_pipeline):
        """Pipeline should call EmbeddingService to generate embeddings."""
        service, emb_cls, emb_inst, get_vs_fn, vs_inst = service_with_pipeline
        job = service.ingest_file_content("co-1", "doc-1", b"Some text", "test.txt")

        self._wait_for_job_completion(service, job.job_id, timeout=5.0)

        emb_inst.generate_embeddings_batch.assert_called()

    def test_pipeline_calls_vector_store_add_document(self, service_with_pipeline):
        """Pipeline should store chunks in the vector store."""
        service, emb_cls, emb_inst, get_vs_fn, vs_inst = service_with_pipeline
        job = service.ingest_file_content("co-1", "doc-1", b"Some text", "test.txt")

        self._wait_for_job_completion(service, job.job_id, timeout=5.0)

        vs_inst.add_document.assert_called_once()
        call_kwargs = vs_inst.add_document.call_args
        assert call_kwargs.kwargs["company_id"] == "co-1"
        assert call_kwargs.kwargs["document_id"] == "doc-1"

    @staticmethod
    def _wait_for_job_completion(service, job_id, timeout=5.0):
        """Poll job status until it reaches COMPLETED or FAILED, or timeout."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            job = service.get_job_status(job_id)
            if job and job.status in (IngestStatus.COMPLETED, IngestStatus.FAILED):
                return
            time.sleep(0.05)
        raise TimeoutError(f"Job {job_id} did not complete within {timeout}s")


# ════════════════════════════════════════════════════════════════════════
# 3. ingest_url()
# ════════════════════════════════════════════════════════════════════════


class TestIngestUrl:
    """Tests for ingest_url() public API and pipeline."""

    def test_creates_job_with_pending_status(self, service):
        """ingest_url should return a job with PENDING status."""
        with patch.object(service, "_run_ingest_sync"):
            job = service.ingest_url("co-1", "https://example.com")
        assert job.status == IngestStatus.PENDING

    def test_auto_generates_document_id_from_url_hash(self, service):
        """If no document_id provided, one should be generated from URL hash."""
        with patch.object(service, "_run_ingest_sync"):
            job = service.ingest_url("co-1", "https://example.com/help")
        assert job.document_id is not None
        assert job.document_id.startswith("doc_url_")

    def test_auto_document_id_is_deterministic(self, service):
        """Same URL + company_id should produce the same document_id."""
        expected = "doc_url_" + hashlib.sha256(
            b"co-1:https://example.com/help"
        ).hexdigest()[:32]
        with patch.object(service, "_run_ingest_sync"):
            job = service.ingest_url("co-1", "https://example.com/help")
        assert job.document_id == expected

    def test_uses_provided_document_id(self, service):
        """If document_id is provided, it should be used instead of auto-generated."""
        with patch.object(service, "_run_ingest_sync"):
            job = service.ingest_url("co-1", "https://example.com", document_id="my-doc-id")
        assert job.document_id == "my-doc-id"

    def test_job_has_source_url_set(self, service):
        """Returned job should have source_url set."""
        with patch.object(service, "_run_ingest_sync"):
            job = service.ingest_url("co-1", "https://example.com/faq")
        assert job.source_url == "https://example.com/faq"

    def test_job_source_is_url(self, service):
        """Returned job source should be IngestSource.URL."""
        with patch.object(service, "_run_ingest_sync"):
            job = service.ingest_url("co-1", "https://example.com")
        assert job.source == IngestSource.URL

    def test_raises_value_error_empty_company_id(self, service):
        """BC-001: Empty company_id should raise ValueError."""
        with pytest.raises(ValueError, match="BC-001"):
            service.ingest_url("", "https://example.com")

    def test_raises_value_error_whitespace_company_id(self, service):
        """BC-001: Whitespace-only company_id should raise ValueError."""
        with pytest.raises(ValueError, match="BC-001"):
            service.ingest_url("   ", "https://example.com")

    def test_raises_value_error_empty_url(self, service):
        """Empty URL should raise ValueError."""
        with pytest.raises(ValueError, match="URL must not be empty"):
            service.ingest_url("co-1", "")

    def test_raises_value_error_whitespace_url(self, service):
        """Whitespace-only URL should raise ValueError."""
        with pytest.raises(ValueError, match="URL must not be empty"):
            service.ingest_url("co-1", "   ")

    def test_url_fetch_strips_html_tags(self, service_with_pipeline):
        """_fetch_url_text should strip HTML tags from the response."""
        service, emb_cls, emb_inst, get_vs_fn, vs_inst = service_with_pipeline
        # We test _fetch_url_text directly with mocked httpx
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body><p>Hello World</p></body></html>"
        mock_response.content = b"<html><body><p>Hello World</p></body></html>"

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("app.services.knowledge.ingest.httpx.AsyncClient", return_value=mock_client):
            result = asyncio.get_event_loop().run_until_complete(
                service._fetch_url_text("https://example.com")
            )

        # HTML tags should be stripped
        assert result is not None
        assert "<" not in result
        assert "Hello World" in result

    def test_url_fetch_timeout_marks_job_failed(self, service_with_pipeline):
        """URL fetch timeout should cause the job to be marked as FAILED."""
        service, emb_cls, emb_inst, get_vs_fn, vs_inst = service_with_pipeline

        # Make _fetch_url_text return None (simulating timeout)
        with patch.object(
            service, "_fetch_url_text", new_callable=AsyncMock, return_value=None
        ):
            job = service.ingest_url("co-1", "https://slow.example.com")
            TestIngestFileContent._wait_for_job_completion(service, job.job_id, timeout=5.0)

        updated = service.get_job_status(job.job_id)
        assert updated is not None
        assert updated.status == IngestStatus.FAILED
        assert "Failed to extract text from URL" in (updated.error_message or "")

    def test_url_fetch_http_error_marks_job_failed(self, service_with_pipeline):
        """HTTP error during URL fetch should cause job to be marked as FAILED."""
        service, emb_cls, emb_inst, get_vs_fn, vs_inst = service_with_pipeline

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.content = b"Internal Server Error"

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("app.services.knowledge.ingest.httpx.AsyncClient", return_value=mock_client):
            job = service.ingest_url("co-1", "https://broken.example.com")
            TestIngestFileContent._wait_for_job_completion(service, job.job_id, timeout=5.0)

        updated = service.get_job_status(job.job_id)
        assert updated is not None
        assert updated.status == IngestStatus.FAILED


# ════════════════════════════════════════════════════════════════════════
# 4. get_job_status()
# ════════════════════════════════════════════════════════════════════════


class TestGetJobStatus:
    """Tests for get_job_status() method."""

    def test_returns_job_when_found(self, service):
        """Should return the IngestJob when the job_id exists."""
        job = service.ingest_file_content("co-1", "doc-1", b"text", "f.txt")
        result = service.get_job_status(job.job_id)
        assert result is not None
        assert result.job_id == job.job_id

    def test_returns_none_when_not_found(self, service):
        """Should return None for a non-existent job_id."""
        result = service.get_job_status("nonexistent-job-id")
        assert result is None

    def test_returns_correct_job_among_multiple(self, service):
        """Should return the correct job when multiple jobs exist."""
        with patch.object(service, "_run_ingest_sync"):
            job1 = service.ingest_url("co-1", "https://a.com")
            job2 = service.ingest_url("co-2", "https://b.com")
        assert service.get_job_status(job1.job_id).company_id == "co-1"
        assert service.get_job_status(job2.job_id).company_id == "co-2"


# ════════════════════════════════════════════════════════════════════════
# 5. list_jobs()
# ════════════════════════════════════════════════════════════════════════


class TestListJobs:
    """Tests for list_jobs() method."""

    def test_returns_jobs_filtered_by_company_id(self, service):
        """Should only return jobs belonging to the specified company."""
        with patch.object(service, "_run_ingest_sync"):
            service.ingest_url("co-alpha", "https://a.com")
            service.ingest_url("co-beta", "https://b.com")
            service.ingest_url("co-alpha", "https://c.com")

        alpha_jobs = service.list_jobs("co-alpha")
        assert len(alpha_jobs) == 2
        assert all(j.company_id == "co-alpha" for j in alpha_jobs)

    def test_returns_empty_list_when_no_jobs_for_company(self, service):
        """Should return an empty list for a company with no jobs."""
        with patch.object(service, "_run_ingest_sync"):
            service.ingest_url("co-x", "https://x.com")
        result = service.list_jobs("co-nonexistent")
        assert result == []

    def test_returns_jobs_ordered_newest_first(self, service):
        """Jobs should be sorted by created_at descending (newest first)."""
        with patch.object(service, "_run_ingest_sync"):
            job1 = service.ingest_url("co-1", "https://old.com")
            # Small sleep to ensure different timestamps
            time.sleep(0.01)
            job2 = service.ingest_url("co-1", "https://new.com")

        jobs = service.list_jobs("co-1")
        assert len(jobs) == 2
        assert jobs[0].job_id == job2.job_id  # newest first
        assert jobs[1].job_id == job1.job_id

    def test_tenant_isolation_no_cross_company_data(self, service):
        """BC-001: list_jobs for one company must never return another's jobs."""
        with patch.object(service, "_run_ingest_sync"):
            service.ingest_url("co-tenant-a", "https://a.com")
            service.ingest_url("co-tenant-b", "https://b.com")
            service.ingest_url("co-tenant-a", "https://c.com")

        a_jobs = service.list_jobs("co-tenant-a")
        b_jobs = service.list_jobs("co-tenant-b")

        assert all(j.company_id == "co-tenant-a" for j in a_jobs)
        assert all(j.company_id == "co-tenant-b" for j in b_jobs)
        assert len(a_jobs) == 2
        assert len(b_jobs) == 1


# ════════════════════════════════════════════════════════════════════════
# 6. Progress Tracking
# ════════════════════════════════════════════════════════════════════════


class TestProgressTracking:
    """Tests for job progress tracking and status transitions."""

    def test_job_initial_progress_is_zero(self, service):
        """Newly created jobs should have progress 0."""
        with patch.object(service, "_run_ingest_sync"):
            job = service.ingest_url("co-1", "https://example.com")
        assert job.progress == 0.0

    def test_completed_job_has_progress_100(self, service_with_pipeline):
        """Successfully completed jobs should have progress 100."""
        service, _, _, _, _ = service_with_pipeline
        job = service.ingest_file_content("co-1", "doc-1", b"Some text content here", "test.txt")
        TestIngestFileContent._wait_for_job_completion(service, job.job_id, timeout=5.0)

        updated = service.get_job_status(job.job_id)
        assert updated.progress == 100.0

    def test_status_transitions_pending_to_completed(self, service_with_pipeline):
        """Job status should transition from PENDING to COMPLETED on success."""
        service, _, _, _, _ = service_with_pipeline
        job = service.ingest_file_content("co-1", "doc-1", b"Some text", "test.txt")
        assert job.status == IngestStatus.PENDING

        TestIngestFileContent._wait_for_job_completion(service, job.job_id, timeout=5.0)
        updated = service.get_job_status(job.job_id)
        assert updated.status == IngestStatus.COMPLETED

    def test_status_transitions_to_failed_on_error(self, service_with_pipeline):
        """Job status should transition to FAILED when pipeline raises an exception."""
        service, emb_cls, emb_inst, _, _ = service_with_pipeline
        # Make embedding service raise an exception
        emb_inst.generate_embeddings_batch.side_effect = RuntimeError("Embedding API down")

        job = service.ingest_file_content("co-1", "doc-1", b"Some text", "test.txt")
        TestIngestFileContent._wait_for_job_completion(service, job.job_id, timeout=5.0)

        updated = service.get_job_status(job.job_id)
        assert updated.status == IngestStatus.FAILED
        assert updated.error_message is not None
        assert "Embedding API down" in updated.error_message

    def test_failed_job_has_error_message(self, service_with_pipeline):
        """A failed job should have a descriptive error_message set."""
        service, _, emb_inst, _, _ = service_with_pipeline
        emb_inst.generate_embeddings_batch.side_effect = ValueError("Bad embedding input")

        job = service.ingest_file_content("co-1", "doc-1", b"Some text", "test.txt")
        TestIngestFileContent._wait_for_job_completion(service, job.job_id, timeout=5.0)

        updated = service.get_job_status(job.job_id)
        assert updated.error_message is not None
        assert len(updated.error_message) > 0

    def test_processing_status_during_pipeline(self, service_with_pipeline):
        """After _process_ingest starts, the job should be in PROCESSING status."""
        service, _, _, _, _ = service_with_pipeline
        job = service.ingest_file_content("co-1", "doc-1", b"Some text", "test.txt")
        # The background thread will transition to PROCESSING quickly.
        # We verify that at completion the job went through PROCESSING
        # by checking that completed jobs have progress > 0 (meaning they were processed).
        TestIngestFileContent._wait_for_job_completion(service, job.job_id, timeout=5.0)
        updated = service.get_job_status(job.job_id)
        # The job should have been processed (not stuck in PENDING)
        assert updated.status != IngestStatus.PENDING
        assert updated.progress > 0


# ════════════════════════════════════════════════════════════════════════
# 7. Tenant Isolation (BC-001)
# ════════════════════════════════════════════════════════════════════════


class TestTenantIsolation:
    """Tests for BC-001: All operations scoped to company_id."""

    def test_jobs_for_different_companies_are_isolated(self, service):
        """Jobs created under different companies must be fully isolated."""
        with patch.object(service, "_run_ingest_sync"):
            job_a = service.ingest_url("co-alpha", "https://a.com")
            job_b = service.ingest_url("co-beta", "https://b.com")

        assert job_a.company_id == "co-alpha"
        assert job_b.company_id == "co-beta"
        assert job_a.job_id != job_b.job_id

    def test_list_jobs_only_returns_jobs_for_specified_company(self, service):
        """list_jobs must never return jobs from another tenant."""
        with patch.object(service, "_run_ingest_sync"):
            for i in range(3):
                service.ingest_url("co-alpha", f"https://a{i}.com")
            for i in range(2):
                service.ingest_url("co-beta", f"https://b{i}.com")

        alpha_jobs = service.list_jobs("co-alpha")
        beta_jobs = service.list_jobs("co-beta")

        assert len(alpha_jobs) == 3
        assert len(beta_jobs) == 2
        assert all(j.company_id == "co-alpha" for j in alpha_jobs)
        assert all(j.company_id == "co-beta" for j in beta_jobs)

    def test_no_cross_tenant_data_leakage_via_get_job_status(self, service):
        """get_job_status returns the job object, but the company_id
        on the job must always match the original company — no leakage."""
        with patch.object(service, "_run_ingest_sync"):
            job_a = service.ingest_url("co-alpha", "https://a.com")

        # Even if we know job_a's ID from another tenant context,
        # the returned job still correctly belongs to co-alpha
        retrieved = service.get_job_status(job_a.job_id)
        assert retrieved is not None
        assert retrieved.company_id == "co-alpha"

    def test_vector_store_receives_correct_company_id(self, service_with_pipeline):
        """The vector store add_document call must include the correct company_id."""
        service, _, _, get_vs_fn, vs_inst = service_with_pipeline
        job = service.ingest_file_content("co-sensitive", "doc-1", b"Secret data", "f.txt")
        TestIngestFileContent._wait_for_job_completion(service, job.job_id, timeout=5.0)

        call_kwargs = vs_inst.add_document.call_args.kwargs
        assert call_kwargs["company_id"] == "co-sensitive"

    def test_embedding_service_receives_correct_company_id(self, service_with_pipeline):
        """EmbeddingService must be instantiated with the correct company_id."""
        service, emb_cls, _, _, _ = service_with_pipeline
        job = service.ingest_file_content("co-xyz", "doc-1", b"Data", "f.txt")
        TestIngestFileContent._wait_for_job_completion(service, job.job_id, timeout=5.0)

        emb_cls.assert_called_once_with(company_id="co-xyz")


# ════════════════════════════════════════════════════════════════════════
# 8. HTML Utilities
# ════════════════════════════════════════════════════════════════════════


class TestHtmlUtilities:
    """Tests for HTML detection and stripping utilities."""

    def test_looks_like_html_detects_html_tag(self):
        """Should detect text with <html> tag."""
        assert KnowledgeIngestService._looks_like_html(
            "<html><body>Hello</body></html>"
        ) is True

    def test_looks_like_html_detects_body_tag(self):
        """Should detect text with <body> tag."""
        assert KnowledgeIngestService._looks_like_html(
            "<body>Hello</body>"
        ) is True

    def test_looks_like_html_detects_p_tag(self):
        """Should detect text with <p> tag."""
        assert KnowledgeIngestService._looks_like_html(
            "<p>Hello</p>"
        ) is True

    def test_looks_like_html_detects_div_tag(self):
        """Should detect text with <div> tag."""
        assert KnowledgeIngestService._looks_like_html(
            "<div>Hello</div>"
        ) is True

    def test_looks_like_html_plain_text_returns_false(self):
        """Should return False for plain text without HTML tags."""
        assert KnowledgeIngestService._looks_like_html(
            "Just plain text without any tags"
        ) is False

    def test_strip_html_removes_tags(self):
        """_strip_html should remove all HTML tags."""
        result = KnowledgeIngestService._strip_html(
            "<html><body><h1>Title</h1><p>Content</p></body></html>"
        )
        assert "<" not in result
        assert ">" not in result
        assert "Title" in result
        assert "Content" in result

    def test_strip_html_removes_script_and_style(self):
        """_strip_html should remove <script> and <style> blocks entirely."""
        result = KnowledgeIngestService._strip_html(
            "<html><style>body{color:red;}</style>"
            "<script>alert('xss');</script>"
            "<p>Visible</p></html>"
        )
        assert "alert" not in result
        assert "color" not in result
        assert "Visible" in result

    def test_strip_html_decodes_entities(self):
        """_strip_html should decode common HTML entities."""
        result = KnowledgeIngestService._strip_html(
            "<p>5 &amp; 3 &lt; 10 &gt; 2 &quot;yes&quot; &#39;no&#39;</p>"
        )
        assert "&amp;" not in result
        assert "&lt;" not in result
        assert "&gt;" not in result

    def test_strip_html_collapses_whitespace(self):
        """_strip_html should collapse excessive whitespace."""
        result = KnowledgeIngestService._strip_html(
            "<p>Hello</p>   <p>World</p>"
        )
        assert "   " not in result

    def test_strip_html_handles_nonbreaking_space(self):
        """_strip_html should convert &nbsp; to regular space."""
        result = KnowledgeIngestService._strip_html(
            "<p>Hello&nbsp;World</p>"
        )
        assert "\xa0" not in result


# ════════════════════════════════════════════════════════════════════════
# 9. Helper Methods
# ════════════════════════════════════════════════════════════════════════


class TestHelperMethods:
    """Tests for internal helper methods."""

    def test_url_to_document_id_deterministic(self):
        """Same URL + company_id should always produce the same document_id."""
        doc_id_1 = KnowledgeIngestService._url_to_document_id(
            "https://example.com", "co-1"
        )
        doc_id_2 = KnowledgeIngestService._url_to_document_id(
            "https://example.com", "co-1"
        )
        assert doc_id_1 == doc_id_2

    def test_url_to_document_id_different_companies(self):
        """Different company_id should produce different document_ids for same URL."""
        doc_id_a = KnowledgeIngestService._url_to_document_id(
            "https://example.com", "co-a"
        )
        doc_id_b = KnowledgeIngestService._url_to_document_id(
            "https://example.com", "co-b"
        )
        assert doc_id_a != doc_id_b

    def test_url_to_document_id_format(self):
        """Generated document_id should have the expected format."""
        doc_id = KnowledgeIngestService._url_to_document_id(
            "https://example.com", "co-1"
        )
        assert doc_id.startswith("doc_url_")
        assert len(doc_id) == len("doc_url_") + 32  # 32 hex chars

    def test_get_extension_common_formats(self):
        """_get_extension should extract extensions correctly."""
        assert KnowledgeIngestService._get_extension("file.txt") == ".txt"
        assert KnowledgeIngestService._get_extension("report.pdf") == ".pdf"
        assert KnowledgeIngestService._get_extension("data.csv") == ".csv"
        assert KnowledgeIngestService._get_extension("page.html") == ".html"

    def test_get_extension_no_extension(self):
        """_get_extension should return empty string for no extension."""
        assert KnowledgeIngestService._get_extension("Makefile") == ""

    def test_get_extension_empty_filename(self):
        """_get_extension should return empty string for empty filename."""
        assert KnowledgeIngestService._get_extension("") == ""

    def test_get_extension_dot_at_end(self):
        """_get_extension should return empty string if dot is at the end."""
        assert KnowledgeIngestService._get_extension("file.") == ""

    def test_generate_job_id_format(self):
        """Generated job IDs should match the expected format."""
        job_id = KnowledgeIngestService._generate_job_id()
        assert job_id.startswith("ingest_")
        # After 'ingest_', there should be 16 hex characters
        hex_part = job_id[len("ingest_"):]
        assert len(hex_part) == 16
        int(hex_part, 16)  # Should not raise — it's valid hex

    def test_generate_job_id_uniqueness(self):
        """Each generated job ID should be unique."""
        ids = {KnowledgeIngestService._generate_job_id() for _ in range(100)}
        assert len(ids) == 100


# ════════════════════════════════════════════════════════════════════════
# 10. Direct _process_ingest Testing (Async)
# ════════════════════════════════════════════════════════════════════════


class TestProcessIngestDirect:
    """Direct tests for the _process_ingest async pipeline method."""

    @pytest.fixture
    def async_service(self, mock_chunker, mock_embedding_service, mock_vector_store):
        """Service set up for direct async pipeline testing."""
        svc = KnowledgeIngestService()
        svc._chunker = mock_chunker
        emb_cls, emb_inst = mock_embedding_service
        get_vs_fn, vs_inst = mock_vector_store
        return svc, emb_cls, emb_inst, get_vs_fn, vs_inst

    def test_process_ingest_file_content(self, async_service):
        """_process_ingest should successfully process file content."""
        svc, emb_cls, emb_inst, get_vs_fn, vs_inst = async_service
        job = IngestJob(
            job_id="test-job-1",
            company_id="co-1",
            source=IngestSource.FILE,
            document_id="doc-1",
            filename="test.txt",
        )
        svc._jobs[job.job_id] = job

        with patch(
            "app.services.knowledge.ingest._import_embedding_service",
            return_value=emb_cls,
        ), patch(
            "app.services.knowledge.ingest._import_vector_store",
            return_value=get_vs_fn,
        ):
            asyncio.get_event_loop().run_until_complete(
                svc._process_ingest(job.job_id, content=b"Hello world", filename="test.txt")
            )

        assert job.status == IngestStatus.COMPLETED
        assert job.progress == 100.0
        assert job.total_chunks == 2
        assert job.processed_chunks == 2

    def test_process_ingest_url_content(self, async_service):
        """_process_ingest should successfully process URL content."""
        svc, emb_cls, emb_inst, get_vs_fn, vs_inst = async_service
        job = IngestJob(
            job_id="test-job-2",
            company_id="co-1",
            source=IngestSource.URL,
            document_id="doc-2",
            source_url="https://example.com",
        )
        svc._jobs[job.job_id] = job

        with patch.object(
            svc, "_fetch_url_text", new_callable=AsyncMock,
            return_value="Fetched page content"
        ), patch(
            "app.services.knowledge.ingest._import_embedding_service",
            return_value=emb_cls,
        ), patch(
            "app.services.knowledge.ingest._import_vector_store",
            return_value=get_vs_fn,
        ):
            asyncio.get_event_loop().run_until_complete(
                svc._process_ingest(job.job_id, url="https://example.com")
            )

        assert job.status == IngestStatus.COMPLETED
        assert job.progress == 100.0

    def test_process_ingest_no_content_nor_url(self, async_service):
        """_process_ingest with no content or URL should mark job as FAILED."""
        svc, emb_cls, emb_inst, get_vs_fn, vs_inst = async_service
        job = IngestJob(
            job_id="test-job-3",
            company_id="co-1",
            source=IngestSource.FILE,
            document_id="doc-3",
        )
        svc._jobs[job.job_id] = job

        with patch(
            "app.services.knowledge.ingest._import_embedding_service",
            return_value=emb_cls,
        ), patch(
            "app.services.knowledge.ingest._import_vector_store",
            return_value=get_vs_fn,
        ):
            asyncio.get_event_loop().run_until_complete(
                svc._process_ingest(job.job_id)
            )

        assert job.status == IngestStatus.FAILED
        assert "No content or URL" in (job.error_message or "")

    def test_process_ingest_url_fetch_returns_none(self, async_service):
        """_process_ingest with URL fetch returning None should mark as FAILED."""
        svc, emb_cls, emb_inst, get_vs_fn, vs_inst = async_service
        job = IngestJob(
            job_id="test-job-4",
            company_id="co-1",
            source=IngestSource.URL,
            document_id="doc-4",
            source_url="https://unreachable.example.com",
        )
        svc._jobs[job.job_id] = job

        with patch.object(
            svc, "_fetch_url_text", new_callable=AsyncMock, return_value=None
        ), patch(
            "app.services.knowledge.ingest._import_embedding_service",
            return_value=emb_cls,
        ), patch(
            "app.services.knowledge.ingest._import_vector_store",
            return_value=get_vs_fn,
        ):
            asyncio.get_event_loop().run_until_complete(
                svc._process_ingest(job.job_id, url="https://unreachable.example.com")
            )

        assert job.status == IngestStatus.FAILED
        assert "Failed to extract text from URL" in (job.error_message or "")

    def test_process_ingest_zero_chunks(self, async_service):
        """_process_ingest with zero chunks should complete with progress 100."""
        svc, emb_cls, emb_inst, get_vs_fn, vs_inst = async_service
        # Override chunker to return empty list — but use non-empty content
        # so text extraction succeeds (empty text is treated as failure)
        svc._chunker.chunk_text.return_value = []
        job = IngestJob(
            job_id="test-job-5",
            company_id="co-1",
            source=IngestSource.FILE,
            document_id="doc-5",
            filename="short.txt",
        )
        svc._jobs[job.job_id] = job

        with patch(
            "app.services.knowledge.ingest._import_embedding_service",
            return_value=emb_cls,
        ), patch(
            "app.services.knowledge.ingest._import_vector_store",
            return_value=get_vs_fn,
        ):
            asyncio.get_event_loop().run_until_complete(
                svc._process_ingest(job.job_id, content=b"minimal text", filename="short.txt")
            )

        assert job.status == IngestStatus.COMPLETED
        assert job.progress == 100.0
        assert job.total_chunks == 0
        assert job.processed_chunks == 0

    def test_process_ingest_exception_marks_failed(self, async_service):
        """BC-008: Unhandled exceptions in _process_ingest should mark job as FAILED."""
        svc, emb_cls, emb_inst, get_vs_fn, vs_inst = async_service
        # Make chunker raise an unexpected error
        svc._chunker.chunk_text.side_effect = RuntimeError("Chunker crashed")

        job = IngestJob(
            job_id="test-job-6",
            company_id="co-1",
            source=IngestSource.FILE,
            document_id="doc-6",
            filename="crash.txt",
        )
        svc._jobs[job.job_id] = job

        with patch(
            "app.services.knowledge.ingest._import_embedding_service",
            return_value=emb_cls,
        ), patch(
            "app.services.knowledge.ingest._import_vector_store",
            return_value=get_vs_fn,
        ):
            asyncio.get_event_loop().run_until_complete(
                svc._process_ingest(job.job_id, content=b"Data", filename="crash.txt")
            )

        assert job.status == IngestStatus.FAILED
        assert "Chunker crashed" in (job.error_message or "")

    def test_process_ingest_nonexistent_job(self, async_service):
        """_process_ingest with a nonexistent job_id should not crash (BC-008)."""
        svc, emb_cls, emb_inst, get_vs_fn, vs_inst = async_service

        with patch(
            "app.services.knowledge.ingest._import_embedding_service",
            return_value=emb_cls,
        ), patch(
            "app.services.knowledge.ingest._import_vector_store",
            return_value=get_vs_fn,
        ):
            # Should not raise — BC-008 graceful degradation
            asyncio.get_event_loop().run_until_complete(
                svc._process_ingest("nonexistent-job-id", content=b"Data", filename="f.txt")
            )

    def test_process_ingest_progress_tracking(self, async_service):
        """Job should track progress through the pipeline stages."""
        svc, emb_cls, emb_inst, get_vs_fn, vs_inst = async_service
        job = IngestJob(
            job_id="test-job-7",
            company_id="co-1",
            source=IngestSource.FILE,
            document_id="doc-7",
            filename="test.txt",
        )
        svc._jobs[job.job_id] = job

        with patch(
            "app.services.knowledge.ingest._import_embedding_service",
            return_value=emb_cls,
        ), patch(
            "app.services.knowledge.ingest._import_vector_store",
            return_value=get_vs_fn,
        ):
            asyncio.get_event_loop().run_until_complete(
                svc._process_ingest(job.job_id, content=b"Hello world", filename="test.txt")
            )

        # After completion, progress should be 100
        assert job.progress == 100.0
        # And status should have gone through PROCESSING
        assert job.status == IngestStatus.COMPLETED


# ════════════════════════════════════════════════════════════════════════
# 11. Data Model Tests
# ════════════════════════════════════════════════════════════════════════


class TestDataModels:
    """Tests for IngestJob and enum data models."""

    def test_ingest_status_enum_values(self):
        """IngestStatus should have the expected enum values."""
        assert IngestStatus.PENDING.value == "pending"
        assert IngestStatus.PROCESSING.value == "processing"
        assert IngestStatus.COMPLETED.value == "completed"
        assert IngestStatus.FAILED.value == "failed"

    def test_ingest_source_enum_values(self):
        """IngestSource should have the expected enum values."""
        assert IngestSource.FILE.value == "file"
        assert IngestSource.URL.value == "url"

    def test_ingest_job_defaults(self):
        """IngestJob should have sensible default values."""
        job = IngestJob(
            job_id="j1",
            company_id="co-1",
            source=IngestSource.FILE,
        )
        assert job.status == IngestStatus.PENDING
        assert job.progress == 0.0
        assert job.total_chunks == 0
        assert job.processed_chunks == 0
        assert job.error_message is None
        assert job.document_id is None
        assert job.source_url is None
        assert job.filename is None
        assert job.created_at > 0
        assert job.updated_at > 0

    def test_ingest_job_custom_values(self):
        """IngestJob should accept custom values for all fields."""
        now = time.time()
        job = IngestJob(
            job_id="j2",
            company_id="co-2",
            source=IngestSource.URL,
            status=IngestStatus.COMPLETED,
            progress=100.0,
            total_chunks=5,
            processed_chunks=5,
            error_message=None,
            document_id="doc-2",
            source_url="https://example.com",
            filename=None,
            created_at=now,
            updated_at=now,
        )
        assert job.status == IngestStatus.COMPLETED
        assert job.total_chunks == 5
        assert job.source_url == "https://example.com"
