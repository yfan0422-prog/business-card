"""测试 MCP Server JSON-RPC 协议"""
import json
import pytest
from unittest.mock import Mock, patch, MagicMock

from app.mcp_server import (
    handle_request, TOOLS, TOOL_HANDLERS,
    _contact_to_dict, _knowledge_to_dict
)


class TestMCPProtocol:
    def test_initialize(self):
        request = {
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0"}}
        }
        response = handle_request(request)
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert "protocolVersion" in response["result"]
        assert response["result"]["serverInfo"]["name"] == "business-card-mcp"
        assert "tools" in response["result"]["capabilities"]

    def test_tools_list(self):
        request = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        response = handle_request(request)
        assert "tools" in response["result"]
        assert len(response["result"]["tools"]) >= 8

    def test_tools_list_all_have_schema(self):
        request = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        response = handle_request(request)
        for tool in response["result"]["tools"]:
            assert "name" in tool
            assert "description" in tool
            assert "inputSchema" in tool
            assert "type" in tool["inputSchema"]

    def test_ping(self):
        request = {"jsonrpc": "2.0", "id": 3, "method": "ping", "params": {}}
        response = handle_request(request)
        assert response["jsonrpc"] == "2.0"
        assert response["result"] == {}

    def test_unknown_method(self):
        request = {"jsonrpc": "2.0", "id": 4, "method": "unknown_method", "params": {}}
        response = handle_request(request)
        assert response["error"]["code"] == -32601

    def test_notifications_initialized(self):
        request = {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
        response = handle_request(request)
        assert response is None  # No response for notifications

    def test_unknown_tool(self):
        request = {
            "jsonrpc": "2.0", "id": 5, "method": "tools/call",
            "params": {"name": "nonexistent_tool", "arguments": {}}
        }
        response = handle_request(request)
        assert response["error"]["code"] == -32601


class TestToolHandlers:
    def test_all_tools_have_handlers(self):
        tool_names = {t["name"] for t in TOOLS}
        handler_names = set(TOOL_HANDLERS.keys())
        missing = tool_names - handler_names
        assert not missing, f"Missing handlers: {missing}"

    def test_search_contacts_requires_query(self):
        result = TOOL_HANDLERS["search_contacts"]({"query": "", "limit": 5})
        assert "error" in result

    def test_get_statistics_returns_structure(self):
        result = TOOL_HANDLERS["get_statistics"]({})
        assert "total_contacts" in result
        assert "total_companies" in result
        assert "total_knowledge" in result
        assert "knowledge_by_type" in result

    def test_list_recent_contacts(self):
        result = TOOL_HANDLERS["list_recent_contacts"]({"limit": 5})
        assert "contacts" in result
        assert "total" in result
        assert len(result["contacts"]) <= 5

    def test_get_contact_nonexistent(self):
        result = TOOL_HANDLERS["get_contact"]({"contact_id": 99999})
        assert "error" in result

    def test_get_contact_knowledge_nonexistent(self):
        result = TOOL_HANDLERS["get_contact_knowledge"]({"contact_id": 99999})
        assert "error" in result

    def test_get_knowledge_entry_nonexistent(self):
        result = TOOL_HANDLERS["get_knowledge_entry"]({"entry_id": 99999})
        assert "error" in result

    def test_get_company_info_not_found(self):
        result = TOOL_HANDLERS["get_company_info"]({"company_name": "不存在的公司xyz"})
        assert "error" in result

    def test_search_companies_requires_query(self):
        result = TOOL_HANDLERS["search_companies"]({"query": ""})
        assert "error" in result

    def test_list_knowledge_by_type(self):
        result = TOOL_HANDLERS["list_knowledge_entries"]({"limit": 5, "entry_type": "text"})
        assert "entries" in result


class TestDataConversion:
    def test_contact_to_dict(self):
        contact = Mock()
        contact.id = 1
        contact.name = "张三"
        contact.company = "测试公司"
        contact.department = None
        contact.position = "工程师"
        contact.mobile = "13800138000"
        contact.phone = None
        contact.email = "test@test.com"
        contact.company_address = None
        contact.notes = None
        contact.avatar_path = None
        contact.business_card_path = None
        contact.created_at = None
        contact.updated_at = None

        result = _contact_to_dict(contact)
        assert result["id"] == 1
        assert result["name"] == "张三"
        assert result["has_avatar"] is False
        assert "knowledge_entries" not in result

    def test_knowledge_to_dict(self):
        entry = Mock()
        entry.id = 1
        entry.title = "测试知识"
        entry.content = "这是测试内容"
        entry.entry_type = "text"
        entry.tags = "tag1,tag2"
        entry.audio_transcript = None
        entry.image_annotation = None
        entry.source_description = None
        entry.file_path = None
        entry.created_at = None
        entry.updated_at = None

        result = _knowledge_to_dict(entry)
        assert result["id"] == 1
        assert result["title"] == "测试知识"
        assert result["entry_type"] == "text"
