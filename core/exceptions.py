"""Divan Core — Hiyerarşik exception sistemi.

Tüm Divan hataları `DivanError`'dan türer. Bu sayede üst katmanlar
tek bir except bloğuyla tüm Divan hatalarını yakalayabilir,
alt katmanlar ise spesifik hata türlerine göre davranabilir.
"""

from __future__ import annotations
from typing import Optional


class DivanError(Exception):
    """Tüm Divan hatalarının kök sınıfı."""

    def __init__(self, message: str, *, cause: Optional[Exception] = None) -> None:
        self.cause = cause
        super().__init__(message)


# ── Client (Ağ / API) Hataları ────────────────────────────────────────────


class ClientError(DivanError):
    """Bir court client'ın API çağrısında oluşan hataların kök sınıfı."""


class RateLimitError(ClientError):
    """HTTP 429 veya yerel token-bucket taşması.

    Attributes:
        retry_after: Saniye cinsinden beklenmesi gereken süre.
    """

    def __init__(self, retry_after: float, message: str = "") -> None:
        self.retry_after = retry_after
        super().__init__(
            message or f"Rate limit aşıldı. {retry_after:.1f}s sonra tekrar deneyin."
        )


class CircuitOpenError(ClientError):
    """Circuit breaker OPEN durumunda; istekler engelleniyor.

    Attributes:
        remaining_seconds: Devre kapanana kadar kalan yaklaşık süre.
    """

    def __init__(self, remaining_seconds: float) -> None:
        self.remaining_seconds = remaining_seconds
        super().__init__(
            f"Circuit breaker açık. ~{remaining_seconds:.0f}s sonra yeniden denenecek."
        )


class EndpointUnavailableError(ClientError):
    """Hedef sunucu erişilemez durumda (DNS, timeout, connection refused)."""


class AuthenticationError(ClientError):
    """Token / session doğrulama başarısız (KİK AES imzası vb.)."""


# ── Document (Belge İşleme) Hataları ──────────────────────────────────────


class DocumentError(DivanError):
    """Belge getirme veya dönüştürme hatalarının kök sınıfı."""


class DocumentNotFoundError(DocumentError):
    """İstenen belge ID'si bulunamadı."""

    def __init__(self, document_id: str) -> None:
        self.document_id = document_id
        super().__init__(f"Belge bulunamadı: {document_id}")


class ConversionError(DocumentError):
    """HTML / PDF → Markdown dönüşümü başarısız."""


class MalformedResponseError(DocumentError):
    """API'den beklenmeyen formatta yanıt geldi."""


# ── Validation Hataları ───────────────────────────────────────────────────


class ValidationError(DivanError):
    """Giriş parametresi doğrulama hatası."""
