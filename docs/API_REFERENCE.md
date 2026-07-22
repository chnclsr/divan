# Divan — API ve Komut Referansı

## 1. REST API (FastAPI) Referansı

Divan, dış uygulamaların entegre olabilmesi için Swagger destekli bir FastAPI sunucusu barındırır.
Sunucuyu başlatmak için terminalden `uvicorn divan.api.server:app --reload` komutunu çalıştırabilirsiniz. (Varsayılan olarak `http://127.0.0.1:8000` adresinde başlar).

*Swagger dökümantasyonunu `http://127.0.0.1:8000/docs` adresinde bulabilirsiniz.*

### `GET /api/v1/health`
Sisteme bağlı olan tüm mahkeme istemcilerinin (Bedesten, AYM, Emsal) o anki sağlık (ulaşılabilirlik) durumunu ve gecikme sürelerini (ping) döner.

### `POST /api/v1/search`
Gelişmiş içtihat/karar araması yapar. `courts` parametresi verilmezse desteklenen tüm kurumlarda paralel arama yapar.

**Örnek JSON İsteği:**
```json
{
  "query": "işe iade davası",
  "courts": ["YARGITAY", "DANISTAY"],
  "page": 1,
  "page_size": 10
}
```

### `GET /api/v1/decisions/{court_type}/{document_id}`
Bir kararın detaylı referans bilgilerini ve Markdown formatına dönüştürülmüş tam metnini döndürür. Arama sonuçlarında dönen `id` ve `court_type` alanları kullanılmalıdır.

### `GET /api/v1/decisions/{court_type}/{document_id}/export?format={format}`
Kararı belirtilen formatta indirir. (Tarayıcıda dosya indirme tetikler).
Desteklenen formatlar: `markdown`, `json`, `docx`.

---

## 2. MCP Araçları (Tools) Referansı

Claude (veya desteklenen diğer LLM istemcileri) sisteme bağlandığında LLM'in kullanımına aşağıdaki fonksiyonlar açılır. LLM, dilediği gibi parametre atayarak sunucuda arama yaptırabilir.

### `search_decisions`
- **query** *(string, zorunlu)*: Arama metni.
- **courts** *(array of string, opsiyonel)*: Hangi kurumlarda aranacağı. Boşsa tümü. (Örn: `["YARGITAY", "ANAYASA_NORM"]`)
- **chamber** *(string, opsiyonel)*: Daire veya kurul filtresi. Sadece kısaltma (Örn: `H1`, `CGK`, `D3`).
- **esas_no** / **karar_no** *(string, opsiyonel)*: (Örn: `2024/123`).
- **date_start** / **date_end** *(string, opsiyonel)*: `YYYY-MM-DD` formatında.
- **page** / **page_size** *(integer)*: Sayfalama.

### `get_decision_content`
LLM, kararı bulduktan sonra metnin tamamını analiz etmek isterse bu aracı çağırarak tam Markdown metnini kendi Context'ine çeker.
- **document_id** *(string, zorunlu)*: Kararın ID'si.
- **court_type** *(string, zorunlu)*: Kararın hangi mahkemeye ait olduğu.

---

## 3. Komut Satırı (CLI) Referansı

Terminal üzerinden, Python betikleri yazmak zorunda kalmadan tüm özelliklere erişebilirsiniz.

### `divan search`
Arama yapmak için kullanılır.
```bash
# Temel kullanım (Tüm kurumlarda arar)
divan search "kıdem tazminatı"

# Sadece belirli bir kurumda aramak (Örn: ANAYASA_BIREYSEL)
divan search "ifade özgürlüğü" --court ANAYASA_BIREYSEL

# İkinci sayfayı getirmek
divan search "kıdem tazminatı" --page 2
```

### `divan get`
Belge okumak ve dışa aktarmak için kullanılır.
```bash
# Kararın metnini (Markdown olarak render edilip) terminale basar
divan get 20241098 YARGITAY

# Kararı Word dosyası (DOCX) olarak bulunduğunuz klasöre kaydeder
divan get 20241098 YARGITAY --export docx

# Kararı JSON olarak kaydeder
divan get 20241098 YARGITAY --export json
```
