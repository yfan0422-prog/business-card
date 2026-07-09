"""测试繁简中文一体化搜索"""
import pytest
from app.chinese_utils import to_simplified, to_traditional, get_search_variants


class TestChineseConversion:
    def test_traditional_to_simplified(self):
        result = to_simplified("繁體字與簡體字一體化搜索")
        assert "体" in result
        assert "与" in result
        assert result == "繁体字与简体字一体化搜索"

    def test_simplified_to_traditional(self):
        result = to_traditional("简体字搜索测试")
        assert "體" in result
        assert "測" in result
        assert result == "簡體字搜索測試"

    def test_empty_string(self):
        assert to_simplified("") == ""
        assert to_traditional("") == ""
        assert to_simplified(None) is None

    def test_no_chinese_text(self):
        result = to_simplified("Hello World 123")
        assert result == "Hello World 123"

    def test_mixed_text(self):
        result = to_simplified("AI人工智能與機器學習")
        assert "与" in result
        assert "AI" in result

    def test_common_traditional_chars(self):
        """测试常见的繁简对应"""
        pairs = [
            ("國家", "国家"),
            ("學習", "学习"),
            ("機器", "机器"),
            ("網絡", "网络"),
            ("數據", "数据"),
            ("開發", "开发"),
            ("銀行", "银行"),
            ("聯繫", "联系"),
        ]
        for trad, simp in pairs:
            assert to_simplified(trad) == simp
            assert to_traditional(simp) == trad


class TestSearchVariants:
    def test_simplified_query_generates_both(self):
        variants = get_search_variants("国家")
        assert "国家" in variants  # 简体
        assert "國家" in variants  # 繁体
        assert len(variants) == 2

    def test_traditional_query_generates_both(self):
        variants = get_search_variants("學習")
        assert "學習" in variants  # 繁体
        assert "学习" in variants  # 简体
        assert len(variants) == 2

    def test_same_in_both_scripts(self):
        """某些词繁简相同"""
        variants = get_search_variants("人")
        assert "人" in variants
        # 繁简相同则只有一个变体

    def test_empty_query(self):
        assert get_search_variants("") == [""]
        assert get_search_variants(None) == [None]

    def test_no_duplicates(self):
        variants = get_search_variants("测试")
        assert len(variants) == len(set(variants))
