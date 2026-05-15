from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.database import close_pool, init_schema
from app.routers.auth import router as auth_router
from app.routers.books import router as books_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_schema()
    yield
    await close_pool()


app = FastAPI(title="Books API", version="0.1.0", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(books_router)


def _safe_errors(errors) -> list[dict]:
    """Sanitise Pydantic errors: ctx may hold ValueError instances which aren't JSON-serialisable."""
    safe: list[dict] = []
    for err in errors:
        e = {k: v for k, v in dict(err).items() if k != "url"}
        ctx = e.get("ctx")
        if isinstance(ctx, dict):
            e["ctx"] = {k: (str(v) if isinstance(v, Exception) else v) for k, v in ctx.items()}
        if isinstance(e.get("input"), (bytes, bytearray)):
            e["input"] = "<bytes>"
        safe.append(e)
    return safe


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": _safe_errors(exc.errors())},
    )


@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok"}