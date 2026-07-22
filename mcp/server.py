"""Divan Interfaces — FastMCP Server.

MCP (Model Context Protocol) sunucusu, Claude veya diğer uyumlu LLM'lere
hukuki araştırma yetenekleri sağlar. yargi-mcp'nin işlevselliğini
Divan'ın yeni, modüler altyapısı üzerinden sunar.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastmcp import FastMCP
from pydantic import Field

from ..config import AppConfig
from ..core.enums import CourtType
from ..core.models import SearchQuery, DateRange
from ..clients.factory import CourtClientFactory
from ..services.search import UnifiedSearchService
from ..services.document import DocumentService
from ..infrastructure.cache import LRUMemoryCache

logger = logging.getLogger(__name__)

# ── Altyapı Hazırlığı ──
config = AppConfig()
cache = LRUMemoryCache(max_size=config.cache_max_size, default_ttl=config.cache_ttl)
client_factory = CourtClientFactory(config, cache)
search_service = UnifiedSearchService(client_factory)
document_service = DocumentService(client_factory)


# ── Sunucu Tanımı ──
app = FastMCP(
    name=config.mcp_server_name,
    version=config.mcp_server_version,
    instructions="""Türk Hukuk Araştırma Asistanı (Divan).
Bu sunucu, Yargıtay, Danıştay, Anayasa Mahkemesi ve diğer derece mahkemelerinin
içtihatlarına tek bir noktadan, birleşik ve asenkron erişim sağlar.

Arama yetenekleri:
- 'search_decisions' ile aynı anda birden fazla mahkemede arama yapın.
- 'get_decision_content' ile kararların tam Markdown metinlerini okuyun.
- Aramalarda 'query' parametresi tam cümle destekler.
- Geniş aramalarda mutlaka sayfalama ('page', 'page_size') kullanın.
"""
)


@app.tool()
async def search_decisions(
    query: str = Field(..., description="Arama metni (örn: 'işe iade', 'haksız fiil')"),
    courts: Optional[list[str]] = Field(
        None,
        description=(
            "Aranacak mahkeme/kurumlar. Geçerli değerler: YARGITAY, DANISTAY, "
            "ANAYASA_NORM, ANAYASA_BIREYSEL, YEREL_HUKUK, ISTINAF_HUKUK, KYB, EMSAL, "
            "MEVZUAT, BDDK, BTK, GIB, KIK, KVKK, REKABET, SAYISTAY, SIGORTA_TAHKIM, "
            "UYUSMAZLIK. Boş bırakılırsa yüksek yargı + emsal aranır (YARGITAY, "
            "DANISTAY, ANAYASA_NORM, ANAYASA_BIREYSEL, EMSAL). Uzman kurumlar "
            "(BDDK, KVKK, GIB vb.) ile mevzuat için ilgili değeri açıkça belirtin."
        )
    ),
    chamber: Optional[str] = Field(None, description="Daire veya kurul kısaltması (örn: 'H1', 'HGK', 'D3')"),
    esas_no: Optional[str] = Field(None, description="Esas numarası filtreleme (örn: '2023/123')"),
    karar_no: Optional[str] = Field(None, description="Karar numarası filtreleme (örn: '2023/456')"),
    date_start: Optional[str] = Field(None, description="Başlangıç tarihi (YYYY-MM-DD)"),
    date_end: Optional[str] = Field(None, description="Bitiş tarihi (YYYY-MM-DD)"),
    page: int = Field(1, ge=1, description="Sayfa numarası"),
    page_size: int = Field(10, ge=1, le=50, description="Sayfa başına kayıt sayısı"),
    expand: bool = Field(
        True,
        description=(
            "Hukuki eşanlam genişletmesi. True ise sorgu, resmi hukuki "
            "terimlerle otomatik genişletilir (örn: 'işten çıkarma' -> 'fesih', "
            "'iş akdinin feshi'), böylece farklı kelimelerle yazılmış ilgili "
            "kararlar da bulunur (recall). Tek istek, gecikme eklemez. Çok dar/"
            "spesifik terim aradığında kapatabilirsin."
        )
    ),
    semantic: bool = Field(
        False,
        description=(
            "True ise ilk 8 aday için kararın tam metninden sorgunun geçtiği "
            "paragraf ('snippet') çıkarılıp sonuca eklenir; böylece alaka düzeyini "
            "başlıktan değil gerçek bağlamdan değerlendirebilirsin. Sıralama sana "
            "bırakılır (snippet'leri oku, en alakalıyı seç). Yavaştır (~20-30s, "
            "tam metin indirir) — sadece alaka için bağlam gerektiğinde kullan."
        )
    )
) -> str:
    """Belirtilen kriterlere göre Türk mahkemelerinde içtihat araması yapar.
    
    Elde edilen sonuçlarda her bir kararın `id` değeri ve `court_type` değeri
    bulunacaktır. Tam metni okumak için bu iki değeri kullanarak
    `get_decision_content` aracını çağırın.
    """
    logger.info(f"MCP Tool 'search_decisions' called: query='{query}'")
    
    # Python direct call fallback for FieldInfo defaults
    from pydantic.fields import FieldInfo
    if isinstance(courts, FieldInfo): courts = None
    if isinstance(chamber, FieldInfo): chamber = None
    if isinstance(esas_no, FieldInfo): esas_no = None
    if isinstance(karar_no, FieldInfo): karar_no = None
    if isinstance(date_start, FieldInfo): date_start = None
    if isinstance(date_end, FieldInfo): date_end = None
    if isinstance(page, FieldInfo) or page is None: page = 1
    if isinstance(page_size, FieldInfo) or page_size is None: page_size = 10
    if isinstance(expand, FieldInfo) or expand is None: expand = True
    if isinstance(semantic, FieldInfo) or semantic is None: semantic = False
    
    # Enum dönüşümleri
    target_courts = []
    if courts:
        for c in courts:
            try:
                if c.upper() in CourtType.__members__:
                    target_courts.append(CourtType[c.upper()])
                else:
                    target_courts.append(CourtType(c.upper()))
            except ValueError:
                return f"Hata: Geçersiz mahkeme türü '{c}'"
    else:
        # Varsayılanlar
        target_courts = [
            CourtType.YARGITAY, CourtType.DANISTAY, 
            CourtType.ANAYASA_NORM, CourtType.ANAYASA_BIREYSEL,
            CourtType.EMSAL
        ]
        
    # Tarih dönüşümleri
    date_range = None
    if date_start or date_end:
        from datetime import date
        try:
            start_d = date.fromisoformat(date_start) if date_start else None
            end_d = date.fromisoformat(date_end) if date_end else None
            date_range = DateRange(start=start_d, end=end_d)
        except ValueError:
            return "Hata: Tarih formatı YYYY-MM-DD olmalıdır."

    search_query = SearchQuery(
        query=query,
        courts=target_courts,
        chamber=chamber,
        esas_no=esas_no,
        karar_no=karar_no,
        date_range=date_range,
        page=page,
        page_size=page_size,
        semantic=semantic,
        expand=expand
    )

    try:
        result = await search_service.search(search_query)
        import json
        
        compact_results = {
            "total_records": result.total_records,
            "page": result.page,
            "page_size": result.page_size,
            "courts_searched": [c.name for c in result.courts_searched],
            "errors": result.errors,
            "decisions": [
                {
                    "id": d.id,
                    "court": d.court_type.name,
                    "type": d.decision_type.name if d.decision_type else None,
                    "esas_no": d.esas_no,
                    "karar_no": d.karar_no,
                    "date": d.decision_date_str or (d.decision_date.isoformat() if d.decision_date else None),
                    "title": d.title,
                    "snippet": d.snippet,
                    "summary": (d.summary[:500] + "...") if d.summary and len(d.summary) > 500 else d.summary,
                    "chamber": d.chamber_name or d.chamber_code
                }
                for d in result.decisions
            ]
        }
        return json.dumps(compact_results, ensure_ascii=False)
    except Exception as e:
        logger.exception("Search error in MCP")
        return f"Arama sırasında beklenmeyen hata oluştu: {e}"


@app.tool()
async def get_decision_content(
    document_id: str = Field(..., description="Kararın benzersiz ID'si (arama sonucundan alınır)"),
    court_type: str = Field(..., description="Kararın ait olduğu mahkeme türü (örn: YARGITAY, ANAYASA_NORM)")
) -> str:
    """Bir içtihadın/kararın Markdown formatındaki tam metnini döndürür.
    
    Bu araç `search_decisions` aracından alınan `id` ve `court_type`
    bilgilerine ihtiyaç duyar.
    """
    logger.info(f"MCP Tool 'get_decision_content' called: id='{document_id}', court='{court_type}'")
    
    try:
        target_court = CourtType(court_type.upper())
    except ValueError:
        return f"Hata: Geçersiz mahkeme türü '{court_type}'"

    try:
        decision = await document_service.get_document(document_id, target_court)
        if decision.markdown_content:
            return decision.markdown_content
        return "Karar metni boş veya dönüştürülemedi."
    except Exception as e:
        logger.exception("Document fetch error in MCP")
        return f"Karar getirilirken hata oluştu: {e}"


# Sunucu başlatma hook'ları eklenebilir, şimdilik auto-run için if __name__ yeterli
if __name__ == "__main__":
    app.run()
