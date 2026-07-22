"""Divan Interfaces — Command Line Interface.

Rich kütüphanesi kullanarak terminal üzerinden güzel,
renkli ve interaktif hukuki arama deneyimi sunar.
"""

import asyncio
import sys
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.markdown import Markdown
from rich.panel import Panel

from ..config import AppConfig
from ..core.enums import CourtType, ExportFormat
from ..core.models import SearchQuery
from ..clients.factory import CourtClientFactory
from ..services.search import UnifiedSearchService
from ..services.document import DocumentService
from ..services.export import ExportService
from ..infrastructure.cache import LRUMemoryCache

app = typer.Typer(
    name="divan",
    help="Divan: Türk Hukuk Araştırma Asistanı",
    no_args_is_help=True
)

console = Console()

# ── Altyapı Hazırlığı ──
def get_services():
    config = AppConfig()
    cache = LRUMemoryCache(max_size=config.cache_max_size, default_ttl=config.cache_ttl)
    client_factory = CourtClientFactory(config, cache)
    search_service = UnifiedSearchService(client_factory)
    document_service = DocumentService(client_factory)
    export_service = ExportService()
    return search_service, document_service, export_service, client_factory


@app.command()
def search(
    query: str = typer.Argument(..., help="Arama metni"),
    court: Optional[str] = typer.Option(None, "--court", "-c", help="Mahkeme türü (örn: YARGITAY, DANISTAY)"),
    page: int = typer.Option(1, "--page", "-p", help="Sayfa numarası"),
):
    """Mahkemelerde içtihat araması yap."""
    search_service, _, _, client_factory = get_services()

    async def _search():
        courts = []
        if court:
            try:
                courts.append(CourtType(court.upper()))
            except ValueError:
                console.print(f"[red]Geçersiz mahkeme türü: {court}[/red]")
                return
        else:
            courts = [CourtType.YARGITAY, CourtType.DANISTAY, CourtType.ANAYASA_NORM, CourtType.EMSAL]
            
        search_query = SearchQuery(query=query, courts=courts, page=page)
        
        with console.status(f"[bold green]'{query}' aranıyor..."):
            result = await search_service.search(search_query)
            
        if not result.has_results:
            console.print("[yellow]Sonuç bulunamadı.[/yellow]")
            if result.errors:
                for k, v in result.errors.items():
                    console.print(f"[red]{k}: {v}[/red]")
            return
            
        table = Table(title=f"Arama Sonuçları (Sayfa {result.page}/{result.total_pages})")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Kurum", style="magenta")
        table.add_column("Daire", style="green")
        table.add_column("E. / K.", style="blue")
        table.add_column("Tarih", style="yellow")
        
        for d in result.decisions:
            ek = f"{d.esas_no or '-'} / {d.karar_no or '-'}"
            table.add_row(
                d.id,
                d.court_type.name,
                d.chamber_name or "-",
                ek,
                d.decision_date_str or "-"
            )
            
        console.print(table)
        console.print(f"Toplam [bold]{result.total_records}[/bold] kayıt bulundu.")
        
        if result.errors:
            console.print("\n[red]Bazı kurumlarda hata oluştu:[/red]")
            for k, v in result.errors.items():
                console.print(f"- {k}: {v}")
                
        await client_factory.close_all()

    asyncio.run(_search())


@app.command()
def get(
    document_id: str = typer.Argument(..., help="Karar ID'si"),
    court: str = typer.Argument(..., help="Mahkeme türü (örn: YARGITAY)"),
    export: Optional[str] = typer.Option(None, "--export", "-e", help="Dışa aktar (markdown, docx, json)"),
):
    """Bir kararın tam metnini oku veya dışa aktar."""
    _, document_service, export_service, client_factory = get_services()
    
    async def _get():
        try:
            court_type = CourtType(court.upper())
        except ValueError:
            console.print(f"[red]Geçersiz mahkeme türü: {court}[/red]")
            return
            
        with console.status(f"[bold green]{document_id} getiriliyor..."):
            try:
                decision = await document_service.get_document(document_id, court_type)
            except Exception as e:
                console.print(f"[red]Hata: {e}[/red]")
                return
                
        if export:
            try:
                fmt = ExportFormat(export.lower())
                content = await export_service.export(decision, fmt)
                
                ext = export.lower()
                filename = f"{document_id}.{ext}"
                with open(filename, "wb") as f:
                    f.write(content)
                console.print(f"[green]Başarıyla kaydedildi: {filename}[/green]")
            except Exception as e:
                console.print(f"[red]Dışa aktarma hatası: {e}[/red]")
        else:
            if decision.markdown_content:
                md = Markdown(decision.markdown_content)
                console.print(Panel(md, title=decision.reference, expand=False))
            else:
                console.print("[yellow]Karar içeriği boş.[/yellow]")
                
        await client_factory.close_all()

    asyncio.run(_get())


def main():
    app()

if __name__ == "__main__":
    main()
