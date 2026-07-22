"""KVKK (Kişisel Verileri Koruma Kurumu) Client for Divan."""

from typing import Optional
import re
from urllib.parse import urlparse
from pydantic import HttpUrl

from divan.core.models import Decision, CourtType
from divan.core.enums import DecisionType
from divan.clients.base_scraper import BaseScraperClient


class KvkkClient(BaseScraperClient):
    """KVKK Kararları araması yapan istemci."""

    @property
    def search_engine_type(self) -> str:
        return "brave"

    @property
    def search_domain(self) -> str:
        return "kvkk.gov.tr"

    @property
    def court_type(self) -> CourtType:
        return CourtType.KVKK

    def _build_search_query(self, user_query: str) -> str:
        base_query = 'site:kvkk.gov.tr "karar özeti"'
        if user_query.strip():
            return f"{base_query} {user_query.strip()}"
        return base_query

    def _extract_id_from_url(self, url: str) -> Optional[str]:
        try:
            parsed_url = urlparse(url)
            path_parts = parsed_url.path.strip('/').split('/')
            if len(path_parts) >= 3 and path_parts[0] == 'Icerik':
                return '/'.join(path_parts[1:])  # e.g., "7288/2021-1303"
        except Exception:
            pass
        return None

    def _parse_search_result(self, raw_result: dict, decision_id: str) -> Decision:
        title = raw_result.get("title", "")
        
        # Extract decision date (DD/MM/YYYY format)
        decision_date = None
        date_match = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', title)
        if date_match:
            decision_date = date_match.group(1)
            
        # Extract decision number (YYYY/XXXX format)
        decision_number = None
        number_match = re.search(r'(\d{4}/\d+)', title)
        if number_match:
            decision_number = number_match.group(1)
            
        return Decision(
            id=decision_id,
            court_type=CourtType.KVKK,
            decision_type=DecisionType.KURUL_KARARI,
            title=title,
            summary=raw_result.get("description", ""),
            decision_date_str=decision_date,
            karar_no=decision_number,
            raw_metadata=raw_result
        )

    def _get_document_url(self, document_id: str) -> str:
        return f"https://www.kvkk.gov.tr/Icerik/{document_id}"
