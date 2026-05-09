import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models import Contact, Company
from app.crud import contact_crud, company_crud

TEST_DATABASE_URL = "sqlite:///./test_crud.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_create_and_get_contact(db):
    contact = contact_crud.create(
        db,
        name="张三",
        company="某某科技有限公司",
        department="研发部",
        position="技术总监",
        mobile="13800138000",
        email="zhangsan@example.com"
    )

    assert contact.id is not None
    assert contact.name == "张三"

    retrieved = contact_crud.get(db, id=contact.id)
    assert retrieved is not None
    assert retrieved.name == "张三"


def test_search_contact(db):
    contact_crud.create(db, name="张三", company="某某科技")
    contact_crud.create(db, name="李四", company="某某科技")
    contact_crud.create(db, name="王五", company="另一家公司")

    results = contact_crud.search(db, "张三")
    assert len(results) == 1
    assert results[0].name == "张三"

    results = contact_crud.search(db, "某某科技")
    assert len(results) == 2


def test_get_by_company(db):
    contact_crud.create(db, name="张三", company="某某科技")
    contact_crud.create(db, name="李四", company="某某科技")
    contact_crud.create(db, name="王五", company="另一家公司")

    results = contact_crud.get_by_company(db, "某某科技")
    assert len(results) == 2


def test_update_contact(db):
    contact = contact_crud.create(db, name="张三", company="原公司")
    updated = contact_crud.update(db, contact, company="新公司")
    assert updated.company == "新公司"


def test_delete_contact(db):
    contact = contact_crud.create(db, name="张三")
    result = contact_crud.delete(db, contact.id)
    assert result is True

    retrieved = contact_crud.get(db, contact.id)
    assert retrieved is None
