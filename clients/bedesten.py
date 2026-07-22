"""Divan Clients — Bedesten (Adalet Bakanlığı) client.

Bedesten API, 5 farklı mahkeme türünü tek endpoint'ten sunar:
Yargıtay, Danıştay, Yerel Hukuk, İstinaf Hukuk ve KYB.
Bu, Divan'ın en kapsamlı client'ıdır.
"""

from __future__ import annotations

import base64
import logging
from datetime import date as date_type
from typing import Any, Optional

from ..core.enums import CourtType, DecisionType, resolve_chamber
from ..core.models import Decision, SearchQuery, SearchResult
from ..core.exceptions import DocumentNotFoundError, MalformedResponseError
from .base import BaseCourtClient

logger = logging.getLogger(__name__)

# Bedesten CourtType → API itemType eşleştirmesi
_COURT_TO_ITEM_TYPE: dict[CourtType, str] = {
    CourtType.YARGITAY: "YARGITAYKARARI",
    CourtType.DANISTAY: "DANISTAYKARAR",
    CourtType.YEREL_HUKUK: "YERELHUKUK",
    CourtType.ISTINAF_HUKUK: "ISTINAFHUKUK",
    CourtType.KYB: "KYB",
}


class BedestanClient(BaseCourtClient):
    """Adalet Bakanlığı Bedesten API client.

    Endpoint: https://bedesten.adalet.gov.tr
    Kapsam: Yargıtay, Danıştay, Yerel Hukuk, İstinaf Hukuk, KYB
    Protokol: REST JSON (POST)

    Supports:
        - Multi-court search (tek istekte birden fazla mahkeme)
        - 79 daire/kurul filtreleme
        - ISO 8601 tarih aralığı filtreleme
        - Tam cümle arama (çift tırnak)
        - Base64 encoded HTML/PDF belge getirme
    """

    SEARCH_ENDPOINT = "/emsal-karar/searchDocuments"
    DOCUMENT_ENDPOINT = "/emsal-karar/getDocumentContent"

    @property
    def court_type(self) -> CourtType:
        return CourtType.YARGITAY  # Birincil kimlik

    @property
    def supports_boolean_or(self) -> bool:
        return True  # Bedesten Solr altyapısı Boolean OR destekler

    @property
    def supported_courts(self) -> list[CourtType]:
        return [
            CourtType.YARGITAY,
            CourtType.DANISTAY,
            CourtType.YEREL_HUKUK,
            CourtType.ISTINAF_HUKUK,
            CourtType.KYB,
        ]

    @classmethod
    def _get_base_url(cls) -> str:
        return "https://bedesten.adalet.gov.tr"

    @classmethod
    def _get_default_headers(cls) -> dict[str, str]:
        return {
            "Accept": "*/*",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
            "AdaletApplicationName": "UyapMevzuat",
            "Content-Type": "application/json; charset=utf-8",
            "Origin": "https://mevzuat.adalet.gov.tr",
            "Referer": "https://mevzuat.adalet.gov.tr/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/137.0.0.0 Safari/537.36"
            ),
        }

    # ── Search ────────────────────────────────────────────────────────────

    async def _do_search(self, query: SearchQuery) -> SearchResult:
        """Bedesten API'de arama yap."""
        # Court type listesi oluştur
        item_types = []
        for court in query.courts:
            if court in _COURT_TO_ITEM_TYPE:
                item_types.append(_COURT_TO_ITEM_TYPE[court])
        if not item_types:
            item_types = ["YARGITAYKARARI", "DANISTAYKARAR"]

        # Daire filtresi
        birim_adi = ""
        if query.chamber:
            birim_adi = resolve_chamber(query.chamber)

        # Tarih filtreleri
        karar_tarihi_start = ""
        karar_tarihi_end = ""
        if query.date_range:
            karar_tarihi_start = query.date_range.to_iso_start()
            karar_tarihi_end = query.date_range.to_iso_end()

        # API payload data
        data_payload = {
            "pageSize": query.page_size,
            "pageNumber": query.page,
            "itemTypeList": item_types,
            "phrase": query.query,
            "kararTarihiStart": karar_tarihi_start or None,
            "kararTarihiEnd": karar_tarihi_end or None,
        }

        # Eğer arama kelimesi varsa Solr default relevance sort kullansın, yoksa tarihe göre sıralasın
        if not query.query:
            data_payload["sortFields"] = ["KARAR_TARIHI"]
            data_payload["sortDirection"] = "desc"

        # birimAdi boş string ise gönderme
        if birim_adi:
            data_payload["birimAdi"] = birim_adi

        # Null alanları temizle
        cleaned_data = {k: v for k, v in data_payload.items() if v is not None}

        payload = {
            "data": cleaned_data,
            "applicationName": "UyapMevzuat",
            "paging": True,
        }

        logger.info(
            f"Bedesten search: phrase='{query.query}', courts={item_types}, "
            f"chamber='{birim_adi}', page={query.page}"
        )

        response = await self._http.post(self.SEARCH_ENDPOINT, json=payload)
        data = response.json()

        return self._parse_search_response(data, query)

    def _parse_search_response(self, data: dict[str, Any], query: SearchQuery) -> SearchResult:
        """API yanıtını unified SearchResult'a dönüştür."""
        response_data = data.get("data")
        if not response_data:
            return SearchResult(
                page=query.page,
                page_size=query.page_size,
                courts_searched=query.courts,
            )

        raw_decisions = response_data.get("emsalKararList", [])
        total = response_data.get("total", 0)

        decisions: list[Decision] = []
        for raw in raw_decisions:
            decisions.append(self._raw_to_decision(raw))

        total_pages = (total + query.page_size - 1) // query.page_size if total > 0 else 0

        return SearchResult(
            decisions=decisions,
            total_records=total,
            page=query.page,
            page_size=query.page_size,
            total_pages=total_pages,
            courts_searched=query.courts,
        )

    def _raw_to_decision(self, raw: dict[str, Any]) -> Decision:
        """Ham Bedesten API yanıtını Decision modeline normalize et."""
        # itemType bilgisini CourtType'a çevir
        item_type_name = ""
        item_type_data = raw.get("itemType", {})
        if isinstance(item_type_data, dict):
            item_type_name = item_type_data.get("name", "")

        court_type = CourtType.YARGITAY  # varsayılan
        for ct, api_name in _COURT_TO_ITEM_TYPE.items():
            if api_name == item_type_name:
                court_type = ct
                break

        # Tarih parse
        decision_date = None
        date_str = raw.get("kararTarihiStr", "")
        if date_str:
            try:
                parts = date_str.split(".")
                if len(parts) == 3:
                    decision_date = date_type(
                        int(parts[2]), int(parts[1]), int(parts[0])
                    )
            except (ValueError, IndexError):
                pass

        document_id = str(raw.get("documentId", ""))

        return Decision(
            id=document_id,
            court_type=court_type,
            decision_type=DecisionType.KARAR,
            esas_no=raw.get("esasNo"),
            karar_no=raw.get("kararNo"),
            esas_yil=raw.get("esasNoYil"),
            esas_sira=raw.get("esasNoSira"),
            karar_yil=raw.get("kararNoYil"),
            karar_sira=raw.get("kararNoSira"),
            chamber_name=raw.get("birimAdi"),
            decision_date=decision_date,
            decision_date_str=date_str,
            source_url=f"https://mevzuat.adalet.gov.tr/ictihat/{document_id}",
            raw_metadata=raw,
        )

    # ── Document ──────────────────────────────────────────────────────────

    async def _do_get_document(self, document_id: str) -> Decision:
        """Bedesten API'den belge getir ve Markdown'a çevir."""
        payload = {
            "data": {"documentId": document_id},
            "applicationName": "UyapMevzuat",
        }

        logger.info(f"Bedesten document fetch: ID={document_id}")
        response = await self._http.post(self.DOCUMENT_ENDPOINT, json=payload)
        data = response.json()

        doc_data = data.get("data")
        if not doc_data or not doc_data.get("content"):
            raise DocumentNotFoundError(document_id)

        # Base64 decode
        try:
            content_bytes = base64.b64decode(doc_data["content"])
        except Exception as e:
            raise MalformedResponseError(
                f"Base64 decode hatası (ID: {document_id}): {e}", cause=e
            ) from e

        mime_type = doc_data.get("mimeType", "text/html")

        # İçeriği Markdown'a çevir
        if mime_type == "text/html":
            html_content = content_bytes.decode("utf-8")
            markdown = await self._html_to_markdown(html_content)
        elif mime_type == "application/pdf":
            markdown = await self._pdf_to_markdown(content_bytes)
        else:
            markdown = f"Desteklenmeyen içerik türü: {mime_type}"

        return Decision(
            id=document_id,
            court_type=CourtType.YARGITAY,  # Belge türünden anlaşılamaz
            markdown_content=markdown,
            source_url=f"https://mevzuat.adalet.gov.tr/ictihat/{document_id}",
            raw_metadata={"mime_type": mime_type},
        )
