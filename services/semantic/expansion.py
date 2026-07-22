"""Divan Semantic Services — Deterministik sorgu genişletme (Query Expansion).

Recall (kapsayıcılık) sorununu çözer: keyword araması, sorgudaki kelime karar
metnindeki resmi terimden farklıysa ilgili kararı kaçırır. Bu modül, kullanıcı
dilindeki bir ifadeyi ("işten çıkarma") mahkeme/API'nin tanıdığı resmi hukuki
terimlere ("fesih", "iş akdinin feshi", "haklı nedenle fesih") eşler.

Tasarım ilkeleri:
    - LLM YOK. Saf statik sözlük. 0 gecikme, 0 API, 0 model.
    - Boolean OR üreten motorlar (Bedesten) için TEK sorguya dönüşür; N paralel
      arama YAPILMAZ (rate-limit çarpanından kaçınmak için).
    - DAR sözlük + terim tavanı: aşırı genişletme precision'ı öldürür.
    - İfade düzeyinde substring eşleştirme; Türkçe morfoloji peşinde koşulmaz.

Sözlüğü genişletmek: sadece yüksek-güven, resmi hukuki eşanlam grupları ekleyin.
Her grup çift yönlüdür (grup içi herhangi bir terim eşleşirse tümü eklenir).
"""

from __future__ import annotations

# Terim sayısı tavanı — OR sorgusunu odaklı tutar, gürültüyü sınırlar.
MAX_EXPANSION_TERMS = 5

# Her iç liste, birbirinin resmi hukuki karşılığı olan terimlerden oluşur.
# Grup içindeki HERHANGİ bir terim sorguda geçerse, grubun tamamı genişletmeye
# katılır. Terimleri dar ve yüksek-güvenli tutun.
_SYNONYM_GROUPS: list[list[str]] = [
    # İş Hukuku — fesih
    ["işten çıkarma", "işten çıkarılma", "işten atılma", "fesih",
     "iş akdinin feshi", "iş sözleşmesinin feshi", "haklı nedenle fesih"],
    ["işe iade", "işe iade davası", "feshin geçersizliği"],
    ["kıdem tazminatı", "kıdem"],
    ["ihbar tazminatı", "ihbar öneli", "ihbar süresi"],
    ["mobbing", "psikolojik taciz", "işyerinde psikolojik taciz"],
    ["fazla mesai", "fazla çalışma", "fazla çalışma ücreti"],
    ["iş kazası", "işyeri kazası", "meslek hastalığı"],
    # Borçlar / Tazminat
    ["haksız fiil", "haksız eylem"],
    ["manevi tazminat", "manevi zarar"],
    ["maddi tazminat", "maddi zarar"],
    # İdare Hukuku
    ["iptal davası", "idari işlemin iptali"],
    ["yürütmenin durdurulması", "tedbir kararı"],
    # Ceza
    ["beraat", "beraat kararı"],
    ["zamanaşımı", "dava zamanaşımı", "ceza zamanaşımı"],
]


def expand_query(query: str, max_terms: int = MAX_EXPANSION_TERMS) -> list[str]:
    """Sorguyu resmi hukuki eşanlamlarla genişlet.

    Args:
        query: Kullanıcı/LLM sorgusu.
        max_terms: Döndürülecek toplam terim tavanı (orijinal dahil).

    Returns:
        Terim listesi. İlk eleman DAİMA orijinal sorgudur. Sözlükte eşleşme
        yoksa yalnızca `[query]` döner (no-op, sıfır maliyet).
    """
    q = (query or "").strip()
    if not q:
        return []

    q_lower = q.lower()
    terms: list[str] = [q]
    seen: set[str] = {q_lower}

    for group in _SYNONYM_GROUPS:
        # Grup içinde herhangi bir terim sorguda geçiyor mu?
        if any(t in q_lower for t in group):
            for t in group:
                tl = t.lower()
                if tl not in seen:
                    seen.add(tl)
                    terms.append(t)
        if len(terms) >= max_terms:
            break

    return terms[:max_terms]


def build_or_phrase(terms: list[str]) -> str:
    """Terim listesini Boolean-OR destekleyen motorlar (Bedesten) için tek
    sorgu string'ine çevir.

    Çok kelimeli terimler tam-ifade araması için çift tırnağa alınır:
        ['fesih', 'iş akdinin feshi'] -> 'fesih OR "iş akdinin feshi"'

    Tek terim varsa tırnaksız, olduğu gibi döner (OR eklenmez).
    """
    if not terms:
        return ""
    if len(terms) == 1:
        return terms[0]

    parts: list[str] = []
    for t in terms:
        parts.append(f'"{t}"' if " " in t else t)
    return " OR ".join(parts)
