"""
名片管理系统 MCP Server — 基于 JSON-RPC 2.0 over stdio

支持其他 AI Agent 通过 MCP 协议调用名片系统的数据和知识。

启动方式:
    python -m app.mcp_server
    或
    python app/mcp_server.py

MCP 客户端配置示例 (Claude Desktop / Claude Code):
{
    "mcpServers": {
        "business-card": {
            "command": "python",
            "args": ["-m", "app.mcp_server"],
            "cwd": "/path/to/business-card"
        }
    }
}
"""
import sys
import json
import logging
from typing import Any, Dict, List, Optional
from pathlib import Path

# 确保项目根目录在 path 中
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import SessionLocal, init_db
from app.crud import contact_crud, company_crud
from app.knowledge_crud import knowledge_crud
from app.models import Contact, Company, KnowledgeEntry
from app.config import Config
from app.chinese_utils import get_search_variants

logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr  # stderr 不影响 stdio 通信
)
logger = logging.getLogger(__name__)

# ── MCP 工具定义 ─────────────────────────────────────

TOOLS = [
    {
        "name": "search_contacts",
        "description": "搜索名片联系人。支持姓名、公司、部门、职位、备注等字段的模糊搜索，自动支持繁简体中文一体化搜索。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词（支持繁简体中文）"
                },
                "limit": {
                    "type": "integer",
                    "description": "返回结果数量上限，默认20",
                    "default": 20
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_contact",
        "description": "获取指定联系人的完整信息，包括所有字段、关联的公司信息、以及关联的随记知识条目。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "contact_id": {
                    "type": "integer",
                    "description": "联系人ID"
                }
            },
            "required": ["contact_id"]
        }
    },
    {
        "name": "list_recent_contacts",
        "description": "获取最近添加的联系人列表",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "返回数量，默认20",
                    "default": 20
                }
            }
        }
    },
    {
        "name": "search_knowledge",
        "description": "搜索随记知识库。支持按关键词搜索标题、内容、标签和语音转录文本，自动支持繁简体中文一体化搜索。可按类型筛选。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词（支持繁简体中文）"
                },
                "entry_type": {
                    "type": "string",
                    "description": "条目类型筛选：voice(语音)、file(文件)、photo(照片)、text(文字)",
                    "enum": ["voice", "file", "photo", "text"]
                },
                "limit": {
                    "type": "integer",
                    "description": "返回结果数量上限，默认20",
                    "default": 20
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_contact_knowledge",
        "description": "获取与指定联系人关联的所有随记知识条目，按时间倒序排列。这些是用户在与该联系人交往过程中积累的知识。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "contact_id": {
                    "type": "integer",
                    "description": "联系人ID"
                }
            },
            "required": ["contact_id"]
        }
    },
    {
        "name": "get_knowledge_entry",
        "description": "获取单条随记知识条目的完整内容",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entry_id": {
                    "type": "integer",
                    "description": "知识条目ID"
                }
            },
            "required": ["entry_id"]
        }
    },
    {
        "name": "list_knowledge_entries",
        "description": "列出随记知识条目，可按类型筛选，按时间倒序排列",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "返回数量，默认20",
                    "default": 20
                },
                "entry_type": {
                    "type": "string",
                    "description": "条目类型筛选",
                    "enum": ["voice", "file", "photo", "text"]
                },
                "offset": {
                    "type": "integer",
                    "description": "分页偏移量",
                    "default": 0
                }
            }
        }
    },
    {
        "name": "get_company_info",
        "description": "获取公司详细信息，包括简介、经营情况、热点新闻和公司下的所有联系人",
        "inputSchema": {
            "type": "object",
            "properties": {
                "company_name": {
                    "type": "string",
                    "description": "公司名称"
                }
            },
            "required": ["company_name"]
        }
    },
    {
        "name": "search_companies",
        "description": "搜索公司，支持繁简体中文一体化搜索",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词"
                },
                "limit": {
                    "type": "integer",
                    "description": "返回结果数量上限",
                    "default": 20
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_statistics",
        "description": "获取名片管理系统的统计概览：名片总数、公司数量、随记总数及各类型分布",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    }
]


# ── 工具处理函数 ─────────────────────────────────────

def _contact_to_dict(c: Contact, include_knowledge: bool = False) -> Dict[str, Any]:
    """将 Contact 对象转为字典"""
    result = {
        "id": c.id,
        "name": c.name,
        "company": c.company,
        "department": c.department,
        "position": c.position,
        "mobile": c.mobile,
        "phone": c.phone,
        "email": c.email,
        "company_address": c.company_address,
        "notes": c.notes,
        "has_avatar": bool(c.avatar_path),
        "has_business_card": bool(c.business_card_path),
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }
    if include_knowledge:
        db = SessionLocal()
        entries = knowledge_crud.get_by_contact(db, c.id)
        result["knowledge_entries"] = [
            {
                "id": e.id, "title": e.title,
                "content": e.content[:300],
                "entry_type": e.entry_type,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in entries
        ]
        db.close()
    return result


def _knowledge_to_dict(e: KnowledgeEntry, include_contacts: bool = False) -> Dict[str, Any]:
    """将 KnowledgeEntry 转为字典"""
    result = {
        "id": e.id,
        "title": e.title,
        "content": e.content,
        "entry_type": e.entry_type,
        "tags": e.tags,
        "audio_transcript": e.audio_transcript,
        "image_annotation": e.image_annotation,
        "source_description": e.source_description,
        "file_path": e.file_path,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "updated_at": e.updated_at.isoformat() if e.updated_at else None,
    }
    if include_contacts:
        db = SessionLocal()
        linked_ids = knowledge_crud.get_linked_contact_ids(db, e.id)
        if linked_ids:
            contacts = db.query(Contact).filter(Contact.id.in_(linked_ids)).all()
            result["linked_contacts"] = [{"id": c.id, "name": c.name} for c in contacts]
        else:
            result["linked_contacts"] = []
        db.close()
    return result


def handle_search_contacts(args: dict) -> dict:
    query = args.get("query", "")
    limit = args.get("limit", 20)
    if not query.strip():
        return {"error": "搜索关键词不能为空"}
    db = SessionLocal()
    contacts = contact_crud.search(db, query)
    if len(contacts) > limit:
        contacts = contacts[:limit]
    result = [_contact_to_dict(c) for c in contacts]
    db.close()
    return {"contacts": result, "total": len(result)}


def handle_get_contact(args: dict) -> dict:
    contact_id = args.get("contact_id")
    db = SessionLocal()
    contact = contact_crud.get(db, contact_id)
    if not contact:
        db.close()
        return {"error": f"联系人不存在: id={contact_id}"}
    result = _contact_to_dict(contact, include_knowledge=True)
    db.close()
    return result


def handle_list_recent_contacts(args: dict) -> dict:
    limit = args.get("limit", 20)
    db = SessionLocal()
    contacts = contact_crud.list_recent(db, limit=limit)
    result = [_contact_to_dict(c) for c in contacts]
    db.close()
    return {"contacts": result, "total": len(result)}


def handle_search_knowledge(args: dict) -> dict:
    query = args.get("query", "")
    entry_type = args.get("entry_type")
    limit = args.get("limit", 20)
    if not query.strip():
        return {"error": "搜索关键词不能为空"}
    db = SessionLocal()
    entries = knowledge_crud.search(db, query, limit=limit)
    if entry_type:
        entries = [e for e in entries if e.entry_type == entry_type]
    result = [_knowledge_to_dict(e, include_contacts=True) for e in entries[:limit]]
    db.close()
    return {"entries": result, "total": len(result)}


def handle_get_contact_knowledge(args: dict) -> dict:
    contact_id = args.get("contact_id")
    db = SessionLocal()
    contact = contact_crud.get(db, contact_id)
    if not contact:
        db.close()
        return {"error": f"联系人不存在: id={contact_id}"}
    entries = knowledge_crud.get_by_contact(db, contact_id)
    result = [_knowledge_to_dict(e) for e in entries]
    db.close()
    return {
        "contact": {"id": contact.id, "name": contact.name},
        "knowledge_entries": result,
        "total": len(result)
    }


def handle_get_knowledge_entry(args: dict) -> dict:
    entry_id = args.get("entry_id")
    db = SessionLocal()
    entry = knowledge_crud.get(db, entry_id)
    if not entry:
        db.close()
        return {"error": f"知识条目不存在: id={entry_id}"}
    result = _knowledge_to_dict(entry, include_contacts=True)
    db.close()
    return result


def handle_list_knowledge_entries(args: dict) -> dict:
    limit = args.get("limit", 20)
    offset = args.get("offset", 0)
    entry_type = args.get("entry_type")
    db = SessionLocal()
    if entry_type:
        entries = knowledge_crud.get_by_type(db, entry_type, limit=limit)
    else:
        entries = knowledge_crud.list_recent(db, limit=limit, offset=offset)
    result = [_knowledge_to_dict(e, include_contacts=True) for e in entries]
    total = knowledge_crud.count(db)
    db.close()
    return {"entries": result, "total": total, "returned": len(result)}


def handle_get_company_info(args: dict) -> dict:
    company_name = args.get("company_name", "").strip()
    if not company_name:
        return {"error": "公司名称不能为空"}
    db = SessionLocal()
    company = db.query(Company).filter(Company.name == company_name).first()
    if not company:
        # 模糊搜索
        variants = get_search_variants(company_name)
        for v in variants:
            company = db.query(Company).filter(Company.name.contains(v)).first()
            if company:
                break
    if not company:
        db.close()
        return {"error": f"未找到公司: {company_name}"}

    contacts = contact_crud.get_by_company(db, company.name)
    news = []
    if company.latest_news:
        try:
            news = json.loads(company.latest_news)
        except (json.JSONDecodeError, TypeError):
            pass

    result = {
        "id": company.id,
        "name": company.name,
        "description": company.description,
        "website": company.website,
        "address": company.address,
        "business_performance": company.hot_topics,
        "hot_news": news,
        "contacts": [{"id": c.id, "name": c.name, "position": c.position} for c in contacts],
        "contacts_count": len(contacts),
    }
    db.close()
    return result


def handle_search_companies(args: dict) -> dict:
    query = args.get("query", "")
    limit = args.get("limit", 20)
    if not query.strip():
        return {"error": "搜索关键词不能为空"}
    db = SessionLocal()
    companies = company_crud.search(db, query)
    result = [{
        "id": c.id, "name": c.name, "description": c.description,
        "website": c.website, "address": c.address,
    } for c in companies[:limit]]
    db.close()
    return {"companies": result, "total": len(result)}


def handle_get_statistics(args: dict) -> dict:
    db = SessionLocal()
    total_contacts = db.query(Contact).count()
    total_companies = db.query(Company).count()
    total_knowledge = knowledge_crud.count(db)
    stats = {
        "total_contacts": total_contacts,
        "total_companies": total_companies,
        "total_knowledge": total_knowledge,
        "knowledge_by_type": {
            "voice": knowledge_crud.count_by_type(db, "voice"),
            "file": knowledge_crud.count_by_type(db, "file"),
            "photo": knowledge_crud.count_by_type(db, "photo"),
            "text": knowledge_crud.count_by_type(db, "text"),
        }
    }
    db.close()
    return stats


# ── 工具路由 ─────────────────────────────────────────

TOOL_HANDLERS = {
    "search_contacts": handle_search_contacts,
    "get_contact": handle_get_contact,
    "list_recent_contacts": handle_list_recent_contacts,
    "search_knowledge": handle_search_knowledge,
    "get_contact_knowledge": handle_get_contact_knowledge,
    "get_knowledge_entry": handle_get_knowledge_entry,
    "list_knowledge_entries": handle_list_knowledge_entries,
    "get_company_info": handle_get_company_info,
    "search_companies": handle_search_companies,
    "get_statistics": handle_get_statistics,
}

# ── JSON-RPC 处理 ────────────────────────────────────

def handle_request(request: dict) -> dict:
    """处理单个 JSON-RPC 请求"""
    req_id = request.get("id")
    method = request.get("method", "")
    params = request.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {
                    "name": "business-card-mcp",
                    "version": "1.0.0"
                },
                "capabilities": {
                    "tools": {}
                }
            }
        }

    if method == "notifications/initialized":
        # 无需回复
        return None

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": TOOLS}
        }

    if method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})
        handler = TOOL_HANDLERS.get(tool_name)

        if not handler:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"未知工具: {tool_name}"}
            }

        try:
            result = handler(tool_args)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}
                    ]
                }
            }
        except Exception as e:
            logger.error(f"Tool execution error: {e}", exc_info=True)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {"type": "text", "text": json.dumps({"error": str(e)}, ensure_ascii=False)}
                    ]
                },
                "isError": True
            }

    if method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"未知方法: {method}"}
    }


def send_response(response: dict):
    """发送 JSON-RPC 响应到 stdout"""
    if response is None:
        return
    sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
    sys.stdout.flush()


# ── 主循环 ───────────────────────────────────────────

def main():
    """MCP Server 主入口 — 从 stdin 读取 JSON-RPC 请求，处理后写入 stdout"""
    # 初始化数据库
    Config.ensure_dirs()
    init_db()
    logger.info("MCP Server started, waiting for requests...")

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            response = handle_request(request)
            send_response(response)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON: {e}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)


if __name__ == "__main__":
    main()
