import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Config:
    # 企业微信配置
    WECHAT_CORP_ID = os.getenv("WECHAT_CORP_ID", "")
    WECHAT_SECRET = os.getenv("WECHAT_SECRET", "")
    WECHAT_AGENT_ID = os.getenv("WECHAT_AGENT_ID", "")
    WECHAT_TOKEN = os.getenv("WECHAT_TOKEN", "")
    WECHAT_ENCODING_AES_KEY = os.getenv("WECHAT_ENCODING_AES_KEY", "")

    # 数据目录
    BASE_DIR = Path(__file__).parent.parent
    DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
    DB_DIR = DATA_DIR / "db"
    PHOTOS_DIR = DATA_DIR / "photos"
    AVATARS_DIR = DATA_DIR / "avatars"
    FONTS_DIR = BASE_DIR / "fonts"

    # 数据库
    DATABASE_URL = f"sqlite:///{DB_DIR}/business_cards.db"

    # 服务
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 8000))

    @classmethod
    def ensure_dirs(cls):
        cls.DB_DIR.mkdir(parents=True, exist_ok=True)
        cls.PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
        cls.AVATARS_DIR.mkdir(parents=True, exist_ok=True)
        cls.FONTS_DIR.mkdir(parents=True, exist_ok=True)
