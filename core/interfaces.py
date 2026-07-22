"""Divan Core — Abstract base classes (interfaces).

Bu modül, Divan'ın tüm katmanları arasındaki sözleşmeleri tanımlar.
Her interface bir ABC olarak tanımlanmıştır; concrete implementasyonlar
kendi modüllerinde bu ABC'lerden türer.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from .enums import CourtType, ExportFormat
from .models import Decision, HealthStatus, SearchQuery, SearchResult


class ICourtClient(ABC):
    """Bir mahkeme/kurum API'sine erişim sözleşmesi.

    Her court client bu interface'i implemente eder. Factory pattern
    ile CourtType'a göre doğru client oluşturulur.
    """

    @property
    @abstractmethod
    def court_type(self) -> CourtType:
        """Bu client'ın hangi kuruma ait olduğu."""
        ...

    @property
    @abstractmethod
    def supported_courts(self) -> list[CourtType]:
        """Bu client'ın desteklediği tüm CourtType'lar.

        Bedesten gibi birden fazla mahkemeyi kapsayan client'lar için
        birden fazla CourtType döner.
        """
        ...

    @property
    def supports_boolean_or(self) -> bool:
        """Bu client, sorgu string'inde Boolean OR sözdizimini destekliyor mu?

        True ise servis, genişletilmiş terimleri tek bir OR sorgusuna
        birleştirip gönderir (recall için). False ise düz sorgu gönderilir
        (OR sözdizimi bozuk sonuç üretmesin diye). Varsayılan: False.
        """
        return False

    @abstractmethod
    async def search(self, query: SearchQuery) -> SearchResult:
        """Karar arama."""
        ...

    @abstractmethod
    async def get_document(self, document_id: str) -> Decision:
        """Belge ID'siyle tam metin getirme."""
        ...

    async def health_check(self) -> HealthStatus:
        """Endpoint sağlık kontrolü. Varsayılan: sağlıklı."""
        return HealthStatus(
            court_type=self.court_type,
            is_healthy=True,
        )

    async def close(self) -> None:
        """Kaynakları serbest bırak (HTTP client vb.)."""


class ISearchService(ABC):
    """Birleşik arama servisi sözleşmesi."""

    @abstractmethod
    async def search(self, query: SearchQuery) -> SearchResult:
        """Birden fazla mahkemede paralel arama."""
        ...

    @abstractmethod
    async def search_single(self, query: SearchQuery, court: CourtType) -> SearchResult:
        """Tek bir mahkemede arama."""
        ...


class IDocumentService(ABC):
    """Belge getirme ve işleme servisi sözleşmesi."""

    @abstractmethod
    async def get_document(self, document_id: str, court_type: CourtType) -> Decision:
        """Belge getir, Markdown'a çevir, cache'le."""
        ...


class IExporter(ABC):
    """Dışa aktarma sözleşmesi."""

    @abstractmethod
    async def export(self, decision: Decision, fmt: ExportFormat) -> bytes:
        """Kararı istenen formata dönüştür."""
        ...


class ICacheBackend(ABC):
    """In-memory cache backend sözleşmesi."""

    @abstractmethod
    async def get(self, key: str) -> Optional[bytes]:
        ...

    @abstractmethod
    async def set(self, key: str, value: bytes, ttl: int = 3600) -> None:
        ...

    @abstractmethod
    async def delete(self, key: str) -> None:
        ...

    @abstractmethod
    async def clear(self) -> None:
        ...
