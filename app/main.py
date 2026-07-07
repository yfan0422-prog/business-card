import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from app.config import Config
from app.database import init_db
from app import web_ui

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="名片管理系统")

# 静态文件（PWA 图标等）
static_path = Path(__file__).parent / "static"
static_path.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

# Web管理界面
app.include_router(web_ui.router, prefix="/web")


@app.on_event("startup")
async def startup_event():
    Config.ensure_dirs()
    init_db()
    logger.info("Database initialized")


@app.get("/")
async def root():
    return RedirectResponse("/web/")


@app.get("/health")
async def health():
    return {"status": "ok"}
