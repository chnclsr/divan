import asyncio
import json
import sys
sys.path.insert(0, r"c:\Users\PC_9928\Desktop\Cihan\ÖZEL\yargı_\yargi-mcp")

from bedesten_mcp_module.client import BedestenApiClient
from bedesten_mcp_module.models import BedestenSearchRequest, BedestenSearchData, BedestenCourtTypeEnum
from bedesten_mcp_module.enums import BirimAdiEnum

async def test_search():
    client = BedestenApiClient()
    data = BedestenSearchData(
        pageSize=10,
        pageNumber=1,
        itemTypeList=["YARGITAYKARARI"],
        phrase="tapu iptali",
        birimAdi="H1",
        kararTarihiStart="",
        kararTarihiEnd=""
    )
    request = BedestenSearchRequest(data=data)
    try:
        response = await client.search_documents(request)
        if response.data and response.data.emsalKararList:
            # print the first result as JSON
            print(json.dumps(response.data.emsalKararList[0].model_dump(), indent=2, ensure_ascii=False))
        else:
            print("No results found.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_search())
