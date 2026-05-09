from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse
import logging
from app.config import Config
from app.database import init_db
from app.wechat_bot import WeChatBot
from app.message_handler import MessageHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="名片管理系统")
wechat_bot = WeChatBot()
message_handler = MessageHandler()


@app.on_event("startup")
async def startup_event():
    Config.ensure_dirs()
    init_db()
    logger.info("Database initialized")


@app.get("/")
async def root():
    return {"status": "ok", "message": "名片管理系统运行中"}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/wechat")
async def verify_wechat(
    msg_signature: str = None,
    timestamp: str = None,
    nonce: str = None,
    echostr: str = None
):
    if not wechat_bot.verify_signature(msg_signature, timestamp, nonce, echostr or ""):
        raise HTTPException(status_code=403, detail="Invalid signature")
    return PlainTextResponse(echostr or "")


@app.post("/wechat")
async def handle_wechat_message(
    request: Request,
    msg_signature: str = None,
    timestamp: str = None,
    nonce: str = None
):
    body = await request.body()
    body_str = body.decode("utf-8")

    logger.info(f"Received message: {body_str}")

    if not wechat_bot.verify_signature(msg_signature, timestamp, nonce, body_str):
        raise HTTPException(status_code=403, detail="Invalid signature")

    try:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(body_str)

        to_user_name = root.findtext("ToUserName")
        from_user_name = root.findtext("FromUserName")
        msg_type = root.findtext("MsgType")

        logger.info(f"From: {from_user_name}, Type: {msg_type}")

        if msg_type == "event":
            event = root.findtext("Event")
            logger.info(f"Event: {event}")
            return PlainTextResponse("success")

        if msg_type == "text":
            content = root.findtext("Content")
            message_handler._handle_text(None, from_user_name, content)

        elif msg_type == "image":
            media_id = root.findtext("MediaId")
            message_handler._handle_image(None, from_user_name, media_id)

        return PlainTextResponse("success")

    except Exception as e:
        logger.error(f"Error handling message: {e}")
        return PlainTextResponse("success")
