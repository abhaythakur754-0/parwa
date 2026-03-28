"""
Compression Middleware for PARWA Performance Optimization.

Week 26 - Builder 4: API Response Caching + Compression
Target: Compression reduces size >60%, Gzip + Brotli support

Features:
- Gzip compression for responses >1KB
- Brotli compression for supported clients
- Compression level: 4 (balance)
- Skip compression for already compressed
- Content-Type filtering
"""

import gzip
import brotli
import logging
from typing import Set, Optional, Callable
from fastapi import Request, Response
from fastapi.responses import Response as FastAPIResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp, Message, Receive, Send, Scope

logger = logging.getLogger(__name__)


class CompressionMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for response compression.

    Features:
    - Gzip and Brotli compression
    - Configurable compression level
    - Automatic content-type filtering
    - Size threshold for compression
    """

    # Content types that should be compressed
    COMPRESSIBLE_TYPES: Set[str] = {
        "application/json",
        "application/javascript",
        "application/x-javascript",
        "application/xml",
        "application/xhtml+xml",
        "text/html",
        "text/css",
        "text/javascript",
        "text/xml",
        "text/plain",
        "text/x-component",
        "text/x-cross-domain-policy",
    }

    # Content types that are already compressed
    ALREADY_COMPRESSED: Set[str] = {
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
        "image/avif",
        "video/mp4",
        "video/webm",
        "audio/mpeg",
        "audio/ogg",
        "application/pdf",
        "application/zip",
        "application/gzip",
        "application/x-gzip",
    }

    def __init__(
        self,
        app: ASGIApp,
        minimum_size: int = 1024,
        gzip_level: int = 4,
        brotli_level: int = 4,
        enable_brotli: bool = True
    ):
        """
        Initialize compression middleware.

        Args:
            app: ASGI application.
            minimum_size: Minimum response size for compression (bytes).
            gzip_level: Gzip compression level (1-9).
            brotli_level: Brotli compression level (1-11).
            enable_brotli: Whether to enable Brotli compression.
        """
        super().__init__(app)
        self.minimum_size = minimum_size
        self.gzip_level = gzip_level
        self.brotli_level = brotli_level
        self.enable_brotli = enable_brotli

    def _should_compress(self, response: Response, accept_encoding: str) -> bool:
        """
        Determine if response should be compressed.

        Args:
            response: Response object.
            accept_encoding: Accept-Encoding header value.

        Returns:
            True if response should be compressed.
        """
        # Check if client accepts compression
        if not accept_encoding:
            return False

        # Check content type
        content_type = response.headers.get("content-type", "")
        base_content_type = content_type.split(";")[0].strip().lower()

        # Skip already compressed content
        if base_content_type in self.ALREADY_COMPRESSED:
            return False

        # Only compress compressible types
        if base_content_type not in self.COMPRESSIBLE_TYPES:
            return False

        # Check content length
        content_length = response.headers.get("content-length")
        if content_length and int(content_length) < self.minimum_size:
            return False

        # Check if already encoded
        if response.headers.get("content-encoding"):
            return False

        return True

    def _get_encoding(self, accept_encoding: str) -> Optional[str]:
        """
        Determine best encoding based on Accept-Encoding header.

        Args:
            accept_encoding: Accept-Encoding header value.

        Returns:
            Encoding to use ("br", "gzip", or None).
        """
        encodings = [e.strip().lower() for e in accept_encoding.split(",")]

        # Prefer Brotli if supported
        if self.enable_brotli and "br" in encodings:
            return "br"

        # Fall back to Gzip
        if "gzip" in encodings:
            return "gzip"

        return None

    def _compress(self, content: bytes, encoding: str) -> bytes:
        """
        Compress content using specified encoding.

        Args:
            content: Content to compress.
            encoding: Compression encoding ("br" or "gzip").

        Returns:
            Compressed content.
        """
        if encoding == "br":
            return brotli.compress(content, quality=self.brotli_level)
        elif encoding == "gzip":
            return gzip.compress(content, compresslevel=self.gzip_level)
        return content

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request through compression middleware.

        Args:
            request: FastAPI request.
            call_next: Next middleware/handler.

        Returns:
            Response.
        """
        # Get Accept-Encoding header
        accept_encoding = request.headers.get("accept-encoding", "")

        # Process request
        response = await call_next(request)

        # Check if should compress
        if not self._should_compress(response, accept_encoding):
            return response

        # Determine encoding
        encoding = self._get_encoding(accept_encoding)
        if not encoding:
            return response

        # Get response body
        response_body = b""
        async for chunk in response.body_iterator:
            response_body += chunk

        # Check minimum size
        if len(response_body) < self.minimum_size:
            return Response(
                content=response_body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type
            )

        # Compress
        compressed = self._compress(response_body, encoding)

        # Calculate compression ratio
        original_size = len(response_body)
        compressed_size = len(compressed)
        compression_ratio = (1 - compressed_size / original_size) * 100

        # Log compression stats
        logger.debug(
            f"Compressed {original_size} bytes to {compressed_size} bytes "
            f"({compression_ratio:.1f}% reduction) using {encoding}"
        )

        # Create compressed response
        headers = dict(response.headers)
        headers["content-encoding"] = encoding
        headers["content-length"] = str(compressed_size)
        headers["vary"] = "Accept-Encoding"
        headers["x-compression-ratio"] = f"{compression_ratio:.1f}"

        return Response(
            content=compressed,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type
        )


def setup_compression_middleware(
    app: ASGIApp,
    minimum_size: int = 1024,
    gzip_level: int = 4,
    brotli_level: int = 4
) -> None:
    """
    Setup compression middleware on FastAPI app.

    Args:
        app: FastAPI application.
        minimum_size: Minimum response size for compression.
        gzip_level: Gzip compression level.
        brotli_level: Brotli compression level.
    """
    app.add_middleware(
        CompressionMiddleware,
        minimum_size=minimum_size,
        gzip_level=gzip_level,
        brotli_level=brotli_level
    )


__all__ = [
    "CompressionMiddleware",
    "setup_compression_middleware",
]
