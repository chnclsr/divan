"""Divan Interfaces — FastAPI REST API.

Dış uygulamaların Divan'ın arama yeteneklerini REST üzerinden 
kullanabilmesi için standart bir API sunar.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query, Path
from fastapi.responses import Response
from pydantic import BaseModel

from ..config import AppConfig
from ..core.enums import CourtType, ExportFormat
from ..core.models import SearchQuery, DateRange
from ..core.exceptions import DocumentNotFoundError
from ..clients.factory import CourtClientFactory
from ..services.search import UnifiedSearchService
from ..services.document import DocumentService
from ..services.export import ExportService
from ..infrastructure.cache import LRUMemoryCache

logger = logging.getLogger(__name__)

# ── Altyapı Hazırlığı ──
config = AppConfig()
cache = LRUMemoryCache(max_size=config.cache_max_size, default_ttl=config.cache_ttl)
client_factory = CourtClientFactory(config, cache)
search_service = UnifiedSearchService(client_factory)
document_service = DocumentService(client_factory)
export_service = ExportService()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Divan API başlatılıyor...")
    yield
    # Shutdown
    logger.info("Divan API kapatılıyor, kaynaklar temizleniyor...")
    await client_factory.close_all()


app = FastAPI(
    title=config.app_name,
    version=config.version,
    description="Türk Hukuk Araştırma REST API",
    lifespan=lifespan,
)


# ── Schemas ──
class SearchRequest(BaseModel):
    query: str
    courts: Optional[list[str]] = None
    chamber: Optional[str] = None
    esas_no: Optional[str] = None
    karar_no: Optional[str] = None
    date_start: Optional[str] = None
    date_end: Optional[str] = None
    page: int = 1
    page_size: int = 10


# ── Routes ──

@app.get("/api/v1/health")
async def health_check():
    """Tüm bağlı kurumların sağlık durumunu raporlar."""
    all_clients = client_factory.create_all()
    results = {}
    
    for name, client in all_clients.items():
        status = await client.health_check()
        results[name] = status.model_dump()
        
    return {"status": "ok", "components": results}


@app.post("/api/v1/search")
async def search_decisions(req: SearchRequest):
    """Gelişmiş karar araması yapar."""
    target_courts = []
    if req.courts:
        for c in req.courts:
            try:
                target_courts.append(CourtType(c.upper()))
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Geçersiz mahkeme türü: {c}")
    else:
        target_courts = [
            CourtType.YARGITAY, CourtType.DANISTAY, 
            CourtType.ANAYASA_NORM, CourtType.ANAYASA_BIREYSEL,
            CourtType.EMSAL
        ]
        
    date_range = None
    if req.date_start or req.date_end:
        from datetime import date
        try:
            start_d = date.fromisoformat(req.date_start) if req.date_start else None
            end_d = date.fromisoformat(req.date_end) if req.date_end else None
            date_range = DateRange(start=start_d, end=end_d)
        except ValueError:
            raise HTTPException(status_code=400, detail="Tarih formatı YYYY-MM-DD olmalıdır.")

    search_query = SearchQuery(
        query=req.query,
        courts=target_courts,
        chamber=req.chamber,
        esas_no=req.esas_no,
        karar_no=req.karar_no,
        date_range=date_range,
        page=req.page,
        page_size=req.page_size
    )

    try:
        result = await search_service.search(search_query)
        return result
    except Exception as e:
        logger.exception("API Search Error")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/decisions/{court_type}/{document_id}")
async def get_decision(
    court_type: str = Path(..., description="YARGITAY, DANISTAY, vs."),
    document_id: str = Path(...)
):
    """Belge ID'si ve Mahkeme Türü ile kararın detayını getirir."""
    try:
        target_court = CourtType(court_type.upper())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Geçersiz mahkeme türü: {court_type}")
        
    try:
        decision = await document_service.get_document(document_id, target_court)
        return decision
    except DocumentNotFoundError:
        raise HTTPException(status_code=404, detail="Karar bulunamadı.")
    except Exception as e:
        logger.exception("API Document Fetch Error")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/decisions/{court_type}/{document_id}/export")
async def export_decision(
    court_type: str,
    document_id: str,
    format: str = Query("markdown", description="markdown, json, docx")
):
    """Kararı belirtilen formatta dışa aktarır."""
    try:
        target_court = CourtType(court_type.upper())
        export_fmt = ExportFormat(format.lower())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Geçersiz format veya mahkeme: {e}")
        
    try:
        decision = await document_service.get_document(document_id, target_court)
        content = await export_service.export(decision, export_fmt)
        
        media_types = {
            ExportFormat.MARKDOWN: "text/markdown",
            ExportFormat.JSON: "application/json",
            ExportFormat.DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        }
        
        headers = {}
        if export_fmt == ExportFormat.DOCX:
            headers["Content-Disposition"] = f"attachment; filename={document_id}.docx"
            
        return Response(content=content, media_type=media_types[export_fmt], headers=headers)
        
    except DocumentNotFoundError:
        raise HTTPException(status_code=404, detail="Karar bulunamadı.")
    except Exception as e:
        logger.exception("API Export Error")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.api_host, port=config.api_port)
