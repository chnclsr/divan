import ast

def analyze_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    tree = ast.parse(content)
    tools = []
    
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) or isinstance(node, ast.FunctionDef):
            is_tool = False
            description = ""
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Call):
                    if isinstance(decorator.func, ast.Attribute) and decorator.func.attr == 'tool':
                        is_tool = True
                        for keyword in decorator.keywords:
                            if keyword.arg == 'description':
                                if isinstance(keyword.value, ast.Constant):
                                    description = keyword.value.value
                                elif isinstance(keyword.value, ast.Str): # Python 3.7 and below
                                    description = keyword.value.s
            if is_tool:
                tools.append({
                    'name': node.name,
                    'description': description
                })
    return tools

print("Yargi-MCP Tools:")
yargi_tools = analyze_file(r"c:\Users\PC_9928\Desktop\Cihan\ÖZEL\yargı_\yargi-mcp\mcp_server_main.py")
for t in yargi_tools:
    print(f"- {t['name']}: {t['description']}")

print("\nMevzuat-MCP Tools:")
mevzuat_tools = analyze_file(r"c:\Users\PC_9928\Desktop\Cihan\ÖZEL\yargı_\mevzuat-mcp\mevzuat_mcp_server.py")
for t in mevzuat_tools:
    print(f"- {t['name']}: {t['description']}")
