"""RAG 算命 MVP —— FastAPI 入口。"""
from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs("data", exist_ok=True)
    yield


app = FastAPI(title="RAG 算命", lifespan=lifespan)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


app.include_router(router)
app.mount("/", StaticFiles(directory="static", html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    # 默认监听 0.0.0.0，便于内网穿透/局域网访问；只想本机访问可设 HOST=127.0.0.1
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8300"))
    uvicorn.run(app, host=host, port=port)