from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import Config

Config.ensure_dirs()

engine = create_engine(
    Config.DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from app import models
    Base.metadata.create_all(bind=engine)
    # 轻量迁移：为已有数据库添加新列
    _migrate_columns()


def _migrate_columns():
    """为已有表添加新列（SQLite 兼容）"""
    import sqlite3
    try:
        conn = sqlite3.connect(str(Config.DB_DIR / "business_cards.db"))
        cursor = conn.execute("PRAGMA table_info(companies)")
        existing = {row[1] for row in cursor.fetchall()}
        if "org_structure" not in existing:
            conn.execute("ALTER TABLE companies ADD COLUMN org_structure TEXT")
            conn.commit()
        conn.close()
    except Exception:
        pass
