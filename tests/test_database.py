import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models import Contact, Company

TEST_DATABASE_URL = "sqlite:///./test.db"
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


def test_create_contact(db):
    contact = Contact(
        name="张三",
        company="某某科技有限公司",
        department="研发部",
        position="技术总监",
        mobile="13800138000",
        email="zhangsan@example.com"
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)

    assert contact.id is not None
    assert contact.name == "张三"
    assert contact.company == "某某科技有限公司"


def test_create_company(db):
    company = Company(
        name="某某科技有限公司",
        description="一家创新科技公司",
        website="https://example.com"
    )
    db.add(company)
    db.commit()
    db.refresh(company)

    assert company.id is not None
    assert company.name == "某某科技有限公司"
