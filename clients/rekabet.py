"""Rekabet Kurumu Client for Divan."""

from typing import Optional
import re
from divan.core.models import Decision, CourtType
from divan.core.enums import DecisionType
from divan.clients.base_scraper import BaseScraperClient


class RekabetClient(BaseScraperClient):
    """Rekabet Kurumu Kararları araması yapan istemci."""

    @property
    def search_engine_type(self) -> str:
        return "tavily"

    @property
    def search_domain(self) -> str:
        return "rekabet.gov.tr"

    @property
    def court_type(self) -> CourtType:
        return CourtType.REKABET

    def _build_search_query(self, user_query: str) -> str:
        return user_query

    def _extract_id_from_url(self, url: str) -> Optional[str]:
        # Rekabet Kurumu document IDs are usually GUIDs or filenames in the URL
        match = re.search(r'Dosya/([^/]+\.pdf)', url, re.IGNORECASE)
        if match:
            return match.group(1)
        match = re.search(r'Karar/([^/]+)', url, re.IGNORECASE)
        if match:
            return match.group(1)
        return "UNKNOWN_ID"

    def _parse_search_result(self, raw_result: dict, decision_id: str) -> Decision:
        return Decision(
            id=decision_id,
            court_type=CourtType.REKABET,
            decision_type=DecisionType.KURUL_KARARI,
            title=raw_result.get("title", "").replace("[PDF]", "").strip(),
            summary=raw_result.get("content", "")[:500],
            raw_metadata=raw_result
        )

    def _get_document_url(self, document_id: str) -> str:
        if document_id.endswith(".pdf"):
            return f"https://www.rekabet.gov.tr/Dosya/{document_id}"
        return f"https://www.rekabet.gov.tr/Karar/{document_id}"