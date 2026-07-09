"""知识引擎 — 基于多模态大模型的文件解读和图片分析"""
import base64
import json
import logging
from typing import Dict, Any
from pathlib import Path
import requests

logger = logging.getLogger(__name__)

FILE_INTERPRET_PROMPT = """请分析以下文档内容，提取关键知识点并整理为结构化笔记。

要求：
1. 生成一个简短的标题（不超过30字）
2. 提取核心内容摘要（不超过300字）
3. 列出3-5个关键要点
4. 给出2-4个分类标签

以JSON格式返回：
{"title": "...", "summary": "...", "key_points": ["...", "..."], "tags": ["...", "..."]}

以下是文档内容：
---
{document_content}
---
"""

IMAGE_ANALYZE_PROMPT = """请分析这张图片的内容，提取关键信息。

要求：
1. 描述图片中展示的内容（不超过200字）
2. 如果图片中有文字，提取出来
3. 总结图片传达的关键信息（2-3个要点）
4. 给出2-3个分类标签

以JSON格式返回：
{"description": "...", "extracted_text": "...", "key_points": ["...", "..."], "tags": ["...", "..."]}
"""


class KnowledgeEngine:
    def __init__(self, api_base: str, api_key: str, model_name: str):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.model_name = model_name

    def interpret_file(self, file_path: Path) -> Dict[str, Any]:
        """读取文件内容并调用AI提取关键知识点"""
        if not file_path.exists():
            return {"error": f"文件不存在: {file_path}"}

        try:
            content = self._read_file_content(file_path)
        except Exception as e:
            return {"error": f"文件读取失败: {str(e)}"}

        if not content or not content.strip():
            return {"error": "文件内容为空"}

        prompt = FILE_INTERPRET_PROMPT.replace("{document_content}", content[:8000])

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        body = {
            "model": self.model_name,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 800
        }

        try:
            url = f"{self.api_base}/chat/completions"
            resp = requests.post(url, headers=headers, json=body, timeout=120)
            resp.raise_for_status()
            data = resp.json()

            response_content = data["choices"][0]["message"]["content"]
            logger.info(f"Knowledge interpret raw response: {response_content[:200]}...")

            return self._parse_response(response_content)

        except requests.exceptions.Timeout:
            return {"error": "文件解读请求超时，请重试"}
        except requests.exceptions.RequestException as e:
            logger.error(f"Knowledge interpret API error: {e}")
            return {"error": f"API调用失败: {str(e)}"}
        except Exception as e:
            logger.error(f"Knowledge interpret error: {e}")
            return {"error": f"解读失败: {str(e)}"}

    def analyze_image(self, image_path: Path) -> Dict[str, Any]:
        """分析图片内容，提取关键信息"""
        if not image_path.exists():
            return {"error": f"图片不存在: {image_path}"}

        try:
            with open(image_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")

            suffix = image_path.suffix.lower()
            mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                        ".png": "image/png", ".webp": "image/webp"}
            mime_type = mime_map.get(suffix, "image/jpeg")

            data_url = f"data:{mime_type};base64,{image_data}"

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            body = {
                "model": self.model_name,
                "messages": [
                    {"role": "user", "content": [
                        {"type": "image_url", "image_url": {"url": data_url}},
                        {"type": "text", "text": IMAGE_ANALYZE_PROMPT}
                    ]}
                ],
                "max_tokens": 500
            }

            url = f"{self.api_base}/chat/completions"
            resp = requests.post(url, headers=headers, json=body, timeout=90)
            resp.raise_for_status()
            data = resp.json()

            response_content = data["choices"][0]["message"]["content"]
            logger.info(f"Image analyze raw response: {response_content[:200]}...")

            return self._parse_response(response_content)

        except requests.exceptions.Timeout:
            return {"error": "图片分析请求超时，请重试"}
        except requests.exceptions.RequestException as e:
            logger.error(f"Image analyze API error: {e}")
            return {"error": f"API调用失败: {str(e)}"}
        except Exception as e:
            logger.error(f"Image analyze error: {e}")
            return {"error": f"分析失败: {str(e)}"}

    def _read_file_content(self, file_path: Path) -> str:
        """读取文件文本内容"""
        suffix = file_path.suffix.lower()

        if suffix in (".txt", ".md", ".csv", ".json", ".xml", ".html", ".py", ".js", ".ts", ".css"):
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()

        if suffix == ".pdf":
            try:
                import subprocess
                result = subprocess.run(
                    ["pdftotext", "-layout", str(file_path), "-"],
                    capture_output=True, text=True, timeout=30
                )
                if result.returncode == 0:
                    return result.stdout
            except Exception:
                pass
            # Fallback: try PyPDF2
            try:
                from PyPDF2 import PdfReader
                reader = PdfReader(str(file_path))
                return "\n".join(page.extract_text() or "" for page in reader.pages)
            except ImportError:
                return f"[PDF文件需要安装 pdftotext 或 PyPDF2 来读取: {file_path.name}]"

        if suffix == ".docx":
            try:
                from docx import Document
                doc = Document(str(file_path))
                return "\n".join(p.text for p in doc.paragraphs)
            except ImportError:
                return f"[Word文件需要安装 python-docx 来读取: {file_path.name}]"

        return f"[不支持的文件格式: {suffix}]"

    def _parse_response(self, content: str) -> Dict[str, Any]:
        """解析模型返回的JSON内容（复用 OCR 的解析模式）"""
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

        return {"error": "无法解析模型返回内容", "raw": content[:500]}

    def research_company(self, company_name: str) -> Dict[str, Any]:
        """研究公司信息：主营业务、经营业绩、近期热点新闻"""
        prompt = COMPANY_RESEARCH_PROMPT.replace("{company_name}", company_name)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        body = {
            "model": self.model_name,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 1500
        }

        try:
            url = f"{self.api_base}/chat/completions"
            resp = requests.post(url, headers=headers, json=body, timeout=120)
            resp.raise_for_status()
            data = resp.json()

            response_content = data["choices"][0]["message"]["content"]
            logger.info(f"Company research raw response: {response_content[:300]}...")

            return self._parse_response(response_content)

        except requests.exceptions.Timeout:
            return {"error": "公司研究请求超时，请重试"}
        except requests.exceptions.RequestException as e:
            logger.error(f"Company research API error: {e}")
            return {"error": f"API调用失败: {str(e)}"}
        except Exception as e:
            logger.error(f"Company research error: {e}")
            return {"error": f"研究失败: {str(e)}"}


COMPANY_RESEARCH_PROMPT = """请基于你的知识，对以下公司进行简要研究分析，以JSON格式返回。

公司名称：{company_name}

要求：
1. 公司简介：简要介绍这家公司（不超过200字），包括：
   - 主营业务和核心产品
   - 行业地位
2. 经营情况：如果了解，简要说明近期的经营业绩、财报情况或市场表现（不超过200字）。如不了解具体数据，请说明你所知的业务发展趋势。
3. 组织架构：根据你所知的信息，描述该公司的主要组织架构。列出主要部门/事业群及其核心职能，以及已知的关键负责人或高管（如果知道姓名的话）。以层级结构组织。
4. 热点新闻：列出3-5条近期与该公司相关的热点新闻或重要动态（每条不超过80字）。请注明大概的时间和来源。如果知道原文链接，请提供url字段；不知道则设为null。
5. 如果对公司完全不了解，请将 is_known 设为 false，并简要说明。

以JSON格式返回（只返回JSON，不要其他文字）：
{
    "is_known": true,
    "company_intro": "公司简介内容...",
    "business_performance": "经营情况内容...",
    "org_structure": [
        {"name": "CEO办公室", "role": "张某某（CEO）", "children": [
            {"name": "技术部", "role": "李某某（CTO）", "children": []},
            {"name": "市场部", "role": "王某某（CMO）", "children": []}
        ]},
        {"name": "事业部A", "role": "", "children": []}
    ],
    "hot_news": [
        {"title": "新闻标题", "summary": "新闻摘要", "time": "大约时间", "source": "来源名称", "url": "https://..."},
        {"title": "新闻标题", "summary": "新闻摘要", "time": "大约时间", "source": "来源名称", "url": null}
    ],
    "disclaimer": "以上信息基于模型训练数据，可能不是最新的，请以官方信息为准。"
}
"""


KNOWLEDGE_SUMMARY_PROMPT = """请分析以下关于联系人「{contact_name}」的随记内容，提炼出关键信息点，按时间顺序整理成有条理的总结。

每条信息点需要注明来源于哪条随记（source_entry_id 对应给出的随记ID）。

随记内容：
---
{knowledge_entries_text}
---

要求：
1. 整体总结：综合所有随记，用不超过200字概括与该联系人相关的核心信息
2. 关键信息点：按时间顺序列出3-8个重要信息点，每个点注明来源随记ID
3. 话题标签：根据内容给出3-5个分类标签

以JSON格式返回（只返回JSON，不要其他文字）：
{{
    "summary": "整体总结...",
    "key_points": [
        {{"point": "信息点内容", "source_entry_ids": [1], "time_context": "时间背景"}},
        {{"point": "信息点内容", "source_entry_ids": [2, 3], "time_context": "时间背景"}}
    ],
    "topic_tags": ["标签1", "标签2"]
}}
"""


def summarize_contact_knowledge(api_base: str, api_key: str, model_name: str,
                                 contact_name: str, knowledge_entries: list) -> Dict[str, Any]:
    """对联系人的随记内容进行AI提炼总结"""
    if not knowledge_entries:
        return {"error": "没有随记内容可供提炼"}

    # 构建随记文本
    entries_text_parts = []
    for e in knowledge_entries:
        date_str = e.created_at.strftime("%Y-%m-%d") if e.created_at else "未知时间"
        type_labels = {"voice": "语音", "file": "文件", "photo": "照片", "text": "文字"}
        type_label = type_labels.get(e.entry_type, "文字")
        entries_text_parts.append(
            f"[随记ID:{e.id} | {date_str} | {type_label}] {e.title}\n{e.content[:500]}"
        )
    entries_text = "\n\n---\n\n".join(entries_text_parts)

    prompt = KNOWLEDGE_SUMMARY_PROMPT.format(
        contact_name=contact_name,
        knowledge_entries_text=entries_text
    )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    body = {
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1000
    }

    try:
        url = f"{api_base.rstrip('/')}/chat/completions"
        resp = requests.post(url, headers=headers, json=body, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        response_content = data["choices"][0]["message"]["content"]
        logger.info(f"Knowledge summary raw: {response_content[:200]}...")

        # 复用 OCR 的解析模式
        import json as _json
        try:
            return _json.loads(response_content)
        except _json.JSONDecodeError:
            pass
        import re
        match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response_content)
        if match:
            try:
                return _json.loads(match.group(1))
            except _json.JSONDecodeError:
                pass
        match = re.search(r'\{[\s\S]*\}', response_content)
        if match:
            try:
                return _json.loads(match.group(0))
            except _json.JSONDecodeError:
                pass
        return {"error": "无法解析AI返回内容", "raw": response_content[:500]}

    except requests.exceptions.Timeout:
        return {"error": "知识提炼请求超时，请重试"}
    except requests.exceptions.RequestException as e:
        logger.error(f"Knowledge summary API error: {e}")
        return {"error": f"API调用失败: {str(e)}"}
    except Exception as e:
        logger.error(f"Knowledge summary error: {e}")
        return {"error": f"提炼失败: {str(e)}"}
