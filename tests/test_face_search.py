"""测试人脸搜索引擎"""
import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from app.face_search import FaceSearchEngine, FACE_COMPARE_PROMPT


class TestFaceSearchInit:
    def test_init_strips_trailing_slash(self):
        engine = FaceSearchEngine(
            api_base="https://api.example.com/v1/",
            api_key="test-key",
            model_name="test-model"
        )
        assert engine.api_base == "https://api.example.com/v1"
        assert engine.api_key == "test-key"
        assert engine.model_name == "test-model"

    def test_init_without_trailing_slash(self):
        engine = FaceSearchEngine(
            api_base="https://api.example.com/v1",
            api_key="test-key",
            model_name="test-model"
        )
        assert engine.api_base == "https://api.example.com/v1"


class TestEncodeImage:
    def test_encodes_jpg_image(self):
        engine = FaceSearchEngine(
            api_base="https://api.example.com",
            api_key="test-key",
            model_name="test-model"
        )
        # Create a minimal valid JPEG
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' ", #\x1c\x1c\x1c\x1f\x1f\x1f\x1f?J\xff\xd9')
            tmp_path = Path(f.name)

        try:
            data_url, mime = engine._encode_image(tmp_path)
            assert data_url.startswith("data:image/jpeg;base64,")
            assert mime == "image/jpeg"
        finally:
            tmp_path.unlink()

    def test_encodes_png_image(self):
        engine = FaceSearchEngine(
            api_base="https://api.example.com",
            api_key="test-key",
            model_name="test-model"
        )
        # Create a minimal valid PNG
        import struct
        def make_png():
            def chunk(chunk_type, data):
                c = chunk_type + data
                crc = struct.pack(">I", 0xDEADBEEF & 0xFFFFFFFF)
                return struct.pack(">I", len(data)) + c + crc
            return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)) + chunk(b'IEND', b'')

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(make_png())
            tmp_path = Path(f.name)

        try:
            data_url, mime = engine._encode_image(tmp_path)
            assert data_url.startswith("data:image/png;base64,")
            assert mime == "image/png"
        finally:
            tmp_path.unlink()

    def test_encodes_webp_image(self):
        engine = FaceSearchEngine(
            api_base="https://api.example.com",
            api_key="test-key",
            model_name="test-model"
        )
        with tempfile.NamedTemporaryFile(suffix=".webp", delete=False) as f:
            f.write(b'RIFF\x00\x00\x00\x00WEBPVP8 \x00\x00\x00\x00')
            tmp_path = Path(f.name)

        try:
            data_url, mime = engine._encode_image(tmp_path)
            assert data_url.startswith("data:image/webp;base64,")
            assert mime == "image/webp"
        finally:
            tmp_path.unlink()

    def test_unknown_extension_defaults_to_jpeg(self):
        engine = FaceSearchEngine(
            api_base="https://api.example.com",
            api_key="test-key",
            model_name="test-model"
        )
        with tempfile.NamedTemporaryFile(suffix=".bmp", delete=False) as f:
            f.write(b'\x00' * 10)
            tmp_path = Path(f.name)

        try:
            data_url, mime = engine._encode_image(tmp_path)
            assert data_url.startswith("data:image/jpeg;base64,")
            assert mime == "image/jpeg"
        finally:
            tmp_path.unlink()


class TestParseResponse:
    def setup_method(self):
        self.engine = FaceSearchEngine(
            api_base="https://api.example.com",
            api_key="test-key",
            model_name="test-model"
        )

    def test_parse_direct_json(self):
        content = '{"is_same_person": true, "confidence": 0.95, "reasoning": "五官一致"}'
        result = self.engine._parse_response(content)
        assert result["is_same_person"] is True
        assert result["confidence"] == 0.95
        assert result["reasoning"] == "五官一致"

    def test_parse_json_in_code_block(self):
        content = '```json\n{"is_same_person": false, "confidence": 0.1, "reasoning": "不同人"}\n```'
        result = self.engine._parse_response(content)
        assert result["is_same_person"] is False
        assert result["confidence"] == 0.1

    def test_parse_json_in_code_block_no_lang(self):
        content = '```\n{"is_same_person": true, "confidence": 0.8, "reasoning": "相似"}\n```'
        result = self.engine._parse_response(content)
        assert result["is_same_person"] is True
        assert result["confidence"] == 0.8

    def test_parse_embedded_json(self):
        content = '根据分析，结论是：\n{"is_same_person": true, "confidence": 0.87, "reasoning": "脸型和五官匹配"}'
        result = self.engine._parse_response(content)
        assert result["is_same_person"] is True
        assert result["confidence"] == 0.87

    def test_parse_invalid_content_returns_error(self):
        content = '这是一段无法解析的文字'
        result = self.engine._parse_response(content)
        assert "error" in result
        assert "无法解析" in result["error"]
        assert content in result["raw"]

    def test_parse_empty_string(self):
        result = self.engine._parse_response("")
        assert "error" in result


class TestCompareFaces:
    def setup_method(self):
        self.engine = FaceSearchEngine(
            api_base="https://api.example.com",
            api_key="test-key",
            model_name="test-model"
        )

    def test_query_image_not_exists(self):
        result = self.engine.compare_faces(
            Path("/nonexistent/query.jpg"),
            Path("/nonexistent/target.jpg")
        )
        assert "error" in result
        assert "不存在" in result["error"]

    def test_target_image_not_exists(self):
        # Create a query image
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' ", #\x1c\x1c\x1c\x1f\x1f\x1f\x1f?J\xff\xd9')
            query_path = Path(f.name)

        try:
            result = self.engine.compare_faces(query_path, Path("/nonexistent/target.jpg"))
            assert "error" in result
            assert "不存在" in result["error"]
        finally:
            query_path.unlink()

    @patch('app.face_search.requests.post')
    def test_successful_comparison(self, mock_post):
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '{"is_same_person": true, "confidence": 0.92, "reasoning": "同一人"}'}}]
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        # Create two temp images
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' ", #\x1c\x1c\x1c\x1f\x1f\x1f\x1f?J\xff\xd9')
            query_path = Path(f.name)
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' ", #\x1c\x1c\x1c\x1f\x1f\x1f\x1f?J\xff\xd9')
            target_path = Path(f.name)

        try:
            result = self.engine.compare_faces(query_path, target_path)
            assert result["is_same_person"] is True
            assert result["confidence"] == 0.92
            assert result["reasoning"] == "同一人"

            # Verify API was called with correct params
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert call_args[0][0] == "https://api.example.com/chat/completions"
            assert call_args[1]["json"]["model"] == "test-model"
        finally:
            query_path.unlink()
            target_path.unlink()

    @patch('app.face_search.requests.post')
    def test_api_timeout(self, mock_post):
        import requests as req
        mock_post.side_effect = req.exceptions.Timeout()

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' ", #\x1c\x1c\x1c\x1f\x1f\x1f\x1f?J\xff\xd9')
            query_path = Path(f.name)
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' ", #\x1c\x1c\x1c\x1f\x1f\x1f\x1f?J\xff\xd9')
            target_path = Path(f.name)

        try:
            result = self.engine.compare_faces(query_path, target_path)
            assert "error" in result
            assert "超时" in result["error"]
        finally:
            query_path.unlink()
            target_path.unlink()

    @patch('app.face_search.requests.post')
    def test_request_exception(self, mock_post):
        import requests as req
        mock_post.side_effect = req.exceptions.ConnectionError("Connection refused")

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' ", #\x1c\x1c\x1c\x1f\x1f\x1f\x1f?J\xff\xd9')
            query_path = Path(f.name)
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' ", #\x1c\x1c\x1c\x1f\x1f\x1f\x1f?J\xff\xd9')
            target_path = Path(f.name)

        try:
            result = self.engine.compare_faces(query_path, target_path)
            assert "error" in result
            assert "API调用失败" in result["error"]
        finally:
            query_path.unlink()
            target_path.unlink()


class TestSearchMatches:
    def setup_method(self):
        self.engine = FaceSearchEngine(
            api_base="https://api.example.com",
            api_key="test-key",
            model_name="test-model"
        )

    def test_empty_contacts(self):
        result = self.engine.search_matches(
            Path("/tmp/query.jpg"), [], Path("/tmp/photos")
        )
        assert result == []

    def test_contacts_without_avatar_skipped(self):
        contact = Mock()
        contact.avatar_path = None
        result = self.engine.search_matches(
            Path("/tmp/query.jpg"), [contact], Path("/tmp/photos")
        )
        assert result == []

    def test_missing_avatar_file_skipped(self):
        contact = Mock()
        contact.avatar_path = "nonexistent_avatar.jpg"
        result = self.engine.search_matches(
            Path("/tmp/query.jpg"), [contact], Path("/tmp/photos")
        )
        assert result == []

    def test_error_result_skipped(self):
        with patch.object(FaceSearchEngine, 'compare_faces',
                          return_value={"error": "API调用失败"}):
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
                f.write(b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' ", #\x1c\x1c\x1c\x1f\x1f\x1f\x1f?J\xff\xd9')
                avatar_path = Path(f.name)

            try:
                contact = Mock()
                contact.avatar_path = avatar_path.name
                result = self.engine.search_matches(
                    avatar_path, [contact], avatar_path.parent
                )
                assert result == []
            finally:
                avatar_path.unlink()

    def test_not_same_person_skipped(self):
        with patch.object(FaceSearchEngine, 'compare_faces',
                          return_value={"is_same_person": False, "confidence": 0.1, "reasoning": "不同人"}):
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
                f.write(b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' ", #\x1c\x1c\x1c\x1f\x1f\x1f\x1f?J\xff\xd9')
                avatar_path = Path(f.name)

            try:
                contact = Mock()
                contact.avatar_path = avatar_path.name
                contact.name = "Test User"
                result = self.engine.search_matches(
                    avatar_path, [contact], avatar_path.parent
                )
                assert result == []
            finally:
                avatar_path.unlink()

    def test_low_confidence_skipped(self):
        with patch.object(FaceSearchEngine, 'compare_faces',
                          return_value={"is_same_person": True, "confidence": 0.3, "reasoning": "不太确定"}):
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
                f.write(b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' ", #\x1c\x1c\x1c\x1f\x1f\x1f\x1f?J\xff\xd9')
                avatar_path = Path(f.name)

            try:
                contact = Mock()
                contact.avatar_path = avatar_path.name
                contact.name = "Test User"
                result = self.engine.search_matches(
                    avatar_path, [contact], avatar_path.parent, confidence_threshold=0.6
                )
                assert result == []
            finally:
                avatar_path.unlink()

    def test_successful_match(self):
        with patch.object(FaceSearchEngine, 'compare_faces',
                          return_value={"is_same_person": True, "confidence": 0.85, "reasoning": "五官匹配"}):
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
                f.write(b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' ", #\x1c\x1c\x1c\x1f\x1f\x1f\x1f?J\xff\xd9')
                avatar_path = Path(f.name)

            try:
                contact = Mock()
                contact.avatar_path = avatar_path.name
                contact.name = "Test User"
                result = self.engine.search_matches(
                    avatar_path, [contact], avatar_path.parent
                )
                assert len(result) == 1
                assert result[0]["contact"] == contact
                assert result[0]["confidence"] == 0.85
                assert result[0]["reasoning"] == "五官匹配"
            finally:
                avatar_path.unlink()

    def test_multiple_matches_sorted_by_confidence(self):
        high_conf = {"is_same_person": True, "confidence": 0.95, "reasoning": "很确定"}
        low_conf = {"is_same_person": True, "confidence": 0.7, "reasoning": "比较像"}

        with patch.object(FaceSearchEngine, 'compare_faces', side_effect=[low_conf, high_conf]):
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
                f.write(b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' ", #\x1c\x1c\x1c\x1f\x1f\x1f\x1f?J\xff\xd9')
                avatar_path = Path(f.name)

            try:
                contact1 = Mock()
                contact1.avatar_path = avatar_path.name
                contact1.name = "User A"
                contact2 = Mock()
                contact2.avatar_path = avatar_path.name
                contact2.name = "User B"

                result = self.engine.search_matches(
                    avatar_path, [contact1, contact2], avatar_path.parent
                )
                assert len(result) == 2
                # Should be sorted by confidence descending
                assert result[0]["confidence"] == 0.95
                assert result[1]["confidence"] == 0.7
            finally:
                avatar_path.unlink()

    def test_custom_confidence_threshold(self):
        with patch.object(FaceSearchEngine, 'compare_faces',
                          return_value={"is_same_person": True, "confidence": 0.75, "reasoning": "可能是"}):
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
                f.write(b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' ", #\x1c\x1c\x1c\x1f\x1f\x1f\x1f?J\xff\xd9')
                avatar_path = Path(f.name)

            try:
                contact = Mock()
                contact.avatar_path = avatar_path.name
                # Threshold 0.6 → should match (0.75 >= 0.6)
                result_low = self.engine.search_matches(
                    avatar_path, [contact], avatar_path.parent, confidence_threshold=0.6
                )
                assert len(result_low) == 1

                # Threshold 0.8 → should NOT match (0.75 < 0.8)
                result_high = self.engine.search_matches(
                    avatar_path, [contact], avatar_path.parent, confidence_threshold=0.8
                )
                assert len(result_high) == 0
            finally:
                avatar_path.unlink()
