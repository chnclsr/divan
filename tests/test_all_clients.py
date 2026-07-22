import pytest
import asyncio
from divan.config import AppConfig
from divan.core.models import SearchQuery
from divan.core.enums import CourtType
from divan.clients.factory import CourtClientFactory

@pytest.fixture(scope="module")
def app_config():
    return AppConfig()

@pytest.fixture(scope="module")
async def client_factory(app_config):
    factory = CourtClientFactory(app_config)
    yield factory
    await factory.close_all()

@pytest.mark.asyncio
async def test_all_clients_instantiation(client_factory):
    clients = client_factory.create_all()
    assert len(clients) == 13
    
    expected_keys = [
        'bedesten', 'anayasa', 'emsal', 'mevzuat', 'bddk', 
        'kvkk', 'gib', 'sigorta_tahkim', 'kik', 'btk', 
        'rekabet', 'sayistay', 'uyusmazlik'
    ]
    
    for key in expected_keys:
        assert key in clients

@pytest.mark.asyncio
async def test_health_checks(client_factory):
    """Her client'ın health_check'ini çağırır (Network isteği atar)."""
    clients = client_factory.create_all()
    
    tasks = []
    for name, client in clients.items():
        # Sadece hızlı dönebilecek olanları test edelim, KIK ve KVKK bazen yavaş olabilir
        tasks.append(client.health_check())
        
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Assertions
    for i, result in enumerate(results):
        client_name = list(clients.keys())[i]
        if isinstance(result, Exception):
            print(f"Health check failed for {client_name}: {result}")
        else:
            print(f"{client_name} health: {result.is_healthy}")
            # We don't assert is_healthy == True because external APIs might be down,
            # but we assert that the method returns a HealthStatus object.
            assert result.court_type is not None

@pytest.mark.asyncio
async def test_mevzuat_client(client_factory):
    """MevzuatClient özel testi."""
    client = client_factory.create(CourtType.MEVZUAT)
    assert client.court_type == CourtType.MEVZUAT
    
@pytest.mark.asyncio
async def test_kik_client(client_factory):
    """KikClient özel testi."""
    client = client_factory.create(CourtType.KIK)
    assert client.court_type == CourtType.KIK

@pytest.mark.asyncio
async def test_sayistay_client(client_factory):
    """SayistayClient özel testi (BaseScraperClient)."""
    client = client_factory.create(CourtType.SAYISTAY)
    assert client.court_type == CourtType.SAYISTAY
    assert client.search_engine_type == "brave"
    assert client.search_domain == "sayistay.gov.tr"
