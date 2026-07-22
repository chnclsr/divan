"""Divan Core — Domain enumerations."""

from enum import Enum, auto


class CourtType(str, Enum):
    """Desteklenen mahkeme ve kurum türleri.

    Her değer, ilgili kurumun Bedesten/API endpoint'indeki
    tanımlayıcısıyla uyumludur.
    """

    # Yüksek Yargı
    YARGITAY = "YARGITAYKARARI"
    DANISTAY = "DANISTAYKARAR"
    ANAYASA_NORM = "ANAYASA_NORM"
    ANAYASA_BIREYSEL = "ANAYASA_BIREYSEL"

    # Alt Derece
    YEREL_HUKUK = "YERELHUKUK"
    ISTINAF_HUKUK = "ISTINAFHUKUK"
    KYB = "KYB"

    # UYAP
    EMSAL = "EMSAL"

    # Mevzuat
    MEVZUAT = "MEVZUAT"
    
    BDDK = "BDDK"
    BTK = "BTK"
    GIB = "GIB"
    KIK = "KIK"
    KVKK = "KVKK"
    REKABET = "REKABET"
    SAYISTAY = "SAYISTAY"
    SIGORTA_TAHKIM = "SIGORTA_TAHKIM"
    UYUSMAZLIK = "UYUSMAZLIK"


class DecisionType(str, Enum):
    """Karar türleri."""

    KARAR = "karar"
    ILAM = "ilam"
    OZELGE = "ozelge"
    KURUL_KARARI = "kurul_karari"
    NORM_DENETIMI = "norm_denetimi"
    BIREYSEL_BASVURU = "bireysel_basvuru"
    MEVZUAT = "mevzuat"


class SearchScope(str, Enum):
    """Arama kapsamı."""

    FULL_TEXT = "full_text"
    ESAS_NO = "esas_no"
    KARAR_NO = "karar_no"
    TITLE = "title"


class CircuitState(str, Enum):
    """Circuit breaker durumları."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class ExportFormat(str, Enum):
    """Dışa aktarma formatları."""

    MARKDOWN = "markdown"
    JSON = "json"
    DOCX = "docx"
    PDF = "pdf"


# Bedesten API'sindeki birim adı kısaltma haritası
# yargi-mcp'deki 80+ seçenekli Literal yerine dict-based lookup
CHAMBER_MAP: dict[str, str] = {
    # Yargıtay Hukuk Daireleri
    **{f"H{i}": f"{i}. Hukuk Dairesi" for i in range(1, 24)},
    # Yargıtay Ceza Daireleri
    **{f"C{i}": f"{i}. Ceza Dairesi" for i in range(1, 24)},
    # Yargıtay Kurullar
    "HGK": "Hukuk Genel Kurulu",
    "CGK": "Ceza Genel Kurulu",
    "BGK": "Büyük Genel Kurul",
    "HBK": "Hukuk Daireleri Başkanlar Kurulu",
    "CBK": "Ceza Daireleri Başkanlar Kurulu",
    # Danıştay Daireleri
    **{f"D{i}": f"{i}. Daire" for i in range(1, 18)},
    # Danıştay Kurullar
    "DBGK": "Danıştay Büyük Genel Kurulu",
    "IDDK": "İdare Dava Daireleri Kurulu",
    "VDDK": "Vergi Dava Daireleri Kurulu",
    "IBK": "İçtihatları Birleştirme Kurulu",
    "IIK": "İdari İşler Kurulu",
    "DBK": "Danıştay Başkanlar Kurulu",
    "AYIM": "Askeri Yüksek İdare Mahkemesi",
    **{f"AYIM{i}": f"Askeri Yüksek İdare Mahkemesi {i}. Daire" for i in range(1, 4)},
    # Tümü
    "ALL": "",
}


def resolve_chamber(abbreviation: str) -> str:
    """Kısaltmayı tam birim adına çevir. Bilinmeyenleri olduğu gibi döndür."""
    return CHAMBER_MAP.get(abbreviation.upper(), abbreviation)
