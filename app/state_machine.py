from typing import Dict, Any, Optional, Callable
from enum import Enum, auto
from dataclasses import dataclass


class InputState(Enum):
    IDLE = auto()
    WAITING_NAME = auto()
    WAITING_COMPANY = auto()
    WAITING_DEPARTMENT = auto()
    WAITING_POSITION = auto()
    WAITING_MOBILE = auto()
    WAITING_PHONE = auto()
    WAITING_EMAIL = auto()
    WAITING_ADDRESS = auto()
    WAITING_NOTES = auto()
    WAITING_AVATAR = auto()
    EDITING = auto()


@dataclass
class UserSession:
    user_id: str
    state: InputState = InputState.IDLE
    contact_data: Dict[str, Any] = None
    temp_card_photo_path: Optional[str] = None
    editing_contact_id: Optional[int] = None

    def reset(self):
        self.state = InputState.IDLE
        self.contact_data = {}
        self.temp_card_photo_path = None
        self.editing_contact_id = None


class StateMachine:
    INPUT_FIELDS = [
        ("name", "姓名", InputState.WAITING_NAME),
        ("company", "公司名称", InputState.WAITING_COMPANY),
        ("department", "部门（可选，输入'跳过'）", InputState.WAITING_DEPARTMENT, True),
        ("position", "职位（可选，输入'跳过'）", InputState.WAITING_POSITION, True),
        ("mobile", "手机（可选，输入'跳过'）", InputState.WAITING_MOBILE, True),
        ("phone", "电话（可选，输入'跳过'）", InputState.WAITING_PHONE, True),
        ("email", "邮箱（可选，输入'跳过'）", InputState.WAITING_EMAIL, True),
        ("company_address", "地址（可选，输入'跳过'）", InputState.WAITING_ADDRESS, True),
        ("notes", "备注（可选，输入'跳过'）", InputState.WAITING_NOTES, True),
    ]

    def __init__(self):
        self.sessions: Dict[str, UserSession] = {}

    def get_session(self, user_id: str) -> UserSession:
        if user_id not in self.sessions:
            self.sessions[user_id] = UserSession(user_id=user_id, contact_data={})
        return self.sessions[user_id]

    def start_new_entry(self, user_id: str, card_photo_path: Optional[str] = None) -> str:
        session = self.get_session(user_id)
        session.reset()
        session.temp_card_photo_path = card_photo_path
        return self._proceed_to_next_field(session)

    def start_edit(self, user_id: str, contact_id: int, current_data: Dict[str, Any]) -> str:
        session = self.get_session(user_id)
        session.reset()
        session.editing_contact_id = contact_id
        session.contact_data = current_data.copy()
        session.state = InputState.EDITING
        return self._get_edit_menu()

    def process_input(self, user_id: str, text: str) -> tuple[bool, str, Optional[Dict[str, Any]]]:
        session = self.get_session(user_id)

        if session.state == InputState.EDITING:
            return self._process_edit_input(session, text)

        if session.state == InputState.WAITING_AVATAR:
            return self._process_avatar_input(session, text)

        field_info = self._get_field_info(session.state)
        if not field_info:
            return False, "当前不在录入状态，请发送'新增'开始录入", None

        field_name, _, _, is_optional = field_info

        if is_optional and text.strip() in ["跳过", "跳过。", ""]:
            session.contact_data[field_name] = None
            return True, self._proceed_to_next_field(session), None

        session.contact_data[field_name] = text.strip()
        return True, self._proceed_to_next_field(session), None

    def _get_field_info(self, state: InputState):
        for field in self.INPUT_FIELDS:
            if field[2] == state:
                return field if len(field) >= 4 else field + (False,)
        return None

    def _proceed_to_next_field(self, session: UserSession) -> str:
        current_idx = -1

        for i, field in enumerate(self.INPUT_FIELDS):
            if field[2] == session.state:
                current_idx = i
                break

        next_idx = current_idx + 1

        if next_idx >= len(self.INPUT_FIELDS):
            session.state = InputState.WAITING_AVATAR
            return "是否上传头像照片？（请直接发送照片，或回复'跳过'）"

        next_field = self.INPUT_FIELDS[next_idx]
        session.state = next_field[2]
        return f"请输入{next_field[1]}："

    def _process_avatar_input(self, session: UserSession, text: str) -> tuple[bool, str, Optional[Dict[str, Any]]]:
        if text.strip() in ["跳过", "跳过。", ""]:
            session.contact_data["avatar_path"] = None
        else:
            session.contact_data["avatar_path"] = text

        session.contact_data["business_card_path"] = session.temp_card_photo_path

        session.state = InputState.IDLE
        data = session.contact_data.copy()
        session.reset()

        return True, "录入完成！", data

    def _get_edit_menu(self) -> str:
        return """请选择要编辑的字段：
1. 姓名
2. 公司
3. 部门
4. 职位
5. 手机
6. 电话
7. 邮箱
8. 地址
9. 备注
0. 完成编辑

请回复数字或字段名称"""

    def _process_edit_input(self, session: UserSession, text: str) -> tuple[bool, str, Optional[Dict[str, Any]]]:
        text = text.strip()

        if text in ["0", "完成", "完成编辑"]:
            data = session.contact_data.copy()
            contact_id = session.editing_contact_id
            session.reset()
            return True, "编辑完成！", {"id": contact_id, **data}

        field_map = {
            "1": "name", "姓名": "name",
            "2": "company", "公司": "company",
            "3": "department", "部门": "department",
            "4": "position", "职位": "position",
            "5": "mobile": "mobile", "手机": "mobile",
            "6": "phone": "phone", "电话": "phone",
            "7": "email": "email", "邮箱": "email",
            "8": "company_address": "company_address", "地址": "company_address",
            "9": "notes": "notes", "备注": "notes",
        }

        if text in field_map:
            session.editing_field = field_map[text]
            return True, f"请输入新的{text}：", None

        if hasattr(session, "editing_field"):
            session.contact_data[session.editing_field] = text
            delattr(session, "editing_field")
            return True, f"已更新！\n{self._get_edit_menu()}", None

        return True, self._get_edit_menu(), None
