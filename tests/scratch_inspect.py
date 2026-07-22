import sys
sys.path.insert(0, r"c:\Users\PC_9928\Desktop\Cihan\ÖZEL\yargı_\yargi-mcp")

try:
    from mcp_server_main import app
    print("Yargi-MCP Tools:")
    for name, tool in app.tools.items():
        print(f"Tool: {name}")
        print(f"Description: {tool.description}")
        print("---")
except Exception as e:
    print(f"Error loading yargi-mcp: {e}")

sys.path.insert(0, r"c:\Users\PC_9928\Desktop\Cihan\ÖZEL\yargı_\mevzuat-mcp")
try:
    from mevzuat_mcp_server import app as mevzuat_app
    print("\nMevzuat-MCP Tools:")
    for name, tool in mevzuat_app.tools.items():
        print(f"Tool: {name}")
        print(f"Description: {tool.description}")
        print("---")
except Exception as e:
    print(f"Error loading mevzuat-mcp: {e}")
