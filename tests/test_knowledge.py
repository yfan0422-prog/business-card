"""测试随记知识库功能"""
import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from app.knowledge_crud import knowledge_crud, CRUDKnowledge
from app.knowledge_engine import KnowledgeEngine, FILE_INTERPRET_PROMPT, IMAGE_ANALYZE_PROMPT


class TestKnowledgeCRUD:
    def test_create_entry(self):
        db = Mock()
        entry = knowledge_crud.create(
            db, title="测试标题", content="测试内容",
            entry_type="text", tags="tag1,tag2"
        )
        db.add.assert_called_once()
        db.commit.assert_called_once()

    def test_get_entry(self):
        db = Mock()
        knowledge_crud.get(db, 1)
        db.query.assert_called_once()

    def test_list_recent(self):
        db = Mock()
        knowledge_crud.list_recent(db, limit=10, offset=0)
        db.query.assert_called_once()

    def test_count(self):
        db = Mock()
        knowledge_crud.count(db)
        db.query.assert_called_once()

    def test_search(self):
        db = Mock()
        knowledge_crud.search(db, "关键词")
        db.query.assert_called_once()

    def test_get_by_type(self):
        db = Mock()
        knowledge_crud.get_by_type(db, "voice", limit=5)
        db.query.assert_called_once()

    def test_delete(self):
        db = Mock()
        mock_entry = Mock()
        mock_entry.id = 1
        # Simulate get returning an entry
        db.query.return_value.filter.return_value.first.return_value = mock_entry
        result = knowledge_crud.delete(db, 1)
        assert result is True

    def test_delete_nonexistent(self):
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = None
        result = knowledge_crud.delete(db, 999)
        assert result is False

    def test_link_contact_new(self):
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = None
        result = knowledge_crud.link_contact(db, 1, 2)
        db.add.assert_called_once()
        db.commit.assert_called_once()
        assert result is not None

    def test_link_contact_existing(self):
        db = Mock()
        existing = Mock()
        db.query.return_value.filter.return_value.first.return_value = existing
        result = knowledge_crud.link_contact(db, 1, 2)
        assert result == existing

    def test_unlink_contact_found(self):
        db = Mock()
        link = Mock()
        db.query.return_value.filter.return_value.first.return_value = link
        result = knowledge_crud.unlink_contact(db, 1, 2)
        assert result is True
        db.delete.assert_called_once()

    def test_unlink_contact_not_found(self):
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = None
        result = knowledge_crud.unlink_contact(db, 1, 2)
        assert result is False


class TestKnowledgeEngine:
    def setup_method(self):
        self.engine = KnowledgeEngine(
            api_base="https://api.example.com",
            api_key="test-key",
            model_name="test-model"
        )

    def test_init_strips_trailing_slash(self):
        engine = KnowledgeEngine(
            api_base="https://api.example.com/v1/",
            api_key="test-key",
            model_name="test-model"
        )
        assert engine.api_base == "https://api.example.com/v1"

    def test_interpret_file_not_exists(self):
        result = self.engine.interpret_file(Path("/nonexistent/file.txt"))
        assert "error" in result
        assert "不存在" in result["error"]

    def test_interpret_file_empty(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False) as f:
            f.write("   ")
            tmp_path = Path(f.name)
        try:
            result = self.engine.interpret_file(tmp_path)
            assert "error" in result
        finally:
            tmp_path.unlink()

    @patch('app.knowledge_engine.requests.post')
    def test_interpret_file_success(self, mock_post):
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": json.dumps({
                "title": "AI发展趋势",
                "summary": "本文讨论了AI的最新进展",
                "key_points": ["要点1", "要点2", "要点3"],
                "tags": ["AI", "技术", "趋势"]
            })}}]
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False) as f:
            f.write("这是一篇关于人工智能发展趋势的文章。")
            tmp_path = Path(f.name)
        try:
            result = self.engine.interpret_file(tmp_path)
            assert result["title"] == "AI发展趋势"
            assert len(result["key_points"]) == 3
            assert len(result["tags"]) == 3
            mock_post.assert_called_once()
        finally:
            tmp_path.unlink()

    @patch('app.knowledge_engine.requests.post')
    def test_interpret_file_timeout(self, mock_post):
        import requests as req
        mock_post.side_effect = req.exceptions.Timeout()

        with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False) as f:
            f.write("test content")
            tmp_path = Path(f.name)
        try:
            result = self.engine.interpret_file(tmp_path)
            assert "error" in result
            assert "超时" in result["error"]
        finally:
            tmp_path.unlink()

    def test_analyze_image_not_exists(self):
        result = self.engine.analyze_image(Path("/nonexistent/img.jpg"))
        assert "error" in result
        assert "不存在" in result["error"]

    @patch('app.knowledge_engine.requests.post')
    def test_analyze_image_success(self, mock_post):
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": json.dumps({
                "description": "一张会议白板照片",
                "extracted_text": "Q3目标：提升用户留存",
                "key_points": ["产品留存策略", "用户增长计划"],
                "tags": ["会议", "产品"]
            })}}]
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' ", #\x1c\x1c\x1c\x1f\x1f\x1f\x1f?J\xff\xd9')
            tmp_path = Path(f.name)
        try:
            result = self.engine.analyze_image(tmp_path)
            assert result["description"] == "一张会议白板照片"
            assert len(result["key_points"]) == 2
        finally:
            tmp_path.unlink()

    def test_read_file_txt(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False) as f:
            f.write("Hello World")
            tmp_path = Path(f.name)
        try:
            content = self.engine._read_file_content(tmp_path)
            assert content == "Hello World"
        finally:
            tmp_path.unlink()

    def test_read_file_md(self):
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
            f.write("# Title\n\nContent here")
            tmp_path = Path(f.name)
        try:
            content = self.engine._read_file_content(tmp_path)
            assert "# Title" in content
        finally:
            tmp_path.unlink()

    def test_read_file_unsupported_format(self):
        with tempfile.NamedTemporaryFile(suffix=".xyz", mode="w", delete=False) as f:
            f.write("data")
            tmp_path = Path(f.name)
        try:
            content = self.engine._read_file_content(tmp_path)
            assert "不支持" in content
        finally:
            tmp_path.unlink()

    def test_parse_response_direct_json(self):
        content = '{"title": "测试", "summary": "摘要", "key_points": ["a", "b"], "tags": ["t1"]}'
        result = self.engine._parse_response(content)
        assert result["title"] == "测试"

    def test_parse_response_json_in_code_block(self):
        content = '```json\n{"title": "测试", "summary": "摘要", "key_points": ["a"], "tags": ["t1"]}\n```'
        result = self.engine._parse_response(content)
        assert result["title"] == "测试"

    def test_parse_response_invalid(self):
        content = "这不是有效的JSON"
        result = self.engine._parse_response(content)
        assert "error" in result


class TestCompanyResearch:
    def setup_method(self):
        self.engine = KnowledgeEngine(
            api_base="https://api.example.com",
            api_key="test-key",
            model_name="test-model"
        )

    @patch('app.knowledge_engine.requests.post')
    def test_research_company_success(self, mock_post):
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": json.dumps({
                "is_known": True,
                "company_intro": "腾讯是一家互联网科技公司，主营社交、游戏、金融科技等业务。",
                "business_performance": "2024年Q3营收1672亿元，同比增长8%。",
                "hot_news": [
                    {"title": "腾讯发布新游戏", "summary": "腾讯游戏发布多款新品", "time": "2024年12月"},
                    {"title": "微信生态持续扩张", "summary": "微信小程序日活突破6亿", "time": "2024年11月"}
                ],
                "disclaimer": "以上信息基于训练数据。"
            })}}]
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        result = self.engine.research_company("腾讯")
        assert result["is_known"] is True
        assert "腾讯" in result["company_intro"]
        assert len(result["hot_news"]) == 2
        assert result["hot_news"][0]["title"] == "腾讯发布新游戏"
        mock_post.assert_called_once()

    @patch('app.knowledge_engine.requests.post')
    def test_research_company_not_known(self, mock_post):
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": json.dumps({
                "is_known": False,
                "company_intro": "",
                "business_performance": "",
                "hot_news": [],
                "disclaimer": "不了解该公司。"
            })}}]
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        result = self.engine.research_company("未知小公司")
        assert result["is_known"] is False

    @patch('app.knowledge_engine.requests.post')
    def test_research_company_timeout(self, mock_post):
        import requests as req
        mock_post.side_effect = req.exceptions.Timeout()

        result = self.engine.research_company("腾讯")
        assert "error" in result
        assert "超时" in result["error"]


class TestRenderCardPage:
    def test_card_page_with_company_info(self):
        from app.web_ui import render_card_page
        from unittest.mock import Mock

        contact = Mock()
        contact.id = 1
        contact.name = "张三"
        contact.company = "腾讯"
        contact.position = "工程师"
        contact.department = None
        contact.mobile = None
        contact.phone = None
        contact.email = None
        contact.company_address = None
        contact.notes = None

        company_info = {
            "name": "腾讯",
            "description": "互联网科技公司",
            "business_performance": "营收增长8%",
            "website": "https://www.tencent.com",
        }
        company_news = [
            {"title": "新闻1", "summary": "摘要1", "time": "2024年12月"},
            {"title": "新闻2", "summary": "摘要2", "time": "2024年11月"},
        ]
        knowledge_entries = [
            {"id": 1, "title": "会议记录", "content": "讨论了合作方案", "entry_type": "text",
             "created_at": "2024-12-01 10:00", "created_at_iso": "2024-12-01T10:00:00"},
        ]

        html = render_card_page(
            contact, True, "test_card.jpg",
            company_info=company_info,
            company_news=company_news,
            knowledge_entries=knowledge_entries
        )

        assert "张三" in html
        assert "腾讯" in html
        assert "互联网科技公司" in html
        assert "营收增长8%" in html
        assert "新闻1" in html
        assert "新闻2" in html
        assert "会议记录" in html
        assert "近期热点新闻" in html
        assert "相关随记" in html
        assert "refreshCompanyInfo" in html

    def test_card_page_without_company(self):
        from app.web_ui import render_card_page
        from unittest.mock import Mock

        contact = Mock()
        contact.id = 2
        contact.name = "李四"
        contact.company = None
        contact.position = None

        html = render_card_page(contact, False, "", company_info=None, company_news=None, knowledge_entries=[])
        assert "李四" in html
        assert "AI 研究该公司" not in html
        assert "相关随记" in html  # 空状态也会显示
