import asyncio
import httpx

async def test_and_operator():
    url = "https://bedesten.adalet.gov.tr/emsal-karar/searchDocuments"
    headers = {
        "Accept": "*/*",
        "AdaletApplicationName": "UyapMevzuat",
        "Content-Type": "application/json; charset=utf-8",
    }
    
    # Payload with AND operator
    payload_and = {
        "data": {
            "pageSize": 5,
            "pageNumber": 1,
            "itemTypeList": ["YARGITAYKARARI"],
            "phrase": "kat AND malikleri AND kurulu",
        },
        "applicationName": "UyapMevzuat",
        "paging": True,
    }

    async with httpx.AsyncClient() as client:
        try:
            print("Testing AND operator...")
            res = await client.post(url, json=payload_and, headers=headers)
            print(f"Status: {res.status_code}")
            if res.status_code == 200:
                data = res.json()
                results = data.get("data", {}).get("emsalKararList", [])
                print(f"Found: {len(results)} items")
                for i, r in enumerate(results):
                    print(f"  {i+1}. ID: {r.get('documentId')}, Date: {r.get('kararTarihiStr')}, Esas: {r.get('esasNo')}, Birim: {r.get('birimAdi')}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_and_operator())
