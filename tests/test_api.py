"""测试 FastAPI 端点和 Web UI API"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, SessionLocal, engine


@pytest.fixture
def client():
    """创建测试客户端，使用内存数据库"""
    # 确保表存在
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_root_redirects_to_web(self, client):
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 307  # Temporary redirect


class TestWebAPI:
    def test_api_contacts_returns_list(self, client):
        response = client.get("/web/api/contacts")
        assert response.status_code == 200
        data = response.json()
        assert "contacts" in data
        assert "companies" in data
        assert isinstance(data["contacts"], list)
        assert isinstance(data["companies"], list)

    def test_web_home_returns_html(self, client):
        response = client.get("/web/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "名片管理系统" in response.text

    def test_web_new_returns_form(self, client):
        response = client.get("/web/new")
        assert response.status_code == 200
        assert "添加新名片" in response.text

    def test_api_contacts_with_search(self, client):
        response = client.get("/web/api/contacts?q=不存在的名字")
        assert response.status_code == 200
        data = response.json()
        assert data["contacts"] == []


class TestContactSave:
    def test_save_new_contact(self, client):
        response = client.post("/web/save", data={
            "name": "测试用户",
            "company": "测试公司",
            "department": "测试部",
            "position": "工程师",
            "mobile": "13800138000",
            "email": "test@test.com",
            "notes": "自动化测试"
        }, follow_redirects=False)
        assert response.status_code == 302

        # 验证数据已保存
        db = SessionLocal()
        from app.crud import contact_crud
        contact = contact_crud.get_by_name(db, "测试用户")
        assert contact is not None
        assert contact.company == "测试公司"
        db.close()

    def test_save_contact_empty_name_fails(self, client):
        response = client.post("/web/save", data={
            "name": "   ",
            "company": "测试公司"
        })
        assert response.status_code == 400  # Validation error handled

    def test_save_and_update_contact(self, client):
        # 创建
        response = client.post("/web/save", data={
            "name": "待更新用户",
            "company": "原公司"
        }, follow_redirects=False)
        assert response.status_code == 302

        # 查找 ID
        db = SessionLocal()
        from app.crud import contact_crud
        contact = contact_crud.get_by_name(db, "待更新用户")
        contact_id = contact.id
        db.close()

        # 更新
        response = client.post("/web/save", data={
            "id": str(contact_id),
            "name": "已更新用户",
            "company": "新公司"
        }, follow_redirects=False)
        assert response.status_code == 302

        # 验证更新
        db = SessionLocal()
        updated = contact_crud.get(db, contact_id)
        assert updated.name == "已更新用户"
        assert updated.company == "新公司"
        db.close()


class TestWebPages:
    def test_edit_page_nonexistent_redirects(self, client):
        response = client.get("/web/edit/99999", follow_redirects=False)
        assert response.status_code == 302

    def test_card_page_nonexistent_redirects(self, client):
        response = client.get("/web/card/99999", follow_redirects=False)
        assert response.status_code == 302

    def test_company_page_nonexistent_redirects(self, client):
        response = client.get("/web/company/99999", follow_redirects=False)
        assert response.status_code == 302

    def test_photo_nonexistent_returns_error(self, client):
        response = client.get("/web/photo/nonexistent.jpg")
        assert response.status_code == 200
        assert "error" in response.json()
