from fastapi.testclient import TestClient
from backend.main import app, settings
def test_health_route_reports_service():
 client=TestClient(app)
 response=client.get("/health")
 assert response.status_code==200 and response.json()["service"]=="affiliate-os-api"
def test_auth_me_endpoint_does_not_invent_provider_metrics():
 with TestClient(app) as client:
  response=client.get("/api/integrations")
  assert response.status_code==200
  data=response.json()
  assert data["verification_policy"].startswith("No provider")
  assert all(x["write_access_verified"] is False for x in data["items"])



def test_cors_preflight_allows_idempotency_key_for_browser_writes():
    origin = settings.allowed_origins[0]
    with TestClient(app) as client:
        response = client.options(
            "/api/distribution/queue",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,x-csrf-token,idempotency-key",
            },
        )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin
    allow_headers = response.headers.get("access-control-allow-headers", "").lower()
    assert "idempotency-key" in allow_headers
    assert "x-csrf-token" in allow_headers
