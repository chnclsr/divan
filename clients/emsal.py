"""Divan Clients — UYAP Emsal Kararlar client.

emsal.uyap.gov.tr üzerinden emsal karar araması ve belge getirme.
"""

from __future__ import annotations

import html as html_module
import logging
from typing import Any, Optional

from ..core.enums import CourtType, DecisionType
from ..core.models import Decision, SearchQuery, SearchResult
from ..core.exceptions import DocumentNotFoundError
from .base import BaseCourtClient

logger = logging.getLogger(__name__)


class EmsalClient(BaseCourtClient):
    """UYAP Emsal Kararlar API client.

    Endpoint: https://emsal.uyap.gov.tr
    Kapsam: Emsal kararlar (BAM, Yerel Mahkemeler)
    Protokol: REST JSON (POST/GET)
    """

    SEARCH_ENDPOINT = "/aramadetaylist"
    DOCUMENT_ENDPOINT = "/getDokuman"

    @property
    def court_type(self) -> CourtType:
        return CourtType.EMSAL

    @property
    def supported_courts(self) -> list[CourtType]:
        return [CourtType.EMSAL]

    @classmethod
    def _get_base_url(cls) -> str:
        return "https://emsal.uyap.gov.tr"

    @classmethod
    def _get_default_headers(cls) -> dict[str, str]:
        return {
            "Content-Type": "application/json; charset=UTF-8",
            "Accept": "application/json, text/plain, */*",
            "X-Requested-With": "XMLHttpRequest",
        }

    @classmethod
    def _get_ssl_verify(cls) -> bool:
        # UYAP sunucusu SSL sertifika sorunları yaşayabiliyor
        return False

    # ── Search ────────────────────────────────────────────────────────────

    async def _do_search(self, query: SearchQuery) -> SearchResult:
        """UYAP Emsal API'de arama yap."""
        # Emsal'in beklediği payload yapısı
        search_data: dict[str, Any] = {
            "arananKelime": query.query,
            "pageSize": query.page_size,
            "pageNumber": query.page,
            "siralama": "1",
            "siralamaDirection": "desc",
        }

        # Tarih filtreleri
        if query.date_range:
            if query.date_range.start:
                search_data["baslangicTarihi"] = query.date_range.to_dd_mm_yyyy_start()
            if query.date_range.end:
                search_data["bitisTarihi"] = query.date_range.to_dd_mm_yyyy_end()

        # Esas/Karar no filtreleri
        if query.esas_no:
            parts = query.esas_no.split("/")
            if len(parts) >= 1:
                search_data["esasYil"] = parts[0]
            if len(parts) >= 2:
                search_data["esasIlkSiraNo"] = parts[1]

        if query.karar_no:
            parts = query.karar_no.split("/")
            if len(parts) >= 1:
                search_data["kararYil"] = parts[0]
            if len(parts) >= 2:
                search_data["kararIlkSiraNo"] = parts[1]

        # Boş alanları temizle
        cleaned_data = {k: v for k, v in search_data.items() if v}
        payload = {"data": cleaned_data}

        logger.info(f"Emsal search: keyword='{query.query}', page={query.page}")
        response = await self._http.post(self.SEARCH_ENDPOINT, json=payload)
        data = response.json()

        return self._parse_search_response(data, query)

    def _parse_search_response(self, data: dict[str, Any], query: SearchQuery) -> SearchResult:
        """Emsal API yanıtını unified SearchResult'a dönüştür."""
        inner_data = data.get("data", {})
        raw_items = inner_data.get("data", []) if isinstance(inner_data, dict) else []
        total = inner_data.get("recordsTotal", 0) if isinstance(inner_data, dict) else 0

        decisions: list[Decision] = []
        for item in raw_items:
            decisions.append(self._raw_to_decision(item))

        total_pages = (total + query.page_size - 1) // query.page_size if total > 0 else 0

        return SearchResult(
            decisions=decisions,
            total_records=total,
            page=query.page,
            page_size=query.page_size,
            total_pages=total_pages,
            courts_searched=[CourtType.EMSAL],
        )

    def _raw_to_decision(self, item: dict[str, Any]) -> Decision:
        """Ham Emsal yanıtını Decision modeline normalize et."""
        doc_id = str(item.get("id", ""))
        esas_no_raw = item.get("esasNo", "")
        karar_no_raw = item.get("kararNo", "")
        daire = item.get("dpiMapiDaire", "") or item.get("birimAdi", "")
        tarih = item.get("kararTarihi", "")

        return Decision(
            id=doc_id,
            court_type=CourtType.EMSAL,
            decision_type=DecisionType.KARAR,
            esas_no=esas_no_raw if esas_no_raw else None,
            karar_no=karar_no_raw if karar_no_raw else None,
            chamber_name=daire,
            decision_date_str=tarih,
            source_url=f"{self._get_base_url()}{self.DOCUMENT_ENDPOINT}?id={doc_id}",
            document_url=f"{self._get_base_url()}{self.DOCUMENT_ENDPOINT}?id={doc_id}",
            raw_metadata=item,
        )

    # ── Document ──────────────────────────────────────────────────────────

    async def _do_get_document(self, document_id: str) -> Decision:
        """Emsal kararının tam metnini getir ve Markdown'a çevir."""
        endpoint = f"{self.DOCUMENT_ENDPOINT}?id={document_id}"

        logger.info(f"Emsal document fetch: ID={document_id}")
        response = await self._http.get(endpoint)

        # Emsal /getDokuman JSON döner: {"data": "<html>..."}
        data = response.json()
        html_content = data.get("data", "")

        if not html_content or not isinstance(html_content, str):
            raise DocumentNotFoundError(document_id)

        # HTML ön temizlik (Emsal'e özgü)
        cleaned_html = self._clean_emsal_html(html_content)
        markdown = await self._html_to_markdown(cleaned_html)

        return Decision(
            id=document_id,
            court_type=CourtType.EMSAL,
            markdown_content=markdown,
            source_url=f"{self._get_base_url()}{self.DOCUMENT_ENDPOINT}?id={document_id}",
        )

    @staticmethod
    def _clean_emsal_html(raw_html: str) -> str:
        """Emsal'in döndürdüğü HTML'deki kaçış karakterlerini temizle."""
        content = html_module.unescape(raw_html)
        content = content.replace('\\"', '"')
        content = content.replace("\\r\\n", "\n")
        content = content.replace("\\n", "\n")
        content = content.replace("\\t", "\t")
        return content
