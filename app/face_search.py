"""人脸搜索 — 基于多模态大模型的人脸比对"""
import base64
import json
import logging
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path
import requests

logger = logging.getLogger(__name__)

FACE_COMPARE_PROMPT = """请仔细对比这两张人脸照片，判断他们是否是同一个人。

请以JSON格式返回你的判断结果，格式如下：
{
    "is_same_person": true/false,
    "confidence": 0.0-1.0,
    "reasoning": "简要说明判断理由"
}

要求：
1. 只返回JSON，不要任何其他文字
2. confidence是0-1之间的数值，表示你对判断的置信度
3. is_same_person为true表示是同一个人，false表示不是
4. reasoning简要说明你的判断理由，比如五官相似、脸型匹配等
"""


class FaceSearchEngine:
    def __init__(self, api_base: str, api_key: str, model_name: str):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.model_name = model_name

    def _encode_image(self, image_path: Path) -> Tuple[str, str]:
        """将图片编码为 base64 data URL"""
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        suffix = image_path.suffix.lower()
        mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                     ".png": "image/png", ".webp": "image/webp"}
        mime_type = mime_map.get(suffix, "image/jpeg")

        return f"data:{mime_type};base64,{image_data}", mime_type

    def compare_faces(self, query_image_path: Path, target_image_path: Path) -> Dict[str, Any]:
        """比对两张人脸是否是同一个人"""
        if not query_image_path.exists():
            return {"error": f"查询图片不存在: {query_image_path}"}
        if not target_image_path.exists():
            return {"error": f"目标图片不存在: {target_image_path}"}

        try:
            query_data_url, _ = self._encode_image(query_image_path)
            target_data_url, _ = self._encode_image(target_image_path)

            # 构造 OpenAI 兼容请求
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            body = {
                "model": self.model_name,
                "messages": [
                    {"role": "user", "content": [
                        {"type": "image_url", "image_url": {"url": query_data_url}},
                        {"type": "image_url", "image_url": {"url": target_data_url}},
                        {"type": "text", "text": FACE_COMPARE_PROMPT}
                    ]}
                ],
                "max_tokens": 500
            }

            url = f"{self.api_base}/chat/completions"
            resp = requests.post(url, headers=headers, json=body, timeout=90)
            resp.raise_for_status()
            data = resp.json()

            content = data["choices"][0]["message"]["content"]
            logger.info(f"Face compare raw response: {content[:200]}...")

            return self._parse_response(content)

        except requests.exceptions.Timeout:
            return {"error": "人脸比对请求超时，请重试"}
        except requests.exceptions.RequestException as e:
            logger.error(f"Face compare API error: {e}")
            return {"error": f"API调用失败: {str(e)}"}
        except Exception as e:
            logger.error(f"Face compare error: {e}")
            return {"error": f"比对失败: {str(e)}"}

    def _parse_response(self, content: str) -> Dict[str, Any]:
        """解析模型返回内容"""
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        import re
        match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        match = re.search(r'\{[\s\S]*\}', content)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        return {"error": f"无法解析模型返回内容", "raw": content[:500]}

    def search_matches(
        self,
        query_image_path: Path,
        target_contacts: List[Any],
        photos_dir: Path,
        confidence_threshold: float = 0.6
    ) -> List[Dict[str, Any]]:
        """
        在联系人列表中搜索匹配的人脸

        返回：按置信度排序的匹配列表，每个元素包含 contact 和 match_info
        """
        matches = []

        for contact in target_contacts:
            if not contact.avatar_path:
                continue

            avatar_path = photos_dir / contact.avatar_path
            if not avatar_path.exists():
                continue

            result = self.compare_faces(query_image_path, avatar_path)

            if "error" in result:
                logger.warning(f"Error comparing with {contact.name}: {result['error']}")
                continue

            is_same = result.get("is_same_person", False)
            confidence = result.get("confidence", 0.0)

            if is_same and confidence >= confidence_threshold:
                matches.append({
                    "contact": contact,
                    "confidence": confidence,
                    "reasoning": result.get("reasoning", "")
                })

        matches.sort(key=lambda x: x["confidence"], reverse=True)
        return matches
