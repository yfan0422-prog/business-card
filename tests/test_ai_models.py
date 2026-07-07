"""测试 AI 模型管理 CRUD"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.ai_models import ai_model_manager

TEST_DATABASE_URL = "sqlite:///./test_ai_models.db"
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


class TestAIModelManager:
    def test_create_model(self, db):
        model = ai_model_manager.create(
            db, name="GLM-5.2", provider="智谱AI",
            api_base="https://open.bigmodel.cn/api/paas/v4",
            api_key="sk-test123", model_name="glm-4v-flash"
        )
        assert model.id is not None
        assert model.name == "GLM-5.2"
        assert model.provider == "智谱AI"

    def test_get_model(self, db):
        created = ai_model_manager.create(
            db, name="Test", provider="Test",
            api_base="https://test.com/v1", api_key="sk-123",
            model_name="test-v1"
        )
        retrieved = ai_model_manager.get(db, created.id)
        assert retrieved.name == "Test"

    def test_list_all(self, db):
        ai_model_manager.create(
            db, name="M1", provider="P1",
            api_base="https://a.com", api_key="k1", model_name="m1"
        )
        ai_model_manager.create(
            db, name="M2", provider="P2",
            api_base="https://b.com", api_key="k2", model_name="m2"
        )
        models = ai_model_manager.list_all(db)
        assert len(models) == 2

    def test_set_active(self, db):
        m1 = ai_model_manager.create(
            db, name="M1", provider="P1",
            api_base="https://a.com", api_key="k1", model_name="m1"
        )
        m2 = ai_model_manager.create(
            db, name="M2", provider="P2",
            api_base="https://b.com", api_key="k2", model_name="m2"
        )
        # Activate first
        ai_model_manager.set_active(db, m1.id)
        active = ai_model_manager.get_active(db)
        assert active.id == m1.id

        # Switch to second
        ai_model_manager.set_active(db, m2.id)
        active = ai_model_manager.get_active(db)
        assert active.id == m2.id

    def test_get_active_none(self, db):
        active = ai_model_manager.get_active(db)
        assert active is None

    def test_update_model(self, db):
        m = ai_model_manager.create(
            db, name="Old", provider="Old",
            api_base="https://old.com", api_key="sk-old",
            model_name="old-v1"
        )
        updated = ai_model_manager.update(db, m.id, name="New")
        assert updated.name == "New"

    def test_delete_model(self, db):
        m = ai_model_manager.create(
            db, name="ToDelete", provider="X",
            api_base="https://x.com", api_key="sk-x",
            model_name="x-v1"
        )
        assert ai_model_manager.delete(db, m.id) is True
        assert ai_model_manager.get(db, m.id) is None

    def test_delete_nonexistent(self, db):
        assert ai_model_manager.delete(db, 999) is False

    def test_update_nonexistent(self, db):
        assert ai_model_manager.update(db, 999, name="X") is None
