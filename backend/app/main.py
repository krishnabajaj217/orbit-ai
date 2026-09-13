from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.chat import router as chat_router
from .config import get_settings
from .llm.ollama import is_reachable


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield


app = FastAPI(
    title="Orbit Agent V2",
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


app.include_router(chat_router)


@app.get("/api/health")
async def health() -> dict[str, object]:

    settings = get_settings()

    reachable = await is_reachable()

    return {
        "backend": "running",
        "ollama": (
            "reachable"
            if reachable
            else "unreachable"
        ),
        "model": settings.ollama_model,
    }