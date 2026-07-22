"""KİK (Kamu İhale Kurumu) Client for Divan.

Uses the EKAPv2 API which requires AES-192-CBC request signing and 
AES-256-CBC document ID encryption. Ported from the legacy kik_mcp_module.
"""

import os
import uuid
import base64
import asyncio
from datetime import datetime
from markitdown import MarkItDown
import logging

try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend
    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False

from divan.core.models import Decision, SearchQuery, SearchResult, HealthStatus, CourtType
from divan.core.enums import DecisionType
from divan.clients.base import BaseCourtClient

logger = logging.getLogger(__name__)


class KikClient(BaseCourtClient):
    """Kamu İhale Kurumu Uyuşmazlık Kararları araması yapan istemci."""

    ENDPOINT_UYUSMAZLIK = "/b_ihalearaclari/api/KurulKararlari/GetKurulKararlari"

    @classmethod
    def _get_base_url(cls) -> str:
        return "https://ekapv2.kik.gov.tr"


    DOCUMENT_ID_ENCRYPTION_KEY = bytes([
        236, 193, 164, 43, 12, 135, 121, 170, 4, 244, 123, 219, 82, 158, 124, 174,
        174, 228, 219, 174, 208, 104, 174, 120, 32, 76, 250, 4, 143, 159, 211, 176
    ])

    REQUEST_SIGNING_KEY = b"Qm2LtXR0aByP69vZNKef4wMJ"

    @property
    def court_type(self) -> CourtType:
        return CourtType.KIK

    @property
    def supported_courts(self) -> set[CourtType]:
        return {CourtType.KIK}

    def _sign_request_value(self, plaintext: str, iv: bytes) -> str:
        if not HAS_CRYPTOGRAPHY:
            raise ImportError("cryptography library required for KIK v2 request signing")
        cipher = Cipher(
            algorithms.AES(self.REQUEST_SIGNING_KEY),
            modes.CBC(iv),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()
        data = plaintext.encode("utf-8")
        block_size = 16
        padding_len = block_size - (len(data) % block_size)
        padded = data + bytes([padding_len] * padding_len)
        ciphertext = encryptor.update(padded) + encryptor.finalize()
        return base64.b64encode(ciphertext).decode("ascii")

    def _generate_security_headers(self) -> dict:
        if not HAS_CRYPTOGRAPHY:
            raise ImportError("cryptography library required for KIK v2 request signing")
        request_guid = str(uuid.uuid4())
        iv = os.urandom(16)
        timestamp_ms = str(int(datetime.now().timestamp() * 1000))
        return {
            "X-Custom-Request-Guid": request_guid,
            "X-Custom-Request-R8id": self._sign_request_value(request_guid, iv),
            "X-Custom-Request-Siv": base64.b64encode(iv).decode("ascii"),
            "X-Custom-Request-Ts": self._sign_request_value(timestamp_ms, iv),
        }

    def _encrypt_document_id(self, numeric_id: str) -> str:
        if not HAS_CRYPTOGRAPHY:
            raise ImportError("cryptography library required for document ID encryption")
        iv = os.urandom(16)
        cipher = Cipher(
            algorithms.AES(self.DOCUMENT_ID_ENCRYPTION_KEY),
            modes.CBC(iv),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()
        plaintext = numeric_id.encode('utf-8')
        block_size = 16
        padding_len = block_size - (len(plaintext) % block_size)
        padded_plaintext = plaintext + bytes([padding_len] * padding_len)
        ciphertext = encryptor.update(padded_plaintext) + encryptor.finalize()
        return iv.hex() + ciphertext.hex()

    async def _do_search(self, query: SearchQuery) -> SearchResult:
        key_value_pairs = []
        if query.query:
            key_value_pairs.append({"key": "KararMetni", "value": query.query})
        if query.esas_no or query.karar_no:
            key_value_pairs.append({"key": "KararNo", "value": query.karar_no or query.esas_no})
        if not key_value_pairs:
            key_value_pairs.append({"key": "KararMetni", "value": ""})

        payload = {
            "sorgulaKurulKararlari": {
                "keyValuePairs": {
                    "keyValueOfstringanyType": key_value_pairs
                }
            }
        }
        
        headers = self._generate_security_headers()
        
        try:
            # Bypass resilient client for SSL/origin headers if needed, but we'll try with it first
            response = await self._http.post(
                self.ENDPOINT_UYUSMAZLIK,
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            data = response.json()
            
            result_data = data.get("SorgulaKurulKararlariResponse", {}).get("SorgulaKurulKararlariResult", {})
            if result_data.get("hataKodu") and result_data.get("hataKodu") != "0":
                raise ValueError(f"KIK API Hatası: {result_data.get('hataMesaji')}")
                
            decisions = []
            for group in result_data.get("KurulKararTutanakDetayListesi", []):
                for detail in group.get("KurulKararTutanakDetayi", []):
                    decisions.append(Decision(
                        id=str(detail.get("gundemMaddesiId")),
                        court_type=CourtType.KIK,
                        decision_type=DecisionType.KURUL_KARARI,
                        esas_no=detail.get("kararNo"),
                        karar_no=detail.get("kararNo"),
                        decision_date_str=detail.get("kararTarihi"),
                        title=detail.get("basvuruKonusu"),
                        summary=f"Başvuran: {detail.get('basvuran')}, İdare: {detail.get('idareAdi')}",
                        raw_metadata=detail
                    ))
                    
            return SearchResult(
                decisions=decisions,
                total_records=len(decisions),
                page=1,
                page_size=len(decisions),
                courts_searched=[CourtType.KIK]
            )
        except Exception as e:
            logger.error(f"KIK arama hatası: {e}")
            raise

    async def _do_get_document(self, document_id: str) -> Decision:
        try:
            # 1. Get real URL
            headers = self._generate_security_headers()
            url_payload = {"sorguSayfaTipi": 2}
            url_res = await self._http.post(
                "/b_ihalearaclari/api/KurulKararlari/GetSorgulamaUrl",
                json=url_payload,
                headers=headers
            )
            url_res.raise_for_status()
            base_doc_url = url_res.json().get("sorgulamaUrl", "")
            
            if not base_doc_url:
                raise ValueError("Doküman URL alınamadı")
                
            karar_id = document_id
            if document_id.isdigit():
                karar_id = self._encrypt_document_id(document_id)
                
            doc_url = f"{base_doc_url}?KararId={karar_id}"
            
            # 2. Fetch HTML
            doc_res = await self._http.get(doc_url, follow_redirects=True)
            doc_res.raise_for_status()
            
            md = MarkItDown(enable_plugins=False)
            result = await asyncio.to_thread(md.convert_stream, doc_res.content, file_extension=".html")
            
            return Decision(
                id=document_id,
                court_type=CourtType.KIK,
                decision_type=DecisionType.KURUL_KARARI,
                markdown_content=result.text_content,
                source_url=doc_url,
                raw_metadata={}
            )
        except Exception as e:
            logger.error(f"KIK doküman indirme hatası: {e}")
            raise
