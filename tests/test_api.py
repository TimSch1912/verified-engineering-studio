import hashlib

from fastapi.testclient import TestClient
from starlette.requests import Request

from ves.app import _client_identity, app, review_service

client = TestClient(app)


def test_health_and_public_index():
    assert client.get("/").status_code == 200
    health = client.get("/healthz")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"


def test_review_status_is_cost_safe_and_not_cached(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    response = client.get("/api/review/status")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    payload = response.json()
    assert payload["api_configured"] is False
    assert payload["live_ai_available"] is False
    assert payload["deterministic_fallback_available"] is True
    assert payload["reason"] == "not_configured"
    assert "OPENAI_API_KEY" not in response.text


def test_module_and_evidence_endpoints():
    modules = client.get("/api/modules")
    assert modules.status_code == 200
    assert {item["id"] for item in modules.json()} == {"cfd", "isaac"}
    cases = client.get("/api/modules/cfd/cases")
    assert cases.status_code == 200
    assert len(cases.json()[0]["package_sha256"]) == 64
    evidence = client.get("/api/modules/cfd/cases/laurons-v9/evidence")
    assert evidence.status_code == 200
    assert evidence.json()["schema_version"] == "ves.evidence.v1"
    prompts = client.get("/api/modules/cfd/review-prompts")
    assert prompts.status_code == 200
    assert [item["id"] for item in prompts.json()] == ["support", "grid-study", "review-brief"]

    wave = client.get("/assets/cfd/wave-top.png")
    assert wave.status_code == 200
    assert hashlib.sha256(wave.content).hexdigest() == (
        "2624295a80f56c634f776946c91154d538d3b61db9a11ad85107c218df960fdd"
    )


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
    assert {finding["title"] for finding in payload["verdict"]["findings"]} == {
        "Discretization uncertainty remains open",
        "Public package is not yet reproduction-complete",
    }
    assert payload["provenance"]["evidence_sha256"]


def test_unknown_module_returns_404():
    assert client.get("/api/modules/unknown/cases").status_code == 404


def test_whitespace_only_review_question_is_rejected():
    response = client.post(
        "/api/review",
        json={"module_id": "cfd", "case_id": "laurons-v9", "question": "   \n  "},
    )
    assert response.status_code == 422


def _request(peer: str, forwarded: str | None = None) -> Request:
    headers = []
    if forwarded is not None:
        headers.append((b"cf-connecting-ip", forwarded.encode("ascii")))
    return Request({"type": "http", "headers": headers, "client": (peer, 12345)})


def test_cloudflare_address_is_trusted_only_from_loopback(monkeypatch):
    monkeypatch.setattr(review_service, "client_identity", lambda address: address)

    assert _client_identity(_request("127.0.0.1", "203.0.113.44")) == "203.0.113.44"
    assert _client_identity(_request("198.51.100.8", "203.0.113.44")) == "198.51.100.8"
    assert _client_identity(_request("127.0.0.1", "bad,203.0.113.44")) == "127.0.0.1"
    assert (
        _client_identity(_request("127.0.0.1", "2001:db8:1234:5678:abcd::1"))
        == "2001:db8:1234:5678::/64"
    )
