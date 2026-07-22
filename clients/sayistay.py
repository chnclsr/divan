"""Sayıştay Client for Divan."""

from typing import Optional
import re
from divan.core.models import Decision, CourtType
from divan.core.enums import DecisionType
from divan.clients.base_scraper import BaseScraperClient


class SayistayClient(BaseScraperClient):
    """Sayıştay Kararları araması yapan istemci."""

    @property
    def search_engine_type(self) -> str:
        return "brave"

    @property
    def search_domain(self) -> str:
        return "sayistay.gov.tr"

    @property
    def court_type(self) -> CourtType:
        return CourtType.SAYISTAY

    def _build_search_query(self, user_query: str) -> str:
        return f"site:sayistay.gov.tr {user_query}"

    def _extract_id_from_url(self, url: str) -> Optional[str]:
        # Example: https://www.sayistay.gov.tr/KararlarGenelKurul/Detay/1234
        match = re.search(r'Detay/(\d+)', url, re.IGNORECASE)
        if match:
            return match.group(1)
        return "UNKNOWN_ID"

    def _parse_search_result(self, raw_result: dict, decision_id: str) -> Decision:
        return Decision(
            id=decision_id,
            court_type=CourtType.SAYISTAY,
            decision_type=DecisionType.KARAR,
            title=raw_result.get("title", "").replace("[PDF]", "").strip(),
            summary=raw_result.get("description", "")[:500],
            raw_metadata=raw_result
        )

    def _get_document_url(self, document_id: str) -> str:
        # We will default to Genel Kurul if not known from search
        return f"https://www.sayistay.gov.tr/KararlarGenelKurul/Detay/{document_id}"