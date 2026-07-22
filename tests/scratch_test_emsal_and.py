import asyncio
import httpx

async def test_emsal_and():
    url = "https://emsal.uyap.gov.tr/aramadetaylist"
    headers = {
        "Content-Type": "application/json; charset=UTF-8",
        "Accept": "application/json, text/plain, */*",
        "X-Requested-With": "XMLHttpRequest",
    }
    
    # Payload with AND operator
    payload_and = {
        "data": {
            "arananKelime": "kat AND malikleri AND kurulu",
            "pageSize": 5,
            "pageNumber": 1,
        }
    }
    
    # Payload without AND operator
    payload_normal = {
        "data": {
            "arananKelime": "kat malikleri kurulu",
            "pageSize": 5,
            "pageNumber": 1,
        }
    }

    async with httpx.AsyncClient(verify=False) as client:
        try:
            print("Testing Emsal with AND operator...")
            res1 = await client.post(url, json=payload_and, headers=headers)
            if res1.status_code == 200:
                data = res1.json().get("data", {})
                results = data.get("data", []) if isinstance(data, dict) else []
                print(f"AND Found: {data.get('recordsTotal', 0)} total records")
                for i, r in enumerate(results):
                    print(f"  {i+1}. ID: {r.get('id')}, Date: {r.get('kararTarihi')}, Esas: {r.get('esasNo')}")
            
            print("\nTesting Emsal without AND operator...")
            res2 = await client.post(url, json=payload_normal, headers=headers)
            if res2.status_code == 200:
                data = res2.json().get("data", {})
                results = data.get("data", []) if isinstance(data, dict) else []
                print(f"Normal Found: {data.get('recordsTotal', 0)} total records")
                for i, r in enumerate(results):
                    print(f"  {i+1}. ID: {r.get('id')}, Date: {r.get('kararTarihi')}, Esas: {r.get('esasNo')}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_emsal_and())
