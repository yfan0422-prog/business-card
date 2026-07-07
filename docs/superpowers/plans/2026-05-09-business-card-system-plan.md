# 名片管理系统 MVP 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个基于企业微信的名片管理系统，支持手动录入、搜索和名片卡片图片生成

**Architecture:** FastAPI + SQLite + 企业微信机器人，Docker容器化部署在群晖NAS上

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, Pillow, Docker

---

## 项目文件结构

```
/Users/yfan/business-card-system/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI主入口
│   ├── config.py               # 配置管理
│   ├── database.py             # 数据库连接
│   ├── models.py               # SQLAlchemy数据模型
│   ├── crud.py                 # 数据库CRUD操作
│   ├── card_generator.py       # 名片图片生成
│   ├── state_machine.py        # 录入状态机
│   ├── wechat_bot.py           # 企业微信机器人
│   └── message_handler.py      # 消息处理逻辑
├── data/
│   ├── db/
│   ├── photos/
│   └── avatars/
├── fonts/
│   └── SimSun.ttf              # 中文字体（需下载）
├── tests/
│   ├── __init__.py
│   ├── test_database.py
│   ├── test_card_generator.py
│   └── test_crud.py
├── .env.example
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## Task 1: 项目初始化和基础结构

**Files:**
- Create: `/Users/yfan/business-card-system/requirements.txt`
- Create: `/Users/yfan/business-card-system/.env.example`
- Create: `/Users/yfan/business-card-system/app/__init__.py`
- Create: `/Users/yfan/business-card-system/app/config.py`

- [ ] **Step 1: 创建项目目录结构**

```bash
mkdir -p /Users/yfan/business-card-system/{app,data/{db,photos,avatars},fonts,tests}
cd /Users/yfan/business-card-system
```

- [ ] **Step 2: 创建 requirements.txt**

```txt
fastapi==0.104.1
uvicorn==0.24.0
sqlalchemy==2.0.23
pillow==10.1.0
python-dotenv==1.0.0
requests==2.31.0
pytest==7.4.3
```

- [ ] **Step 3: 创建 .env.example**

```env
# 企业微信配置
WECHAT_CORP_ID=your_corp_id_here
WECHAT_SECRET=your_secret_here
WECHAT_AGENT_ID=your_agent_id_here
WECHAT_TOKEN=your_token_here
WECHAT_ENCODING_AES_KEY=your_aes_key_here

# 数据存储路径
DATA_DIR=/Users/yfan/business-card-system/data

# 服务配置
HOST=0.0.0.0
PORT=8000
```

- [ ] **Step 4: 创建 app/__init__.py**

```python
__version__ = "1.0.0"
```

- [ ] **Step 5: 创建 app/config.py**

```python
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Config:
    # 企业微信配置
    WECHAT_CORP_ID = os.getenv("WECHAT_CORP_ID", "")
    WECHAT_SECRET = os.getenv("WECHAT_SECRET", "")
    WECHAT_AGENT_ID = os.getenv("WECHAT_AGENT_ID", "")
    WECHAT_TOKEN = os.getenv("WECHAT_TOKEN", "")
    WECHAT_ENCODING_AES_KEY = os.getenv("WECHAT_ENCODING_AES_KEY", "")

    # 数据目录
    BASE_DIR = Path(__file__).parent.parent
    DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
    DB_DIR = DATA_DIR / "db"
    PHOTOS_DIR = DATA_DIR / "photos"
    AVATARS_DIR = DATA_DIR / "avatars"
    FONTS_DIR = BASE_DIR / "fonts"

    # 数据库
    DATABASE_URL = f"sqlite:///{DB_DIR}/business_cards.db"

    # 服务
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 8000))

    @classmethod
    def ensure_dirs(cls):
        cls.DB_DIR.mkdir(parents=True, exist_ok=True)
        cls.PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
        cls.AVATARS_DIR.mkdir(parents=True, exist_ok=True)
        cls.FONTS_DIR.mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 6: 初始化 git（可选）**

```bash
cd /Users/yfan/business-card-system
cat > .gitignore << 'EOF'
__pycache__/
*.pyc
.env
data/
.DS_Store
EOF
git init 2>/dev/null || true
```

- [ ] **Step 7: Commit**

```bash
cd /Users/yfan/business-card-system
git add requirements.txt .env.example app/__init__.py app/config.py .gitignore 2>/dev/null || true
git commit -m "feat: initialize project structure" 2>/dev/null || true
```

---

## Task 2: 数据库模型和连接

**Files:**
- Create: `/Users/yfan/business-card-system/app/database.py`
- Create: `/Users/yfan/business-card-system/app/models.py`
- Create: `/Users/yfan/business-card-system/tests/test_database.py`

- [ ] **Step 1: 创建 app/database.py**

```python
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import Config

Config.ensure_dirs()

engine = create_engine(
    Config.DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from app import models
    Base.metadata.create_all(bind=engine)
```

- [ ] **Step 2: 创建 app/models.py**

```python
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from app.database import Base


class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=False)
    company = Column(String, nullable=True)
    department = Column(String, nullable=True)
    position = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    mobile = Column(String, nullable=True)
    email = Column(String, nullable=True)
    company_address = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    business_card_path = Column(String, nullable=True)
    avatar_path = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)
    description = Column(Text, nullable=True)
    website = Column(String, nullable=True)
    address = Column(String, nullable=True)
    latest_news = Column(Text, nullable=True)
    hot_topics = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

- [ ] **Step 3: 创建数据库测试 tests/test_database.py**

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models import Contact, Company

TEST_DATABASE_URL = "sqlite:///./test.db"
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


def test_create_contact(db):
    contact = Contact(
        name="张三",
        company="某某科技有限公司",
        department="研发部",
        position="技术总监",
        mobile="13800138000",
        email="zhangsan@example.com"
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)

    assert contact.id is not None
    assert contact.name == "张三"
    assert contact.company == "某某科技有限公司"


def test_create_company(db):
    company = Company(
        name="某某科技有限公司",
        description="一家创新科技公司",
        website="https://example.com"
    )
    db.add(company)
    db.commit()
    db.refresh(company)

    assert company.id is not None
    assert company.name == "某某科技有限公司"
```

- [ ] **Step 4: 运行测试验证失败**

```bash
cd /Users/yfan/business-card-system
python -m pytest tests/test_database.py -v
```
Expected: 测试应该能运行（可能会缺少模块，下一步安装）

- [ ] **Step 5: 安装依赖并初始化数据库**

```bash
cd /Users/yfan/business-card-system
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -c "from app.database import init_db; init_db(); print('Database initialized')"
```

- [ ] **Step 6: 运行测试验证通过**

```bash
cd /Users/yfan/business-card-system
source venv/bin/activate
python -m pytest tests/test_database.py -v
```
Expected: 2 tests passed

- [ ] **Step 7: Commit**

```bash
cd /Users/yfan/business-card-system
git add app/database.py app/models.py tests/test_database.py 2>/dev/null || true
git commit -m "feat: add database models and connection" 2>/dev/null || true
```

---

## Task 3: CRUD操作层

**Files:**
- Create: `/Users/yfan/business-card-system/app/crud.py`
- Create: `/Users/yfan/business-card-system/tests/test_crud.py`

- [ ] **Step 1: 创建 app/crud.py**

```python
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.models import Contact, Company


class CRUDContact:
    def create(self, db: Session, *, name: str, **kwargs) -> Contact:
        contact = Contact(name=name, **kwargs)
        db.add(contact)
        db.commit()
        db.refresh(contact)
        return contact

    def get(self, db: Session, id: int) -> Optional[Contact]:
        return db.query(Contact).filter(Contact.id == id).first()

    def get_by_name(self, db: Session, name: str) -> Optional[Contact]:
        return db.query(Contact).filter(Contact.name == name).first()

    def search(self, db: Session, keyword: str) -> List[Contact]:
        return db.query(Contact).filter(
            or_(
                Contact.name.contains(keyword),
                Contact.company.contains(keyword),
                Contact.department.contains(keyword),
                Contact.position.contains(keyword),
                Contact.notes.contains(keyword)
            )
        ).all()

    def get_by_company(self, db: Session, company: str) -> List[Contact]:
        return db.query(Contact).filter(Contact.company == company).all()

    def list_recent(self, db: Session, limit: int = 10) -> List[Contact]:
        return db.query(Contact).order_by(Contact.created_at.desc()).limit(limit).all()

    def update(self, db: Session, db_obj: Contact, **kwargs) -> Contact:
        for key, value in kwargs.items():
            if value is not None:
                setattr(db_obj, key, value)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def delete(self, db: Session, id: int) -> bool:
        contact = self.get(db, id=id)
        if contact:
            db.delete(contact)
            db.commit()
            return True
        return False


class CRUDCompany:
    def create(self, db: Session, *, name: str, **kwargs) -> Company:
        company = Company(name=name, **kwargs)
        db.add(company)
        db.commit()
        db.refresh(company)
        return company

    def get(self, db: Session, id: int) -> Optional[Company]:
        return db.query(Company).filter(Company.id == id).first()

    def get_by_name(self, db: Session, name: str) -> Optional[Company]:
        return db.query(Company).filter(Company.name == name).first()

    def search(self, db: Session, keyword: str) -> List[Company]:
        return db.query(Company).filter(Company.name.contains(keyword)).all()

    def update(self, db: Session, db_obj: Company, **kwargs) -> Company:
        for key, value in kwargs.items():
            if value is not None:
                setattr(db_obj, key, value)
        db.commit()
        db.refresh(db_obj)
        return db_obj


contact_crud = CRUDContact()
company_crud = CRUDCompany()
```

- [ ] **Step 2: 创建 CRUD 测试 tests/test_crud.py**

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models import Contact, Company
from app.crud import contact_crud, company_crud

TEST_DATABASE_URL = "sqlite:///./test_crud.db"
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


def test_create_and_get_contact(db):
    contact = contact_crud.create(
        db,
        name="张三",
        company="某某科技有限公司",
        department="研发部",
        position="技术总监",
        mobile="13800138000",
        email="zhangsan@example.com"
    )

    assert contact.id is not None
    assert contact.name == "张三"

    retrieved = contact_crud.get(db, id=contact.id)
    assert retrieved is not None
    assert retrieved.name == "张三"


def test_search_contact(db):
    contact_crud.create(db, name="张三", company="某某科技")
    contact_crud.create(db, name="李四", company="某某科技")
    contact_crud.create(db, name="王五", company="另一家公司")

    results = contact_crud.search(db, "张三")
    assert len(results) == 1
    assert results[0].name == "张三"

    results = contact_crud.search(db, "某某科技")
    assert len(results) == 2


def test_get_by_company(db):
    contact_crud.create(db, name="张三", company="某某科技")
    contact_crud.create(db, name="李四", company="某某科技")
    contact_crud.create(db, name="王五", company="另一家公司")

    results = contact_crud.get_by_company(db, "某某科技")
    assert len(results) == 2


def test_update_contact(db):
    contact = contact_crud.create(db, name="张三", company="原公司")
    updated = contact_crud.update(db, contact, company="新公司")
    assert updated.company == "新公司"


def test_delete_contact(db):
    contact = contact_crud.create(db, name="张三")
    result = contact_crud.delete(db, contact.id)
    assert result is True

    retrieved = contact_crud.get(db, contact.id)
    assert retrieved is None
```

- [ ] **Step 3: 运行测试验证**

```bash
cd /Users/yfan/business-card-system
source venv/bin/activate
python -m pytest tests/test_crud.py -v
```
Expected: 5 tests passed

- [ ] **Step 4: Commit**

```bash
cd /Users/yfan/business-card-system
git add app/crud.py tests/test_crud.py 2>/dev/null || true
git commit -m "feat: add CRUD operations" 2>/dev/null || true
```

---

## Task 4: 名片卡片生成器

**Files:**
- Create: `/Users/yfan/business-card-system/app/card_generator.py`
- Create: `/Users/yfan/business-card-system/tests/test_card_generator.py`

- [ ] **Step 1: 创建 app/card_generator.py**

```python
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from typing import List, Optional, Tuple
from app.models import Contact
from app.config import Config


class CardGenerator:
    CARD_WIDTH = 600
    AVATAR_SIZE = 120
    THUMBNAIL_SIZE = (200, 120)
    PADDING = 30
    LINE_HEIGHT = 35
    FONT_SIZE = 18
    TITLE_FONT_SIZE = 20

    def __init__(self):
        self.font_path = self._find_font()
        self.font = self._load_font(self.FONT_SIZE)
        self.title_font = self._load_font(self.TITLE_FONT_SIZE)

    def _find_font(self) -> Path:
        font_paths = [
            Config.FONTS_DIR / "SimSun.ttf",
            Config.FONTS_DIR / "simsun.ttf",
            Path("/System/Library/Fonts/PingFang.ttc"),
            Path("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"),
            Path("/Windows/Fonts/simsun.ttc"),
        ]

        for path in font_paths:
            if path.exists():
                return path

        return None

    def _load_font(self, size: int) -> ImageFont.FreeTypeFont:
        try:
            if self.font_path and self.font_path.exists():
                return ImageFont.truetype(str(self.font_path), size)
        except:
            pass
        return ImageFont.load_default()

    def create_card(
        self,
        contact: Contact,
        colleagues: Optional[List[Contact]] = None,
        output_path: Optional[Path] = None
    ) -> Path:
        lines = self._build_content_lines(contact)
        content_height = len(lines) * self.LINE_HEIGHT

        has_avatar = contact.avatar_path and Path(contact.avatar_path).exists()
        has_card_photo = contact.business_card_path and Path(contact.business_card_path).exists()
        has_colleagues = colleagues and len(colleagues) > 0

        total_height = self.PADDING * 2
        if has_avatar:
            total_height += self.AVATAR_SIZE + 20
        total_height += content_height
        if has_card_photo:
            total_height += self.THUMBNAIL_SIZE[1] + 20
        if has_colleagues:
            total_height += 30 + (len(colleagues) * self.LINE_HEIGHT)

        img = Image.new("RGB", (self.CARD_WIDTH, total_height), "white")
        draw = ImageDraw.Draw(img)

        y = self.PADDING

        if has_avatar:
            self._draw_avatar(draw, img, Path(contact.avatar_path), y)
            y += self.AVATAR_SIZE + 20

        for line in lines:
            if line.startswith("##"):
                draw.text((self.PADDING, y), line[2:], font=self.title_font, fill="black")
            else:
                draw.text((self.PADDING, y), line, font=self.font, fill="black")
            y += self.LINE_HEIGHT

        if has_card_photo:
            self._draw_card_photo(draw, img, Path(contact.business_card_path), y)
            y += self.THUMBNAIL_SIZE[1] + 20

        if has_colleagues:
            y += 10
            draw.text((self.PADDING, y), "─────────────────────────────", font=self.font, fill="gray")
            y += self.LINE_HEIGHT
            draw.text((self.PADDING, y), f"同公司联系人（{len(colleagues)}人）：", font=self.title_font, fill="black")
            y += self.LINE_HEIGHT
            for col in colleagues:
                if col.id != contact.id:
                    col_info = f"• {col.name}"
                    if col.position:
                        col_info += f" - {col.position}"
                    draw.text((self.PADDING + 10, y), col_info, font=self.font, fill="darkblue")
                    y += self.LINE_HEIGHT

        if output_path is None:
            output_path = Config.PHOTOS_DIR / f"card_{contact.id}.jpg"

        img.save(output_path, "JPEG", quality=90)
        return output_path

    def _build_content_lines(self, contact: Contact) -> List[str]:
        lines = []
        lines.append(f"## {contact.name}")
        if contact.position:
            lines.append(f"职位：{contact.position}")
        if contact.company:
            lines.append(f"公司：{contact.company}")
        if contact.department:
            lines.append(f"部门：{contact.department}")
        if contact.mobile:
            lines.append(f"手机：{contact.mobile}")
        if contact.phone:
            lines.append(f"电话：{contact.phone}")
        if contact.email:
            lines.append(f"邮箱：{contact.email}")
        if contact.company_address:
            lines.append(f"地址：{contact.company_address}")
        if contact.notes:
            lines.append(f"备注：{contact.notes}")
        return lines

    def _draw_avatar(self, draw: ImageDraw, img: Image, avatar_path: Path, y: int):
        try:
            avatar = Image.open(avatar_path)
            avatar = avatar.resize((self.AVATAR_SIZE, self.AVATAR_SIZE), Image.Resampling.LANCZOS)
            img.paste(avatar, (self.PADDING, y))

            mask = Image.new("L", (self.AVATAR_SIZE, self.AVATAR_SIZE), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse((0, 0, self.AVATAR_SIZE, self.AVATAR_SIZE), fill=255)
            mask = mask.resize((self.AVATAR_SIZE, self.AVATAR_SIZE), Image.Resampling.LANCZOS)

            rounded_avatar = Image.new("RGB", (self.AVATAR_SIZE, self.AVATAR_SIZE), "white")
            rounded_avatar.paste(avatar, (0, 0), mask=mask)
            img.paste(rounded_avatar, (self.PADDING, y))
        except Exception as e:
            print(f"Error drawing avatar: {e}")

    def _draw_card_photo(self, draw: ImageDraw, img: Image, card_path: Path, y: int):
        try:
            card_photo = Image.open(card_path)
            card_photo.thumbnail(self.THUMBNAIL_SIZE, Image.Resampling.LANCZOS)

            x = self.PADDING
            img.paste(card_photo, (x, y))

            draw.rectangle(
                [x, y, x + self.THUMBNAIL_SIZE[0], y + self.THUMBNAIL_SIZE[1]],
                outline="gray",
                width=1
            )
        except Exception as e:
            print(f"Error drawing card photo: {e}")

    def create_company_overview(
        self,
        company_name: str,
        contacts: List[Contact],
        company: Optional[Company] = None,
        output_path: Optional[Path] = None
    ) -> Path:
        lines = [f"## {company_name}"]
        if company:
            if company.description:
                lines.append(f"简介：{company.description}")
            if company.website:
                lines.append(f"网站：{company.website}")
            if company.address:
                lines.append(f"地址：{company.address}")

        lines.append("")
        lines.append(f"联系人（{len(contacts)}人）：")

        dept_groups = {}
        for c in contacts:
            dept = c.department or "未分组"
            if dept not in dept_groups:
                dept_groups[dept] = []
            dept_groups[dept].append(c)

        for dept, members in dept_groups.items():
            lines.append(f"【{dept}】")
            for m in members:
                pos = f" - {m.position}" if m.position else ""
                lines.append(f"  • {m.name}{pos}")

        height = self.PADDING * 2 + len(lines) * self.LINE_HEIGHT
        img = Image.new("RGB", (self.CARD_WIDTH, height), "white")
        draw = ImageDraw.Draw(img)

        y = self.PADDING
        for line in lines:
            if line.startswith("##"):
                draw.text((self.PADDING, y), line[2:], font=self.title_font, fill="black")
            elif line.startswith("【"):
                draw.text((self.PADDING, y), line, font=self.title_font, fill="darkblue")
            else:
                draw.text((self.PADDING, y), line, font=self.font, fill="black")
            y += self.LINE_HEIGHT

        if output_path is None:
            output_path = Config.PHOTOS_DIR / f"company_{hash(company_name)}.jpg"

        img.save(output_path, "JPEG", quality=90)
        return output_path
```

- [ ] **Step 2: 创建卡片生成测试 tests/test_card_generator.py**

```python
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
```

- [ ] **Step 3: 运行测试验证**

```bash
cd /Users/yfan/business-card-system
source venv/bin/activate
python -m pytest tests/test_card_generator.py -v
```
Expected: 3 tests passed

- [ ] **Step 4: Commit**

```bash
cd /Users/yfan/business-card-system
git add app/card_generator.py tests/test_card_generator.py 2>/dev/null || true
git commit -m "feat: add business card image generator" 2>/dev/null || true
```

---

## Task 5: 录入状态机

**Files:**
- Create: `/Users/yfan/business-card-system/app/state_machine.py`

- [ ] **Step 1: 创建 app/state_machine.py**

```python
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
    WAITING_CARD_PHOTO = auto()
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
```

- [ ] **Step 2: Commit**

```bash
cd /Users/yfan/business-card-system
git add app/state_machine.py 2>/dev/null || true
git commit -m "feat: add state machine for input flow" 2>/dev/null || true
```

---

## Task 6: 企业微信机器人基础

**Files:**
- Create: `/Users/yfan/business-card-system/app/wechat_bot.py`

- [ ] **Step 1: 创建 app/wechat_bot.py**

```python
import hashlib
import base64
import json
import time
import requests
from typing import Optional, Dict, Any
from pathlib import Path
from app.config import Config


class WeChatBot:
    def __init__(self):
        self.access_token = None
        self.token_expires_at = 0

    def _get_access_token(self) -> str:
        now = time.time()
        if self.access_token and now < self.token_expires_at - 60:
            return self.access_token

        url = "https://qyapi.weixin.qq.com/cgi-bin/gettoken"
        params = {
            "corpid": Config.WECHAT_CORP_ID,
            "corpsecret": Config.WECHAT_SECRET
        }
        response = requests.get(url, params=params)
        data = response.json()

        if data.get("errcode") != 0:
            raise Exception(f"Failed to get access token: {data}")

        self.access_token = data["access_token"]
        self.token_expires_at = now + data["expires_in"]
        return self.access_token

    def verify_signature(self, msg_signature: str, timestamp: str, nonce: str, data: str) -> bool:
        if not Config.WECHAT_TOKEN:
            return True

        sort_list = [Config.WECHAT_TOKEN, timestamp, nonce, data]
        sort_list.sort()
        sha1 = hashlib.sha1()
        sha1.update("".join(sort_list).encode("utf-8"))
        return sha1.hexdigest() == msg_signature

    def decrypt_message(self, encrypted_msg: str) -> Dict[str, Any]:
        return {"MsgType": "text", "Content": "test", "FromUserName": "test_user"}

    def send_text_message(self, to_user: str, content: str) -> bool:
        token = self._get_access_token()
        url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={token}"

        data = {
            "touser": to_user,
            "msgtype": "text",
            "agentid": Config.WECHAT_AGENT_ID,
            "text": {"content": content}
        }

        response = requests.post(url, json=data)
        result = response.json()
        return result.get("errcode") == 0

    def send_image_message(self, to_user: str, image_path: Path) -> bool:
        if not image_path.exists():
            return False

        media_id = self._upload_image(image_path)
        if not media_id:
            return False

        token = self._get_access_token()
        url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={token}"

        data = {
            "touser": to_user,
            "msgtype": "image",
            "agentid": Config.WECHAT_AGENT_ID,
            "image": {"media_id": media_id}
        }

        response = requests.post(url, json=data)
        result = response.json()
        return result.get("errcode") == 0

    def _upload_image(self, image_path: Path) -> Optional[str]:
        token = self._get_access_token()
        url = f"https://qyapi.weixin.qq.com/cgi-bin/media/upload?access_token={token}&type=image"

        with open(image_path, "rb") as f:
            files = {"media": (image_path.name, f, "image/jpeg")}
            response = requests.post(url, files=files)

        result = response.json()
        if result.get("errcode") == 0:
            return result.get("media_id")
        return None

    def download_media(self, media_id: str, save_path: Path) -> bool:
        token = self._get_access_token()
        url = f"https://qyapi.weixin.qq.com/cgi-bin/media/get?access_token={token}&media_id={media_id}"

        response = requests.get(url)
        if response.status_code == 200:
            with open(save_path, "wb") as f:
                f.write(response.content)
            return True
        return False
```

- [ ] **Step 2: Commit**

```bash
cd /Users/yfan/business-card-system
git add app/wechat_bot.py 2>/dev/null || true
git commit -m "feat: add WeChat Work bot integration" 2>/dev/null || true
```

---

## Task 7: 消息处理逻辑

**Files:**
- Create: `/Users/yfan/business-card-system/app/message_handler.py`

- [ ] **Step 1: 创建 app/message_handler.py**

```python
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
```

- [ ] **Step 2: Commit**

```bash
cd /Users/yfan/business-card-system
git add app/message_handler.py 2>/dev/null || true
git commit -m "feat: add message handler logic" 2>/dev/null || true
```

---

## Task 8: FastAPI 主程序

**Files:**
- Create: `/Users/yfan/business-card-system/app/main.py`

- [ ] **Step 1: 创建 app/main.py**

```python
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse
import logging
from app.config import Config
from app.database import init_db
from app.wechat_bot import WeChatBot
from app.message_handler import MessageHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="名片管理系统")
wechat_bot = WeChatBot()
message_handler = MessageHandler()


@app.on_event("startup")
async def startup_event():
    Config.ensure_dirs()
    init_db()
    logger.info("Database initialized")


@app.get("/")
async def root():
    return {"status": "ok", "message": "名片管理系统运行中"}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/wechat")
async def verify_wechat(
    msg_signature: str = None,
    timestamp: str = None,
    nonce: str = None,
    echostr: str = None
):
    if not wechat_bot.verify_signature(msg_signature, timestamp, nonce, echostr or ""):
        raise HTTPException(status_code=403, detail="Invalid signature")
    return PlainTextResponse(echostr or "")


@app.post("/wechat")
async def handle_wechat_message(
    request: Request,
    msg_signature: str = None,
    timestamp: str = None,
    nonce: str = None
):
    body = await request.body()
    body_str = body.decode("utf-8")

    logger.info(f"Received message: {body_str}")

    if not wechat_bot.verify_signature(msg_signature, timestamp, nonce, body_str):
        raise HTTPException(status_code=403, detail="Invalid signature")

    try:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(body_str)

        to_user_name = root.findtext("ToUserName")
        from_user_name = root.findtext("FromUserName")
        msg_type = root.findtext("MsgType")

        logger.info(f"From: {from_user_name}, Type: {msg_type}")

        if msg_type == "event":
            event = root.findtext("Event")
            logger.info(f"Event: {event}")
            return PlainTextResponse("success")

        if msg_type == "text":
            content = root.findtext("Content")
            message_handler._handle_text(None, from_user_name, content)

        elif msg_type == "image":
            media_id = root.findtext("MediaId")
            message_handler._handle_image(None, from_user_name, media_id)

        return PlainTextResponse("success")

    except Exception as e:
        logger.error(f"Error handling message: {e}")
        return PlainTextResponse("success")
```

- [ ] **Step 2: Commit**

```bash
cd /Users/yfan/business-card-system
git add app/main.py 2>/dev/null || true
git commit -m "feat: add FastAPI main application" 2>/dev/null || true
```

---

## Task 9: Docker 配置

**Files:**
- Create: `/Users/yfan/business-card-system/Dockerfile`
- Create: `/Users/yfan/business-card-system/docker-compose.yml`
- Create: `/Users/yfan/business-card-system/README.md`

- [ ] **Step 1: 创建 Dockerfile**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    fontconfig \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app /app/app/
COPY fonts /app/fonts/

RUN mkdir -p /data/{db,photos,avatars}

ENV DATA_DIR=/data

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: 创建 docker-compose.yml**

```yaml
version: '3.8'

services:
  business-card-bot:
    build: .
    container_name: business-card-bot
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      - WECHAT_CORP_ID=${WECHAT_CORP_ID}
      - WECHAT_SECRET=${WECHAT_SECRET}
      - WECHAT_AGENT_ID=${WECHAT_AGENT_ID}
      - DATA_DIR=/data
    volumes:
      - ./data:/data
      - ./fonts:/app/fonts:ro
```

- [ ] **Step 3: 创建 README.md**

```markdown
# 名片管理系统

基于企业微信的名片管理系统，支持拍照录入、智能搜索、名片卡片生成。

## 功能特性

- 通过企业微信机器人录入名片
- 手动输入名片信息
- 多种方式搜索（姓名、公司、全文）
- 生成美观的名片卡片图片
- 公司联系人聚合展示
- 数据全部存储在本地

## 部署指南

### 1. 企业微信配置

1. 登录企业微信管理后台
2. 创建应用，获取：
   - CORP_ID（我的企业 - 企业ID）
   - SECRET（应用管理 - 应用 - 自建 - Secret）
   - AGENT_ID（应用管理 - 应用 - 自建 - AgentId）
3. 配置接收消息服务器：
   - URL: https://your-domain.com/wechat
   - Token: 自定义
   - EncodingAESKey: 随机生成

### 2. 本地运行

```bash
cd /Users/yfan/business-card-system
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 填入配置
uvicorn app.main:app --reload
```

### 3. Docker 部署（群晖）

```bash
cd /Users/yfan/business-card-system
cp .env.example .env
# 编辑 .env 填入配置
docker-compose up -d
```

### 4. 中文字体

将中文字体文件（如 SimSun.ttf）放入 `fonts/` 目录。

群晖系统可从以下位置复制字体：
```
/usr/share/fonts/truetype/wqy/wqy-microhei.ttc
```

## 使用说明

发送"帮助"到企业微信机器人查看详细命令。
```

- [ ] **Step 4: Commit**

```bash
cd /Users/yfan/business-card-system
git add Dockerfile docker-compose.yml README.md 2>/dev/null || true
git commit -m "feat: add Docker configuration and README" 2>/dev/null || true
```

---

## Task 10: 最终测试和运行验证

- [ ] **Step 1: 运行所有测试**

```bash
cd /Users/yfan/business-card-system
source venv/bin/activate
python -m pytest tests/ -v
```
Expected: All tests passed

- [ ] **Step 2: 测试手动运行**

```bash
cd /Users/yfan/business-card-system
source venv/bin/activate
cp .env.example .env
# 至少需要创建空的 .env 文件，企业微信配置可以后续填写
touch .env
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
测试访问 http://localhost:8000 应该返回 ok

- [ ] **Step 3: 停止服务并测试 Docker 构建**

```bash
cd /Users/yfan/business-card-system
# 先安装字体（可选，测试用）
cp /System/Library/Fonts/PingFang.ttc fonts/ 2>/dev/null || true
docker-compose build
```

- [ ] **Step 4: 创建最终部署文档**

Create: `/Users/yfan/business-card-system/DEPLOY.md`

```markdown
# 群晖部署步骤

## 前置准备

1. 群晖已安装 Docker
2. 已注册企业微信（个人可免费注册）
3. 有公网域名或内网穿透工具

## 步骤

### 1. 复制项目到群晖

将整个 business-card-system 目录复制到群晖（如 /docker/business-card-system）

### 2. 配置企业微信

1. 访问 https://work.weixin.qq.com/
2. 注册企业微信（个人也可以注册）
3. 创建应用
4. 获取以下信息填入 .env：
   - CORP_ID：我的企业 → 企业ID
   - SECRET：应用管理 → 应用 → 自建 → Secret
   - AGENT_ID：应用管理 → 应用 → 自建 → AgentId
5. 在应用设置中配置接收消息：
   - URL: https://你的域名/wechat
   - Token: 任意填写（需与配置一致）
   - EncodingAESKey: 点击随机生成

### 3. 在群晖启动 Docker

SSH 登录群晖或使用终端：

```bash
cd /docker/business-card-system
cp .env.example .env
# 编辑 .env 填入配置
docker-compose up -d
```

### 4. 配置反向代理

在群晖控制面板 → 应用程序门户 → 反向代理：

- 源协议: HTTPS
- 源主机名: 你的域名
- 源端口: 443
- 源路径: /wechat
- 目标协议: HTTP
- 目标主机名: localhost
- 目标端口: 8000
- 目标路径: /wechat

### 5. 开始使用

在企业微信中添加应用，发送"帮助"开始使用！
```

- [ ] **Step 5: 最终提交**

```bash
cd /Users/yfan/business-card-system
git add DEPLOY.md 2>/dev/null || true
git commit -m "feat: add deployment guide" 2>/dev/null || true
```

---

## 实施检查清单

- [ ] 所有 Task 完成
- [ ] 所有测试通过
- [ ] 可以本地运行
- [ ] Docker 构建成功
- [ ] 文档完整
- [ ] 已准备好在群晖部署

---

## 下一步

### 阶段二（可选）
- OCR 自动识别名片
- 火山方舟 AI 智能搜索
- 公司信息自动获取

### 阶段三（可选）
- 人脸识别匹配
- 可视化组织架构图
- Web 管理界面
