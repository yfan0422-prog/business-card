"""测试 state_machine 状态机"""
import pytest
from app.state_machine import StateMachine, InputState, UserSession


class TestUserSession:
    def test_new_session_defaults(self):
        session = UserSession(user_id="user1")
        assert session.user_id == "user1"
        assert session.state == InputState.IDLE
        assert session.contact_data == {}
        assert session.temp_card_photo_path is None
        assert session.editing_contact_id is None

    def test_reset_clears_all_data(self):
        session = UserSession(
            user_id="user1",
            state=InputState.WAITING_NAME,
            contact_data={"name": "test"},
            temp_card_photo_path="/tmp/photo.jpg",
            editing_contact_id=42
        )
        session.reset()
        assert session.state == InputState.IDLE
        assert session.contact_data == {}
        assert session.temp_card_photo_path is None
        assert session.editing_contact_id is None


class TestStateMachine:
    def test_get_session_creates_new(self):
        sm = StateMachine()
        session = sm.get_session("user1")
        assert session.user_id == "user1"
        assert session.state == InputState.IDLE

    def test_get_session_returns_existing(self):
        sm = StateMachine()
        session1 = sm.get_session("user1")
        session1.state = InputState.WAITING_NAME
        session2 = sm.get_session("user1")
        assert session2.state == InputState.WAITING_NAME

    def test_start_new_entry_begins_name_input(self):
        sm = StateMachine()
        reply = sm.start_new_entry("user1")
        assert "姓名" in reply
        session = sm.get_session("user1")
        assert session.state == InputState.WAITING_NAME

    def test_start_new_entry_with_card_photo(self):
        sm = StateMachine()
        reply = sm.start_new_entry("user1", card_photo_path="/tmp/card.jpg")
        assert "姓名" in reply
        session = sm.get_session("user1")
        assert session.temp_card_photo_path == "/tmp/card.jpg"

    def test_process_name_input(self):
        sm = StateMachine()
        sm.start_new_entry("user1")
        done, reply, data = sm.process_input("user1", "张三")
        assert done is True
        assert data is None
        assert "公司" in reply
        session = sm.get_session("user1")
        assert session.contact_data["name"] == "张三"

    def test_process_company_input(self):
        sm = StateMachine()
        sm.start_new_entry("user1")
        sm.process_input("user1", "张三")
        done, reply, data = sm.process_input("user1", "某科技公司")
        assert "部门" in reply
        session = sm.get_session("user1")
        assert session.contact_data["company"] == "某科技公司"

    def test_skip_optional_field(self):
        sm = StateMachine()
        sm.start_new_entry("user1")
        sm.process_input("user1", "张三")
        sm.process_input("user1", "某公司")
        done, reply, data = sm.process_input("user1", "跳过")
        assert done is True
        assert data is None
        session = sm.get_session("user1")
        assert session.contact_data["department"] is None

    def test_process_all_fields_to_completion(self):
        sm = StateMachine()
        sm.start_new_entry("user1")

        fields_and_values = [
            "张三",           # name
            "某科技公司",      # company
            "研发部",          # department
            "技术总监",        # position
            "13800138000",    # mobile
            "010-12345678",   # phone
            "test@test.com",  # email
            "北京市朝阳区",    # company_address
            "2024年认识",      # notes
        ]

        for value in fields_and_values:
            done, reply, data = sm.process_input("user1", value)
            if data:
                break  # reached completion

        # After all fields, should ask for avatar
        session = sm.get_session("user1")
        assert session.state == InputState.WAITING_AVATAR

    def test_avatar_skip_completes_entry(self):
        sm = StateMachine()
        sm.start_new_entry("user1")
        for val in ["张三", "某公司", "跳过", "跳过", "跳过", "跳过", "跳过", "跳过", "跳过"]:
            sm.process_input("user1", val)

        done, reply, data = sm.process_input("user1", "跳过")
        assert done is True
        assert data is not None
        assert data["name"] == "张三"
        assert data["company"] == "某公司"
        assert data["business_card_path"] is None

    def test_process_input_when_idle_returns_error(self):
        sm = StateMachine()
        done, reply, data = sm.process_input("user1", "随便输入")
        assert done is False
        assert "不在录入状态" in reply

    def test_start_edit_shows_menu(self):
        sm = StateMachine()
        reply = sm.start_edit("user1", 1, {"name": "张三", "company": "某公司"})
        assert "编辑" in reply
        session = sm.get_session("user1")
        assert session.state == InputState.EDITING
        assert session.editing_contact_id == 1

    def test_edit_select_field(self):
        sm = StateMachine()
        sm.start_edit("user1", 1, {"name": "张三", "company": "某公司"})
        done, reply, data = sm.process_input("user1", "1")
        assert done is True
        assert data is None
        assert "姓名" in reply

    def test_edit_input_new_value(self):
        sm = StateMachine()
        sm.start_edit("user1", 1, {"name": "张三", "company": "某公司"})
        sm.process_input("user1", "1")  # select name field
        done, reply, data = sm.process_input("user1", "李四")
        assert done is True
        assert "已更新" in reply

    def test_edit_complete_returns_data(self):
        sm = StateMachine()
        sm.start_edit("user1", 42, {"name": "张三", "company": "某公司"})
        done, reply, data = sm.process_input("user1", "0")
        assert done is True
        assert data is not None
        assert data["id"] == 42
        assert data["name"] == "张三"

    def test_edit_by_field_name(self):
        sm = StateMachine()
        sm.start_edit("user1", 1, {"name": "张三"})
        done, reply, data = sm.process_input("user1", "姓名")
        assert done is True
        assert "姓名" in reply

    def test_start_new_entry_resets_previous_session(self):
        sm = StateMachine()
        sm.start_new_entry("user1")
        sm.process_input("user1", "张三")

        # Start a new entry
        sm.start_new_entry("user1")
        session = sm.get_session("user1")
        assert session.contact_data == {}
        assert session.state == InputState.WAITING_NAME
