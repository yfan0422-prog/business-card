"""OCR 抽象层 — 基于 OpenAI 兼容协议调用多模态大模型识别名片"""
import base64
import json
import logging
from typing import Optional, Dict, Any
from pathlib import Path
import requests

logger = logging.getLogger(__name__)

OCR_PROMPT = """请识别这张名片图片，提取出所有可见信息，以JSON格式返回。

要求：
1. 只返回JSON，不要任何其他文字
2. 字段名用英文（name/company/department/position/mobile/phone/email/company_address）
3. 识别不出的字段设为 null
4. 如果图片不是名片，返回 {"error": "未识别到名片"}

返回格式示例：
{"name":"张三","company":"某某科技","department":"研发部","position":"技术总监","mobile":"13800138000","phone":"010-12345678","email":"zhangsan@example.com","company_address":"北京市朝阳区xxx","notes":""}
"""


class OCREngine:
    def __init__(self, api_base: str, api_key: str, model_name: str):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.model_name = model_name

    def recognize(self, image_path: Path) -> Dict[str, Any]:
        if not image_path.exists():
            return {"error": f"图片不存在: {image_path}"}

        # 读取图片并转 base64
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        # 推断 MIME 类型
        suffix = image_path.suffix.lower()
        mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                     ".png": "image/png", ".webp": "image/webp"}
        mime_type = mime_map.get(suffix, "image/jpeg")

        data_url = f"data:{mime_type};base64,{image_data}"

        # 构造 OpenAI 兼容请求
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        body = {
            "model": self.model_name,
            "messages": [
                {"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {"type": "text", "text": OCR_PROMPT}
                ]}
            ],
            "max_tokens": 500
        }

        try:
            url = f"{self.api_base}/chat/completions"
            resp = requests.post(url, headers=headers, json=body, timeout=60)
            resp.raise_for_status()
            data = resp.json()

            content = data["choices"][0]["message"]["content"]
            logger.info(f"OCR raw response: {content[:200]}...")

            # 提取 JSON
            return self._parse_response(content)

        except requests.exceptions.Timeout:
            return {"error": "OCR请求超时，请重试"}
        except requests.exceptions.RequestException as e:
            logger.error(f"OCR API error: {e}")
            return {"error": f"API调用失败: {str(e)}"}
        except Exception as e:
            logger.error(f"OCR error: {e}")
            return {"error": f"识别失败: {str(e)}"}

    def _parse_response(self, content: str) -> Dict[str, Any]:
        # 尝试直接解析
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # 尝试提取 ```json ... ``` 块
        import re
        match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试提取第一个 { ... } 对象
        match = re.search(r'\{[\s\S]*\}', content)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        return {"error": f"无法解析模型返回内容", "raw": content[:500]}
