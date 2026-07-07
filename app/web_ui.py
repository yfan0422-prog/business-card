"""
名片管理系统 - Web 管理界面
"""
from fastapi import APIRouter, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse
from pydantic import BaseModel, field_validator
from typing import Optional
from pathlib import Path

from app.config import Config
from app.database import SessionLocal
from app.models import Contact, Company, AIModel
from app.crud import contact_crud, company_crud
from app.card_generator import CardGenerator
from app.ai_models import ai_model_manager
import requests as http_requests
from app.ocr import OCREngine, OCR_PROMPT

router = APIRouter()

# ── 共享样式 ──────────────────────────────────────────

SHARED_CSS = """
:root {
    --primary: #2563eb; --primary-hover: #1d4ed8; --danger: #dc2626; --danger-hover: #b91c1c;
    --success: #16a34a; --warning: #f59e0b; --bg: #f8fafc; --card-bg: #ffffff;
    --text: #1e293b; --text-muted: #64748b; --border: #e2e8f0;
    --radius: 12px; --shadow: 0 1px 3px rgba(0,0,0,.08), 0 1px 2px rgba(0,0,0,.06);
    --shadow-lg: 0 10px 25px rgba(0,0,0,.1);
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    background: var(--bg); color: var(--text); line-height: 1.6; min-height: 100vh;
}
.container { max-width: 960px; margin: 0 auto; padding: 16px; }
header {
    background: var(--card-bg); border-bottom: 1px solid var(--border); padding: 16px 24px;
    position: sticky; top: 0; z-index: 100; box-shadow: var(--shadow);
}
header .inner { max-width: 960px; margin: 0 auto; display: flex; align-items: center; justify-content: space-between; }
header h1 { font-size: 1.25rem; font-weight: 700; display: flex; align-items: center; gap: 8px; }
header nav { display: flex; gap: 4px; }
header nav a {
    padding: 8px 16px; border-radius: 8px; text-decoration: none; color: var(--text-muted);
    font-weight: 500; font-size: .875rem; transition: all .15s;
}
header nav a:hover, header nav a.active { background: #eff6ff; color: var(--primary); }
.stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 24px; }
.stat-card {
    background: var(--card-bg); border-radius: var(--radius); padding: 20px;
    box-shadow: var(--shadow); text-align: center;
}
.stat-card .num { font-size: 2rem; font-weight: 700; color: var(--primary); }
.stat-card .label { font-size: .8rem; color: var(--text-muted); margin-top: 4px; }
.search-bar { display: flex; gap: 8px; margin-bottom: 20px; }
.search-bar input {
    flex: 1; padding: 10px 16px; border: 2px solid var(--border); border-radius: 10px;
    font-size: .95rem; transition: border-color .2s; outline: none;
}
.search-bar input:focus { border-color: var(--primary); }
.btn {
    display: inline-flex; align-items: center; gap: 6px; padding: 10px 20px;
    border: none; border-radius: 10px; font-size: .9rem; font-weight: 600;
    cursor: pointer; text-decoration: none; transition: all .15s; white-space: nowrap;
}
.btn-primary { background: var(--primary); color: #fff; }
.btn-primary:hover { background: var(--primary-hover); transform: translateY(-1px); }
.btn-danger { background: var(--danger); color: #fff; }
.btn-danger:hover { background: var(--danger-hover); }
.btn-ghost { background: transparent; color: var(--text-muted); border: 1px solid var(--border); }
.btn-ghost:hover { background: #f1f5f9; }
.btn-sm { padding: 6px 12px; font-size: .8rem; border-radius: 6px; }
.contact-grid { display: grid; gap: 12px; }
.contact-card {
    background: var(--card-bg); border-radius: var(--radius); padding: 20px;
    box-shadow: var(--shadow); display: flex; justify-content: space-between;
    align-items: center; gap: 16px; transition: box-shadow .2s;
}
.contact-card:hover { box-shadow: var(--shadow-lg); }
.contact-info h3 { font-size: 1.05rem; margin-bottom: 4px; }
.contact-info h3 a { color: var(--text); text-decoration: none; }
.contact-info h3 a:hover { color: var(--primary); }
.contact-info .meta { font-size: .85rem; color: var(--text-muted); display: flex; flex-wrap: wrap; gap: 12px; }
.contact-info .meta span { display: inline-flex; align-items: center; gap: 4px; }
.contact-actions { display: flex; gap: 6px; flex-shrink: 0; }
.form-page { max-width: 640px; margin: 0 auto; }
.form-card { background: var(--card-bg); border-radius: var(--radius); padding: 32px; box-shadow: var(--shadow); }
.form-card h2 { font-size: 1.3rem; margin-bottom: 24px; display: flex; align-items: center; gap: 8px; }
.form-group { margin-bottom: 18px; }
.form-group label { display: block; font-size: .85rem; font-weight: 600; margin-bottom: 6px; color: var(--text-muted); }
.form-group input, .form-group textarea {
    width: 100%; padding: 10px 14px; border: 2px solid var(--border); border-radius: 10px;
    font-size: .95rem; transition: border-color .2s; outline: none; font-family: inherit;
}
.form-group input:focus, .form-group textarea:focus { border-color: var(--primary); }
.form-group textarea { resize: vertical; min-height: 80px; }
.form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.form-actions { display: flex; gap: 12px; margin-top: 28px; padding-top: 20px; border-top: 1px solid var(--border); }
.empty-state { text-align: center; padding: 60px 20px; color: var(--text-muted); }
.empty-state .icon { font-size: 3rem; margin-bottom: 16px; }
.empty-state h3 { font-size: 1.2rem; margin-bottom: 8px; color: var(--text); }
.card-detail { background: var(--card-bg); border-radius: var(--radius); padding: 32px; box-shadow: var(--shadow); text-align: center; }
.card-detail img { max-width: 100%; border-radius: 8px; box-shadow: var(--shadow); }
.toast-container { position: fixed; top: 20px; right: 20px; z-index: 9999; display: flex; flex-direction: column; gap: 8px; }
.toast {
    padding: 14px 20px; border-radius: 10px; color: #fff; font-weight: 500; font-size: .9rem;
    box-shadow: var(--shadow-lg); animation: slideIn .3s ease; max-width: 380px;
}
.toast.success { background: var(--success); }
.toast.error { background: var(--danger); }
@keyframes slideIn { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
.modal-overlay {
    position: fixed; inset: 0; background: rgba(0,0,0,.4); z-index: 1000;
    display: flex; align-items: center; justify-content: center;
}
.modal {
    background: var(--card-bg); border-radius: var(--radius); padding: 32px;
    max-width: 420px; width: 90%; box-shadow: var(--shadow-lg); text-align: center;
}
.modal h3 { margin-bottom: 12px; }
.modal p { color: var(--text-muted); margin-bottom: 24px; }
.modal-actions { display: flex; gap: 10px; justify-content: center; }
.pagination { display: flex; gap: 6px; justify-content: center; margin-top: 24px; }
.pagination button {
    padding: 8px 14px; border: 1px solid var(--border); border-radius: 8px;
    background: var(--card-bg); cursor: pointer; font-size: .85rem; transition: all .15s;
}
.pagination button:hover { border-color: var(--primary); color: var(--primary); }
.pagination button.active { background: var(--primary); color: #fff; border-color: var(--primary); }
@media (max-width: 640px) {
    .contact-card { flex-direction: column; align-items: flex-start; }
    .contact-actions { width: 100%; }
    .form-row { grid-template-columns: 1fr; }
    header .inner { flex-direction: column; gap: 8px; }
    .stats { grid-template-columns: 1fr 1fr; }
}
"""

SHARED_JS = """
<script>
function showToast(msg, type='success') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = 'toast ' + type;
    toast.textContent = msg;
    container.appendChild(toast);
    setTimeout(() => { toast.style.opacity='0'; toast.style.transition='opacity .3s'; setTimeout(() => toast.remove(), 300); }, 3000);
}
function confirmDelete(id, name) {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `<div class="modal">
        <h3>确认删除</h3><p>确定要删除 <strong>${name}</strong> 吗？此操作不可撤销。</p>
        <div class="modal-actions">
            <button class="btn btn-ghost" onclick="this.closest('.modal-overlay').remove()">取消</button>
            <button class="btn btn-danger" onclick="doDelete(${id})">确认删除</button>
        </div>
    </div>`;
    document.body.appendChild(overlay);
    overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });
}
async function doDelete(id) {
    try {
        const resp = await fetch('/web/api/contacts/' + id, { method: 'DELETE' });
        if (resp.ok) { showToast('删除成功'); setTimeout(() => location.reload(), 800); }
        else { const err = await resp.json(); showToast(err.detail || '删除失败', 'error'); }
    } catch(e) { showToast('网络错误', 'error'); }
}
function debounce(fn, ms) { let t; return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); }; }
</script>
"""


def layout(title: str, content: str, active_nav: str = "") -> str:
    """用共享的 header + 样式包装页面"""
    nav_home = 'class="active"' if active_nav == "home" else ""
    nav_new = 'class="active"' if active_nav == "new" else ""
    nav_ocr = 'class="active"' if active_nav == "ocr" else ""
    nav_models = 'class="active"' if active_nav == "models" else ""
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="theme-color" content="#2563eb">
    <title>{title} - 名片管理系统</title>
    <link rel="manifest" href="/static/manifest.json">
    <link rel="icon" href="/static/icon.svg">
    <style>{SHARED_CSS}</style>
</head>
<body>
    <header>
        <div class="inner">
            <h1>📇 名片管理系统</h1>
            <nav>
                <a href="/web/" {nav_home}>🏠 首页</a>
                <a href="/web/ocr" {nav_ocr}>📷 拍照录入</a>
                <a href="/web/new" {nav_new}>➕ 添加</a>
                <a href="/web/models" {nav_models}>🤖 模型管理</a>
            </nav>
        </div>
    </header>
    <div class="container">{content}</div>
    <div id="toast-container" class="toast-container"></div>
    {SHARED_JS}
</body>
</html>"""


# ── 首页 ─────────────────────────────────────────────

def render_home(contacts: list, companies: list, total_contacts: int, total_companies: int) -> str:
    contact_cards = ""
    for c in contacts:
        meta_parts = []
        if c.company:
            meta_parts.append(f"<span>🏢 {c.company}</span>")
        if c.department:
            meta_parts.append(f"<span>📂 {c.department}</span>")
        if c.position:
            meta_parts.append(f"<span>💼 {c.position}</span>")
        if c.mobile:
            meta_parts.append(f"<span>📱 {c.mobile}</span>")
        meta_html = " ".join(meta_parts) if meta_parts else '<span style="color:#94a3b8;">暂无更多信息</span>'

        contact_cards += f"""
        <div class="contact-card">
            <div class="contact-info">
                <h3><a href="/web/card/{c.id}">{c.name}</a></h3>
                <div class="meta">{meta_html}</div>
            </div>
            <div class="contact-actions">
                <a href="/web/card/{c.id}" class="btn btn-primary btn-sm">🖼️ 名片</a>
                <a href="/web/edit/{c.id}" class="btn btn-ghost btn-sm">✏️ 编辑</a>
                <button class="btn btn-danger btn-sm" onclick="confirmDelete({c.id}, '{c.name}')">🗑️</button>
            </div>
        </div>"""

    empty_html = ""
    if not contacts:
        empty_html = """<div class="empty-state">
            <div class="icon">📭</div>
            <h3>还没有名片</h3>
            <p>点击右上角「添加」录入第一张名片吧</p>
            <a href="/web/new" class="btn btn-primary" style="margin-top:16px;">➕ 添加第一张名片</a>
        </div>"""

    company_cards = ""
    for comp in companies:
        company_cards += f"""
        <div class="contact-card">
            <div class="contact-info">
                <h3><a href="/web/company/{comp['id']}">🏢 {comp['name']}</a></h3>
                <div class="meta"><span>{comp.get('description', '')}</span></div>
            </div>
            <div class="contact-actions">
                <a href="/web/company/{comp['id']}" class="btn btn-ghost btn-sm">查看全部 →</a>
            </div>
        </div>"""

    content = f"""
    <div class="stats">
        <div class="stat-card"><div class="num">{total_contacts}</div><div class="label">📇 名片总数</div></div>
        <div class="stat-card"><div class="num">{total_companies}</div><div class="label">🏢 公司数量</div></div>
    </div>

    <div class="search-bar">
        <input type="text" id="searchInput" placeholder="🔍 搜索姓名、公司、职位..." autofocus>
        <button class="btn btn-primary" onclick="doSearch()">搜索</button>
    </div>

    <div id="results-area">
        <h2 style="margin-bottom:12px;font-size:1.1rem;">📋 名片列表</h2>
        <div class="contact-grid" id="contactList">{contact_cards}</div>
        {empty_html}
        <div class="pagination" id="pagination"></div>
    </div>

    {f'''<h2 style="margin:32px 0 12px;font-size:1.1rem;">🏢 公司列表</h2>
    <div class="contact-grid">{company_cards}</div>''' if companies else ''}

    <script>
    let allContacts = [];
    const PAGE_SIZE = 8;
    let currentPage = 1;

    async function loadAllContacts() {{
        try {{
            const resp = await fetch('/web/api/contacts?limit=200');
            const data = await resp.json();
            allContacts = data.contacts;
            renderPage(1);
        }} catch(e) {{ console.error(e); }}
    }}

    function renderPage(page) {{
        currentPage = page;
        const start = (page - 1) * PAGE_SIZE;
        const pageItems = allContacts.slice(start, start + PAGE_SIZE);
        const grid = document.getElementById('contactList');
        if (pageItems.length === 0 && allContacts.length === 0) {{
            grid.innerHTML = `<div class="empty-state"><div class="icon">📭</div><h3>还没有名片</h3><p>点击右上角「添加」录入第一张名片吧</p></div>`;
            document.getElementById('pagination').innerHTML = '';
            return;
        }}
        if (pageItems.length === 0) {{
            renderPage(page - 1); return;
        }}
        grid.innerHTML = pageItems.map(c => `
            <div class="contact-card">
                <div class="contact-info">
                    <h3><a href="/web/card/${{c.id}}">${{c.name}}</a></h3>
                    <div class="meta">
                        ${{c.company ? '<span>🏢 '+c.company+'</span>' : ''}}
                        ${{c.department ? '<span>📂 '+c.department+'</span>' : ''}}
                        ${{c.position ? '<span>💼 '+c.position+'</span>' : ''}}
                        ${{c.mobile ? '<span>📱 '+c.mobile+'</span>' : ''}}
                    </div>
                </div>
                <div class="contact-actions">
                    <a href="/web/card/${{c.id}}" class="btn btn-primary btn-sm">🖼️ 名片</a>
                    <a href="/web/edit/${{c.id}}" class="btn btn-ghost btn-sm">✏️ 编辑</a>
                    <button class="btn btn-danger btn-sm" onclick="confirmDelete(${{c.id}}, '${{c.name}}')">🗑️</button>
                </div>
            </div>
        `).join('');

        const totalPages = Math.ceil(allContacts.length / PAGE_SIZE);
        let pagHTML = '';
        if (totalPages > 1) {{
            for (let i = 1; i <= totalPages; i++) {{
                pagHTML += `<button class="${{i === currentPage ? 'active' : ''}}" onclick="renderPage(${{i}})">${{i}}</button>`;
            }}
        }}
        document.getElementById('pagination').innerHTML = pagHTML;
    }}

    const doSearch = debounce(async function() {{
        const q = document.getElementById('searchInput').value.trim();
        if (!q) {{ loadAllContacts(); return; }}
        try {{
            const resp = await fetch('/web/api/contacts?q=' + encodeURIComponent(q));
            const data = await resp.json();
            allContacts = data.contacts;
            renderPage(1);
        }} catch(e) {{ console.error(e); }}
    }}, 300);

    document.getElementById('searchInput').addEventListener('input', doSearch);
    loadAllContacts();
    </script>
    """
    return layout("首页", content, active_nav="home")


# ── 新增 / 编辑表单 ──────────────────────────────────

def render_form(contact: Optional[Contact] = None) -> str:
    is_edit = contact is not None
    title_text = "✏️ 编辑名片" if is_edit else "➕ 添加新名片"
    id_input = f'<input type="hidden" name="id" value="{contact.id}">' if is_edit else ""
    get = lambda f: getattr(contact, f, "") or "" if contact else ""

    content = f"""
    <div class="form-page">
        <div class="form-card">
            <h2>{title_text}</h2>
            <form action="/web/save" method="post">
                {id_input}
                <div class="form-group">
                    <label>姓名 <span style="color:var(--danger);">*</span></label>
                    <input type="text" name="name" value="{get('name')}" required placeholder="请输入姓名" autofocus>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>公司</label>
                        <input type="text" name="company" value="{get('company')}" placeholder="公司名称">
                    </div>
                    <div class="form-group">
                        <label>部门</label>
                        <input type="text" name="department" value="{get('department')}" placeholder="所属部门">
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>职位</label>
                        <input type="text" name="position" value="{get('position')}" placeholder="职位名称">
                    </div>
                    <div class="form-group">
                        <label>手机</label>
                        <input type="text" name="mobile" value="{get('mobile')}" placeholder="手机号码">
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>电话</label>
                        <input type="text" name="phone" value="{get('phone')}" placeholder="固定电话">
                    </div>
                    <div class="form-group">
                        <label>邮箱</label>
                        <input type="email" name="email" value="{get('email')}" placeholder="email@example.com">
                    </div>
                </div>
                <div class="form-group">
                    <label>地址</label>
                    <input type="text" name="company_address" value="{get('company_address')}" placeholder="公司地址">
                </div>
                <div class="form-group">
                    <label>备注</label>
                    <textarea name="notes" rows="3" placeholder="相识过程、备注信息...">{get('notes')}</textarea>
                </div>
                <div class="form-actions">
                    <button type="submit" class="btn btn-primary">💾 保存</button>
                    <a href="/web/" class="btn btn-ghost">取消</a>
                </div>
            </form>
        </div>
    </div>
    """
    return layout(title_text.replace("➕ ", "").replace("✏️ ", ""), content, active_nav="new" if not is_edit else "")


# ── 名片详情页 ────────────────────────────────────────

def render_card_page(contact: Contact, card_exists: bool, card_filename: str) -> str:
    info_rows = []
    for label, field in [("公司", "company"), ("部门", "department"), ("职位", "position"),
                          ("手机", "mobile"), ("电话", "phone"), ("邮箱", "email"),
                          ("地址", "company_address"), ("备注", "notes")]:
        val = getattr(contact, field, None)
        if val:
            info_rows.append(f"<div class='form-group'><label>{label}</label><p>{val}</p></div>")

    img_html = ""
    if card_exists:
        img_html = f'<img src="/web/photo/{card_filename}" alt="{contact.name}的名片" style="max-width:100%;border-radius:8px;box-shadow:var(--shadow);">'
    else:
        img_html = '<div class="empty-state"><div class="icon">🖼️</div><h3>名片生成失败</h3></div>'

    content = f"""
    <div style="max-width:700px;margin:0 auto;">
        <div class="card-detail" style="margin-bottom:20px;">
            <h2 style="font-size:1.5rem;margin-bottom:4px;">{contact.name}</h2>
            {f'<p style="color:var(--text-muted);">{contact.position or ""} {("@" + contact.company) if contact.company else ""}</p>' if (contact.position or contact.company) else ''}
        </div>
        <div class="card-detail">
            {img_html}
        </div>
        <div style="margin-top:20px;display:flex;gap:10px;justify-content:center;">
            <a href="/web/edit/{contact.id}" class="btn btn-primary">✏️ 编辑</a>
            <a href="/web/" class="btn btn-ghost">← 返回首页</a>
        </div>
    </div>
    """
    return layout(f"{contact.name}的名片", content)


# ── 公司详情页 ────────────────────────────────────────

def render_company_page(company: Company, contacts: list) -> str:
    contact_items = ""
    for c in contacts:
        contact_items += f"""
        <div class="contact-card">
            <div class="contact-info">
                <h3><a href="/web/card/{c.id}">{c.name}</a></h3>
                <div class="meta">
                    {f'<span>💼 {c.position}</span>' if c.position else ''}
                    {f'<span>📂 {c.department}</span>' if c.department else ''}
                    {f'<span>📱 {c.mobile}</span>' if c.mobile else ''}
                </div>
            </div>
            <div class="contact-actions">
                <a href="/web/card/{c.id}" class="btn btn-primary btn-sm">🖼️ 名片</a>
            </div>
        </div>"""

    content = f"""
    <div class="card-detail" style="text-align:left;margin-bottom:20px;">
        <h2 style="font-size:1.5rem;">🏢 {company.name}</h2>
        {f'<p style="color:var(--text-muted);margin-top:8px;">{company.description}</p>' if company.description else ''}
        {f'<p style="margin-top:4px;"><a href="{company.website}" target="_blank">{company.website}</a></p>' if company.website else ''}
    </div>
    <h2 style="margin-bottom:12px;">联系人 ({len(contacts)})</h2>
    <div class="contact-grid">{contact_items}</div>
    <div style="margin-top:20px;text-align:center;">
        <a href="/web/" class="btn btn-ghost">← 返回首页</a>
    </div>
    """
    return layout(f"{company.name}", content)


# ── AI 模型管理页 ─────────────────────────────────────

def render_models_page(models: list) -> str:
    cards = ""
    for m in models:
        active_badge = ' <span style="background:#16a34a;color:#fff;padding:1px 6px;border-radius:3px;font-size:.7rem;">当前</span>' if m.is_active else ""
        cards += f"""
        <div style="background:var(--card-bg);border:1px solid var(--border);border-radius:8px;padding:12px;margin-bottom:8px;">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:16px;">
                <div style="flex:1;">
                    <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
                        <strong style="font-size:1rem;">{m.name}</strong>
                        {active_badge}
                    </div>
                    <div style="font-size:.85rem;color:var(--text-muted);display:flex;flex-wrap:wrap;gap:8px;">
                        <span><strong>厂商:</strong> {m.provider}</span>
                        <span><strong>模型:</strong> {m.model_name}</span>
                        <span style="font-family:monospace;opacity:.8;">{m.api_base}</span>
                    </div>
                </div>
                <div style="display:flex;gap:4px;flex-shrink:0;">
                    <button class="btn btn-primary btn-sm" onclick="activateModel({m.id})" {'disabled' if m.is_active else ''}>启用</button>
                    <button class="btn btn-ghost btn-sm" onclick="editModel({m.id}, '{m.name}', '{m.provider}', '{m.api_base}', '{m.model_name}')">编辑</button>
                    <button class="btn btn-danger btn-sm" onclick="confirmDeleteModel({m.id}, '{m.name}')">删除</button>
                </div>
            </div>
        </div>"""

    content = f"""
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
        <h2 style="font-size:1.1rem;margin:0;">🤖 AI 模型管理</h2>
        <button class="btn btn-primary btn-sm" onclick="showAddModal()">➕ 添加模型</button>
    </div>

    <div id="modelsList">
        {cards if cards else '<div class="card-detail" style="text-align:center;padding:28px;color:var(--text-muted);">还没有添加 AI 模型<br><br><button class="btn btn-primary btn-sm" onclick="showAddModal()">➕ 添加第一个模型</button></div>'}
    </div>

    <div style="margin-top:16px;text-align:center;">
        <a href="/web/" class="btn btn-ghost btn-sm">← 返回首页</a>
    </div>

    <!-- 弹窗 -->
    <div id="modelModal" class="modal-overlay" style="display:none;align-items:flex-start;justify-content:center;padding-top:40px;">
        <div class="modal" style="max-width:520px;width:90%;text-align:left;padding:20px 24px 24px 24px;position:relative;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
                <h3 id="modalTitle" style="margin:0;font-size:1.2rem;">编辑模型配置</h3>
                <button onclick="hideModal()" style="background:transparent;border:none;font-size:1.5rem;cursor:pointer;color:var(--text-muted);padding:0;line-height:1;" title="关闭">×</button>
            </div>
            <form id="modelFormInner" onsubmit="saveModel(event)">
                <input type="hidden" id="modelId">
                <div class="form-group" style="margin-bottom:14px;">
                    <label style="font-weight:600;">配置名称 <span style="color:var(--danger);">*</span></label>
                    <input type="text" id="modelName" required placeholder="ark-model" style="padding:10px 14px;font-size:1rem;">
                </div>
                <div class="form-group" style="margin-bottom:14px;">
                    <label style="font-weight:600;">模型提供商 <span style="color:var(--danger);">*</span></label>
                    <select id="modelProvider" required style="width:100%;padding:10px 14px;border:2px solid var(--border);border-radius:10px;font-size:1rem;cursor:pointer;background:var(--card-bg);">
                        <option value="">请选择...</option>
                        <option value="Anthropic (Claude)">Anthropic (Claude)</option>
                        <option value="OpenAI (GPT)">OpenAI (GPT)</option>
                        <option value="智谱AI (GLM)">智谱AI (GLM)</option>
                        <option value="月之暗面 (Kimi)">月之暗面 (Kimi)</option>
                        <option value="字节跳动 (Doubao)">字节跳动 (Doubao)</option>
                        <option value="DeepSeek">DeepSeek</option>
                        <option value="Custom (兼容 OpenAI API)">Custom (兼容 OpenAI API)</option>
                    </select>
                </div>
                <div class="form-group" style="margin-bottom:14px;">
                    <label style="font-weight:600;">API Key</label>
                    <div style="position:relative;">
                        <input type="password" id="modelApiKey" placeholder="sk-..." style="padding:10px 44px 10px 14px;font-size:1rem;width:100%;">
                        <button type="button" onclick="toggleApiKey()" id="toggleKeyBtn" style="position:absolute;right:10px;top:50%;transform:translateY(-50%);background:transparent;border:none;cursor:pointer;font-size:1.1rem;padding:0;line-height:1;" title="显示/隐藏">👁️</button>
                    </div>
                    <p id="apiKeyHint" style="font-size:.85rem;color:var(--text-muted);margin-top:4px;">留空则不修改已有的 Key</p>
                </div>
                <div class="form-group" style="margin-bottom:14px;">
                    <label style="font-weight:600;">Base URL <span style="color:var(--danger);">*</span></label>
                    <input type="text" id="modelApiBase" required placeholder="https://ark.cn-beijing.volces.com/api/coding/v3" style="padding:10px 14px;font-size:1rem;">
                    <p style="font-size:.85rem;color:var(--text-muted);margin-top:4px;">例: https://api.deepseek.com/v1</p>
                </div>
                <div class="form-group" style="margin-bottom:16px;">
                    <label style="font-weight:600;">模型名称</label>
                    <input type="text" id="modelModelName" placeholder="如: glm-4v-flash">
                </div>
                <div style="display:flex;gap:10px;margin-bottom:16px;">
                    <button type="button" class="btn btn-ghost" onclick="testConnection()" id="testConnBtn" style="padding:10px 18px;">测试连接</button>
                </div>
                <div style="display:flex;gap:10px;justify-content:flex-end;">
                    <button type="button" class="btn btn-ghost" onclick="hideModal()">Cancel</button>
                    <button type="submit" class="btn btn-primary">OK</button>
                </div>
            </form>
        </div>
    </div>

    <script>
    function showAddModal() {{
        document.getElementById('modelModal').style.display = 'flex';
        document.getElementById('modalTitle').textContent = '添加模型配置';
        document.getElementById('modelId').value = '';
        document.getElementById('modelName').value = '';
        document.getElementById('modelProvider').value = '';
        document.getElementById('modelApiBase').value = '';
        document.getElementById('modelModelName').value = '';
        document.getElementById('modelApiKey').value = '';
        document.getElementById('modelApiKey').required = true;
        document.getElementById('apiKeyHint').style.display = 'none';
    }}
    function hideModal() {{ document.getElementById('modelModal').style.display = 'none'; }}
    function toggleApiKey() {{
        const inp = document.getElementById('modelApiKey');
        const btn = document.getElementById('toggleKeyBtn');
        if (inp.type === 'password') {{ inp.type = 'text'; btn.textContent = '🙈'; }}
        else {{ inp.type = 'password'; btn.textContent = '👁️'; }}
    }}
    async function testConnection() {{
        const btn = document.getElementById('testConnBtn');
        const origText = btn.textContent;
        btn.textContent = '⏳ 测试中...';
        btn.disabled = true;
        const body = {{
            api_base: document.getElementById('modelApiBase').value,
            api_key: document.getElementById('modelApiKey').value,
        }};
        try {{
            const resp = await fetch('/web/api/models/test', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify(body)}});
            const data = await resp.json();
            if (data.ok) {{ showToast('✅ 连接成功！模型列表: ' + (data.models || []).join(', ')); }}
            else {{ showToast('❌ 连接失败: ' + (data.error || '未知错误'), 'error'); }}
        }} catch(e) {{ showToast('❌ 请求失败: ' + e.message, 'error'); }}
        btn.textContent = origText;
        btn.disabled = false;
    }}
    function editModel(id, name, provider, apiBase, modelName) {{
        document.getElementById('modelModal').style.display = 'flex';
        document.getElementById('modalTitle').textContent = '编辑模型配置';
        document.getElementById('modelId').value = id;
        document.getElementById('modelName').value = name;
        document.getElementById('modelProvider').value = provider;
        document.getElementById('modelApiBase').value = apiBase;
        document.getElementById('modelModelName').value = modelName;
        document.getElementById('modelApiKey').value = '';
        document.getElementById('modelApiKey').required = false;
        document.getElementById('apiKeyHint').style.display = 'block';
    }}
    async function saveModel(e) {{
        e.preventDefault();
        const id = document.getElementById('modelId').value;
        const body = {{
            name: document.getElementById('modelName').value,
            provider: document.getElementById('modelProvider').value,
            api_base: document.getElementById('modelApiBase').value,
            model_name: document.getElementById('modelModelName').value,
            api_key: document.getElementById('modelApiKey').value,
        }};
        const url = id ? '/web/api/models/' + id : '/web/api/models';
        const method = id ? 'PUT' : 'POST';
        try {{
            const resp = await fetch(url, {{method, headers:{{'Content-Type':'application/json'}}, body:JSON.stringify(body)}});
            if (resp.ok) {{ showToast(id ? '模型已更新' : '模型已添加'); setTimeout(()=>location.reload(),500); }}
            else {{ const err = await resp.json(); showToast(err.detail || '保存失败', 'error'); }}
        }} catch(e) {{ showToast('网络错误', 'error'); }}
    }}
    async function activateModel(id) {{
        try {{
            const resp = await fetch('/web/api/models/' + id + '/activate', {{method:'POST'}});
            if (resp.ok) {{ showToast('已切换模型'); setTimeout(()=>location.reload(),500); }}
            else {{ showToast('切换失败', 'error'); }}
        }} catch(e) {{ showToast('网络错误', 'error'); }}
    }}
    function confirmDeleteModel(id, name) {{
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        overlay.innerHTML = `<div class="modal"><h3>确认删除</h3><p>确定要删除模型 <strong>${{name}}</strong> 吗？</p><div class="modal-actions"><button class="btn btn-ghost" onclick="this.closest('.modal-overlay').remove()">取消</button><button class="btn btn-danger" onclick="doDeleteModel(${{id}})">确认删除</button></div></div>`;
        document.body.appendChild(overlay);
        overlay.addEventListener('click', e => {{ if (e.target === overlay) overlay.remove(); }});
    }}
    async function doDeleteModel(id) {{
        try {{
            const resp = await fetch('/web/api/models/' + id, {{method:'DELETE'}});
            if (resp.ok) {{ showToast('模型已删除'); setTimeout(()=>location.reload(),500); }}
            else {{ showToast('删除失败', 'error'); }}
        }} catch(e) {{ showToast('网络错误', 'error'); }}
    }}
    // 点击遮罩关闭
    document.getElementById('modelModal').addEventListener('click', function(e) {{
        if (e.target === this) {{ hideModal(); }}
    }});
    </script>
    """
    return layout("AI 模型管理", content)


# ── OCR 拍照录入页 ─────────────────────────────────────

def render_ocr_page(has_active_model: bool) -> str:
    if not has_active_model:
        content = """
        <div class="empty-state">
            <div class="icon">🤖</div>
            <h3>没有启用的 AI 模型</h3>
            <p>请先在「模型管理」中添加并启用一个多模态大模型，再进行拍照录入。</p>
            <a href="/web/models" class="btn btn-primary" style="margin-top:16px;">前往模型管理</a>
        </div>"""
        return layout("拍照录入", content)

    content = """
    <div class="form-page">
        <div class="form-card">
            <h2>📷 拍照录入名片</h2>
            <p style="color:var(--text-muted);margin-bottom:20px;">上传名片照片或直接拍照，AI 将自动识别并提取信息</p>

            <!-- 选择方式按钮 -->
            <div id="choiceButtons" style="display:flex;gap:12px;margin-bottom:20px;">
                <button class="btn btn-primary" onclick="startCamera()" style="flex:1;">📷 拍照</button>
                <button class="btn btn-ghost" onclick="showFileSelect()" style="flex:1;">📁 选择图片</button>
            </div>

            <!-- 文件选择区域 -->
            <div id="uploadArea" style="display:none;border:2px dashed var(--border);border-radius:12px;padding:40px;text-align:center;cursor:pointer;transition:all .2s;margin-bottom:20px;"
                 ondrop="handleDrop(event)" ondragover="handleDragOver(event)" ondragleave="handleDragLeave(event)" onclick="document.getElementById('fileInput').click()">
                <div style="font-size:3rem;margin-bottom:12px;">📸</div>
                <p style="font-weight:600;">点击选择或拖拽名片照片到此处</p>
                <p style="color:var(--text-muted);font-size:.85rem;margin-top:4px;">支持 JPG、PNG、WebP 格式</p>
                <input type="file" id="fileInput" accept="image/*" style="display:none;" onchange="handleFileSelect(event)">
            </div>

            <!-- 相机预览区域 -->
            <div id="cameraArea" style="display:none;margin-bottom:20px;">
                <video id="cameraVideo" autoplay playsinline style="width:100%;border-radius:12px;box-shadow:var(--shadow);background:#000;"></video>
                <canvas id="cameraCanvas" style="display:none;"></canvas>
                <div style="display:flex;gap:10px;margin-top:12px;">
                    <button class="btn btn-primary" onclick="capturePhoto()" style="flex:1;">📸 拍摄</button>
                    <button class="btn btn-ghost" onclick="stopCamera()">✕ 取消</button>
                </div>
            </div>

            <!-- 预览区域 -->
            <div id="previewArea" style="display:none;text-align:center;margin-bottom:20px;">
                <img id="previewImage" style="max-width:100%;max-height:300px;border-radius:8px;box-shadow:var(--shadow);">
                <div style="margin-top:12px;display:flex;gap:10px;">
                    <button class="btn btn-primary" onclick="startOCR()" id="ocrBtn" style="flex:1;">🔍 开始识别</button>
                    <button class="btn btn-ghost" onclick="resetUpload()" style="flex:1;">重新选择</button>
                </div>
            </div>

            <div id="ocrProgress" style="display:none;text-align:center;padding:20px;">
                <div style="font-size:2rem;animation:spin 1s linear infinite;">⏳</div>
                <p style="color:var(--text-muted);margin-top:8px;">AI 正在识别名片信息...</p>
            </div>

            <div id="ocrResult" style="display:none;"></div>
        </div>
    </div>

    <style>
    @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
    #uploadArea:hover { border-color: var(--primary); background: #eff6ff; }
    #uploadArea.dragover { border-color: var(--primary); background: #eff6ff; }
    </style>

    <script>
    let selectedFile = null;
    let mediaStream = null;

    function showFileSelect() {
        document.getElementById('choiceButtons').style.display = 'none';
        document.getElementById('uploadArea').style.display = 'block';
    }

    async function startCamera() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            showToast('您的浏览器不支持摄像头功能，请使用「选择图片」', 'error');
            return;
        }
        try {
            const video = document.getElementById('cameraVideo');
            // 先尝试后置摄像头
            try {
                mediaStream = await navigator.mediaDevices.getUserMedia({
                    video: { facingMode: 'environment', width: { ideal: 1920 }, height: { ideal: 1080 } }
                });
            } catch(e) {
                // 如果后置不行，尝试任意摄像头
                mediaStream = await navigator.mediaDevices.getUserMedia({
                    video: { width: { ideal: 1920 }, height: { ideal: 1080 } }
                });
            }
            video.srcObject = mediaStream;
            document.getElementById('choiceButtons').style.display = 'none';
            document.getElementById('cameraArea').style.display = 'block';
        } catch(e) {
            let msg = '无法访问摄像头';
            if (e.name === 'NotAllowedError') {
                msg = '请允许访问摄像头权限';
            } else if (e.name === 'NotFoundError') {
                msg = '未找到摄像头设备';
            } else if (e.name === 'NotReadableError') {
                msg = '摄像头被其他应用占用';
            } else if (location.protocol !== 'https:' && location.hostname !== 'localhost' && location.hostname !== '127.0.0.1') {
                msg = '摄像头功能需要 HTTPS 访问，请使用「选择图片」';
            }
            showToast(msg + '，请使用「选择图片」', 'error');
            console.error(e);
        }
    }

    function stopCamera() {
        if (mediaStream) {
            mediaStream.getTracks().forEach(track => track.stop());
            mediaStream = null;
        }
        document.getElementById('cameraArea').style.display = 'none';
        document.getElementById('choiceButtons').style.display = 'flex';
    }

    function capturePhoto() {
        const video = document.getElementById('cameraVideo');
        const canvas = document.getElementById('cameraCanvas');
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(video, 0, 0);

        canvas.toBlob(function(blob) {
            selectedFile = new File([blob], 'photo.jpg', { type: 'image/jpeg' });
            document.getElementById('previewImage').src = canvas.toDataURL('image/jpeg');
            stopCamera();
            document.getElementById('previewArea').style.display = 'block';
            document.getElementById('ocrResult').style.display = 'none';
        }, 'image/jpeg', 0.9);
    }

    function handleDragOver(e) { e.preventDefault(); document.getElementById('uploadArea').classList.add('dragover'); }
    function handleDragLeave(e) { document.getElementById('uploadArea').classList.remove('dragover'); }
    function handleDrop(e) {
        e.preventDefault();
        document.getElementById('uploadArea').classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) { processFile(e.dataTransfer.files[0]); }
    }
    function handleFileSelect(e) { if (e.target.files.length > 0) { processFile(e.target.files[0]); } }
    function processFile(file) {
        if (!file.type.startsWith('image/')) { showToast('请选择图片文件', 'error'); return; }
        selectedFile = file;
        const reader = new FileReader();
        reader.onload = (e) => {
            document.getElementById('previewImage').src = e.target.result;
            document.getElementById('uploadArea').style.display = 'none';
            document.getElementById('previewArea').style.display = 'block';
            document.getElementById('ocrResult').style.display = 'none';
        };
        reader.readAsDataURL(file);
    }
    function resetUpload() {
        selectedFile = null;
        document.getElementById('fileInput').value = '';
        document.getElementById('uploadArea').style.display = 'none';
        document.getElementById('previewArea').style.display = 'none';
        document.getElementById('ocrResult').style.display = 'none';
        document.getElementById('ocrProgress').style.display = 'none';
        document.getElementById('choiceButtons').style.display = 'flex';
    }
    async function startOCR() {
        if (!selectedFile) return;
        document.getElementById('ocrBtn').disabled = true;
        document.getElementById('ocrProgress').style.display = 'block';
        const formData = new FormData();
        formData.append('file', selectedFile);
        try {
            const resp = await fetch('/web/api/ocr', { method: 'POST', body: formData });
            const data = await resp.json();
            document.getElementById('ocrProgress').style.display = 'none';
            if (data.error) {
                showToast(data.error, 'error');
                document.getElementById('ocrBtn').disabled = false;
                return;
            }
            renderOCRResult(data);
        } catch(e) {
            document.getElementById('ocrProgress').style.display = 'none';
            showToast('识别请求失败', 'error');
            document.getElementById('ocrBtn').disabled = false;
        }
    }
    function renderOCRResult(data) {
        const fields = [
            ['name', '姓名'], ['company', '公司'], ['department', '部门'],
            ['position', '职位'], ['mobile', '手机'], ['phone', '电话'],
            ['email', '邮箱'], ['company_address', '地址']
        ];
        let formHTML = '<form action="/web/save" method="post"><div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">';
        for (const [key, label] of fields) {
            const val = data[key] || '';
            formHTML += `<div class="form-group"><label>${label}</label><input type="text" name="${key}" value="${escapeHtml(val)}"></div>`;
        }
        formHTML += '</div><div class="form-group"><label>备注</label><textarea name="notes" rows="2">' + escapeHtml(data.notes || '') + '</textarea></div>';
        formHTML += '<div class="form-actions"><button type="submit" class="btn btn-primary">💾 确认保存</button><button type="button" class="btn btn-ghost" onclick="resetUpload()">重新录入</button></div></form>';
        document.getElementById('ocrResult').innerHTML = '<h3 style="margin-bottom:16px;">✅ 识别结果 — 请确认并修正</h3>' + formHTML;
        document.getElementById('ocrResult').style.display = 'block';
    }
    function escapeHtml(s) { return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
    </script>
    """
    return layout("拍照录入", content)


# ── Pydantic 验证 ─────────────────────────────────────

class ContactForm(BaseModel):
    id: Optional[int] = None
    name: str
    company: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    mobile: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    company_address: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("姓名不能为空")
        if len(v) > 100:
            raise ValueError("姓名不能超过100个字符")
        return v

    @field_validator("email")
    @classmethod
    def email_valid(cls, v: Optional[str]) -> Optional[str]:
        if v and "@" not in v:
            raise ValueError("邮箱格式不正确")
        return v

    @field_validator("mobile", "phone")
    @classmethod
    def phone_valid(cls, v: Optional[str]) -> Optional[str]:
        if v and not v.strip():
            return None
        return v


# ── 路由 ──────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def web_home():
    db = SessionLocal()
    contacts = contact_crud.list_recent(db, limit=200)
    companies = db.query(Company).all()
    total_contacts = db.query(Contact).count()
    total_companies = db.query(Company).count()
    db.close()

    contacts_data = [
        type('obj', (object,), {
            'id': c.id, 'name': c.name, 'company': c.company,
            'department': c.department, 'position': c.position,
            'mobile': c.mobile, 'phone': c.phone, 'email': c.email,
        }) for c in contacts
    ]
    companies_data = [{"id": c.id, "name": c.name, "description": c.description} for c in companies]

    return HTMLResponse(content=render_home(contacts_data, companies_data, total_contacts, total_companies))


@router.get("/api/contacts")
async def api_contacts(q: str = None, limit: int = 200):
    db = SessionLocal()
    if q:
        contacts = contact_crud.search(db, q)
    else:
        contacts = contact_crud.list_recent(db, limit=limit)

    companies = db.query(Company).all()

    result = {
        "contacts": [
            {"id": c.id, "name": c.name, "company": c.company,
             "department": c.department, "position": c.position,
             "mobile": c.mobile, "phone": c.phone, "email": c.email}
            for c in contacts
        ],
        "companies": [{"id": c.id, "name": c.name, "description": c.description} for c in companies]
    }
    db.close()
    return result


@router.delete("/api/contacts/{contact_id}")
async def api_delete_contact(contact_id: int):
    db = SessionLocal()
    contact = contact_crud.get(db, contact_id)
    if not contact:
        db.close()
        return JSONResponse({"detail": "联系人不存在"}, status_code=404)
    contact_crud.delete(db, contact_id)
    db.close()
    return {"ok": True}


@router.get("/new", response_class=HTMLResponse)
async def web_new():
    return HTMLResponse(content=render_form())


@router.get("/edit/{contact_id}", response_class=HTMLResponse)
async def web_edit(contact_id: int):
    db = SessionLocal()
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    db.close()
    if not contact:
        return RedirectResponse("/web/", status_code=302)
    return HTMLResponse(content=render_form(contact))


@router.post("/save")
async def web_save(
    id: int = Form(None), name: str = Form(...),
    company: str = Form(""), department: str = Form(""),
    position: str = Form(""), mobile: str = Form(""),
    phone: str = Form(""), email: str = Form(""),
    company_address: str = Form(""), notes: str = Form("")
):
    try:
        form_data = ContactForm(
            id=id, name=name, company=company or None,
            department=department or None, position=position or None,
            mobile=mobile or None, phone=phone or None, email=email or None,
            company_address=company_address or None, notes=notes or None
        )
    except Exception:
        return HTMLResponse(
            content='<p style="color:red;text-align:center;padding:40px;">输入数据无效，请检查后重试。 <a href="/web/new">返回</a></p>',
            status_code=400
        )

    db = SessionLocal()
    if form_data.id:
        contact = db.query(Contact).filter(Contact.id == form_data.id).first()
        if contact:
            for f in ["name", "company", "department", "position", "mobile",
                       "phone", "email", "company_address", "notes"]:
                setattr(contact, f, getattr(form_data, f))
            db.commit()
    else:
        contact_crud.create(
            db, name=form_data.name, company=form_data.company,
            department=form_data.department, position=form_data.position,
            mobile=form_data.mobile, phone=form_data.phone,
            email=form_data.email, company_address=form_data.company_address,
            notes=form_data.notes
        )
    db.close()
    return RedirectResponse("/web/", status_code=302)


@router.get("/card/{contact_id}", response_class=HTMLResponse)
async def web_card(contact_id: int):
    db = SessionLocal()
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        db.close()
        return RedirectResponse("/web/", status_code=302)

    colleagues = contact_crud.get_by_company(db, contact.company) if contact.company else []
    generator = CardGenerator()
    output_path = Config.PHOTOS_DIR / f"web_card_{contact.id}.jpg"
    result = generator.create_card(contact, colleagues, output_path=output_path)
    db.close()

    card_filename = f"web_card_{contact.id}.jpg"
    card_exists = result and output_path.exists()
    return HTMLResponse(content=render_card_page(contact, card_exists, card_filename))


@router.get("/photo/{filename}")
async def web_photo(filename: str):
    file_path = Config.PHOTOS_DIR / filename
    if file_path.exists():
        return FileResponse(file_path)
    return {"error": "File not found"}


@router.get("/company/{company_id}", response_class=HTMLResponse)
async def web_company(company_id: int):
    db = SessionLocal()
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        db.close()
        return RedirectResponse("/web/", status_code=302)
    contacts = contact_crud.get_by_company(db, company.name)
    db.close()
    return HTMLResponse(content=render_company_page(company, contacts))


# ── AI 模型管理页面 ───────────────────────────────────

@router.get("/models", response_class=HTMLResponse)
async def web_models():
    db = SessionLocal()
    models = ai_model_manager.list_all(db)
    db.close()
    return HTMLResponse(content=render_models_page(models))


# ── OCR 拍照录入页面 ──────────────────────────────────

@router.get("/ocr", response_class=HTMLResponse)
async def web_ocr():
    db = SessionLocal()
    active = ai_model_manager.get_active(db)
    db.close()
    return HTMLResponse(content=render_ocr_page(active is not None))


# ── AI 模型管理 API ───────────────────────────────────

@router.get("/api/models")
async def api_list_models():
    db = SessionLocal()
    models = ai_model_manager.list_all(db)
    result = [{
        "id": m.id, "name": m.name, "provider": m.provider,
        "api_base": m.api_base, "model_name": m.model_name,
        "is_active": m.is_active
    } for m in models]
    db.close()
    return result


@router.post("/api/models")
async def api_create_model(request: Request):
    body = await request.json()
    db = SessionLocal()
    model = ai_model_manager.create(
        db, name=body["name"], provider=body["provider"],
        api_base=body["api_base"], api_key=body["api_key"],
        model_name=body["model_name"]
    )
    # 如果是第一个模型，自动设为启用
    if ai_model_manager.get_active(db) is None:
        ai_model_manager.set_active(db, model.id)
    db.close()
    return {"ok": True, "id": model.id}


@router.put("/api/models/{model_id}")
async def api_update_model(model_id: int, request: Request):
    body = await request.json()
    update_data = {k: v for k, v in body.items() if v is not None and k != "id"}
    # api_key 为空就不更新
    if "api_key" in update_data and not update_data["api_key"]:
        del update_data["api_key"]
    db = SessionLocal()
    model = ai_model_manager.update(db, model_id, **update_data)
    db.close()
    if not model:
        return JSONResponse({"detail": "模型不存在"}, status_code=404)
    return {"ok": True}


@router.post("/api/models/{model_id}/activate")
async def api_activate_model(model_id: int):
    db = SessionLocal()
    model = ai_model_manager.set_active(db, model_id)
    db.close()
    if not model:
        return JSONResponse({"detail": "模型不存在"}, status_code=404)
    return {"ok": True, "name": model.name}


@router.delete("/api/models/{model_id}")
async def api_delete_model(model_id: int):
    db = SessionLocal()
    ok = ai_model_manager.delete(db, model_id)
    db.close()
    if not ok:
        return JSONResponse({"detail": "模型不存在"}, status_code=404)
    return {"ok": True}


@router.post("/api/models/test")
async def api_test_model_connection(request: Request):
    """测试模型连接 — 调用 /models 端点验证 API Key 是否有效"""
    body = await request.json()
    api_base = body.get("api_base", "").rstrip("/")
    api_key = body.get("api_key", "")

    if not api_base or not api_key:
        return {"ok": False, "error": "Base URL 和 API Key 不能为空"}

    import requests as req
    try:
        headers = {"Authorization": f"Bearer {api_key}"}
        resp = req.get(f"{api_base}/models", headers=headers, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            models = []
            if "data" in data:
                models = [m.get("id", "") for m in data["data"]]
            return {"ok": True, "models": models[:10]}
        else:
            return {"ok": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
    except req.exceptions.Timeout:
        return {"ok": False, "error": "连接超时，请检查 Base URL 是否正确"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ── OCR API ───────────────────────────────────────────

@router.post("/api/ocr")
async def api_ocr(file: UploadFile = File(...)):
    # 获取当前启用的模型
    db = SessionLocal()
    active_model = ai_model_manager.get_active(db)
    db.close()

    if not active_model:
        return JSONResponse({"error": "没有启用的 AI 模型，请先在模型管理中配置"}, status_code=400)

    # 保存上传的图片
    import uuid
    suffix = Path(file.filename).suffix if file.filename else ".jpg"
    temp_path = Config.PHOTOS_DIR / f"ocr_temp_{uuid.uuid4().hex[:8]}{suffix}"
    with open(temp_path, "wb") as f:
        f.write(await file.read())

    # 调用 OCR
    engine = OCREngine(
        api_base=active_model.api_base,
        api_key=active_model.api_key,
        model_name=active_model.model_name
    )
    result = engine.recognize(temp_path)

    # 清理临时文件
    try:
        temp_path.unlink()
    except Exception:
        pass

    return result
