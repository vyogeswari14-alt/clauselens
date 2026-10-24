from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_legal_verify_does_not_overclaim():
    response = client.post("/api/legal-sources/verify", json={"clause_text": "Unlimited liability applies"})
    assert response.status_code == 200
    assert response.json()["status"] == "not_verified"

def test_guidance():
    response = client.post("/api/guidance/ask", json={"question": "What should I check in a contract?", "language": "English"})
    assert response.status_code == 200
    assert "disclaimer" in response.json()
