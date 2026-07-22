"""Mevzuat (Legislation) Client for Divan.

Uses the Bedesten REST API for fetching laws, decrees, regulations, etc.,
providing a unified interface compatible with the Divan architecture.
"""

from typing import Optional, Any
import base64
import asyncio

from divan.core.models import Decision, SearchQuery, SearchResult, HealthStatus, CourtType
from divan.core.enums import DecisionType
from divan.clients.base import BaseCourtClient
from markitdown import MarkItDown

import logging

logger = logging.getLogger(__name__)


class MevzuatClient(BaseCourtClient):
    """Bedesten API üzerinden mevzuat araması yapan istemci."""

    SEARCH_ENDPOINT = "/emsal-karar/searchDocuments"
    DOCUMENT_ENDPOINT = "/emsal-karar/getDocumentContent"

    @classmethod
    def _get_base_url(cls) -> str:
        return "https://bedesten.adalet.gov.tr"

    @property
    def court_type(self) -> CourtType:
        return CourtType.MEVZUAT

    @property
    def supported_courts(self) -> set[CourtType]:
        return {CourtType.MEVZUAT}

    async def _do_search(self, query: SearchQuery) -> SearchResult:
        """Mevzuat araması yapar."""
        payload: dict[str, Any] = {
            "page": query.page,
            "limit": query.page_size,
            "data": {
                "phrase": query.query,
                "isExactPhrase": query.exact_phrase,
                "kurumAdi": "MEVZUAT",
                "arananAlan": ["TUMU"],
                # Mevzuat specific mappings if provided in query model:
                "kanunNo": query.kanun_no if hasattr(query, "kanun_no") else "",
                "mevzuatTur": query.mevzuat_turu if hasattr(query, "mevzuat_turu") else "",
            }
        }

        # Clear empty strings from payload data to match Bedesten requirements
        payload["data"] = {k: v for k, v in payload["data"].items() if v}

        try:
            response = await self.http_client.post(self.SEARCH_ENDPOINT, json=payload)
            data = response.json()
            
            # Map to unified `Decision` model
            decisions = []
            results = data.get("data", [])
            for item in results:
                decision = Decision(
                    id=str(item.get("documentId", "")),
                    court_type=CourtType.MEVZUAT,
                    decision_type=DecisionType.MEVZUAT,
                    title=item.get("mevzuatAd", "İsimsiz Mevzuat"),
                    kanun_no=str(item.get("kanunNo", "")),
                    mevzuat_turu=item.get("mevzuatTur", ""),
                    resmi_gazete_tarihi=item.get("rgTarihi", ""),
                    resmi_gazete_sayisi=str(item.get("rgSayisi", "")),
                    summary=item.get("mevzuatAd", ""),
                    raw_metadata=item,
                )
                decisions.append(decision)

            return SearchResult(
                decisions=decisions,
                total_records=data.get("total", len(decisions)),
                page=query.page,
                page_size=query.page_size,
                courts_searched=[CourtType.MEVZUAT],
            )

        except Exception as e:
            logger.error(f"Mevzuat arama hatası: {e}")
            raise

    async def _do_get_document(self, document_id: str) -> Decision:
        """Belge içeriğini Bedesten'den Markdown olarak getirir."""
        payload = {
            "data": {
                "documentId": document_id
            }
        }

        try:
            response = await self.http_client.post(self.DOCUMENT_ENDPOINT, json=payload)
            data = response.json()
            
            doc_data = data.get("data", {})
            if not doc_data:
                raise ValueError("Belge içeriği bulunamadı.")
            
            content_b64 = doc_data.get("content", "")
            mime_type = doc_data.get("mimeType", "")
            
            content_bytes = base64.b64decode(content_b64)
            
            md_converter = MarkItDown()
            if mime_type == "application/pdf":
                result = md_converter.convert_stream(content_bytes, file_extension=".pdf")
            else:
                result = md_converter.convert_stream(content_bytes, file_extension=".html")
            
            markdown_content = result.text_content
            
            # Create a decision wrapper
            return Decision(
                id=document_id,
                court_type=CourtType.MEVZUAT,
                markdown_content=markdown_content,
                raw_metadata=doc_data
            )
            
        except Exception as e:
            logger.error(f"Mevzuat belge getirme hatası: {e}")
            raise
