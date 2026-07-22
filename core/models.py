"""Divan Core — Unified domain models.

yargi-mcp'deki en büyük mimari sorun, her modülün kendi model setini
tanımlamasıydı (BedestenDecisionEntry, DanistayDecisionEntry, EmsalDecisionEntry...).
Divan'da TEK bir `Decision` modeli var; tüm court client'lar bu modelin
instance'larını döndürür.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, HttpUrl

from .enums import CourtType, DecisionType, ExportFormat


# ── Temel Varlıklar ──────────────────────────────────────────────────────


class Court(BaseModel):
    """Mahkeme veya kurum tanımı."""

    court_type: CourtType
    name: str = Field(..., description="Tam Türkçe ad: 'Yargıtay 1. Hukuk Dairesi'")
    chamber: Optional[str] = Field(None, description="Daire / kurul kısaltması (H1, D3, HGK...)")
    base_url: str = Field(..., description="Kurumun API temel adresi")


class Decision(BaseModel):
    """Birleşik karar modeli — tüm kurumların kararlarını temsil eder.

    Bu, tüm sistemin **lingua franca**'sıdır. Bedesten, AYM, Emsal veya
    herhangi bir başka kaynaktan gelen veriler bu modele normalize edilir.
    """

    # ── Kimlik ──
    id: str = Field(..., description="Kaynak sistemdeki benzersiz belge ID'si")
    court_type: CourtType
    decision_type: DecisionType = DecisionType.KARAR

    # ── Referans Numaraları ──
    esas_no: Optional[str] = Field(None, description="Esas numarası: '2024/1234'")
    karar_no: Optional[str] = Field(None, description="Karar numarası: '2024/5678'")
    esas_yil: Optional[int] = None
    esas_sira: Optional[int] = None
    karar_yil: Optional[int] = None
    karar_sira: Optional[int] = None

    # ── Mahkeme Bilgisi ──
    chamber_name: Optional[str] = Field(None, description="Daire/kurul tam adı")
    chamber_code: Optional[str] = Field(None, description="Daire kısaltması (H1, D3...)")

    # ── Tarihler ──
    decision_date: Optional[date] = None
    decision_date_str: Optional[str] = Field(None, description="Orijinal tarih string'i")

    # ── Mevzuat Bilgisi ──
    mevzuat_turu: Optional[str] = Field(None, description="Mevzuat türü (Kanun, KHK, Yönetmelik vb.)")
    kanun_no: Optional[str] = Field(None, description="Kanun numarası (Örn: 5237)")
    resmi_gazete_tarihi: Optional[str] = None
    resmi_gazete_sayisi: Optional[str] = None
    mevzuat_tertip: Optional[str] = None

    # ── İçerik ──
    title: Optional[str] = None
    summary: Optional[str] = None
    snippet: Optional[str] = Field(None, description="Arama sorgusunun geçtiği bölüm (Semantik Reranking için)")
    markdown_content: Optional[str] = Field(None, description="Karar/Mevzuatın Markdown metni")

    # ── Kaynak Bilgisi ──
    source_url: Optional[str] = None
    document_url: Optional[str] = None

    # ── Ham Metadata ──
    raw_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Kaynak API'den gelen normalize edilmemiş alanlar"
    )

    # ── Timestamps ──
    fetched_at: Optional[datetime] = Field(default_factory=datetime.utcnow)

    @property
    def reference(self) -> str:
        """İnsan tarafından okunabilir referans string'i."""
        parts: list[str] = []
        if self.chamber_name:
            parts.append(self.chamber_name)
        if self.esas_no:
            parts.append(f"E. {self.esas_no}")
        if self.karar_no:
            parts.append(f"K. {self.karar_no}")
        if self.decision_date_str:
            parts.append(f"T. {self.decision_date_str}")
        if self.mevzuat_turu:
            parts.append(self.mevzuat_turu)
        if self.kanun_no:
            parts.append(f"No. {self.kanun_no}")
        if self.resmi_gazete_tarihi:
            parts.append(f"RG. {self.resmi_gazete_tarihi}")
        return ", ".join(parts) if parts else self.id

    def __str__(self) -> str:
        return f"Decision({self.court_type.name}: {self.reference})"

    def __repr__(self) -> str:
        return self.__str__()


# ── Arama Modelleri ───────────────────────────────────────────────────────


class DateRange(BaseModel):
    """Tarih aralığı filtresi."""

    start: Optional[date] = None
    end: Optional[date] = None

    def to_iso_start(self) -> str:
        """Bedesten API formatı: '2024-01-01T00:00:00.000Z'"""
        if self.start:
            return f"{self.start.isoformat()}T00:00:00.000Z"
        return ""

    def to_iso_end(self) -> str:
        if self.end:
            return f"{self.end.isoformat()}T23:59:59.999Z"
        return ""

    def to_dd_mm_yyyy_start(self) -> str:
        """Danıştay / Emsal formatı: 'DD.MM.YYYY'"""
        if self.start:
            return self.start.strftime("%d.%m.%Y")
        return ""

    def to_dd_mm_yyyy_end(self) -> str:
        if self.end:
            return self.end.strftime("%d.%m.%Y")
        return ""


class SearchQuery(BaseModel):
    """Birleşik arama sorgusu — tüm arama parametrelerini taşır."""

    # Metin araması
    query: str = Field("", description="Arama metni")
    exact_phrase: bool = False
    semantic: bool = Field(False, description="Semantik (vektörel) arama yapılsın mı?")

    # Filtreler
    courts: list[CourtType] = Field(
        default_factory=lambda: [CourtType.YARGITAY, CourtType.DANISTAY],
        description="Aranacak mahkeme türleri"
    )
    chamber: Optional[str] = Field(None, description="Daire kısaltması (H1, D3...)")
    date_range: Optional[DateRange] = None

    # Esas / Karar no ile arama (İçtihat)
    esas_no: Optional[str] = None
    karar_no: Optional[str] = None

    # Mevzuat ile arama
    mevzuat_turu: Optional[str] = Field(None, description="Kanun, KHK, Yönetmelik vb.")
    kanun_no: Optional[str] = None

    # Recall için deterministik sorgu genişletme (Boolean-OR destekleyen
    # motorlarda etkin; diğerlerinde yok sayılır). Bkz. services/semantic/expansion.py
    expand: bool = Field(True, description="Hukuki eşanlam genişletmesi (query expansion) uygulansın mı?")

    # Sayfalama
    page: int = Field(1, ge=1)
    page_size: int = Field(10, ge=1, le=100)


class SearchResult(BaseModel):
    """Sayfalanmış arama sonucu container'ı."""

    decisions: list[Decision] = Field(default_factory=list)
    total_records: int = 0
    page: int = 1
    page_size: int = 10
    total_pages: int = 0
    courts_searched: list[CourtType] = Field(default_factory=list)

    # Hata durumları
    errors: dict[str, str] = Field(
        default_factory=dict,
        description="Court-specific hatalar: {'YARGITAY': 'Rate limit aşıldı'}"
    )

    @property
    def has_results(self) -> bool:
        return len(self.decisions) > 0

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0


# ── Sağlık Kontrolü ──────────────────────────────────────────────────────


class HealthStatus(BaseModel):
    """Bir API endpoint'inin sağlık durumu."""

    court_type: CourtType
    is_healthy: bool
    response_time_ms: Optional[float] = None
    error: Optional[str] = None
    checked_at: datetime = Field(default_factory=datetime.utcnow)
