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
    _migrate_columns()


def _migrate_columns():
    """为已有表添加新列（SQLite 兼容）"""
    import sqlite3
    try:
        conn = sqlite3.connect(str(Config.DB_DIR / "business_cards.db"))
        _migrate_contacts(conn)
        _migrate_companies(conn)
        conn.close()
    except Exception:
        pass


def _migrate_contacts(conn):
    """迁移 contacts 表新列"""
    cursor = conn.execute("PRAGMA table_info(contacts)")
    existing = {row[1] for row in cursor.fetchall()}
    new_columns = [
        ("name_en", "TEXT"),
        ("company_en", "TEXT"),
        ("department_en", "TEXT"),
        ("position_en", "TEXT"),
        ("business_card_path_2", "TEXT"),
    ]
    for col_name, col_type in new_columns:
        if col_name not in existing:
            conn.execute(f"ALTER TABLE contacts ADD COLUMN {col_name} {col_type}")
    conn.commit()


def _migrate_companies(conn):
    """迁移 companies 表新列"""
    cursor = conn.execute("PRAGMA table_info(companies)")
    existing = {row[1] for row in cursor.fetchall()}
    if "org_structure" not in existing:
        conn.execute("ALTER TABLE companies ADD COLUMN org_structure TEXT")
    conn.commit()
