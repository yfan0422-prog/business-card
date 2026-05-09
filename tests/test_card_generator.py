import pytest
from pathlib import Path
from app.card_generator import CardGenerator
from app.models import Contact


def test_card_generator_initialization():
    generator = CardGenerator()
    assert generator is not None


def test_build_content_lines():
    generator = CardGenerator()
    contact = Contact(
        name="张三",
        company="某某科技有限公司",
        department="研发部",
        position="技术总监",
        mobile="13800138000",
        email="zhangsan@example.com",
        notes="2023年会议认识"
    )

    lines = generator._build_content_lines(contact)
    assert "## 张三" in lines
    assert "职位：技术总监" in lines
    assert "公司：某某科技有限公司" in lines


def test_create_card_basic():
    generator = CardGenerator()
    contact = Contact(
        id=1,
        name="张三",
        company="某某科技有限公司",
        mobile="13800138000"
    )

    output_path = Path("/tmp/test_card.jpg")
    result_path = generator.create_card(contact, output_path=output_path)

    assert result_path.exists()
    result_path.unlink(missing_ok=True)
