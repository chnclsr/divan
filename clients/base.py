"""Divan Clients — Abstract base court client.

Tüm court client'ların türeyeceği ABC. yargi-mcp'de her client
kendi __init__'inde httpx client, header, token bucket oluşturuyordu.
Divan'da bunların hepsi base class'tan gelir; alt sınıflar sadece
endpoint mantığına odaklanır.
"""

from __future__ import annotations

import asyncio
import io
import logging
from abc import abstractmethod
from typing import Any, Optional

from markitdown import MarkItDown

from ..core.enums import CourtType
from ..core.interfaces import ICourtClient, ICacheBackend
from ..core.models import Decision, HealthStatus, SearchQuery, SearchResult
from ..core.exceptions import ConversionError
from ..config import AppConfig
from ..infrastructure.http_client import ResilientHttpClient
from ..infrastructure.rate_limiter import AsyncTokenBucket
from ..infrastructure.circuit_breaker import CircuitBreaker
from ..infrastructure.cache import CacheKeyBuilder

logger = logging.getLogger(__name__)


def preprocess_query_text(query: str) -> str:
    """Sorgu metnini temizler ve varsayılan AND operatörünü uygular.

    Eğer sorguda çift tırnak, AND, OR, NOT gibi özel arama operatörleri
    yoksa, kelimeleri 'AND' ile bağlayarak sonuçları daraltır ve gürültüyü önler.
    """
    q = (query or "").strip()
    if not q:
        return ""

    # Özel arama operatörleri kontrolü
    special_operators = ['"', ' AND ', ' OR ', ' NOT ', ' and ', ' or ', ' not ', '+', '-', '*']
    if any(op in q for op in special_operators):
        return q

    # Kelimelere böl (2 karakter ve üzeri olanları ve sayıları al)
    words = [w for w in q.split() if len(w) >= 2 or w.isdigit()]
    if len(words) <= 1:
        return q

    # Kelimeleri AND ile birleştir
    return " AND ".join(words)


class BaseCourtClient(ICourtClient):
    """Tüm court client'ların ortak altyapısı.

    Alt sınıflar yalnızca şunları override eder:
        - court_type (property)
        - supported_courts (property)
        - _do_search() — API'ye özgü arama mantığı
        - _do_get_document() — API'ye özgü belge getirme mantığı
        - _get_base_url() — API base URL (classmethod)
        - _get_default_headers() — Varsayılan header'lar (classmethod)

    Base class sağlar:
        - HTTP client yönetimi
        - Rate limiting
        - Circuit breaker
        - Cache entegrasyonu
        - HTML/PDF → Markdown dönüşümü
        - Yapılandırılmış loglama
    """

    def __init__(
        self,
        config: AppConfig,
        rate_limiter: Optional[AsyncTokenBucket] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
        cache: Optional[ICacheBackend] = None,
    ) -> None:
        self._config = config
        self._rate_limiter = rate_limiter
        self._circuit_breaker = circuit_breaker or CircuitBreaker.from_config(
            name=self.court_type.name, config=config.circuit_breaker
        )
        self._cache = cache

        # HTTP client oluştur
        self._http = ResilientHttpClient(
            base_url=self._get_base_url(),
            headers=self._get_default_headers(),
            timeout=config.http_timeout,
            max_retries=config.http_max_retries,
            backoff_base=config.http_backoff_base,
            backoff_max=config.http_backoff_max,
            rate_limiter=self._rate_limiter,
            circuit_breaker=self._circuit_breaker,
            verify_ssl=self._get_ssl_verify(),
        )

        # Markdown converter (lazy init, thread-safe kullanım)
        self._markitdown: Optional[MarkItDown] = None

    # ── Alt sınıfların override edeceği metodlar ──────────────────────────

    @classmethod
    @abstractmethod
    def _get_base_url(cls) -> str:
        """API'nin temel URL'i."""
        ...

    @classmethod
    def _get_default_headers(cls) -> dict[str, str]:
        """Varsayılan HTTP header'lar. Override edilebilir."""
        return {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json; charset=UTF-8",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/137.0.0.0 Safari/537.36"
            ),
        }

    @classmethod
    def _get_ssl_verify(cls) -> bool:
        """SSL doğrulama. Eski sunucular için False yapılabilir."""
        return True

    @abstractmethod
    async def _do_search(self, query: SearchQuery) -> SearchResult:
        """API'ye özgü arama mantığı. Alt sınıf implemente eder."""
        ...

    @abstractmethod
    async def _do_get_document(self, document_id: str) -> Decision:
        """API'ye özgü belge getirme mantığı. Alt sınıf implemente eder."""
        ...

    # ── Public API (cache + error handling wrapper) ───────────────────────

    async def search(self, query: SearchQuery) -> SearchResult:
        """Arama yap. Cache varsa önce cache'e bakar."""
        if query.query:
            query = query.model_copy(update={"query": preprocess_query_text(query.query)})
        cache_key = CacheKeyBuilder.build(
            f"{self.court_type.value}:search",
            query=query.query,
            page=query.page,
            page_size=query.page_size,
            chamber=query.chamber,
            courts=",".join([c.name for c in query.courts]) if query.courts else "",
            esas_no=query.esas_no,
            karar_no=query.karar_no,
            date_start=query.date_range.start.isoformat() if query.date_range and query.date_range.start else "",
            date_end=query.date_range.end.isoformat() if query.date_range and query.date_range.end else "",
        )

        # Cache kontrolü
        if self._cache:
            import json as _json
            cached = await self._cache.get(cache_key)
            if cached:
                logger.debug(f"Cache hit for search: {cache_key}")
                return SearchResult.model_validate_json(cached)

        # API'den getir
        result = await self._do_search(query)

        # Cache'e yaz
        if self._cache and result.has_results:
            await self._cache.set(
                cache_key,
                result.model_dump_json().encode("utf-8"),
                ttl=self._config.cache_ttl,
            )

        return result

    async def get_document(self, document_id: str) -> Decision:
        """Belge getir. Cache varsa önce cache'e bakar."""
        cache_key = CacheKeyBuilder.build(
            f"{self.court_type.value}:document",
            document_id=document_id,
        )

        # Cache kontrolü
        if self._cache:
            cached = await self._cache.get(cache_key)
            if cached:
                logger.debug(f"Cache hit for document: {document_id}")
                return Decision.model_validate_json(cached)

        # API'den getir
        decision = await self._do_get_document(document_id)

        # Cache'e yaz
        if self._cache and decision.markdown_content:
            await self._cache.set(
                cache_key,
                decision.model_dump_json().encode("utf-8"),
                ttl=self._config.cache_ttl,
            )

        return decision

    async def health_check(self) -> HealthStatus:
        """Endpoint erişilebilirlik kontrolü."""
        import time
        start = time.monotonic()
        try:
            response = await self._http.get("/")
            elapsed = (time.monotonic() - start) * 1000
            return HealthStatus(
                court_type=self.court_type,
                is_healthy=response.status_code < 500,
                response_time_ms=round(elapsed, 1),
            )
        except Exception as e:
            elapsed = (time.monotonic() - start) * 1000
            return HealthStatus(
                court_type=self.court_type,
                is_healthy=False,
                response_time_ms=round(elapsed, 1),
                error=str(e),
            )

    async def close(self) -> None:
        """HTTP client'ı kapat."""
        await self._http.close()
        logger.info(f"{self.__class__.__name__}: closed")

    # ── Yardımcı Metodlar ─────────────────────────────────────────────────

    def _get_markitdown(self) -> MarkItDown:
        """Lazy-initialized MarkItDown instance."""
        if self._markitdown is None:
            self._markitdown = MarkItDown()
        return self._markitdown

    async def _html_to_markdown(self, html_content: str) -> str:
        """HTML → Markdown dönüşümü. Event loop'u bloklamaz.

        Args:
            html_content: Dönüştürülecek HTML metni.

        Returns:
            Markdown metni.

        Raises:
            ConversionError: Dönüşüm başarısızsa.
        """
        if not html_content or not html_content.strip():
            return ""
        try:
            def _convert():
                md = self._get_markitdown()
                html_bytes = html_content.encode("utf-8")
                stream = io.BytesIO(html_bytes)
                result = md.convert(stream)
                return result.text_content or ""

            return await asyncio.to_thread(_convert)
        except Exception as e:
            raise ConversionError(f"HTML → Markdown dönüşüm hatası: {e}", cause=e) from e

    async def _pdf_to_markdown(self, pdf_bytes: bytes) -> str:
        """PDF → Markdown dönüşümü. Event loop'u bloklamaz.

        Args:
            pdf_bytes: PDF dosyasının ham byte'ları.

        Returns:
            Markdown metni.

        Raises:
            ConversionError: Dönüşüm başarısızsa.
        """
        if not pdf_bytes:
            return ""
        try:
            def _convert():
                md = self._get_markitdown()
                stream = io.BytesIO(pdf_bytes)
                result = md.convert(stream)
                return result.text_content or ""

            return await asyncio.to_thread(_convert)
        except Exception as e:
            raise ConversionError(f"PDF → Markdown dönüşüm hatası: {e}", cause=e) from e

    # ── Dunder ────────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(court={self.court_type.name}, url={self._get_base_url()})"
