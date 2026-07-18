from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ves.core.models import ReviewEnvelope, ReviewRequest
from ves.core.registry import ModuleRegistry, UnknownModuleError
from ves.core.review import ReviewService
from ves.modules.cfd import CFDModule
from ves.modules.isaac import IsaacModule

PACKAGE_DIR = Path(__file__).resolve().parent
STATIC_DIR = PACKAGE_DIR / "static"

registry = ModuleRegistry()
registry.register(CFDModule())
registry.register(IsaacModule())
review_service = ReviewService()

app = FastAPI(
    title="Verified Engineering Studio",
    version="0.1.0",
    description="Evidence-first AI reviews for modular engineering workflows.",
    docs_url="/api/docs",
    redoc_url=None,
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
async def healthz() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "service": "verified-engineering-studio",
        "openai_configured": review_service.configured,
        "model": review_service.model,
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


@app.get("/api/modules/{module_id}/cases/{case_id}/evidence")
async def get_evidence(module_id: str, case_id: str):
    try:
        return registry.get(module_id).build_evidence(case_id)
    except UnknownModuleError as exc:
        raise HTTPException(status_code=404, detail="Unknown engineering module") from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown evidence case") from exc


@app.post("/api/review", response_model=ReviewEnvelope)
async def create_review(request: ReviewRequest) -> ReviewEnvelope:
    try:
        module = registry.get(request.module_id)
        evidence = module.build_evidence(request.case_id)
    except UnknownModuleError as exc:
        raise HTTPException(status_code=404, detail="Unknown engineering module") from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown evidence case") from exc
    checks = module.validate(evidence)
    return await review_service.review(evidence, checks, request.question)


def run() -> None:
    import uvicorn

    uvicorn.run(
        "ves.app:app",
        host=os.getenv("VES_HOST", "127.0.0.1"),
        port=int(os.getenv("VES_PORT", "8110")),
    )


if __name__ == "__main__":
    run()
