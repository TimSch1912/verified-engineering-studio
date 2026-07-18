from __future__ import annotations

import os
from ipaddress import IPv6Address, ip_address, ip_network
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ves.core.models import ReviewAvailability, ReviewEnvelope, ReviewRequest
from ves.core.registry import ModuleRegistry, UnknownModuleError
from ves.core.review import ReviewService
from ves.modules.cfd import CFDModule
from ves.modules.isaac import IsaacModule

PACKAGE_DIR = Path(__file__).resolve().parent
STATIC_DIR = PACKAGE_DIR / "static"

registry = ModuleRegistry()
cfd_module = CFDModule()
cfd_package = cfd_module.load_package()
registry.register(cfd_module)
registry.register(IsaacModule())
review_service = ReviewService()

app = FastAPI(
    title="Verified Engineering Studio",
    version="0.2.0",
    description="Evidence-first AI reviews for modular engineering workflows.",
    docs_url="/api/docs",
    redoc_url=None,
)
app.mount(
    "/assets/cfd",
    StaticFiles(directory=cfd_package.root / "artifacts"),
    name="cfd-evidence-assets",
)
app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data:; media-src 'self'; "
        "style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; "
        "object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
    )
    return response


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/healthz")
async def healthz() -> dict[str, str | bool | int]:
    return {
        "status": "ok",
        "service": "verified-engineering-studio",
        "openai_configured": review_service.configured,
        "model": review_service.model,
        "cost_guard": True,
        "max_output_tokens": review_service.max_output_tokens,
    }


@app.get("/api/modules")
async def list_modules():
    return registry.descriptors()


@app.get("/api/modules/{module_id}/cases")
async def list_cases(module_id: str):
    try:
        return registry.get(module_id).list_cases()
    except UnknownModuleError as exc:
        raise HTTPException(status_code=404, detail="Unknown engineering module") from exc


@app.get("/api/modules/{module_id}/review-prompts")
async def list_review_prompts(module_id: str):
    try:
        return registry.get(module_id).review_prompts()
    except UnknownModuleError as exc:
        raise HTTPException(status_code=404, detail="Unknown engineering module") from exc


@app.get("/api/modules/{module_id}/cases/{case_id}/evidence")
async def get_evidence(module_id: str, case_id: str):
    try:
        return registry.get(module_id).build_evidence(case_id)
    except UnknownModuleError as exc:
        raise HTTPException(status_code=404, detail="Unknown engineering module") from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown evidence case") from exc


@app.get("/api/review/status", response_model=ReviewAvailability)
async def review_status(request: Request, response: Response) -> ReviewAvailability:
    response.headers["Cache-Control"] = "no-store"
    return review_service.availability(_client_identity(request))


@app.post("/api/review", response_model=ReviewEnvelope)
async def create_review(review_request: ReviewRequest, request: Request) -> ReviewEnvelope:
    try:
        module = registry.get(review_request.module_id)
        evidence = module.build_evidence(review_request.case_id)
    except UnknownModuleError as exc:
        raise HTTPException(status_code=404, detail="Unknown engineering module") from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown evidence case") from exc
    checks = module.validate(evidence)
    return await review_service.review(
        evidence,
        checks,
        review_request.question,
        client_id=_client_identity(request),
    )


def _client_identity(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    try:
        address = ip_address(peer)
    except ValueError:
        return review_service.client_identity("unknown")

    # cloudflared is the only public path and connects over loopback. Never trust a forwarded
    # client header from a non-loopback peer.
    if address.is_loopback:
        forwarded = request.headers.get("cf-connecting-ip", "")
        if forwarded and "," not in forwarded:
            try:
                address = ip_address(forwarded.strip())
            except ValueError:
                pass

    if isinstance(address, IPv6Address) and not address.is_loopback:
        grouped = ip_network(f"{address}/64", strict=False)
        identity_source = f"{grouped.network_address}/64"
    else:
        identity_source = str(address)
    return review_service.client_identity(identity_source)


def run() -> None:
    import uvicorn

    uvicorn.run(
        "ves.app:app",
        host=os.getenv("VES_HOST", "127.0.0.1"),
        port=int(os.getenv("VES_PORT", "8110")),
    )


if __name__ == "__main__":
    run()
