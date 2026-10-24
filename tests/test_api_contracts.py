from fastapi.testclient import TestClient
from backend.main import app
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
