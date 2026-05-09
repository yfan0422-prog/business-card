import uuid
from pathlib import Path
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from app.config import Config
from app.state_machine import StateMachine, InputState
from app.crud import contact_crud, company_crud
from app.card_generator import CardGenerator
from app.wechat_bot import WeChatBot
from app.database import SessionLocal


class MessageHandler:
    def __init__(self):
        self.state_machine = StateMachine()
        self.card_generator = CardGenerator()
        self.wechat_bot = WeChatBot()

    def handle_message(
        self,
        user_id: str,
        message_type: str,
        content: Optional[str] = None,
        media_id: Optional[str] = None
    ):
        db = SessionLocal()
        try:
            if message_type == "image":
                self._handle_image(db, user_id, media_id)
            elif message_type == "text":
                self._handle_text(db, user_id, content)
            else:
                self.wechat_bot.send_text_message(user_id, "暂不支持此类型消息")
        finally:
            db.close()

    def _handle_image(self, db: Session, user_id: str, media_id: str):
        session = self.state_machine.get_session(user_id)

        if session.state == InputState.WAITING_AVATAR:
            filename = f"avatar_{uuid.uuid4().hex[:8]}.jpg"
            save_path = Config.AVATARS_DIR / filename
            if self.wechat_bot.download_media(media_id, save_path):
                done, reply, data = self.state_machine.process_input(user_id, str(save_path))
                self.wechat_bot.send_text_message(user_id, reply)
                if data:
                    self._finish_entry(db, user_id, data)
            else:
                self.wechat_bot.send_text_message(user_id, "头像保存失败，请重试")
            return

        filename = f"card_{uuid.uuid4().hex[:8]}.jpg"
        save_path = Config.PHOTOS_DIR / filename

        if self.wechat_bot.download_media(media_id, save_path):
            reply = self.state_machine.start_new_entry(user_id, str(save_path))
            self.wechat_bot.send_text_message(user_id, f"收到名片照片！{reply}")
        else:
            self.wechat_bot.send_text_message(user_id, "照片保存失败，请重试")

    def _handle_text(self, db: Session, user_id: str, content: str):
        content = content.strip()

        session = self.state_machine.get_session(user_id)

        if session.state != InputState.IDLE and session.state != InputState.EDITING:
            done, reply, data = self.state_machine.process_input(user_id, content)
            self.wechat_bot.send_text_message(user_id, reply)
            if data:
                self._finish_entry(db, user_id, data)
            return

        if self._is_command(content):
            self._handle_command(db, user_id, content)
            return

        results = contact_crud.search(db, content)
        if len(results) == 1:
            self._send_contact_card(db, user_id, results[0])
        elif len(results) > 1:
            names = "、".join([c.name for c in results[:10]])
            self.wechat_bot.send_text_message(user_id, f"找到多个联系人：{names}\n请输入更精确的姓名")
        else:
            self.wechat_bot.send_text_message(user_id, f"未找到\"{content}\"相关的联系人\n发送'帮助'查看可用命令")

    def _is_command(self, content: str) -> bool:
        commands = ["帮助", "help", "搜索", "search", "列表", "list", "新增", "new", "编辑", "edit", "删除", "delete", "公司", "company"]
        for cmd in commands:
            if content.startswith(cmd):
                return True
        return False

    def _handle_command(self, db: Session, user_id: str, content: str):
        if content in ["帮助", "help"]:
            self._send_help(user_id)
        elif content.startswith("搜索") or content.startswith("search"):
            keyword = content[2:].strip() if content.startswith("搜索") else content[6:].strip()
            if keyword:
                self._search_and_send(db, user_id, keyword)
            else:
                self.wechat_bot.send_text_message(user_id, "请输入搜索关键词，如：搜索张三")
        elif content in ["列表", "list"]:
            self._list_recent(db, user_id)
        elif content in ["新增", "new"]:
            reply = self.state_machine.start_new_entry(user_id)
            self.wechat_bot.send_text_message(user_id, reply)
        elif content.startswith("编辑") or content.startswith("edit"):
            name = content[2:].strip() if content.startswith("编辑") else content[4:].strip()
            if name:
                self._start_edit(db, user_id, name)
            else:
                self.wechat_bot.send_text_message(user_id, "请输入要编辑的联系人姓名，如：编辑张三")
        elif content.startswith("删除") or content.startswith("delete"):
            name = content[2:].strip() if content.startswith("删除") else content[6:].strip()
            if name:
                self._delete_contact(db, user_id, name)
            else:
                self.wechat_bot.send_text_message(user_id, "请输入要删除的联系人姓名，如：删除张三")
        elif content.startswith("公司") or content.startswith("company"):
            name = content[2:].strip() if content.startswith("公司") else content[7:].strip()
            if name:
                self._show_company(db, user_id, name)
            else:
                self.wechat_bot.send_text_message(user_id, "请输入公司名称，如：公司某某科技")
        else:
            self._send_help(user_id)

    def _send_help(self, user_id: str):
        help_text = """名片管理系统使用指南：

【录入名片】
直接发送名片照片，按提示输入信息

【搜索名片】
直接输入姓名、公司等关键词
或：搜索 张三

【查看公司】
公司 某某科技

【其他命令】
帮助 - 显示此帮助
列表 - 查看最近录入的名片
新增 - 开始新增名片（无照片）
编辑 姓名 - 编辑联系人
删除 姓名 - 删除联系人"""
        self.wechat_bot.send_text_message(user_id, help_text)

    def _search_and_send(self, db: Session, user_id: str, keyword: str):
        results = contact_crud.search(db, keyword)
        if not results:
            self.wechat_bot.send_text_message(user_id, f"未找到\"{keyword}\"相关的联系人")
        elif len(results) == 1:
            self._send_contact_card(db, user_id, results[0])
        else:
            names = "、".join([c.name for c in results[:10]])
            self.wechat_bot.send_text_message(user_id, f"找到 {len(results)} 位联系人：{names}\n请输入更精确的姓名")

    def _send_contact_card(self, db: Session, user_id: str, contact):
        colleagues = []
        if contact.company:
            colleagues = contact_crud.get_by_company(db, contact.company)
        card_path = self.card_generator.create_card(contact, colleagues)
        if card_path and card_path.exists():
            self.wechat_bot.send_image_message(user_id, card_path)
        else:
            info = f"{contact.name} - {contact.company or '无公司'}"
            self.wechat_bot.send_text_message(user_id, info)

    def _list_recent(self, db: Session, user_id: str):
        contacts = contact_crud.list_recent(db, limit=15)
        if not contacts:
            self.wechat_bot.send_text_message(user_id, "暂无名片记录")
        else:
            lines = ["最近录入的名片："]
            for i, c in enumerate(contacts, 1):
                line = f"{i}. {c.name}"
                if c.company:
                    line += f" - {c.company}"
                lines.append(line)
            self.wechat_bot.send_text_message(user_id, "\n".join(lines))

    def _start_edit(self, db: Session, user_id: str, name: str):
        contact = contact_crud.get_by_name(db, name)
        if not contact:
            self.wechat_bot.send_text_message(user_id, f"未找到联系人\"{name}\"")
            return

        data = {
            "name": contact.name,
            "company": contact.company,
            "department": contact.department,
            "position": contact.position,
            "mobile": contact.mobile,
            "phone": contact.phone,
            "email": contact.email,
            "company_address": contact.company_address,
            "notes": contact.notes,
        }
        reply = self.state_machine.start_edit(user_id, contact.id, data)
        self.wechat_bot.send_text_message(user_id, reply)

    def _delete_contact(self, db: Session, user_id: str, name: str):
        contact = contact_crud.get_by_name(db, name)
        if not contact:
            self.wechat_bot.send_text_message(user_id, f"未找到联系人\"{name}\"")
            return
        contact_crud.delete(db, contact.id)
        self.wechat_bot.send_text_message(user_id, f"已删除联系人：{name}")

    def _show_company(self, db: Session, user_id: str, company_name: str):
        contacts = contact_crud.get_by_company(db, company_name)
        if not contacts:
            self.wechat_bot.send_text_message(user_id, f"未找到公司\"{company_name}\"的联系人")
            return

        company = company_crud.get_by_name(db, company_name)
        card_path = self.card_generator.create_company_overview(company_name, contacts, company)
        if card_path and card_path.exists():
            self.wechat_bot.send_image_message(user_id, card_path)
        else:
            names = "、".join([c.name for c in contacts])
            self.wechat_bot.send_text_message(user_id, f"{company_name} 联系人：{names}")

    def _finish_entry(self, db: Session, user_id: str, data: dict):
        if "id" in data:
            contact_id = data.pop("id")
            contact = contact_crud.get(db, contact_id)
            if contact:
                contact_crud.update(db, contact, **data)
                self.wechat_bot.send_text_message(user_id, "联系人已更新！")
                self._send_contact_card(db, user_id, contact)
        else:
            contact = contact_crud.create(db, **data)
            self.wechat_bot.send_text_message(user_id, "名片录入成功！")
            self._send_contact_card(db, user_id, contact)

            if data.get("company"):
                existing = company_crud.get_by_name(db, data["company"])
                if not existing:
                    company_crud.create(db, name=data["company"])
