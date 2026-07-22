import asyncio
from rich.console import Console
from rich.table import Table

from divan.config import AppConfig
from divan.core.enums import CourtType
from divan.core.models import SearchQuery
from divan.clients.factory import CourtClientFactory
from divan.infrastructure.cache import LRUMemoryCache

console = Console()

async def run_client_test(name: str, court_type: CourtType, query_str: str, factory: CourtClientFactory):
    console.rule(f"[bold cyan]Testing {name} Client ({court_type.value})")
    
    try:
        client = factory.create(court_type)
    except Exception as e:
        console.print(f"[red]Failed to create client: {e}[/red]")
        return
        
    # 1. Test Search
    console.print(f"[yellow]1. Arama Testi: '{query_str}'...[/yellow]")
    search_query = SearchQuery(query=query_str, courts=[court_type], page=1, page_size=3)
    
    try:
        result = await client.search(search_query)
        if not result.has_results:
            console.print("[red]Arama başarılı ancak sonuç bulunamadı![/red]")
            return
            
        console.print(f"[green][OK] Arama Başarılı! Bulunan kayıt: {result.total_records}[/green]")
        
        # Tablo ile sonuçları göster
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("ID")
        table.add_column("Esas/Karar")
        table.add_column("Tarih")
        
        for d in result.decisions:
            ek = f"{d.esas_no or '-'} / {d.karar_no or '-'}"
            table.add_row(d.id, ek, d.decision_date_str or "-")
        console.print(table)
        
        # 2. Test Document Fetching
        first_doc_id = result.decisions[0].id
        console.print(f"\n[yellow]2. Belge Getirme Testi: ID={first_doc_id}...[/yellow]")
        
        doc = await client.get_document(first_doc_id)
        if doc.markdown_content:
            preview = doc.markdown_content[:200].replace("\n", " ") + "..."
            console.print(f"[green][OK] Belge Başarıyla İndirildi ve Çevrildi! ({len(doc.markdown_content)} karakter)[/green]")
            console.print(f"[dim]Önizleme: {preview}[/dim]")
        else:
            console.print("[red]Belge getirildi ancak içerik boş![/red]")
            
    except Exception as e:
        console.print(f"[bold red][FAIL] Test Hata Verdi: {e}[/bold red]")


async def main():
    console.print("[bold green]Divan Entegrasyon Testleri Başlıyor...[/bold green]\n")
    
    config = AppConfig()
    cache = LRUMemoryCache()
    factory = CourtClientFactory(config, cache)
    
    # Bedesten Testi (Yargıtay)
    await run_client_test("Bedesten (Yargıtay)", CourtType.YARGITAY, "işe iade", factory)
    
    # Bedesten Testi (Danıştay)
    await run_client_test("Bedesten (Danıştay)", CourtType.DANISTAY, "vergi ziyaı", factory)
    
    # Anayasa Mahkemesi Testi (Bireysel Başvuru)
    await run_client_test("AYM (Bireysel Başvuru)", CourtType.ANAYASA_BIREYSEL, "ifade özgürlüğü", factory)
    
    # Emsal Testi (UYAP Emsal)
    await run_client_test("UYAP Emsal", CourtType.EMSAL, "haksız fiil", factory)
    
    # Temizlik
    console.print("\n[yellow]Bağlantılar kapatılıyor...[/yellow]")
    await factory.close_all()
    console.print("[bold green]Tüm testler tamamlandı![/bold green]")


if __name__ == "__main__":
    asyncio.run(main())
