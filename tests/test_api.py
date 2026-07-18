from fastapi.testclient import TestClient

from ves.app import app

client = TestClient(app)


def test_health_and_public_index():
    assert client.get("/").status_code == 200
    health = client.get("/healthz")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"


def test_module_and_evidence_endpoints():
    modules = client.get("/api/modules")
    assert modules.status_code == 200
    assert {item["id"] for item in modules.json()} == {"cfd", "isaac"}
    evidence = client.get("/api/modules/cfd/cases/laurons-v9/evidence")
    assert evidence.status_code == 200
    assert evidence.json()["schema_version"] == "ves.evidence.v1"


def test_review_degrades_to_deterministic_mode_without_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    response = client.post(
        "/api/review",
        json={
            "module_id": "cfd",
            "case_id": "laurons-v9",
            "question": "Is the reported resistance supported by the supplied evidence?",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["provenance"]["mode"] == "deterministic-fallback"
    assert payload["verdict"]["status"] == "review"
    assert payload["provenance"]["evidence_sha256"]


def test_unknown_module_returns_404():
    assert client.get("/api/modules/unknown/cases").status_code == 404

