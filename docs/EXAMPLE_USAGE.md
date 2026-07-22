# Divan — Örnek Kullanım Kılavuzu (Hukuki Araştırma)

Bu dokümanda, Divan MCP sunucusunu kullanarak gerçek dünya hukuki araştırma senaryolarının nasıl yürütüldüğü, yapılan sorgular, çağrılan MCP araçları (tools) ve bu araçların döndürdüğü sonuçlar adım adım gösterilmektedir.

---

## Senaryo: Kiracının Sözleşme Süresi Dolmadan Kiralananı Tahliye Etmesi

**Hukuki Sorun:** Evden veya iş yerinden kira sözleşmesi bitmeden erken çıkan kiracı, kalan ayların kirasını ödemeye devam etmek zorunda mıdır? Yargıtay'ın bu konudaki güncel yaklaşımı nedir?

### 1. Arama Girdisi (Query)

LLM veya kullanıcı tarafından Divan MCP sunucusu üzerinden yapılan arama sorgusu:

*   **Arama Metni (Query):** `"makul süre" "erken tahliye"`
*   **Mahkeme Filtresi (Courts):** `["YARGITAYKARARI"]`
*   **Sayfa Boyutu (Page Size):** `20`
*   **Semantik Arama (Semantic):** `true`

#### MCP `search_decisions` Çağrısı:
```json
{
  "query": "\"makul süre\" \"erken tahliye\"",
  "courts": ["YARGITAYKARARI"],
  "page_size": 20,
  "semantic": true
}
```

---

### 2. Arama Sonucu ve MCP Çıktısı

Sorgu sonucunda dönen ham JSON yanıtı ve eşleşen kararların listesi (özet):

```json
{
  "total_records": 689,
  "page": 1,
  "page_size": 20,
  "courts_searched": ["YARGITAY"],
  "errors": {},
  "decisions": [
    {
      "id": "1217563900",
      "court": "YARGITAY",
      "type": "KARAR",
      "esas_no": "2025/6206",
      "karar_no": "2026/2950",
      "date": "12.05.2026",
      "title": null,
      "snippet": "Uyuşmazlık; asıl davada kiralanana yapılan faydalı ve zorunlu imalat bedellerinin tahsili, karşı davada erken tahliye nedeniyle mahrum kalınan kira bedelleri...",
      "chamber": "3. Hukuk Dairesi"
    },
    {
      "id": "1217620100",
      "court": "YARGITAY",
      "type": "KARAR",
      "esas_no": "2025/3422",
      "karar_no": "2026/1397",
      "date": "11.03.2026",
      "title": null,
      "snippet": "...kira bedellerini hiç ödemeden kiralananı kira dönemi süresinden önce tahliye eden 3 aylık makul süre kirasını ödemeyen, kiralananı kiraladığı şekilde hasarsız teslim etmeyen...",
      "chamber": "3. Hukuk Dairesi"
    },
    {
      "id": "1217367800",
      "court": "YARGITAY",
      "type": "KARAR",
      "esas_no": "2025/3414",
      "karar_no": "2026/1301",
      "date": "10.03.2026",
      "title": null,
      "snippet": null,
      "chamber": "3. Hukuk Dairesi"
    },
    {
      "id": "1193786400",
      "court": "YARGITAY",
      "type": "KARAR",
      "esas_no": "2025/1722",
      "karar_no": "2026/44",
      "date": "12.01.2026",
      "title": null,
      "snippet": "...hakkında tahliye istemli dava açılan davalının bir aylık feshi ihbar bildirimini yerine getirmesi kendisinden beklenemez. Kiralananın feshi ihbar koşuluna uyulmadan tahliye edildiğinden bahisle alacak isteminde de bulunulamaz...",
      "chamber": "3. Hukuk Dairesi"
    }
  ]
}
```

---

### 3. Belge Detayının Getirilmesi (get_decision_content)

Arama listesinden belirlenen karar detaylarını tam metin halinde okumak için çağrılan araç:

#### MCP `get_decision_content` Çağrısı:
```json
{
  "document_id": "1193786400",
  "court_type": "YARGITAYKARARI"
}
```

#### Dönen Karar İçeriği (Özetlenmiş Metin):
```markdown
**3. Hukuk Dairesi         2025/1722 E.  ,  2026/44 K.**
**"İçtihat Metni"**

...
Kiralananın, haklı bir sebep olmaksızın erken tahliyesi halinde kural olarak kiracının, kira dönemi sonuna kadarki kira parasından sorumlu olduğu, ancak 6098 sayılı Türk Borçlar Kanunu'nun 114. maddesi göndermesi ile aynı Kanunun 52. maddesi uyarınca kiraya verenin de zararın artmasına neden olmaması gerektiği, kiracının sorumluluğunun kiralananın kira sözleşmesindeki bedel ve koşullarda yeniden kiraya verilebileceği makul süre kadar olduğu, esasen kanun koyucu tarafından bu kuralın Kanunun 325. maddesi ile kanun hükmü haline getirildiği...

Hakkında tahliye istemli olarak dava veya icra takibi ikame edilen kiracı hakkında, erken tahliye sebebiyle tazminat isteminde bulunulmasının 4721 sayılı Türk Medeni Kanunu'nun 2. maddesinde yer alan dürüstlük kuralı ile bağdaşmayacağı...
...
```

---

### 4. Sonuç Analizi ve Emsal Kararların Değerlendirilmesi

Yargıtay'ın erken tahliye durumunda kiracının ödeme yükümlülüğüne ilişkin kuralları şu şekildedir:

1.  **Genel Kural (TBK m. 325):** Sözleşme bitmeden haklı bir sebep olmaksızın kiralananı tahliye eden kiracı, sözleşmeden doğan borçlarını (kira ödemeleri) sözleşme süresince veya kiralananın benzer koşullarla kiraya verilebileceği **makul süre** boyunca ödemeye devam etmekle yükümlüdür.
2.  **Kiraya Verenin Zararı Azaltma Yükümlülüğü (TBK m. 52):** Ev sahibi, taşınmazın boş kaldığı sürenin uzamaması için makul gayreti göstermeli ve taşınmazı yeniden kiraya vermek için çaba sarf etmelidir. Bu doğrultuda kiracı, tüm kalan süre boyunca değil, yalnızca yerin yeniden kiraya verilebileceği süre kadar (genellikle bilirkişi tarafından 2-4 ay arası belirlenir) sorumludur.
3.  **Dürüstlük Kuralı İstisnası (TMK m. 2):** Eğer kiraya veren, kira borcu ödenmediği gerekçesiyle kiracıya karşı tahliye davası açmış veya tahliye talepli icra takibi başlatmışsa, kiracının bu yargılama/takip sırasında mecuru tahliye etmesi "erken haksız tahliye" sayılamaz. Tahliye edilmesini talep eden ev sahibinin, tahliye gerçekleştikten sonra "erken çıktın, makul süre kirasını öde" demesi dürüstlük kuralına aykırı olup, Yargıtay tarafından bu istem reddedilir.
