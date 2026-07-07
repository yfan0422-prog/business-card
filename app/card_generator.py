import logging
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from typing import List, Optional, Tuple
from app.models import Contact, Company
from app.config import Config

logger = logging.getLogger(__name__)


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
            Config.FONTS_DIR / "STHeiti.ttc",
            Path("/System/Library/Fonts/STHeiti Medium.ttc"),
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
        except Exception:
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
            logger.error(f"Error drawing avatar: {e}")

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
            logger.error(f"Error drawing card photo: {e}")

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
