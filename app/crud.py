from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.models import Contact, Company
from app.chinese_utils import get_search_variants


def _build_search_filters(model, fields: list, keyword: str):
    """为单个关键词构建跨字段搜索条件"""
    return or_(*[field.contains(keyword) for field in fields])


def _build_chinese_search(model, fields: list, keyword: str):
    """构建繁简一体化搜索条件 — 对关键词的所有繁简变体做 OR 搜索"""
    variants = get_search_variants(keyword)
    all_filters = []
    for variant in variants:
        all_filters.extend([field.contains(variant) for field in fields])
    return or_(*all_filters)


class CRUDContact:
    def create(self, db: Session, *, name: str, **kwargs) -> Contact:
        contact = Contact(name=name, **kwargs)
        db.add(contact)
        db.commit()
        db.refresh(contact)
        return contact

    def get(self, db: Session, id: int) -> Optional[Contact]:
        return db.query(Contact).filter(Contact.id == id).first()

    def get_by_name(self, db: Session, name: str) -> Optional[Contact]:
        return db.query(Contact).filter(Contact.name == name).first()

    def search(self, db: Session, keyword: str) -> List[Contact]:
        search_fields = [
            Contact.name, Contact.name_en, Contact.company, Contact.company_en,
            Contact.department, Contact.department_en,
            Contact.position, Contact.position_en, Contact.notes
        ]
        return db.query(Contact).filter(
            _build_chinese_search(Contact, search_fields, keyword)
        ).all()

    def get_by_company(self, db: Session, company: str) -> List[Contact]:
        return db.query(Contact).filter(Contact.company == company).all()

    def list_recent(self, db: Session, limit: int = 10) -> List[Contact]:
        return db.query(Contact).order_by(Contact.created_at.desc()).limit(limit).all()

    def update(self, db: Session, db_obj: Contact, **kwargs) -> Contact:
        for key, value in kwargs.items():
            if value is not None:
                setattr(db_obj, key, value)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def delete(self, db: Session, id: int) -> bool:
        contact = self.get(db, id=id)
        if contact:
            db.delete(contact)
            db.commit()
            return True
        return False


class CRUDCompany:
    def create(self, db: Session, *, name: str, **kwargs) -> Company:
        company = Company(name=name, **kwargs)
        db.add(company)
        db.commit()
        db.refresh(company)
        return company

    def get(self, db: Session, id: int) -> Optional[Company]:
        return db.query(Company).filter(Company.id == id).first()

    def get_by_name(self, db: Session, name: str) -> Optional[Company]:
        return db.query(Company).filter(Company.name == name).first()

    def search(self, db: Session, keyword: str) -> List[Company]:
        return db.query(Company).filter(
            _build_chinese_search(Company, [Company.name], keyword)
        ).all()

    def update(self, db: Session, db_obj: Company, **kwargs) -> Company:
        for key, value in kwargs.items():
            if value is not None:
                setattr(db_obj, key, value)
        db.commit()
        db.refresh(db_obj)
        return db_obj


contact_crud = CRUDContact()
company_crud = CRUDCompany()
