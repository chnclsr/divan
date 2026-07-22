<div align="center">
  <h1>Divan</h1>
  <p><b>Enterprise-Grade Legal Research Platform & MCP Server</b></p>
  <p>
    <a href="https://img.shields.io/badge/python-3.9+-blue.svg"><img src="https://img.shields.io/badge/python-3.9+-blue.svg" alt="Python 3.9+"></a>
    <a href="https://img.shields.io/badge/architecture-SOLID-success.svg"><img src="https://img.shields.io/badge/architecture-SOLID-success.svg" alt="SOLID Architecture"></a>
    <a href="https://img.shields.io/badge/interface-MCP%20%7C%20REST%20%7C%20CLI-lightgrey"><img src="https://img.shields.io/badge/interface-MCP%20%7C%20REST%20%7C%20CLI-lightgrey" alt="Interfaces"></a>
  </p>
  <p>
    <a href="#features">Features</a> • 
    <a href="#installation">Installation</a> • 
    <a href="#mcp-server-usage">MCP</a> • 
    <a href="#cli-usage">CLI</a> • 
    <a href="#rest-api">REST API</a> •
    <a href="./docs/ARCHITECTURE.md">Architecture</a>
  </p>
  <p>
    <i>Diğer dillerde oku: <a href="README.md">Türkçe</a></i>
  </p>
</div>

---

Divan is a unified, asynchronous, and highly resilient search platform providing a single point of access to the fragmented jurisprudence databases of Turkish high courts and regional courts (Yargıtay, Danıştay, Anayasa Mahkemesi, BAM, Local Courts).

Built on standard resilience patterns (Circuit Breaker, Token Bucket Rate Limiter, LRU In-Memory Cache) and SOLID principles with a structured API client architecture. It supports the **MCP (Model Context Protocol)** standard for direct integration with Large Language Models (LLMs).

## Features

*   **Unified Data Model:** Regardless of the source, all decisions are converted into a uniform `Decision` model.
*   **Concurrent Search:** Uses `asyncio` to simultaneously search Yargıtay, Danıştay, AYM, and UYAP Emsal databases with a single query and merges the results.
*   **Resilience and Performance Infrastructure:**
    *   **Circuit Breaker:** If UYAP or other institutional servers go down, it halts outgoing requests to prevent unnecessary load and wait times.
    *   **Token Bucket Rate Limiter:** Implements rate limiting to avoid blocks from institutional APIs. Automatically suspends requests for a set period upon receiving HTTP 429.
    *   **In-Memory Caching:** TTL-based LRU in-memory caching to prevent duplicate searches and document downloads from consuming excessive resources and time.
*   **Multi-Interface:** MCP Server (Claude integration), REST API (FastAPI), and Terminal (CLI).
*   **Automatic Conversion:** Instantly converts HTML or Base64-PDF documents returned from institutions into Markdown—the format best understood by LLMs (via `MarkItDown` integration). Optionally, export in `.docx` format.

## Installation

Python 3.9+ is required to run the system. You can install all dependencies and Divan CLI tools by running the following command in the project directory:

```bash
# In the project directory
pip install -e .
```

> **Note:** Divan uses `AppConfig` for configuration. Settings can be overridden using an `.env` file or environment variables (e.g., `DIVAN_HTTP_TIMEOUT=30`).

## MCP Server Usage

Divan comes with a built-in FastMCP server for LLMs to conduct jurisprudence research.

To start the server manually:
```bash
divan-mcp
```

### Claude Desktop Integration
For Claude to access this server, add the following to your `claude_desktop_config.json`:
- **Windows Path:** `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS Path:** `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "divan": {
      "command": "divan-mcp"
    }
  }
}
```

### Cursor Integration
Go to **Settings -> Features -> MCP** in Cursor. Click **+ Add New MCP Server**:
- **Name:** `divan`
- **Type:** `command`
- **Command:** `divan-mcp`

### Cline / Roo Code (VS Code & JetBrains) Integration
Add the following to your `cline_mcp_settings.json`:
- **Cline Windows Path:** `%APPDATA%\Code\User\globalStorage\saoudrizwan.claude-dev\settings\cline_mcp_settings.json`
- **Roo Code Windows Path:** `%APPDATA%\Code\User\globalStorage\roodev.rogue-dev\settings\cline_mcp_settings.json`
*(Or navigate to the **MCP** panel in the extension UI and click the gear icon to open it automatically.)*

```json
{
  "mcpServers": {
    "divan": {
      "command": "divan-mcp",
      "disabled": false,
      "alwaysAllow": []
    }
  }
}
```

### Antigravity Integration
You can manage MCP servers in Antigravity (IDE, 2.0, or CLI) using three methods:

1. **Via UI (Antigravity 2.0 / IDE):**
   - **Antigravity 2.0:** Manage via **Settings (Bottom Left) -> Customizations** in the **Installed MCP Servers** section, or click **Add MCP** to install directly.
   - **Antigravity IDE:** Click the **...** icon at the top of the agent side panel, and select **MCP Servers -> Manage MCP Servers**.

2. **Global Configuration File:**
   Add the configuration to your global `mcp_config.json`:
   - **Windows Path:** `%USERPROFILE%\.gemini\config\mcp_config.json`
   - **macOS/Linux Path:** `~/.gemini/config/mcp_config.json`

3. **Workspace (Project) Level Configuration:**
   Add the configuration to `.agents/mcp_config.json` in the root directory of your active workspace.

**Configuration Format:**
```json
{
  "mcpServers": {
    "divan": {
      "command": "divan-mcp"
    }
  }
}
```

### Windsurf Integration
Add to your `~/.codeium/windsurf_mcp_config.json` (or `%USERPROFILE%\.codeium\windsurf_mcp_config.json` on Windows):

```json
{
  "mcpServers": {
    "divan": {
      "command": "divan-mcp"
    }
  }
}
```

Available MCP Tools for LLMs:
1.  `search_decisions(query, courts, chamber, date_start, date_end, page, page_size)`
2.  `get_decision_content(document_id, court_type)`

## CLI Usage

You can perform lightning-fast searches visually (with Rich) via the terminal.

**Performing a Search:**
```bash
# Search for "işe iade" only in Yargıtay decisions
divan search "işe iade" --court YARGITAY

# Pagination usage
divan search "haksız fiil" --page 2
```

**Reading or Downloading a Document:**
You can read the decision using the `ID` and `Institution` type returned in the search results.

```bash
# Read the decision in the terminal (rendered as Markdown)
divan get 202412345 YARGITAY

# Download the decision as a DOCX Word document to your computer
divan get 202412345 YARGITAY --export docx

# Save the decision as JSON
divan get 202412345 YARGITAY --export json
```

## REST API

If you want to use Divan as a backend service for other software, you can spin up the built-in FastAPI server.

```bash
uvicorn divan.api.server:app --reload
```
*The server will run at `http://127.0.0.1:8000`.*
*Visit `http://127.0.0.1:8000/docs` for the Swagger (OpenAPI) documentation.*

## Documentation Index

For developers and those who want to examine the architecture, you can check the documents under the `docs/` folder (Note: current detailed docs are in Turkish):

- [Architecture and Design Patterns (ARCHITECTURE.md)](./docs/ARCHITECTURE.md)
- [Adding a New Court Client (CLIENT_DEVELOPMENT.md)](./docs/CLIENT_DEVELOPMENT.md)
- [API and Command Reference (API_REFERENCE.md)](./docs/API_REFERENCE.md)
- [Example Usage and Legal Research (EXAMPLE_USAGE.md)](./docs/EXAMPLE_USAGE.md)
