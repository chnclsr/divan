# Yeni Bir Mahkeme İstemcisi (Client) Eklemek

Divan platformuna yeni bir mahkeme, kurum veya veri sağlayıcı eklemek, modüler mimari sayesinde oldukça kolaydır. 

Bütün altyapı ihtiyaçları (Rate Limiter, Circuit Breaker, Cache, HTTP Hata Yakalama, Retries) `BaseCourtClient` sınıfı tarafından yönetilir. Sizin tek yapmanız gereken sisteme **yeni kurumu tanıtmak** ve API'nin **nasıl arama yapıp nasıl belge indireceğini** tanımlamaktır.

## Adım Adım Rehber

Örnek olarak hayali bir kurum olan `REKABET` (Rekabet Kurumu) için bir istemci geliştirelim.

### Adım 1: Kurumu Sisteme Tanıtmak
Yeni kurumu `core/enums.py` içindeki `CourtType` enum'una ekleyin.

```python
# divan/core/enums.py

class CourtType(str, Enum):
    # ... mevcut kurumlar
    REKABET = "REKABET"  # Yeni kurum eklendi
```

### Adım 2: İstemci (Client) Sınıfını Oluşturmak
`clients/rekabet.py` adında yeni bir dosya oluşturun ve `BaseCourtClient`'tan türetin.

Sınıfta zorunlu olarak implemente etmeniz (override etmeniz) gereken **4 temel bileşen** vardır:
1. Kurum tipleri ve API adresi bilgileri (`court_type`, `supported_courts`, `_get_base_url`)
2. `_do_search` metodu (Arama yapar)
3. `_do_get_document` metodu (Belge getirir)

```python
# divan/clients/rekabet.py

from typing import Any
from ..core.enums import CourtType, DecisionType
from ..core.models import Decision, SearchQuery, SearchResult
from .base import BaseCourtClient

class RekabetClient(BaseCourtClient):
    
    @property
    def court_type(self) -> CourtType:
        return CourtType.REKABET

    @property
    def supported_courts(self) -> list[CourtType]:
        return [CourtType.REKABET]

    @classmethod
    def _get_base_url(cls) -> str:
        return "https://api.rekabet.gov.tr"

    @classmethod
    def _get_default_headers(cls) -> dict[str, str]:
        # Kuruma özel header'lar buraya (örn: API_KEY gerekiyorsa)
        return {
            "Content-Type": "application/json",
            "User-Agent": "Divan-Bot"
        }

    async def _do_search(self, query: SearchQuery) -> SearchResult:
        # API'ye nasıl istek atılacağını tanımlıyoruz.
        # self._http nesnesi (ResilientHttpClient) tüm hata yakalama ve backoff'u kendisi yapar.
        payload = {
            "q": query.query,
            "limit": query.page_size,
            "offset": (query.page - 1) * query.page_size
        }
        
        response = await self._http.get("/v1/search", params=payload)
        data = response.json()
        
        # Gelen veriyi (data) okuyup bizim standart Decision modelimize çevirmelisiniz.
        decisions = []
        for item in data.get("results", []):
            decision = Decision(
                id=str(item["id"]),
                court_type=CourtType.REKABET,
                esas_no=item.get("dosya_no"),
                karar_no=item.get("karar_no"),
                chamber_name="Rekabet Kurulu",
                decision_date_str=item.get("tarih"),
                source_url=f"https://rekabet.gov.tr/karar/{item['id']}"
            )
            decisions.append(decision)
            
        return SearchResult(
            decisions=decisions,
            total_records=data.get("total", 0),
            page=query.page,
            page_size=query.page_size,
            courts_searched=[CourtType.REKABET]
        )

    async def _do_get_document(self, document_id: str) -> Decision:
        # Kararın içeriğini API'den indirip Decision'a doldurun.
        response = await self._http.get(f"/v1/kararlar/{document_id}")
        data = response.json()
        
        # EĞER HTML GELİYORSA, OTOMATİK MARKDOWN ÇEVİRİSİNİ KULLANIN:
        html_content = data.get("html", "")
        markdown = await self._html_to_markdown(html_content)
        
        # EĞER BASE64 PDF GELİYORSA:
        # pdf_bytes = base64.b64decode(data["pdf"])
        # markdown = await self._pdf_to_markdown(pdf_bytes)

        return Decision(
            id=document_id,
            court_type=CourtType.REKABET,
            markdown_content=markdown,
            source_url=f"https://rekabet.gov.tr/karar/{document_id}"
        )
```

### Adım 3: Factory'ye Kaydetmek
Yazdığınız istemciyi sistemin (servislerin, API'nin ve CLI'ın) bulabilmesi için `CourtClientFactory` içine kaydetmelisiniz.

```python
# divan/clients/factory.py dosyasında `create` metodunu bulun:

from .rekabet import RekabetClient # <--- Import edin

def create(self, court_type: CourtType) -> ICourtClient:
    # ... mevcut kodlar ...
    
    if court_type == CourtType.REKABET:
        key = "rekabet"
        if key not in self._clients:
            self._clients[key] = RekabetClient(
                config=self._config,
                rate_limiter=self._get_rate_limiter("rekabet"),
                circuit_breaker=self._get_circuit_breaker("rekabet"),
                cache=self._cache,
            )
        return self._clients[key]
```

### İşte Bu Kadar!
Artık yeni Rekabet Kurumu istemciniz aktif. 
Siz hiçbir ekstra kod yazmadan şunlar otomatik olarak gerçekleşecektir:
1. `divan search "google" --court REKABET` CLI komutu çalışır hale gelir.
2. FastAPI'den `/api/v1/search` endpoint'ine `{ "courts": ["REKABET"] }` atılırsa otomatik bu sınıf tetiklenir.
3. Rekabet Kurumu API'si 429 Rate Limit verirse veya çökerse, sizin istemciniz altyapıdan gelen Circuit Breaker sayesinde otomatik dondurulup sistemi koruyacaktır.
4. Çekilen kararlar otomatik olarak bellek içi önbelleğe (Cache) alınır.
