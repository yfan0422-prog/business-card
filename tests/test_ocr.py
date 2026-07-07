"""测试 OCR 引擎"""
import json
import pytest
from pathlib import Path
from unittest.mock import patch, Mock
from app.ocr import OCREngine


class TestOCRParseResponse:
    def setup_method(self):
        self.engine = OCREngine(
            api_base="https://test.api.com/v1",
            api_key="sk-test",
            model_name="test-v1"
        )

    def test_parse_direct_json(self):
        content = '{"name":"张三","company":"某科技","mobile":"13800138000"}'
        result = self.engine._parse_response(content)
        assert result["name"] == "张三"
        assert result["company"] == "某科技"

    def test_parse_json_block(self):
        content = '这是一张名片\n```json\n{"name":"李四","company":"ABC公司"}\n```\n识别完成'
        result = self.engine._parse_response(content)
        assert result["name"] == "李四"

    def test_parse_json_block_no_lang(self):
        content = '识别结果:\n```\n{"name":"王五"}\n```'
        result = self.engine._parse_response(content)
        assert result["name"] == "王五"

    def test_parse_embedded_json(self):
        content = '根据分析，返回内容如下：{"name":"赵六","position":"总监","mobile":"13900139000"}'
        result = self.engine._parse_response(content)
        assert result["name"] == "赵六"

    def test_parse_invalid_content(self):
        content = "无法识别这张图片，请重新拍照"
        result = self.engine._parse_response(content)
        assert "error" in result


class TestOCREngineRecognize:
    def test_file_not_exists(self):
        engine = OCREngine("https://test.com", "sk-123", "test")
        result = engine.recognize(Path("/nonexistent/path.jpg"))
        assert "error" in result
        assert "不存在" in result["error"]

    @patch("app.ocr.requests.post")
    def test_successful_recognition(self, mock_post):
        mock_resp = Mock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": '{"name":"张三","company":"某科技","mobile":"13800138000"}'}}]
        }
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        # Create a test image
        test_img = Path("/tmp/test_card_ocr.jpg")
        from PIL import Image
        img = Image.new("RGB", (100, 100), color="white")
        img.save(test_img)

        engine = OCREngine("https://test.com", "sk-123", "test-v1")
        result = engine.recognize(test_img)

        assert result["name"] == "张三"
        assert result["company"] == "某科技"
        test_img.unlink(missing_ok=True)

    @patch("app.ocr.requests.post")
    def test_api_timeout(self, mock_post):
        import requests as req
        mock_post.side_effect = req.exceptions.Timeout()

        test_img = Path("/tmp/test_card_ocr2.jpg")
        from PIL import Image
        img = Image.new("RGB", (100, 100), color="white")
        img.save(test_img)

        engine = OCREngine("https://test.com", "sk-123", "test-v1")
        result = engine.recognize(test_img)

        assert "error" in result
        assert "超时" in result["error"]
        test_img.unlink(missing_ok=True)
