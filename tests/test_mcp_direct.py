import asyncio
import json
from divan.mcp.server import search_decisions

async def test_mcp():
    print("Testing MCP search_decisions directly...")
    result_str = await search_decisions(
        query="işe iade",
        semantic=True,
        page_size=2
    )
    result = json.loads(result_str)
    print("\n--- MCP Search Output ---")
    print(f"Total Records: {result.get('total_records')}")
    print(f"Page: {result.get('page')}")
    print(f"Page Size: {result.get('page_size')}")
    print(f"Courts Searched: {result.get('courts_searched')}")
    print(f"Errors: {result.get('errors')}")
    
    print("\n--- Decisions with Snippets ---")
    for d in result.get("decisions", []):
        print(f"ID: {d.get('id')} | Court: {d.get('court')} | Title: {d.get('title')}")
        print(f"Snippet: {d.get('snippet')}")
        summary = d.get('summary') or ""
        print(f"Summary: {summary[:100]}...")
        print("-" * 40)

if __name__ == "__main__":
    asyncio.run(test_mcp())
