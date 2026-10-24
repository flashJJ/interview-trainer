"""面试题录入训练系统 - FastAPI 应用入口。"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import init_db
from .routers import (
    analytics,
    auth,
    chat,
    exams,
    knowledge,
    questions,
    retrieval,
    settings,
    wrong_questions,
)
from .routers import settings as settings_router
from .services.runtime import get_embeddings, get_llm

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    mode = "AI 模式（LLM + Embedding API）" if get_llm().enabled else "演示模式（内置规则引擎）"
    print(f"[startup] {settings.app_name} 已启动，运行模式：{mode}")
    yield


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(knowledge.router, prefix=settings.api_prefix)
app.include_router(questions.router, prefix=settings.api_prefix)
app.include_router(exams.router, prefix=settings.api_prefix)
app.include_router(analytics.router, prefix=settings.api_prefix)
app.include_router(settings_router.router, prefix=settings.api_prefix)
app.include_router(wrong_questions.router, prefix=settings.api_prefix)
app.include_router(chat.router, prefix=settings.api_prefix)
app.include_router(retrieval.router, prefix=settings.api_prefix)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "app": settings.app_name,
        "llm_enabled": get_llm().enabled,
        "embedding_mode": get_embeddings().mode,
    }


@app.get("/")
def root():
    return {"app": settings.app_name, "docs": "/docs", "health": "/api/health"}
