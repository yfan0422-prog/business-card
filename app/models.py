from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from app.database import Base


class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=False)
    name_en = Column(String, nullable=True)
    company = Column(String, nullable=True)
    company_en = Column(String, nullable=True)
    department = Column(String, nullable=True)
    department_en = Column(String, nullable=True)
    position = Column(String, nullable=True)
    position_en = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    mobile = Column(String, nullable=True)
    email = Column(String, nullable=True)
    company_address = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    business_card_path = Column(String, nullable=True)
    business_card_path_2 = Column(String, nullable=True)
    avatar_path = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)
    description = Column(Text, nullable=True)
    website = Column(String, nullable=True)
    address = Column(String, nullable=True)
    latest_news = Column(Text, nullable=True)
    hot_topics = Column(Text, nullable=True)
    org_structure = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AIModel(Base):
    __tablename__ = "ai_models"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=False)
    provider = Column(String, nullable=False)
    api_base = Column(String, nullable=False)
    api_key = Column(String, nullable=False)
    model_name = Column(String, nullable=False)
    is_active = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class KnowledgeEntry(Base):
    __tablename__ = "knowledge_entries"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    entry_type = Column(String(20), nullable=False, default="text")  # voice, file, photo, text
    file_path = Column(String, nullable=True)
    audio_transcript = Column(Text, nullable=True)
    image_annotation = Column(Text, nullable=True)
    source_description = Column(String(200), nullable=True)
    tags = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class KnowledgeContactLink(Base):
    __tablename__ = "knowledge_contact_links"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    knowledge_id = Column(Integer, nullable=False, index=True)
    contact_id = Column(Integer, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
