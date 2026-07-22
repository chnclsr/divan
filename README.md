<div align="center">
  <h1>Divan</h1>
  <p><b>Modüler Türk Hukuk Araştırma Platformu & MCP Sunucusu</b></p>
  <p>
    <a href="https://img.shields.io/badge/python-3.9+-blue.svg"><img src="https://img.shields.io/badge/python-3.9+-blue.svg" alt="Python 3.9+"></a>
    <a href="https://img.shields.io/badge/architecture-SOLID-success.svg"><img src="https://img.shields.io/badge/architecture-SOLID-success.svg" alt="SOLID Architecture"></a>
    <a href="https://img.shields.io/badge/interface-MCP%20%7C%20REST%20%7C%20CLI-lightgrey"><img src="https://img.shields.io/badge/interface-MCP%20%7C%20REST%20%7C%20CLI-lightgrey" alt="Interfaces"></a>
  </p>
  <p>
    <a href="#özellikler">Özellikler</a> • 
    <a href="#kurulum">Kurulum</a> • 
    <a href="#mcp-sunucusu-olarak-kullanım">MCP</a> • 
    <a href="#cli-kullanımı">CLI</a> • 
    <a href="#rest-api">REST API</a> •
    <a href="./docs/ARCHITECTURE.md">Mimari</a>
  </p>
  <p>
    <i>Read this in other languages: <a href="README.en.md">English</a></i>
  </p>
</div>

---

Divan; Türkiye'deki farklı yüksek yargı ve derece mahkemelerinin (Yargıtay, Danıştay, Anayasa Mahkemesi, BAM, Yerel Mahkemeler vb.) dağınık içtihat veritabanlarına tek bir noktadan, asenkron ve hataya dayanıklı (resilient) bir şekilde erişim sağlayan bir sistemdir.

Dayanıklılık desenleri (Circuit Breaker, Token Bucket Rate Limiter, LRU In-Memory Cache) ve SOLID prensiplerine uygun, katmanlı bir mimariye sahiptir. Büyük Dil Modelleri (LLM) ile entegre çalışabilmesi için **MCP (Model Context Protocol)** standardını destekler.

## Özellikler

*   **Ortak Veri Modeli:** Hangi kaynaktan gelirse gelsin, tüm kararlar tek tip bir `Decision` modeline dönüştürülür.
*   **Eşzamanlı (Concurrent) Arama:** Tek bir sorgu ile `asyncio` kullanarak aynı anda Yargıtay, Danıştay, AYM ve UYAP Emsal'de arama yapıp sonuçları birleştirir.
*   **Hata Toleransı ve Performans Altyapısı:**
    *   **Circuit Breaker (Devre Kesici):** UYAP veya diğer kurum sunucularında kesinti olması durumunda istek göndermeyi durdurarak gereksiz beklemeleri engeller.
    *   **Token Bucket Rate Limiter:** Kurum API'lerinin limitlerini aşmamak amacıyla akıllı hız sınırlaması yapar. HTTP 429 alındığında kendini otomatik olarak belirli bir süre askıya alır.
    *   **In-Memory Caching (Bellek İçi Önbellek):** Mükerrer aramaların ve belge indirmelerin zaman/kaynak tüketmesini engellemek için TTL destekli bellek içi LRU önbellekleme sunar.
*   **Çoklu Arayüz:** MCP Sunucusu (Claude entegrasyonu), REST API (FastAPI) ve Terminal (CLI).
*   **Otomatik Çeviri:** Kurumlardan dönen HTML veya Base64-PDF belgeleri, LLM'lerin en iyi anladığı formata (Markdown) anında çevirir (`MarkItDown` entegrasyonu). Dilerseniz `.docx` formatında dışa aktarabilirsiniz.

## Kurulum

Sistemin çalışması için Python 3.9+ gereklidir. Proje dizininde aşağıdaki komutu çalıştırarak tüm bağımlılıkları ve Divan CLI araçlarını kurabilirsiniz:

```bash
# Proje dizininde
pip install -e .
```

> **Not:** Divan, yapılandırma için `AppConfig` kullanır. İstenirse `.env` dosyasıyla veya ortam değişkenleri ile (`DIVAN_HTTP_TIMEOUT=30` gibi) ayarlar ezilebilir.

## MCP Sunucusu Olarak Kullanım

Divan, LLM'lerin içtihat araştırması yapabilmesi için yerleşik bir FastMCP sunucusu ile gelir.

Sunucuyu manuel olarak başlatmak için:
```bash
divan-mcp
```

### Claude Desktop Entegrasyonu
Claude'un bu sunucuya erişebilmesi için `claude_desktop_config.json` dosyanıza şu şekilde ekleyin:
- **Windows Konumu:** `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS Konumu:** `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "divan": {
      "command": "divan-mcp"
    }
  }
}
```

### Cursor Entegrasyonu
Cursor'da **Settings -> Features -> MCP** sekmesine gidin. **+ Add New MCP Server** butonuna tıklayın:
- **Name:** `divan`
- **Type:** `command`
- **Command:** `divan-mcp`

### Cline / Roo Code (VS Code & JetBrains) Entegrasyonu
Aşağıdaki ayarları `cline_mcp_settings.json` dosyanıza ekleyin:
- **Cline Windows Konumu:** `%APPDATA%\Code\User\globalStorage\saoudrizwan.claude-dev\settings\cline_mcp_settings.json`
- **Roo Code Windows Konumu:** `%APPDATA%\Code\User\globalStorage\roodev.rogue-dev\settings\cline_mcp_settings.json`
*(Veya eklenti arayüzündeki **MCP** paneline gidip dişli çark simgesine tıklayarak dosyayı açabilirsiniz.)*

```json
{
  "mcpServers": {
    "divan": {
      "command": "divan-mcp",
      "disabled": false,
      "alwaysAllow": []
    }
  }
}
```

### Antigravity Entegrasyonu
Antigravity (IDE, 2.0 veya CLI) üzerinde MCP sunucularını yönetmek için üç yöntem kullanabilirsiniz:

1. **Arayüz Üzerinden (Antigravity 2.0 / IDE):**
   - **Antigravity 2.0:** **Settings (Sol Alt) -> Customizations** sekmesindeki **Installed MCP Servers** bölümünden yönetebilir veya **Add MCP** ile doğrudan ekleyebilirsiniz.
   - **Antigravity IDE:** Ajan panelinin üstündeki **...** simgesine tıklayıp **MCP Servers -> Manage MCP Servers** seçeneğini kullanabilirsiniz.

2. **Global Yapılandırma Dosyası:**
   Aşağıdaki ayarları global `mcp_config.json` dosyanıza ekleyin:
   - **Windows Konumu:** `%USERPROFILE%\.gemini\config\mcp_config.json`
   - **macOS/Linux Konumu:** `~/.gemini/config/mcp_config.json`

3. **Workspace (Proje) Seviyesinde Yapılandırma:**
   Projelerinizin kök dizinindeki `.agents/mcp_config.json` dosyasına ekleyerek yalnızca o projeye özel çalışmasını sağlayabilirsiniz.

**Konfigürasyon Formatı:**
```json
{
  "mcpServers": {
    "divan": {
      "command": "divan-mcp"
    }
  }
}
```

### Windsurf Entegrasyonu
Windsurf'te `~/.codeium/windsurf_mcp_config.json` (veya Windows'ta `%USERPROFILE%\.codeium\windsurf_mcp_config.json`) dosyanıza ekleyin:

```json
{
  "mcpServers": {
    "divan": {
      "command": "divan-mcp"
    }
  }
}
```

LLM'lere açılan MCP Araçları (Tools):
1.  `search_decisions(query, courts, chamber, date_start, date_end, page, page_size)`
2.  `get_decision_content(document_id, court_type)`

## CLI Kullanımı

Terminal üzerinden görsel olarak (Rich ile) çok hızlı araştırmalar yapabilirsiniz.

**Arama Yapmak:**
```bash
# Sadece Yargıtay kararlarında "işe iade" araması
divan search "işe iade" --court YARGITAY

# Sayfalandırma kullanımı
divan search "haksız fiil" --page 2
```

**Belge Okumak veya İndirmek:**
Arama sonuçlarında dönen `ID` ve `Kurum` tipini kullanarak kararı okuyabilirsiniz.

```bash
# Kararı terminalde (Markdown formatında okumak)
divan get 202412345 YARGITAY

# Kararı bilgisayara DOCX Word belgesi olarak indirmek
divan get 202412345 YARGITAY --export docx

# Kararı JSON olarak kaydetmek
divan get 202412345 YARGITAY --export json
```

## REST API

Eğer Divan'ı başka yazılımların arkaplan servisi olarak kullanmak isterseniz, hazır gelen FastAPI sunucusunu ayağa kaldırabilirsiniz.

```bash
uvicorn divan.api.server:app --reload
```
*Sunucu `http://127.0.0.1:8000` adresinde çalışacaktır.*
*Swagger (OpenAPI) dökümantasyonu için `http://127.0.0.1:8000/docs` adresini ziyaret edin.*

## Dokümantasyon Dizini

Geliştiriciler ve mimariyi incelemek isteyenler için `docs/` klasörü altındaki dökümanlara göz atabilirsiniz:

- [Mimari ve Tasarım Desenleri (ARCHITECTURE.md)](./docs/ARCHITECTURE.md)
- [Yeni Bir Mahkeme İstemcisi Eklemek (CLIENT_DEVELOPMENT.md)](./docs/CLIENT_DEVELOPMENT.md)
- [API ve Komut Referansı (API_REFERENCE.md)](./docs/API_REFERENCE.md)
- [Örnek Kullanım ve Hukuki Araştırma (EXAMPLE_USAGE.md)](./docs/EXAMPLE_USAGE.md)

## Lisans

Bu proje **PolyForm Noncommercial License 1.0.0** ile lisanslanmıştır.

- **Ticari olmayan** her kullanıma izin verilir (kişisel çalışma, araştırma, eğitim kurumları, kamu/kâr amacı gütmeyen kuruluşlar).
- **Ticari kullanım yasaktır.** Ticari kullanım için ayrı bir lisans gerekir; iletişim için proje sahibine başvurun.

Tam metin: [LICENSE](./LICENSE) · <https://polyformproject.org/licenses/noncommercial/1.0.0>
