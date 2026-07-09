from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.models import KnowledgeEntry, KnowledgeContactLink
from app.chinese_utils import get_search_variants


def _build_chinese_search_fields(model, fields: list, keyword: str):
    """构建繁简一体化搜索条件"""
    variants = get_search_variants(keyword)
    all_filters = []
    for variant in variants:
        all_filters.extend([field.contains(variant) for field in fields])
    return or_(*all_filters)


class CRUDKnowledge:
    def create(self, db: Session, *, title: str, content: str, entry_type: str = "text", **kwargs) -> KnowledgeEntry:
        entry = KnowledgeEntry(title=title, content=content, entry_type=entry_type, **kwargs)
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry

    def get(self, db: Session, id: int) -> Optional[KnowledgeEntry]:
        return db.query(KnowledgeEntry).filter(KnowledgeEntry.id == id).first()

    def list_recent(self, db: Session, limit: int = 20, offset: int = 0) -> List[KnowledgeEntry]:
        return db.query(KnowledgeEntry).order_by(
            KnowledgeEntry.created_at.desc()
        ).offset(offset).limit(limit).all()

    def count(self, db: Session) -> int:
        return db.query(KnowledgeEntry).count()

    def count_by_type(self, db: Session, entry_type: str) -> int:
        return db.query(KnowledgeEntry).filter(KnowledgeEntry.entry_type == entry_type).count()

    def search(self, db: Session, keyword: str, limit: int = 20) -> List[KnowledgeEntry]:
        search_fields = [
            KnowledgeEntry.title, KnowledgeEntry.content,
            KnowledgeEntry.tags, KnowledgeEntry.audio_transcript,
        ]
        return db.query(KnowledgeEntry).filter(
            _build_chinese_search_fields(KnowledgeEntry, search_fields, keyword)
        ).order_by(KnowledgeEntry.created_at.desc()).limit(limit).all()

    def get_by_contact(self, db: Session, contact_id: int) -> List[KnowledgeEntry]:
        return db.query(KnowledgeEntry).join(
            KnowledgeContactLink,
            KnowledgeEntry.id == KnowledgeContactLink.knowledge_id
        ).filter(KnowledgeContactLink.contact_id == contact_id).order_by(
            KnowledgeEntry.created_at.desc()
        ).all()

    def get_by_type(self, db: Session, entry_type: str, limit: int = 20) -> List[KnowledgeEntry]:
        return db.query(KnowledgeEntry).filter(
            KnowledgeEntry.entry_type == entry_type
        ).order_by(KnowledgeEntry.created_at.desc()).limit(limit).all()

    def update(self, db: Session, db_obj: KnowledgeEntry, **kwargs) -> KnowledgeEntry:
        for key, value in kwargs.items():
            if value is not None:
                setattr(db_obj, key, value)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def delete(self, db: Session, id: int) -> bool:
        entry = self.get(db, id=id)
        if entry:
            db.delete(entry)
            db.commit()
            return True
        return False

    def link_contact(self, db: Session, knowledge_id: int, contact_id: int) -> Optional[KnowledgeContactLink]:
        existing = db.query(KnowledgeContactLink).filter(
            KnowledgeContactLink.knowledge_id == knowledge_id,
            KnowledgeContactLink.contact_id == contact_id
        ).first()
        if existing:
            return existing
        link = KnowledgeContactLink(knowledge_id=knowledge_id, contact_id=contact_id)
        db.add(link)
        db.commit()
        db.refresh(link)
        return link

    def unlink_contact(self, db: Session, knowledge_id: int, contact_id: int) -> bool:
        link = db.query(KnowledgeContactLink).filter(
            KnowledgeContactLink.knowledge_id == knowledge_id,
            KnowledgeContactLink.contact_id == contact_id
        ).first()
        if link:
            db.delete(link)
            db.commit()
            return True
        return False

    def get_linked_contact_ids(self, db: Session, knowledge_id: int) -> List[int]:
        links = db.query(KnowledgeContactLink).filter(
            KnowledgeContactLink.knowledge_id == knowledge_id
        ).all()
        return [l.contact_id for l in links]


knowledge_crud = CRUDKnowledge()
