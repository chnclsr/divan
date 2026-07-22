"""GİB (Gelir İdaresi Başkanlığı) Özelge Client for Divan."""

from typing import Any, Optional
import math
import asyncio
from markitdown import MarkItDown

from divan.core.models import Decision, SearchQuery, SearchResult, HealthStatus, CourtType
from divan.core.enums import DecisionType
from divan.clients.base import BaseCourtClient


class GibClient(BaseCourtClient):
    """GİB Özelge (Mukteza) araması yapan istemci."""

    LIST_PATH = "/gibportal/mevzuat/ozelge/list"
    
    @classmethod
    def _get_base_url(cls) -> str:
        return "https://gib.gov.tr/api"
    
    @property
    def court_type(self) -> CourtType:
        return CourtType.GIB

    @property
    def supported_courts(self) -> set[CourtType]:
        return {CourtType.GIB}

    async def _do_search(self, query: SearchQuery) -> SearchResult:
        body: dict[str, Any] = {
            "status": 2,
            "deleted": False,
            "ktype": 99,
        }
        
        search_term = query.query.strip()
        if search_term:
            body["title"] = search_term
            body["kanunNo"] = search_term
            body["description"] = search_term
            
        if query.esas_no:
            body["ozelgeNo"] = query.esas_no.strip()
            
        if query.date_range:
            if query.date_range.start:
                body["ozelgeStartDate"] = query.date_range.start.isoformat()
            if query.date_range.end:
                body["ozelgeEndDate"] = query.date_range.end.isoformat()
                
        api_query = {
            "page": max(0, query.page - 1),
            "size": query.page_size,
            "sortFieldName": "ozelgeTarih",
            "sortType": "DESC"
        }
        
        try:
            response = await self.http_client.post(self.LIST_PATH, params=api_query, json=body)
            response.raise_for_status()
            payload = response.json()
            
            container = (payload or {}).get("resultContainer") or {}
            raw_items = container.get("content") or []
            
            decisions = []
            for item in raw_items:
                dec = Decision(
                    id=str(item.get("id", "")),
                    court_type=CourtType.GIB,
                    decision_type=DecisionType.OZELGE,
                    title=item.get("title", ""),
                    esas_no=item.get("ozelgeNo", ""),
                    decision_date_str=item.get("ozelgeTarih", ""),
                    kanun_no=item.get("kanunNo", ""),
                    raw_metadata=item
                )
                decisions.append(dec)
                
            total = int(container.get("totalElements") or len(decisions))
            
            return SearchResult(
                decisions=decisions,
                total_records=total,
                page=query.page,
                page_size=query.page_size,
                courts_searched=[CourtType.GIB]
            )
        except Exception as e:
            raise Exception(f"GIB arama hatası: {e}")

    async def _do_get_document(self, document_id: str) -> Decision:
        body = {
            "status": 2,
            "deleted": False,
            "ktype": 99,
            "id": int(document_id),
        }
        query = {"page": 0, "size": 1}
        
        try:
            response = await self.http_client.post(self.LIST_PATH, params=query, json=body)
            response.raise_for_status()
            payload = response.json()
            
            container = (payload or {}).get("resultContainer") or {}
            content = container.get("content") or []
            if not content:
                raise ValueError("Özelge bulunamadı.")
                
            item = content[0]
            description_html = item.get("description", "")
            
            md_converter = MarkItDown(enable_plugins=False)
            result = await asyncio.to_thread(md_converter.convert_stream, description_html.encode("utf-8"), file_extension=".html")
            
            header = f"# {item.get('title', '')}\n**Sayı:** {item.get('ozelgeNo', '')}\n**Tarih:** {item.get('ozelgeTarih', '')}\n\n---\n\n"
            markdown_content = header + result.text_content
            
            return Decision(
                id=document_id,
                court_type=CourtType.GIB,
                decision_type=DecisionType.OZELGE,
                title=item.get("title", ""),
                markdown_content=markdown_content,
                raw_metadata=item
            )
            
        except Exception as e:
            raise Exception(f"GIB belge getirme hatası: {e}")
