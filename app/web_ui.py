"""
名片管理系统 - Web 管理界面
"""
import json
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
from app.face_search import FaceSearchEngine
from app.knowledge_crud import knowledge_crud
from app.knowledge_engine import KnowledgeEngine, summarize_contact_knowledge
from app.models import KnowledgeEntry
from datetime import datetime

router = APIRouter()


# ── 首页JavaScript代码 ──────────────────────────────
HOME_JAVASCRIPT = """
    <script>
    var _allContacts = [];
    var _pageSize = 8;
    var _currentPage = 1;
    var _faceSearchMediaStream = null;

    function previewFacePhoto(input) {
        if (input.files && input.files[0]) {
            var reader = new FileReader();
            reader.onload = function(e) {
                document.getElementById('facePreviewImg').src = e.target.result;
                document.getElementById('facePhotoPreview').style.display = 'block';
            };
            reader.readAsDataURL(input.files[0]);
        }
    }

    async function showFaceSearchCamera() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            showToast('您的浏览器不支持摄像头功能，请使用Chrome、Safari或Edge', 'error');
            return;
        }
        var isSecure = location.protocol === 'https:' || location.hostname === 'localhost' || location.hostname === '127.0.0.1';
        if (!isSecure) {
            showToast('摄像头需要HTTPS环境！请使用 start_https.sh 启动服务', 'error');
            return;
        }

        var video = document.getElementById('faceSearchCameraVideo');
        var modal = document.getElementById('faceSearchCameraModal');

        try {
            _faceSearchMediaStream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: 'user', width: { ideal: 1280 }, height: { ideal: 720 } }
            });
            video.srcObject = _faceSearchMediaStream;
            modal.style.display = 'flex';
        } catch(e) {
            var msg = '无法访问摄像头';
            if (e.name === 'NotAllowedError') {
                msg = '请允许访问摄像头权限';
            } else if (e.name === 'NotFoundError') {
                msg = '未找到摄像头设备';
            } else if (e.name === 'NotReadableError') {
                msg = '摄像头被其他应用占用';
            } else {
                msg = '摄像头启动失败: ' + e.message;
            }
            showToast(msg + '，请使用「上传照片」代替', 'error');
        }
    }

    function closeFaceSearchCamera() {
        if (_faceSearchMediaStream) {
            _faceSearchMediaStream.getTracks().forEach(function(track) { track.stop(); });
            _faceSearchMediaStream = null;
        }
        document.getElementById('faceSearchCameraModal').style.display = 'none';
    }

    function captureFaceSearchPhoto() {
        var video = document.getElementById('faceSearchCameraVideo');
        var canvas = document.getElementById('faceSearchCameraCanvas');
        if (!video.videoWidth) {
            showToast('摄像头尚未就绪，请稍后再试', 'error');
            return;
        }

        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        var ctx = canvas.getContext('2d');
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

        canvas.toBlob(function(blob) {
            if (!blob) {
                showToast('拍照失败，请重试', 'error');
                return;
            }
            var file = new File([blob], 'face.jpg', { type: 'image/jpeg' });
            var reader = new FileReader();
            reader.onload = function(e) {
                document.getElementById('facePreviewImg').src = e.target.result;
                document.getElementById('facePhotoPreview').style.display = 'block';
            };
            reader.readAsDataURL(file);

            try {
                var dt = new DataTransfer();
                dt.items.add(file);
                document.getElementById('facePhotoInput').files = dt.files;
            } catch(ex) {
                // 某些浏览器不支持设置 file input
            }
            closeFaceSearchCamera();
            showToast('拍照成功！请点击「开始搜索」进行人脸比对', 'success');
        }, 'image/jpeg', 0.85);
    }

    async function doFaceSearch() {
        var input = document.getElementById('facePhotoInput');
        if (!input.files || input.files.length === 0) {
            showToast('请先上传或拍摄要搜索的照片', 'error');
            return;
        }

        var btn = document.getElementById('faceSearchBtn');
        var progress = document.getElementById('faceSearchProgress');
        var threshold = document.getElementById('confidenceThreshold').value;

        btn.disabled = true;
        btn.textContent = '搜索中...';
        progress.style.display = 'block';

        var formData = new FormData();
        formData.append('photo', input.files[0]);
        formData.append('confidence_threshold', threshold);

        try {
            var resp = await fetch('/web/api/search-by-face', { method: 'POST', body: formData });
            var data = await resp.json();
            if (data.error) { showToast(data.error, 'error'); return; }
            if (data.message) { showToast(data.message, 'info'); }
            _allContacts = data.contacts || [];
            renderPage(1);
        } catch(e) {
            showToast('搜索失败：' + e.message, 'error');
        } finally {
            btn.disabled = false;
            btn.textContent = '🔍 开始搜索';
            progress.style.display = 'none';
        }
    }

    async function loadAllContacts() {
        try {
            var resp = await fetch('/web/api/contacts?limit=200');
            var data = await resp.json();
            _allContacts = data.contacts || [];
            renderPage(1);
        } catch(e) { console.error(e); }
    }

    function renderPage(page) {
        _currentPage = page;
        var start = (page - 1) * _pageSize;
        var pageItems = _allContacts.slice(start, start + _pageSize);
        var grid = document.getElementById('contactList');
        if (!grid) return;

        if (pageItems.length === 0 && _allContacts.length === 0) {
            grid.innerHTML = '<div class="empty-state"><div class="icon">📭</div><h3>还没有名片</h3><p>点击右上角「添加」录入第一张名片吧</p></div>';
            document.getElementById('pagination').innerHTML = '';
            return;
        }
        if (pageItems.length === 0) { renderPage(page - 1); return; }

        grid.innerHTML = pageItems.map(function(c) {
            var confHtml = '';
            if (c.confidence !== undefined) {
                confHtml = '<div style="margin-top:4px;font-size:.75rem;color:var(--text-muted);">'
                    + '<span style="background:var(--primary);color:#fff;padding:1px 6px;border-radius:3px;">匹配度:' + Math.round(c.confidence * 100) + '%</span>'
                    + (c.reasoning ? '<span style="margin-left:6px;">' + c.reasoning + '</span>' : '')
                    + '</div>';
            }
            var safeName = c.name.replace(/'/g, "\\'");
            return '<div class="contact-card">'
                + '<div class="contact-info">'
                + '<h3><a href="/web/card/' + c.id + '">' + c.name + '</a></h3>'
                + '<div class="meta">'
                + (c.company ? '<span>🏢 ' + c.company + '</span>' : '')
                + (c.department ? '<span>📂 ' + c.department + '</span>' : '')
                + (c.position ? '<span>💼 ' + c.position + '</span>' : '')
                + (c.mobile ? '<span>📱 ' + c.mobile + '</span>' : '')
                + '</div>' + confHtml
                + '</div>'
                + '<div class="contact-actions">'
                + '<a href="/web/card/' + c.id + '" class="btn btn-primary btn-sm">🖼️ 名片</a>'
                + '<a href="/web/edit/' + c.id + '" class="btn btn-ghost btn-sm">✏️ 编辑</a>'
                + '<button class="btn btn-danger btn-sm" onclick="confirmDelete(' + c.id + ', \\'' + safeName + '\\')">🗑️</button>'
                + '</div>'
                + '</div>';
        }).join('');

        var totalPages = Math.ceil(_allContacts.length / _pageSize);
        var pagHTML = '';
        if (totalPages > 1) {
            for (var i = 1; i <= totalPages; i++) {
                pagHTML += '<button class="' + (i === _currentPage ? 'active' : '')
                    + '" onclick="renderPage(' + i + ')">' + i + '</button>';
            }
        }
        document.getElementById('pagination').innerHTML = pagHTML;
    }

    var doSearch = debounce(async function() {
        var q = document.getElementById('searchInput').value.trim();
        if (!q) { loadAllContacts(); return; }
        try {
            var resp = await fetch('/web/api/contacts?q=' + encodeURIComponent(q));
            var data = await resp.json();
            _allContacts = data.contacts || [];
            renderPage(1);
        } catch(e) { console.error(e); }
    }, 300);

    // ── 初始化 ────────────────────────────────────
    document.getElementById('searchInput').addEventListener('input', doSearch);
    loadAllContacts();

    // 点击遮罩关闭摄像头
    document.getElementById('faceSearchCameraModal').addEventListener('click', function(e) {
        if (e.target === this) closeFaceSearchCamera();
    });
    </script>
"""


def generate_filename(suffix: str = ".jpg", prefix: str = "") -> str:
    """生成日期+序号格式的文件名"""
    date_str = datetime.now().strftime("%Y%m%d")

    # 查找今天已有的文件，确定序号
    existing_files = list(Config.PHOTOS_DIR.glob(f"{prefix}{date_str}_*.{suffix.lstrip('.')}"))
    max_num = 0
    for f in existing_files:
        try:
            num_str = f.stem.split("_")[-1]
            num = int(num_str)
            if num > max_num:
                max_num = num
        except (ValueError, IndexError):
            continue

    new_num = max_num + 1
    filename = f"{prefix}{date_str}_{new_num:04d}{suffix}"
    return filename

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
.toast.info { background: var(--primary); }
@keyframes slideIn { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
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
    nav_knowledge = 'class="active"' if active_nav == "knowledge" else ""
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
    {SHARED_JS}
</head>
<body>
    <header>
        <div class="inner">
            <h1>📇 名片管理系统</h1>
            <nav>
                <a href="/web/" {nav_home}>🏠 首页</a>
                <a href="/web/knowledge" {nav_knowledge}>📝 随记</a>
                <a href="/web/ocr" {nav_ocr}>📷 拍照录入</a>
                <a href="/web/new" {nav_new}>➕ 添加</a>
                <a href="/web/models" {nav_models}>🤖 模型管理</a>
            </nav>
        </div>
    </header>
    <div class="container">{content}</div>
    <div id="toast-container" class="toast-container"></div>
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
        name = comp['name']
        contact_count = comp.get('contact_count', 0)
        desc = comp.get('description', '') or ''
        if contact_count:
            desc = f"{contact_count} 位联系人" + (f" · {desc}" if desc else "")
        link = f"/web/company/{comp['id']}"
        company_cards += f"""
        <div class="contact-card">
            <div class="contact-info">
                <h3><a href="{link}">🏢 {name}</a></h3>
                <div class="meta"><span>{desc}</span></div>
            </div>
            <div class="contact-actions">
                <a href="{link}" class="btn btn-ghost btn-sm">查看全部 →</a>
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

    <div style="border:2px dashed var(--border);border-radius:12px;padding:16px;margin-bottom:20px;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
            <span style="font-weight:600;">👤 人脸搜索</span>
        </div>
        <div style="display:flex;gap:10px;align-items:center;">
            <button class="btn btn-primary btn-sm" onclick="document.getElementById('facePhotoInput').click()">📷 上传照片</button>
            <button class="btn btn-primary btn-sm" onclick="showFaceSearchCamera()">📸 拍照</button>
            <button class="btn btn-ghost btn-sm" onclick="doFaceSearch()" id="faceSearchBtn">🔍 开始搜索</button>
        </div>
        <div style="margin-top:10px;">
            <label style="font-size:.85rem;color:var(--text-muted);">置信度阈值：</label>
            <input type="range" id="confidenceThreshold" min="0.3" max="0.95" step="0.05" value="0.6"
                   style="width:150px;" oninput="document.getElementById('confidenceValue').textContent = this.value;">
            <span id="confidenceValue" style="font-size:.85rem;margin-left:8px;">0.6</span>
        </div>
        <input type="file" id="facePhotoInput" accept="image/*" style="display:none;" onchange="previewFacePhoto(this)">
        <div id="facePhotoPreview" style="margin-top:8px;display:none;">
            <img id="facePreviewImg" style="max-height:150px;max-width:100%;border-radius:8px;box-shadow:var(--shadow);">
        </div>
        <div id="faceSearchProgress" style="margin-top:12px;display:none;text-align:center;">
            <div style="font-size:1.5rem;animation:spin 1s linear infinite;">⏳</div>
            <p style="color:var(--text-muted);margin-top:4px;font-size:.85rem;">正在使用 AI 进行人脸比对...</p>
        </div>
    </div>

    <!-- 人脸搜索相机模态框 -->
    <div id="faceSearchCameraModal" class="modal-overlay" style="display:none;align-items:center;justify-content:center;">
        <div class="modal" style="max-width:500px;width:90%;">
            <h3>📸 拍照</h3>
            <video id="faceSearchCameraVideo" autoplay playsinline style="width:100%;border-radius:12px;box-shadow:var(--shadow);background:#000;"></video>
            <canvas id="faceSearchCameraCanvas" style="display:none;"></canvas>
            <div style="display:flex;gap:10px;margin-top:12px;">
                <button type="button" class="btn btn-primary" onclick="captureFaceSearchPhoto()">📸 拍摄</button>
                <button type="button" class="btn btn-ghost" onclick="closeFaceSearchCamera()">✕ 取消</button>
            </div>
        </div>
    </div>

    <div id="results-area">
        <h2 style="margin-bottom:12px;font-size:1.1rem;">📋 名片列表</h2>
        <div class="contact-grid" id="contactList">{contact_cards}</div>
        {empty_html}
        <div class="pagination" id="pagination"></div>
    </div>

    {f'''<h2 style="margin:32px 0 12px;font-size:1.1rem;">🏢 公司列表</h2>
    <div class="contact-grid">{company_cards}</div>''' if companies else ''}

    {HOME_JAVASCRIPT}
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
            <form id="contactForm" action="/web/save" method="post" enctype="multipart/form-data">
                {id_input}
                <div class="form-group">
                    <label>姓名 <span style="color:var(--danger);">*</span></label>
                    <input type="text" name="name" value="{get('name')}" required placeholder="请输入姓名" autofocus>
                </div>
                <div class="form-group">
                    <label>英文姓名</label>
                    <input type="text" name="name_en" value="{get('name_en')}" placeholder="英文姓名（可选）">
                </div>

                <div class="form-group">
                    <label>名片照片</label>
                    <div style="display:flex;gap:10px;align-items:center;">
                        <button type="button" class="btn btn-ghost btn-sm" onclick="document.getElementById('cardPhotoInput').click()">📁 上传图片</button>
                        <button type="button" class="btn btn-primary btn-sm" onclick="showCardPhotoCamera()">📷 拍照</button>
                    </div>
                    <input type="file" id="cardPhotoInput" name="card_photo" accept="image/*" style="display:none;" onchange="previewCardPhoto(this)">
                    <div id="cardPhotoPreview" style="margin-top:8px;{'display:block;' if get('business_card_path') else 'display:none;'}">
                        {f'<img src="/web/photo/{get("business_card_path")}" style="max-height:150px;max-width:100%;border-radius:8px;box-shadow:var(--shadow);">' if get('business_card_path') else ''}
                    </div>
                </div>

                <div class="form-group">
                    <label>头像照片</label>
                    <div style="display:flex;gap:10px;align-items:center;">
                        <button type="button" class="btn btn-ghost btn-sm" onclick="document.getElementById('avatarInput').click()">📁 上传图片</button>
                        <button type="button" class="btn btn-primary btn-sm" onclick="showAvatarCamera()">📷 拍照</button>
                    </div>
                    <input type="file" id="avatarInput" name="avatar" accept="image/*" style="display:none;" onchange="previewAvatar(this)">
                    <div id="avatarPreview" style="margin-top:8px;{'display:block;' if get('avatar_path') else 'display:none;'}">
                        {f'<img src="/web/photo/{get("avatar_path")}" style="max-height:150px;max-width:100%;border-radius:8px;box-shadow:var(--shadow);">' if get('avatar_path') else ''}
                    </div>
                </div>

                <div class="form-row">
                    <div class="form-group">
                        <label>公司</label>
                        <input type="text" name="company" value="{get('company')}" placeholder="公司名称">
                    </div>
                    <div class="form-group">
                        <label>英文公司名</label>
                        <input type="text" name="company_en" value="{get('company_en')}" placeholder="英文公司名（可选）">
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>部门</label>
                        <input type="text" name="department" value="{get('department')}" placeholder="所属部门">
                    </div>
                    <div class="form-group">
                        <label>英文部门</label>
                        <input type="text" name="department_en" value="{get('department_en')}" placeholder="英文部门（可选）">
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>职位</label>
                        <input type="text" name="position" value="{get('position')}" placeholder="职位名称">
                    </div>
                    <div class="form-group">
                        <label>英文职位</label>
                        <input type="text" name="position_en" value="{get('position_en')}" placeholder="英文职位（可选）">
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>手机</label>
                        <input type="text" name="mobile" value="{get('mobile')}" placeholder="手机号码">
                    </div>
                    <div class="form-group">
                        <label>电话</label>
                        <input type="text" name="phone" value="{get('phone')}" placeholder="固定电话">
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

    <div id="photoCameraModal" class="modal-overlay" style="display:none;align-items:center;justify-content:center;">
        <div class="modal" style="max-width:500px;width:90%;">
            <h3>📷 拍照</h3>
            <video id="photoCameraVideo" autoplay playsinline style="width:100%;border-radius:12px;box-shadow:var(--shadow);background:#000;"></video>
            <canvas id="photoCameraCanvas" style="display:none;"></canvas>
            <div style="display:flex;gap:10px;margin-top:12px;">
                <button type="button" class="btn btn-primary" onclick="captureFromModal()">📸 拍摄</button>
                <button type="button" class="btn btn-ghost" onclick="closePhotoCamera()">✕ 取消</button>
            </div>
        </div>
    </div>

    <script>
    let currentPhotoInput = null;
    let photoMediaStream = null;

    function previewCardPhoto(input) {{
        if (input.files && input.files[0]) {{
            const reader = new FileReader();
            reader.onload = function(e) {{
                document.getElementById('cardPhotoPreview').innerHTML = '<img src="' + e.target.result + '" style="max-height:150px;max-width:100%;border-radius:8px;box-shadow:var(--shadow);">';
                document.getElementById('cardPhotoPreview').style.display = 'block';
            }}
            reader.readAsDataURL(input.files[0]);
        }}
    }}

    function previewAvatar(input) {{
        if (input.files && input.files[0]) {{
            const reader = new FileReader();
            reader.onload = function(e) {{
                document.getElementById('avatarPreview').innerHTML = '<img src="' + e.target.result + '" style="max-height:150px;max-width:100%;border-radius:8px;box-shadow:var(--shadow);">';
                document.getElementById('avatarPreview').style.display = 'block';
            }}
            reader.readAsDataURL(input.files[0]);
        }}
    }}

    async function showCardPhotoCamera() {{
        currentPhotoInput = 'cardPhotoInput';
        await showPhotoCamera();
    }}

    async function showAvatarCamera() {{
        currentPhotoInput = 'avatarInput';
        await showPhotoCamera();
    }}

    async function showPhotoCamera() {{
        // 检查浏览器支持
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {{
            showToast('您的浏览器不支持摄像头功能，请使用Chrome、Safari或Edge', 'error');
            return;
        }}

        // 检查是否在安全环境（HTTPS或localhost）
        const isSecure = location.protocol === 'https:' || location.hostname === 'localhost' || location.hostname === '127.0.0.1';
        if (!isSecure) {{
            showToast('摄像头需要HTTPS环境！请使用 start_https.sh 启动服务', 'error');
            return;
        }}

        const video = document.getElementById('photoCameraVideo');
        try {{
            // 先尝试后置摄像头
            try {{
                photoMediaStream = await navigator.mediaDevices.getUserMedia({{
                    video: {{ facingMode: 'environment', width: {{ ideal: 1920 }}, height: {{ ideal: 1080 }} }}
                }});
            }} catch(e) {{
                // 失败则尝试任意摄像头
                photoMediaStream = await navigator.mediaDevices.getUserMedia({{
                    video: {{ width: {{ ideal: 1920 }}, height: {{ ideal: 1080 }} }}
                }});
            }}
            video.srcObject = photoMediaStream;
            document.getElementById('photoCameraModal').style.display = 'flex';
        }} catch(e) {{
            console.error('摄像头错误:', e);
            if (e.name === 'NotAllowedError') {{
                showToast('请允许访问摄像头权限', 'error');
            }} else if (e.name === 'NotFoundError') {{
                showToast('未找到摄像头设备', 'error');
            }} else if (e.name === 'NotReadableError') {{
                showToast('摄像头被其他应用占用', 'error');
            }} else {{
                showToast('无法访问摄像头: ' + e.message + '，请使用上传图片', 'error');
            }}
        }}
    }}

    function closePhotoCamera() {{
        if (photoMediaStream) {{
            photoMediaStream.getTracks().forEach(track => track.stop());
            photoMediaStream = null;
        }}
        document.getElementById('photoCameraModal').style.display = 'none';
    }}

    function captureFromModal() {{
        const video = document.getElementById('photoCameraVideo');
        const canvas = document.getElementById('photoCameraCanvas');
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(video, 0, 0);

        canvas.toBlob(function(blob) {{
            const file = new File([blob], 'photo.jpg', {{ type: 'image/jpeg' }});
            const dataTransfer = new DataTransfer();
            dataTransfer.items.add(file);

            if (currentPhotoInput === 'cardPhotoInput') {{
                document.getElementById('cardPhotoInput').files = dataTransfer.files;
                previewCardPhoto(document.getElementById('cardPhotoInput'));
            }} else {{
                document.getElementById('avatarInput').files = dataTransfer.files;
                previewAvatar(document.getElementById('avatarInput'));
            }}
            closePhotoCamera();
        }}, 'image/jpeg', 0.9);
    }}
    </script>
    """
    return layout(title_text.replace("➕ ", "").replace("✏️ ", ""), content, active_nav="new" if not is_edit else "")


# ── 名片详情页 ────────────────────────────────────────

def render_card_page(
    contact: Contact, card_exists: bool, card_filename: str,
    company_info: dict = None, company_news: list = None,
    knowledge_entries: list = None,
    colleagues_by_dept: list = None, total_colleagues: int = 0,
    org_structure: list = None, contact_name_index: dict = None,
    dept_contacts_map: dict = None
) -> str:
    # ── 基本信息（含双语） ──
    info_rows = []
    # 英文名（有值才显示）
    if getattr(contact, 'name_en', None):
        info_rows.append(f"<div class='form-group'><label>英文姓名</label><p>{contact.name_en}</p></div>")
    for label, field in [("公司", "company"), ("部门", "department"), ("职位", "position"),
                          ("手机", "mobile"), ("电话", "phone"), ("邮箱", "email"),
                          ("地址", "company_address")]:
        val = getattr(contact, field, None)
        val_en = getattr(contact, field + "_en", None)
        if val:
            display = val
            if val_en and val_en.strip().lower() != val.strip().lower():
                display = f"{val} <span style='color:var(--text-muted);font-size:.85rem;'>({val_en})</span>"
            info_rows.append(f"<div class='form-group'><label>{label}</label><p>{display}</p></div>")
        elif val_en:
            info_rows.append(f"<div class='form-group'><label>{label}（英）</label><p>{val_en}</p></div>")
    # 备注
    if contact.notes:
        info_rows.append(f"<div class='form-group'><label>备注</label><p>{contact.notes}</p></div>")

    # ── 名片图片（支持双面） ──
    img_html = ""
    if card_exists:
        img_html = f'<img src="/web/photo/{card_filename}" alt="{contact.name}的名片" style="max-width:100%;border-radius:8px;box-shadow:var(--shadow);margin-bottom:8px;">'
        # 如果存在第二面图片，也显示
        if getattr(contact, 'business_card_path_2', None):
            img_html += f'<img src="/web/photo/{contact.business_card_path_2}" alt="{contact.name}的名片背面" style="max-width:100%;border-radius:8px;box-shadow:var(--shadow);">'
    else:
        img_html = '<div class="empty-state"><div class="icon">🖼️</div><h3>名片生成失败</h3></div>'

    # ── 公司信息区域 ──
    company_section = ""
    if company_info:
        company_news_html = ""
        if company_news:
            news_items = ""
            for n in company_news:
                title = n.get('title', '')
                url = n.get('url', '')
                source = n.get('source', '')
                time_str = n.get('time', '')
                company_name = company_info.get('name', '') if company_info else ''
                # 有真实URL直接跳转，否则生成搜索引擎查询链接
                from urllib.parse import quote
                if url:
                    title_html = f'<a href="{url}" target="_blank" rel="noopener" style="color:var(--primary);text-decoration:none;">📰 {title} 🔗</a>'
                else:
                    search_query = quote(f"{company_name} {title}")
                    search_url = f"https://www.baidu.com/s?wd={search_query}"
                    title_html = f'<a href="{search_url}" target="_blank" rel="noopener" style="color:var(--primary);text-decoration:none;" title="搜索：{company_name} {title}">📰 {title} 🔍</a>'
                # 来源和时间行
                meta_parts = []
                if source:
                    meta_parts.append(f'📢 {source}')
                if time_str:
                    meta_parts.append(f'⏱ {time_str}')
                meta_html = ' · '.join(meta_parts) if meta_parts else ''
                news_items += f"""
                <div style="padding:10px 14px;background:var(--bg);border-radius:8px;margin-bottom:6px;border-left:3px solid var(--primary);">
                    <div style="font-weight:600;font-size:.9rem;margin-bottom:2px;">{title_html}</div>
                    <div style="font-size:.82rem;color:var(--text-muted);line-height:1.5;">{n.get('summary', '')}</div>
                    {f'<div style="font-size:.72rem;color:var(--text-muted);margin-top:4px;">{meta_html}</div>' if meta_html else ''}
                </div>"""
            company_news_html = f"""
            <details open style="margin-top:12px;">
                <summary style="cursor:pointer;font-weight:600;font-size:.95rem;padding:4px 0;">📰 近期热点新闻 ({len(company_news)})</summary>
                <div style="margin-top:8px;">{news_items}</div>
            </details>"""

        # 组织架构
        org_html = ""
        if org_structure:
            org_html = _render_org_chart(org_structure, contact_name_index or {},
                                         company_info.get('name', ''),
                                         dept_contacts=dept_contacts_map)

        perf_html = ""
        if company_info.get("business_performance"):
            perf_html = f"""
            <details style="margin-top:8px;">
                <summary style="cursor:pointer;font-weight:600;font-size:.95rem;padding:4px 0;">📊 经营情况</summary>
                <p style="font-size:.85rem;color:var(--text-muted);line-height:1.6;margin-top:8px;white-space:pre-wrap;">{company_info['business_performance']}</p>
            </details>"""

        company_section = f"""
        <div class="card-detail" style="text-align:left;margin-bottom:16px;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
                <h3 style="margin:0;font-size:1.1rem;">🏢 {company_info['name']}</h3>
                <button class="btn btn-ghost btn-sm" onclick="refreshCompanyInfo('{company_info['name']}')" id="refreshCompanyBtn" title="使用AI重新研究该公司">🔄 刷新研究</button>
            </div>
            <p style="font-size:.85rem;color:var(--text-muted);line-height:1.6;white-space:pre-wrap;">{company_info.get('description', '暂无公司简介')}</p>
            {perf_html}
            {company_news_html}
            {org_html}
            <div id="companyResearchStatus" style="margin-top:8px;"></div>
        </div>"""
    elif contact.company:
        company_section = f"""
        <div class="card-detail" style="text-align:center;margin-bottom:16px;">
            <p style="color:var(--text-muted);margin-bottom:8px;">🏢 {contact.company}</p>
            <button class="btn btn-primary btn-sm" onclick="refreshCompanyInfo('{contact.company}')" id="refreshCompanyBtn">
                🤖 AI 研究该公司
            </button>
            <div id="companyResearchStatus" style="margin-top:8px;"></div>
        </div>"""

    # ── 同公司联系人 ──
    colleagues_section = ""
    if colleagues_by_dept and total_colleagues > 0:
        dept_blocks = ""
        for group in colleagues_by_dept:
            dept_name = group["department"] or "其他部门"
            members = group["contacts"]
            member_items = ""
            for c in members:
                pos = c.position or ""
                mobile = c.mobile or ""
                member_items += f"""
                <a href="/web/card/{c.id}" style="display:flex;align-items:center;gap:8px;padding:8px 10px;background:var(--bg);border-radius:6px;text-decoration:none;color:var(--text);transition:all .15s;"
                   onmouseover="this.style.background='#eff6ff'" onmouseout="this.style.background='var(--bg)'">
                    <span style="font-weight:600;font-size:.85rem;flex:1;">{c.name}</span>
                    {f'<span style="font-size:.75rem;color:var(--text-muted);">💼 {pos}</span>' if pos else ''}
                    {f'<span style="font-size:.75rem;color:var(--text-muted);">📱 {mobile}</span>' if mobile else ''}
                    <span style="color:var(--primary);font-size:.7rem;">查看 →</span>
                </a>"""
            dept_blocks += f"""
            <div style="margin-bottom:12px;">
                <div style="font-size:.8rem;color:var(--text-muted);font-weight:600;margin-bottom:6px;display:flex;align-items:center;gap:6px;">
                    📂 {dept_name}<span style="font-weight:400;">({len(members)}人)</span>
                </div>
                <div style="display:flex;flex-direction:column;gap:4px;">{member_items}</div>
            </div>"""

        colleagues_section = f"""
        <div class="card-detail" style="text-align:left;margin-top:16px;">
            <div style="margin-bottom:12px;">
                <h3 style="margin:0;font-size:1.1rem;">👥 同公司联系人 ({total_colleagues}人)</h3>
            </div>
            {dept_blocks}
        </div>"""

    # ── 随记关联区域 ──
    knowledge_section = ""
    if knowledge_entries:
        # 原始随记列表（可折叠）
        k_items = ""
        for k in knowledge_entries:
            type_icons = {"voice": "🎤", "file": "📄", "photo": "📷", "text": "✏️"}
            icon = type_icons.get(k["entry_type"], "📝")
            k_items += f"""
            <div id="kentry-{k['id']}" style="padding:8px 12px;background:var(--bg);border-radius:6px;margin-bottom:4px;">
                <div style="display:flex;align-items:center;gap:6px;">
                    <span>{icon}</span>
                    <strong style="font-size:.85rem;">{k['title']}</strong>
                    <span style="font-size:.7rem;color:var(--text-muted);margin-left:auto;">{k['created_at']}</span>
                </div>
                <div style="font-size:.78rem;color:var(--text-muted);line-height:1.4;margin-top:2px;">{k['content'][:100]}{'...' if len(k['content']) > 100 else ''}</div>
            </div>"""

        knowledge_section = f"""
        <div class="card-detail" style="text-align:left;margin-top:16px;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
                <h3 style="margin:0;font-size:1.1rem;">📝 相关随记 ({len(knowledge_entries)})</h3>
                <div style="display:flex;gap:6px;">
                    <button class="btn btn-primary btn-sm" onclick="generateKnowledgeSummary({contact.id})" id="genSummaryBtn">🤖 AI 提炼总结</button>
                    <a href="/web/knowledge" class="btn btn-ghost btn-sm">查看全部 →</a>
                </div>
            </div>

            <!-- AI 提炼结果 -->
            <div id="knowledgeSummaryArea" style="display:none;margin-bottom:12px;">
                <div id="knowledgeSummaryContent"></div>
            </div>
            <div id="knowledgeSummaryStatus" style="text-align:center;margin-bottom:8px;"></div>

            <!-- 原始随记列表 -->
            <details style="margin-top:8px;">
                <summary style="cursor:pointer;font-size:.82rem;color:var(--text-muted);padding:4px 0;">展开原始随记列表</summary>
                <div style="margin-top:6px;">{k_items}</div>
            </details>
        </div>"""
    else:
        knowledge_section = """
        <div class="card-detail" style="text-align:center;margin-top:16px;">
            <p style="color:var(--text-muted);">📝 暂无相关随记</p>
            <a href="/web/knowledge" class="btn btn-ghost btn-sm" style="margin-top:4px;">去添加随记</a>
        </div>"""

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

        {company_section}
        {colleagues_section}
        {knowledge_section}
    </div>

    <script>
    function switchOrgView(chartId, view, btn) {{
        document.getElementById(chartId + '_tree').style.display = view === 'tree' ? 'block' : 'none';
        document.getElementById(chartId + '_list').style.display = view === 'list' ? 'block' : 'none';
        document.querySelectorAll('.org-view-btn').forEach(function(b) {{ b.classList.remove('active'); }});
        btn.classList.add('active');
    }}

    async function refreshCompanyInfo(companyName) {{
        var btn = document.getElementById('refreshCompanyBtn');
        var status = document.getElementById('companyResearchStatus');
        if (btn) {{ btn.disabled = true; btn.textContent = '⏳ 研究中...'; }}
        if (status) status.innerHTML = '<span style="color:var(--text-muted);">🤖 AI正在研究 ' + companyName + '...</span>';

        try {{
            var resp = await fetch('/web/api/company/research', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{company_name: companyName}})
            }});
            var data = await resp.json();
            if (data.error) {{
                if (status) status.innerHTML = '<span style="color:var(--danger);">❌ ' + data.error + '</span>';
            }} else if (data.is_known) {{
                if (status) status.innerHTML = '<span style="color:var(--success);">✅ 研究完成，正在刷新...</span>';
                setTimeout(function() {{ location.reload(); }}, 800);
            }} else {{
                if (status) status.innerHTML = '<span style="color:var(--warning);">⚠️ AI对该公司的了解有限</span>';
            }}
        }} catch(e) {{
            if (status) status.innerHTML = '<span style="color:var(--danger);">网络错误</span>';
        }} finally {{
            if (btn) {{ btn.disabled = false; btn.textContent = '🔄 刷新研究'; }}
        }}
    }}

    async function generateKnowledgeSummary(contactId) {{
        var btn = document.getElementById('genSummaryBtn');
        var status = document.getElementById('knowledgeSummaryStatus');
        var area = document.getElementById('knowledgeSummaryArea');
        var content = document.getElementById('knowledgeSummaryContent');

        if (btn) {{ btn.disabled = true; btn.textContent = '⏳ 提炼中...'; }}
        if (status) status.innerHTML = '<span style="color:var(--text-muted);">🤖 AI正在分析随记内容...</span>';

        try {{
            var resp = await fetch('/web/api/contacts/' + contactId + '/knowledge/summary', {{
                method: 'POST'
            }});
            var data = await resp.json();
            if (data.error) {{
                if (status) status.innerHTML = '<span style="color:var(--danger);">❌ ' + data.error + '</span>';
                if (btn) {{ btn.disabled = false; btn.textContent = '🤖 AI 提炼总结'; }}
                return;
            }}

            var html = '';
            if (data.summary) {{
                html += '<div style="background:linear-gradient(135deg,#eff6ff,#f0f9ff);border:1px solid #bae6fd;border-radius:10px;padding:14px;margin-bottom:12px;">';
                html += '<div style="font-weight:600;font-size:.9rem;margin-bottom:6px;">📋 综合总结</div>';
                html += '<p style="font-size:.85rem;color:var(--text);line-height:1.6;margin:0;">' + data.summary + '</p>';
                html += '</div>';
            }}

            if (data.key_points && data.key_points.length) {{
                html += '<div style="font-weight:600;font-size:.9rem;margin-bottom:8px;">🔑 关键信息点</div>';
                html += '<div style="display:flex;flex-direction:column;gap:8px;">';
                for (var i = 0; i < data.key_points.length; i++) {{
                    var kp = data.key_points[i];
                    var sourceLinks = '';
                    if (kp.source_entry_ids && kp.source_entry_ids.length) {{
                        var links = [];
                        for (var j = 0; j < kp.source_entry_ids.length; j++) {{
                            var eid = kp.source_entry_ids[j];
                            links.push('<a href="javascript:void(0)" onclick="var d=document.querySelector(\\'details summary\\');if(d)d.click();var el=document.getElementById(\\'kentry-\\'+' + eid + ');if(el){{el.scrollIntoView({{behavior:\\'smooth\\'}});el.style.background=\\'#fef3c7\\';}}" style="color:var(--primary);font-size:.72rem;">📝随记#' + eid + '</a>');
                        }}
                        sourceLinks = ' <span style="font-size:.7rem;color:var(--text-muted);">来源：' + links.join(' ') + '</span>';
                    }}
                    var timeBadge = kp.time_context ? '<span style="font-size:.7rem;background:var(--border);padding:1px 6px;border-radius:3px;margin-right:4px;">' + kp.time_context + '</span>' : '';
                    html += '<div style="padding:10px 12px;background:var(--bg);border-radius:8px;border-left:3px solid var(--success);">';
                    html += '<div style="display:flex;align-items:flex-start;gap:6px;">';
                    html += '<span style="color:var(--success);font-weight:bold;flex-shrink:0;">' + (i + 1) + '.</span>';
                    html += '<div style="flex:1;"><span style="font-size:.85rem;line-height:1.5;">' + kp.point + '</span>';
                    html += '<div style="margin-top:4px;">' + timeBadge + sourceLinks + '</div></div>';
                    html += '</div></div>';
                }}
                html += '</div>';
            }}

            if (data.topic_tags && data.topic_tags.length) {{
                html += '<div style="margin-top:10px;display:flex;flex-wrap:wrap;gap:4px;">';
                for (var t = 0; t < data.topic_tags.length; t++) {{
                    html += '<span style="background:var(--primary);color:#fff;padding:2px 8px;border-radius:10px;font-size:.7rem;">' + data.topic_tags[t] + '</span>';
                }}
                html += '</div>';
            }}

            content.innerHTML = html;
            area.style.display = 'block';
            if (status) status.innerHTML = '<span style="color:var(--success);">✅ 提炼完成</span>';
            setTimeout(function() {{ if (status) status.innerHTML = ''; }}, 3000);
        }} catch(e) {{
            if (status) status.innerHTML = '<span style="color:var(--danger);">网络错误: ' + e.message + '</span>';
        }} finally {{
            if (btn) {{ btn.disabled = false; btn.textContent = '🔄 重新提炼'; }}
        }}
    }}
    </script>
    """
    return layout(f"{contact.name}的名片", content)


def _render_org_chart(org_data: list, contact_index: dict, company_name: str,
                      dept_contacts: dict = None) -> str:
    """
    渲染组织架构，支持列表和树状图切换。
    AI提供层级结构，数据库提供权威部门名称和人员归属。
    dept_contacts: {部门名: [{"id":1,"name":"张三","position":"工程师"}, ...]}
    """
    import random, re as _re
    chart_id = f"orgchart_{random.randint(10000, 99999)}"
    dept_contacts = dept_contacts or {}

    # ── 部门名匹配：数据库部门 → AI节点 ──
    def _dept_similarity(db_dept: str, ai_name: str) -> float:
        """计算数据库部门名与AI节点名的相似度(0-1)"""
        if db_dept == ai_name:
            return 1.0
        if db_dept in ai_name or ai_name in db_dept:
            return 0.8
        # 去掉"部""中心""组"等后缀再匹配
        for suffix in ["部", "中心", "组", "处", "室", "办"]:
            a = db_dept.rstrip(suffix)
            b = ai_name.rstrip(suffix)
            if a and b and (a in b or b in a):
                return 0.6
        return 0.0

    def _find_best_dept(ai_name: str, available_depts: set) -> tuple:
        """为AI节点找到最匹配的数据库部门"""
        best_dept, best_score = None, 0
        for dept in available_depts:
            score = _dept_similarity(dept, ai_name)
            if score > best_score:
                best_score, best_dept = score, dept
        return best_dept, best_score

    # ── 预处理：为每个AI节点匹配数据库部门，构建增强树 ──
    used_depts = set()

    def _enrich_node(node: dict) -> dict:
        """用数据库数据增强AI节点"""
        ai_name = node.get("name", "")
        ai_role = node.get("role", "")
        children = [_enrich_node(c) for c in node.get("children", [])]

        # 找最匹配的数据库部门
        available = set(dept_contacts.keys()) - used_depts
        best_dept, score = _find_best_dept(ai_name, available)

        enriched = dict(node)  # 不修改原始数据
        enriched["children"] = children
        enriched["db_dept"] = None
        enriched["db_contacts"] = []

        if best_dept and score >= 0.5:
            enriched["db_dept"] = best_dept
            enriched["display_name"] = best_dept  # 用数据库部门名覆盖AI名
            enriched["db_contacts"] = dept_contacts.get(best_dept, [])
            used_depts.add(best_dept)
        else:
            enriched["display_name"] = ai_name

        return enriched

    enriched_org = [_enrich_node(n) for n in org_data]

    # 数据库中有但AI未覆盖的部门，尝试插入到已有节点的子层级
    remaining_depts = set(dept_contacts.keys()) - used_depts
    def _find_parent_in_tree(nodes: list, dept_name: str) -> bool:
        """递归在树中为剩余部门寻找合适父节点插入"""
        for node in nodes:
            ai_name = node.get("name", "")
            score = _dept_similarity(dept_name, ai_name)
            if score >= 0.3:  # 有一定关联就插入
                node.setdefault("children", []).append({
                    "name": dept, "role": "", "children": [],
                    "db_dept": dept, "display_name": dept,
                    "db_contacts": dept_contacts[dept]
                })
                return True
            if node.get("children") and _find_parent_in_tree(node["children"], dept_name):
                return True
        return False

    for dept in sorted(remaining_depts):
        if not _find_parent_in_tree(enriched_org, dept):
            # 实在找不到父节点，才追加到顶层
            enriched_org.append({
                "name": dept, "role": "", "children": [],
                "db_dept": dept, "display_name": dept,
                "db_contacts": dept_contacts[dept]
            })

    # ── 渲染辅助 ──
    def _badges(contacts: list) -> str:
        if not contacts:
            return ""
        b = ""
        for mc in contacts[:8]:
            pos = mc.get("position", "")
            b += f"""<a href="/web/card/{mc['id']}" class="org-badge" title="{pos}">👤 {mc['name']}</a>"""
        return f""" <span class="org-badges">{b}</span>"""

    def _list_node(node: dict, depth: int = 0) -> str:
        name = node.get("display_name", node.get("name", ""))
        role = node.get("role", "")
        children = node.get("children", [])
        contacts = node.get("db_contacts", [])
        indent = 12 * depth
        has_children = len(children) > 0
        node_id = f"{chart_id}_list_{abs(hash(name + str(depth)))}"

        html = f"""<div style="margin-left:{indent}px;padding:3px 0;">"""
        if has_children:
            html += f"""<span onclick="var e=document.getElementById('{node_id}');if(e){{e.style.display=e.style.display==='none'?'block':'none';this.textContent=this.textContent==='▶'?'▼':'▶';}}" style="cursor:pointer;color:var(--text-muted);user-select:none;">▶</span> """
        else:
            html += f"""<span style="color:var(--border);">•</span> """
        # 数据库修正过的不显示AI角色描述
        db_dept = node.get("db_dept")
        display_role = role if not db_dept else ""
        html += f"""<span class="org-name-list">{name}</span>"""
        if display_role:
            html += f""" <span class="org-role">{display_role}</span>"""
        html += _badges(contacts)
        html += "</div>"
        if has_children:
            html += f"""<div id="{node_id}">"""
            for child in children:
                html += _list_node(child, depth + 1)
            html += "</div>"
        return html

    def _tree_node(node: dict) -> str:
        name = node.get("display_name", node.get("name", ""))
        role = node.get("role", "")
        children = node.get("children", [])
        contacts = node.get("db_contacts", [])
        db_dept = node.get("db_dept")
        display_role = role if not db_dept else ""

        card = "<div class=\"v-node-card\">"
        card += f"""<div class="v-node-name">{name}</div>"""
        if display_role:
            card += f"""<div class="v-node-role">{display_role}</div>"""
        badges = _badges(contacts)
        if badges:
            card += f"""<div class="v-node-badges">{badges}</div>"""
        card += "</div>"

        if children:
            children_cards = "".join(_tree_node(c) for c in children)
            return f"""
            <div class="v-node-wrap">
                {card}
                <div class="v-conn-down"></div>
                <div class="v-children-row">
                    {children_cards}
                </div>
            </div>"""
        else:
            return f"""<div class="v-node-wrap v-leaf">{card}</div>"""

    if not enriched_org:
        return ""

    list_html = "".join(_list_node(n) for n in enriched_org)
    top_cards = "".join(_tree_node(n) for n in enriched_org)
    tree_html = f"""<div class="org-v-tree"><div class="v-children-row v-root-row">{top_cards}</div></div>"""

    return f"""
    <style>
    .org-view-btn {{
        padding:5px 14px;border:1px solid var(--border);border-radius:6px;
        background:var(--card-bg);cursor:pointer;font-size:.8rem;color:var(--text-muted);
        transition:all .15s;
    }}
    .org-view-btn:hover {{ border-color:var(--primary);color:var(--primary); }}
    .org-view-btn.active {{ background:var(--primary);color:#fff;border-color:var(--primary); }}

    .org-v-tree {{
        display:flex;flex-direction:column;align-items:center;
        padding:16px 8px;overflow-x:auto;
    }}
    .v-root-row {{
        justify-content:center;
    }}
    .v-children-row {{
        display:flex;justify-content:center;align-items:flex-start;
        gap:0;position:relative;padding-top:28px;
    }}
    .v-children-row::before {{
        content:'';position:absolute;top:0;left:0;right:0;height:0;
        border-top:1.5px solid #cbd5e1;
    }}
    .v-node-wrap {{
        display:flex;flex-direction:column;align-items:center;
        position:relative;padding:0 8px;
    }}
    .v-node-wrap::before {{
        content:'';position:absolute;top:0;left:50%;
        width:0;height:28px;border-left:1.5px solid #cbd5e1;
    }}
    .v-leaf::before {{ display:none; }}
    .v-node-wrap:first-child::before {{
        left:50%;
    }}
    .v-root-row > .v-node-wrap::before {{
        display:none;
    }}
    .v-conn-down {{
        width:0;height:28px;border-left:1.5px solid #cbd5e1;
        flex-shrink:0;
    }}

    .v-node-card {{
        min-width:80px;max-width:200px;
        padding:10px 14px;background:var(--card-bg);
        border:1.5px solid var(--border);border-radius:10px;
        box-shadow:0 1px 3px rgba(0,0,0,.06);
        text-align:center;transition:all .15s;
    }}
    .v-node-card:hover {{
        border-color:var(--primary);box-shadow:0 2px 8px rgba(37,99,235,.12);
    }}
    .v-node-name {{
        font-size:.85rem;font-weight:700;color:var(--text);line-height:1.3;
    }}
    .v-node-role {{
        font-size:.72rem;color:var(--text-muted);margin-top:2px;
    }}
    .v-node-badges {{
        margin-top:4px;display:flex;flex-wrap:wrap;gap:2px;justify-content:center;
    }}

    .org-name-list {{ font-size:.85rem;font-weight:600; }}
    .org-role {{ font-size:.75rem;color:var(--text-muted); }}
    .org-badges {{ margin-left:4px;display:inline-flex;flex-wrap:wrap;gap:2px; }}
    .org-badge {{
        display:inline-block;background:#dbeafe;color:#1e40af;padding:1px 8px;
        border-radius:10px;font-size:.7rem;text-decoration:none;
        transition:all .15s;
    }}
    .org-badge:hover {{ background:#bfdbfe;transform:scale(1.05); }}

    @media (max-width:640px) {{
        .v-node-card {{ min-width:70px;max-width:150px;padding:8px 10px; }}
        .v-node-name {{ font-size:.78rem; }}
    }}
    </style>
    <details open style="margin-top:12px;">
        <summary style="cursor:pointer;font-weight:600;font-size:.95rem;padding:4px 0;">
            🏛 组织架构（AI结构 + 数据库实际人员）
        </summary>
        <div style="margin-top:8px;">
            <div style="display:flex;gap:6px;margin-bottom:8px;">
                <button class="org-view-btn active" onclick="switchOrgView('{chart_id}','tree',this)" id="{chart_id}_btn_tree">🌳 树状图</button>
                <button class="org-view-btn" onclick="switchOrgView('{chart_id}','list',this)" id="{chart_id}_btn_list">📋 列表</button>
            </div>
            <div id="{chart_id}_tree" class="org-view-panel" style="display:block;overflow-x:auto;-webkit-overflow-scrolling:touch;padding:4px;">
                {tree_html}
            </div>
            <div id="{chart_id}_list" class="org-view-panel" style="display:none;overflow-x:auto;">
                {list_html}
            </div>
        </div>
        <div style="font-size:.72rem;color:var(--text-muted);margin-top:4px;">👤 蓝色标签=已有联系人 · 部门名基于数据库实际数据修正</div>
    </details>"""


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

    step_label = "第1步：拍摄/上传名片正面（中文面）"
    content = f"""
    <div class="form-page">
        <div class="form-card">
            <h2>📷 拍照录入名片</h2>
            <p style="color:var(--text-muted);margin-bottom:4px;" id="stepLabel">{step_label}</p>
            <p style="color:var(--text-muted);font-size:.8rem;margin-bottom:20px;" id="stepHint">中英文双面名片可拍两次，自动合并为同一人信息</p>

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
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                    <span style="font-weight:600;">📷 相机预览</span>
                    <div style="display:flex;gap:8px;">
                        <button class="btn btn-ghost btn-sm" onclick="switchCamera()" id="switchCamBtn">🔄 切换摄像头</button>
                        <button class="btn btn-ghost btn-sm" onclick="toggleRotation()">↻ 旋转画面</button>
                    </div>
                </div>
                <div style="position:relative;width:100%;overflow:hidden;border-radius:12px;box-shadow:var(--shadow);background:#000;">
                    <video id="cameraVideo" autoplay playsinline style="width:100%;"></video>
                </div>
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
                <p style="color:var(--text-muted);margin-top:8px;" id="ocrProgressText">AI 正在识别名片信息...</p>
            </div>

            <!-- 合并表单区域 -->
            <div id="ocrResult" style="display:none;"></div>

            <!-- 第二次拍照提示 -->
            <div id="secondRoundHint" style="display:none;text-align:center;padding:16px;background:#f0fdf4;border-radius:8px;margin-bottom:20px;">
                <span style="font-weight:600;color:#166534;">✅ 正面已识别成功</span>
                <p style="color:#166534;margin:4px 0;font-size:.9rem;">如果名片有英文/背面，请继续拍摄第二面，系统将自动合并为同一人信息</p>
            </div>
        </div>
    </div>

    <style>
    @keyframes spin {{ from {{ transform: rotate(0deg); }} to {{ transform: rotate(360deg); }} }}
    #uploadArea:hover {{ border-color: var(--primary); background: #eff6ff; }}
    #uploadArea.dragover {{ border-color: var(--primary); background: #eff6ff; }}
    .ocr-side-badge {{ display:inline-block;padding:2px 8px;border-radius:4px;font-size:.75rem;font-weight:600;margin-bottom:8px; }}
    .badge-front {{ background:#eff6ff;color:#1d4ed8; }}
    .badge-back {{ background:#fef3c7;color:#92400e; }}
    </style>

    <script>
    let selectedFile = null;
    let mediaStream = null;
    let rotation = 0;
    let currentFacingMode = 'environment';
    let firstResult = null;   // 第一面（正面/中文）
    let secondResult = null;  // 第二面（背面/英文）
    let firstCardPhoto = null;
    let secondCardPhoto = null;

    function showFileSelect() {{
        document.getElementById('choiceButtons').style.display = 'none';
        document.getElementById('uploadArea').style.display = 'block';
    }}

    async function startCamera(facingMode) {{
        if (!facingMode) facingMode = currentFacingMode;
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {{
            showToast('您的浏览器不支持摄像头功能，请使用Chrome、Safari或Edge', 'error');
            return;
        }}
        const isSecure = location.protocol === 'https:' || location.hostname === 'localhost' || location.hostname === '127.0.0.1';
        if (!isSecure) {{
            showToast('摄像头需要HTTPS环境！请使用 start_https.sh 启动服务', 'error');
            return;
        }}
        if (mediaStream) {{
            mediaStream.getTracks().forEach(track => track.stop());
            mediaStream = null;
        }}
        try {{
            const video = document.getElementById('cameraVideo');
            mediaStream = await navigator.mediaDevices.getUserMedia({{
                video: {{ facingMode: facingMode, width: {{ ideal: 1920 }}, height: {{ ideal: 1080 }} }}
            }});
            currentFacingMode = facingMode;
            video.srcObject = mediaStream;
            document.getElementById('choiceButtons').style.display = 'none';
            document.getElementById('cameraArea').style.display = 'block';
        }} catch(e) {{
            if (facingMode !== undefined) {{
                try {{
                    const video = document.getElementById('cameraVideo');
                    mediaStream = await navigator.mediaDevices.getUserMedia({{
                        video: {{ width: {{ ideal: 1920 }}, height: {{ ideal: 1080 }} }}
                    }});
                    currentFacingMode = 'unknown';
                    video.srcObject = mediaStream;
                    document.getElementById('choiceButtons').style.display = 'none';
                    document.getElementById('cameraArea').style.display = 'block';
                    return;
                }} catch(e2) {{}}
            }}
            let msg = '无法访问摄像头';
            if (e.name === 'NotAllowedError') msg = '请允许访问摄像头权限';
            else if (e.name === 'NotFoundError') msg = '未找到摄像头设备';
            else if (e.name === 'NotReadableError') msg = '摄像头被其他应用占用';
            showToast(msg + '，请使用「选择图片」', 'error');
        }}
    }}

    async function switchCamera() {{
        const newMode = currentFacingMode === 'environment' ? 'user' : 'environment';
        await startCamera(newMode);
    }}

    function stopCamera() {{
        if (mediaStream) {{
            mediaStream.getTracks().forEach(track => track.stop());
            mediaStream = null;
        }}
        rotation = 0;
        const video = document.getElementById('cameraVideo');
        video.style.transform = '';
        document.getElementById('cameraArea').style.display = 'none';
        if (!firstResult) {{
            document.getElementById('choiceButtons').style.display = 'flex';
        }} else {{
            // 第二面取消后回到合并表单
            renderMergedForm();
        }}
    }}

    function toggleRotation() {{
        rotation = (rotation + 90) % 360;
        document.getElementById('cameraVideo').style.transform = 'rotate(' + rotation + 'deg)';
    }}

    function capturePhoto() {{
        const video = document.getElementById('cameraVideo');
        const canvas = document.getElementById('cameraCanvas');
        const ctx = canvas.getContext('2d');
        if (rotation === 90 || rotation === 270) {{
            canvas.width = video.videoHeight;
            canvas.height = video.videoWidth;
        }} else {{
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
        }}
        ctx.save();
        ctx.translate(canvas.width / 2, canvas.height / 2);
        ctx.rotate(rotation * Math.PI / 180);
        ctx.drawImage(video, -video.videoWidth / 2, -video.videoHeight / 2);
        ctx.restore();
        canvas.toBlob(function(blob) {{
            selectedFile = new File([blob], 'photo.jpg', {{ type: 'image/jpeg' }});
            document.getElementById('previewImage').src = canvas.toDataURL('image/jpeg');
            stopCamera();
            document.getElementById('cameraArea').style.display = 'none';
            document.getElementById('previewArea').style.display = 'block';
            document.getElementById('ocrResult').style.display = 'none';
        }}, 'image/jpeg', 0.9);
    }}

    function handleDragOver(e) {{ e.preventDefault(); document.getElementById('uploadArea').classList.add('dragover'); }}
    function handleDragLeave(e) {{ document.getElementById('uploadArea').classList.remove('dragover'); }}
    function handleDrop(e) {{
        e.preventDefault();
        document.getElementById('uploadArea').classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) processFile(e.dataTransfer.files[0]);
    }}
    function handleFileSelect(e) {{ if (e.target.files.length > 0) processFile(e.target.files[0]); }}
    function processFile(file) {{
        if (!file.type.startsWith('image/')) {{ showToast('请选择图片文件', 'error'); return; }}
        selectedFile = file;
        const reader = new FileReader();
        reader.onload = (e) => {{
            document.getElementById('previewImage').src = e.target.result;
            document.getElementById('uploadArea').style.display = 'none';
            document.getElementById('previewArea').style.display = 'block';
            document.getElementById('ocrResult').style.display = 'none';
        }};
        reader.readAsDataURL(file);
    }}

    function resetUpload() {{
        selectedFile = null;
        firstResult = null;
        secondResult = null;
        firstCardPhoto = null;
        secondCardPhoto = null;
        document.getElementById('fileInput').value = '';
        document.getElementById('uploadArea').style.display = 'none';
        document.getElementById('previewArea').style.display = 'none';
        document.getElementById('ocrResult').style.display = 'none';
        document.getElementById('ocrProgress').style.display = 'none';
        document.getElementById('cameraArea').style.display = 'none';
        document.getElementById('secondRoundHint').style.display = 'none';
        document.getElementById('choiceButtons').style.display = 'flex';
        document.getElementById('stepLabel').textContent = '{step_label}';
    }}

    async function startOCR() {{
        if (!selectedFile) return;
        document.getElementById('ocrBtn').disabled = true;
        document.getElementById('ocrProgress').style.display = 'block';
        const isSecondRound = firstResult !== null;
        document.getElementById('ocrProgressText').textContent = isSecondRound ? 'AI 正在识别背面/英文面...' : 'AI 正在识别名片信息...';
        const formData = new FormData();
        formData.append('file', selectedFile);
        try {{
            const resp = await fetch('/web/api/ocr', {{ method: 'POST', body: formData }});
            const data = await resp.json();
            document.getElementById('ocrProgress').style.display = 'none';
            if (data.error) {{
                showToast(data.error, 'error');
                document.getElementById('ocrBtn').disabled = false;
                return;
            }}
            if (!isSecondRound) {{
                // 第一面结果
                firstResult = data;
                firstCardPhoto = data.card_photo || null;
                showSecondRoundOption();
            }} else {{
                // 第二面结果
                secondResult = data;
                secondCardPhoto = data.card_photo || null;
                renderMergedForm();
            }}
        }} catch(e) {{
            document.getElementById('ocrProgress').style.display = 'none';
            showToast('识别请求失败', 'error');
            document.getElementById('ocrBtn').disabled = false;
        }}
    }}

    function showSecondRoundOption() {{
        // 显示第一面结果摘要 + 添加背面按钮
        const data = firstResult;
        const fields = [
            ['name', '姓名'], ['company', '公司'], ['department', '部门'],
            ['position', '职位'], ['mobile', '手机'], ['phone', '电话'],
            ['email', '邮箱'], ['company_address', '地址']
        ];
        let html = '<h3 style="margin-bottom:8px;">✅ 正面识别成功</h3>';
        html += '<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;font-size:.9rem;margin-bottom:16px;">';
        for (const [key, label] of fields) {{
            if (data[key]) {{
                html += '<div><span style="color:var(--text-muted);">' + label + '：</span>' + escapeHtml(data[key]) + '</div>';
            }}
        }}
        html += '</div>';
        html += '<p style="color:var(--text-muted);font-size:.85rem;margin-bottom:12px;">📌 如果名片有英文/背面，请继续拍摄第二面，信息将自动合并</p>';
        html += '<div style="display:flex;gap:10px;flex-wrap:wrap;">';
        html += '<button class="btn btn-primary" onclick="startSecondRound()">📷 拍摄背面/英文面</button>';
        html += '<button class="btn btn-ghost" onclick="renderMergedForm()">跳过，直接保存</button>';
        html += '<button class="btn btn-ghost" onclick="resetUpload()">重新录入</button>';
        html += '</div>';
        document.getElementById('ocrResult').innerHTML = html;
        document.getElementById('ocrResult').style.display = 'block';
        document.getElementById('previewArea').style.display = 'none';
        document.getElementById('secondRoundHint').style.display = 'block';
        document.getElementById('stepLabel').textContent = '第2步：拍摄名片背面/英文面';
        selectedFile = null;
    }}

    function startSecondRound() {{
        document.getElementById('ocrResult').style.display = 'none';
        document.getElementById('secondRoundHint').style.display = 'none';
        document.getElementById('choiceButtons').style.display = 'flex';
        document.getElementById('stepLabel').textContent = '第2步：拍摄名片背面/英文面';
    }}

    function renderMergedForm() {{
        // 合并两面结果：正面数据为主，背面不同内容填入 _en 字段
        const f = firstResult || {{}};
        const s = secondResult || {{}};

        // 判断第二面是否与第一面不同（不同 → 填入英文字段）
        function isDifferent(key) {{
            const fv = (f[key] || '').trim().toLowerCase();
            const sv = (s[key] || '').trim().toLowerCase();
            return sv && sv !== fv;
        }}

        let photoHidden = '';
        if (firstCardPhoto) photoHidden += '<input type="hidden" name="card_photo_filename" value="' + escapeHtml(firstCardPhoto) + '">';
        if (secondCardPhoto) photoHidden += '<input type="hidden" name="card_photo_filename_2" value="' + escapeHtml(secondCardPhoto) + '">';

        let html = '<form action="/web/save" method="post" enctype="multipart/form-data">';
        html += photoHidden;

        // 提示当前合并状态
        if (secondResult) {{
            html += '<div style="display:flex;align-items:center;gap:8px;margin-bottom:16px;"><span class="ocr-side-badge badge-front">正面</span><span class="ocr-side-badge badge-back">背面</span><span style="font-size:.85rem;color:var(--text-muted);">两面信息已合并，请确认后保存</span></div>';
        }}

        // 双列表格：中文 | 英文
        html += '<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">';
        const fieldPairs = [
            ['name', '姓名'], ['name_en', '英文姓名'],
            ['company', '公司'], ['company_en', '英文公司'],
            ['department', '部门'], ['department_en', '英文部门'],
            ['position', '职位'], ['position_en', '英文职位'],
            ['mobile', '手机', true], ['phone', '电话', true],
            ['email', '邮箱', true], ['company_address', '地址', true],
        ];

        for (const item of fieldPairs) {{
            const key = item[0];
            const label = item[1];
            const isSingle = item[2];
            if (isSingle) {{
                // 单列字段（手机/电话/邮箱/地址只在正面出现）
                html += '<div class="form-group"><label>' + label + '</label><input type="text" name="' + key + '" value="' + escapeHtml(f[key] || '') + '"></div>';
            }} else if (key.endsWith('_en')) {{
                // 英文字段默认填第二面数据
                const baseKey = key.replace('_en', '');
                const enVal = (s[baseKey] || '');
                const cnVal = (f[baseKey] || '');
                // 如果第二面和第一面内容相同（如都是数字），不重复填入
                const isSame = enVal.trim().toLowerCase() === cnVal.trim().toLowerCase();
                const val = (enVal && !isSame) ? enVal : '';
                html += '<div class="form-group" style="background:#fffbeb;border-radius:6px;padding:4px 8px;"><label style="color:#92400e;">' + label + '</label><input type="text" name="' + key + '" value="' + escapeHtml(val) + '" placeholder="自动识别英文信息"></div>';
            }} else {{
                // 中文字段默认填第一面数据
                html += '<div class="form-group"><label>' + label + '</label><input type="text" name="' + key + '" value="' + escapeHtml(f[key] || '') + '"></div>';
            }}
        }}
        html += '</div>';

        // 备注
        let notes = f.notes || '';
        html += '<div class="form-group"><label>备注</label><textarea name="notes" rows="2">' + escapeHtml(notes) + '</textarea></div>';

        html += '<div class="form-actions"><button type="submit" class="btn btn-primary">💾 确认保存</button><button type="button" class="btn btn-ghost" onclick="resetUpload()">重新录入</button></div>';
        html += '</form>';

        document.getElementById('ocrResult').innerHTML = html;
        document.getElementById('ocrResult').style.display = 'block';
        document.getElementById('previewArea').style.display = 'none';
        document.getElementById('secondRoundHint').style.display = 'none';
        document.getElementById('stepLabel').textContent = '确认信息并保存';
        document.getElementById('ocrBtn').disabled = false;
    }}

    function escapeHtml(s) {{ return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }}
    </script>
    """
    return layout("拍照录入", content)


# ── 随记知识库页面 ──────────────────────────────────

def render_knowledge_page(entries: list, stats: dict, contacts: list) -> str:
    """渲染知识库主页"""
    entry_cards = ""
    for e in entries:
        type_icons = {"voice": "🎤", "file": "📄", "photo": "📷", "text": "✏️"}
        icon = type_icons.get(e.entry_type, "📝")
        date_str = e.created_at.strftime("%Y-%m-%d %H:%M") if e.created_at else ""
        linked_names = []
        if hasattr(e, '_linked_contacts'):
            linked_names = [c.name for c in e._linked_contacts]
        linked_str = ", ".join(linked_names[:3])
        if len(linked_names) > 3:
            linked_str += f" 等{len(linked_names)}人"

        entry_cards += f"""
        <div class="contact-card" style="flex-direction:column;align-items:flex-start;gap:8px;">
            <div style="display:flex;justify-content:space-between;width:100%;align-items:flex-start;">
                <div style="flex:1;">
                    <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;">
                        <span style="font-size:1.2rem;">{icon}</span>
                        <strong style="font-size:1rem;">{e.title}</strong>
                        <span style="background:var(--border);color:var(--text-muted);padding:1px 6px;border-radius:4px;font-size:.7rem;">{e.entry_type}</span>
                    </div>
                    <div style="font-size:.85rem;color:var(--text-muted);line-height:1.5;max-height:60px;overflow:hidden;">
                        {e.content[:150]}{'...' if len(e.content) > 150 else ''}
                    </div>
                </div>
                <div style="display:flex;gap:4px;flex-shrink:0;">
                    <button class="btn btn-ghost btn-sm" onclick="editKnowledge({e.id})">✏️</button>
                    <button class="btn btn-danger btn-sm" onclick="confirmDeleteKnowledge({e.id}, '{e.title}')">🗑️</button>
                </div>
            </div>
            <div style="display:flex;justify-content:space-between;width:100%;font-size:.75rem;color:var(--text-muted);">
                <span>{date_str}</span>
                {f'<span>👤 {linked_str}</span>' if linked_str else '<span></span>'}
            </div>
        </div>"""

    empty_html = ""
    if not entries:
        empty_html = """<div class="empty-state">
            <div class="icon">📝</div>
            <h3>还没有随记</h3>
            <p>点击右下角 + 按钮，开始记录你的知识</p>
        </div>"""

    # 联系人选项（用于关联）
    contact_options = "".join(f'<option value="{c["id"]}">{c["name"]}</option>' for c in contacts)

    content = f"""
    <div class="stats">
        <div class="stat-card"><div class="num">{stats['total']}</div><div class="label">📝 随记总数</div></div>
        <div class="stat-card"><div class="num">{stats.get('voice', 0)}</div><div class="label">🎤 语音</div></div>
        <div class="stat-card"><div class="num">{stats.get('file', 0)}</div><div class="label">📄 文件</div></div>
        <div class="stat-card"><div class="num">{stats.get('photo', 0)}</div><div class="label">📷 照片</div></div>
        <div class="stat-card"><div class="num">{stats.get('text', 0)}</div><div class="label">✏️ 文字</div></div>
    </div>

    <div class="search-bar">
        <input type="text" id="knowledgeSearch" placeholder="🔍 搜索随记内容..."
               oninput="filterKnowledge()" autofocus>
        <select id="typeFilter" onchange="filterKnowledge()" style="padding:10px 14px;border:2px solid var(--border);border-radius:10px;font-size:.95rem;">
            <option value="">全部类型</option>
            <option value="voice">🎤 语音</option>
            <option value="file">📄 文件</option>
            <option value="photo">📷 照片</option>
            <option value="text">✏️ 文字</option>
        </select>
    </div>

    <div class="contact-grid" id="knowledgeList">
        {entry_cards}
    </div>
    {empty_html}
    <div class="pagination" id="knowledgePage"></div>

    <!-- 浮动添加按钮 -->
    <button onclick="showQuickAdd()" style="position:fixed;bottom:24px;right:24px;width:56px;height:56px;
        border-radius:50%;background:var(--primary);color:#fff;border:none;font-size:1.8rem;
        box-shadow:0 4px 15px rgba(37,99,235,.4);cursor:pointer;z-index:200;transition:all .2s;"
        title="快速录入">&plus;</button>

    <!-- 快速录入面板 -->
    <div id="quickAddModal" class="modal-overlay" style="display:none;align-items:flex-end;justify-content:center;z-index:500;">
        <div class="modal" style="max-width:540px;width:95%;padding:24px;text-align:left;border-radius:16px 16px 0 0;margin-bottom:0;max-height:85vh;overflow-y:auto;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
                <h3 style="margin:0;">📝 快速录入</h3>
                <button onclick="closeQuickAdd()" style="background:transparent;border:none;font-size:1.5rem;cursor:pointer;">×</button>
            </div>

            <!-- Tab切换 -->
            <div style="display:flex;gap:4px;margin-bottom:16px;border-bottom:2px solid var(--border);">
                <button class="quick-tab active" onclick="switchTab('voice')" id="tab-voice">🎤 语音</button>
                <button class="quick-tab" onclick="switchTab('file')" id="tab-file">📄 文件</button>
                <button class="quick-tab" onclick="switchTab('photo')" id="tab-photo">📷 照片</button>
                <button class="quick-tab" onclick="switchTab('text')" id="tab-text">✏️ 文字</button>
            </div>

            <!-- 语音录入 -->
            <div id="panel-voice" class="quick-panel">
                <p style="color:var(--text-muted);margin-bottom:12px;">点击按钮开始录音，说话内容将自动转为文字</p>
                <div style="text-align:center;margin-bottom:12px;">
                    <button class="btn btn-primary" onclick="startVoiceRecord()" id="voiceRecordBtn" style="font-size:1.5rem;padding:16px 32px;">🎤 开始录音</button>
                    <button class="btn btn-danger" onclick="stopVoiceRecord()" id="voiceStopBtn" style="display:none;font-size:1.5rem;padding:16px 32px;">⏹ 停止录音</button>
                </div>
                <div id="voiceStatus" style="text-align:center;color:var(--text-muted);display:none;">🔴 录音中...</div>
                <div class="form-group"><label>识别结果</label>
                    <textarea id="voiceTranscript" rows="4" placeholder="语音识别结果将显示在这里..." readonly></textarea>
                </div>
            </div>

            <!-- 文件上传 -->
            <div id="panel-file" class="quick-panel" style="display:none;">
                <div id="fileDropZone" style="border:2px dashed var(--border);border-radius:12px;padding:40px;text-align:center;cursor:pointer;transition:all .2s;margin-bottom:12px;"
                     ondrop="handleFileDrop(event)" ondragover="handleFileDragOver(event)" ondragleave="handleFileDragLeave(event)"
                     onclick="document.getElementById('knowledgeFileInput').click()">
                    <div style="font-size:2rem;">📁</div>
                    <p style="font-weight:600;">点击选择或拖拽文件到此处</p>
                    <p style="color:var(--text-muted);font-size:.85rem;">支持 TXT、MD、PDF、DOCX</p>
                    <input type="file" id="knowledgeFileInput" accept=".txt,.md,.pdf,.docx,.csv,.json,.html,.xml" style="display:none;" onchange="handleFileSelect(event)">
                </div>
                <div id="fileInterpretProgress" style="display:none;text-align:center;padding:12px;">
                    <span style="animation:spin 1s linear infinite;">⏳</span> AI正在解读文件...
                </div>
                <div id="fileInterpretResult" style="display:none;"></div>
            </div>

            <!-- 照片+注释 -->
            <div id="panel-photo" class="quick-panel" style="display:none;">
                <div style="display:flex;gap:8px;margin-bottom:12px;">
                    <button class="btn btn-primary btn-sm" onclick="document.getElementById('knowledgePhotoInput').click()">📁 上传图片</button>
                    <button class="btn btn-primary btn-sm" onclick="openKnowledgeCamera()">📷 拍照</button>
                </div>
                <input type="file" id="knowledgePhotoInput" accept="image/*" style="display:none;" onchange="previewKnowledgePhoto(this)">
                <div id="knowledgePhotoPreview" style="display:none;text-align:center;margin-bottom:12px;">
                    <img id="knowledgePhotoImg" style="max-height:200px;max-width:100%;border-radius:8px;box-shadow:var(--shadow);">
                </div>
                <div class="form-group"><label>文字注释</label>
                    <textarea id="photoAnnotation" rows="3" placeholder="为这张图片添加注释..."></textarea>
                </div>
                <div style="text-align:center;margin-bottom:12px;">
                    <button class="btn btn-ghost btn-sm" onclick="startPhotoVoiceAnnotation()" id="photoVoiceBtn">🎤 语音注释</button>
                </div>
            </div>

            <!-- 文字录入 -->
            <div id="panel-text" class="quick-panel" style="display:none;">
                <div class="form-group"><label>标题</label>
                    <input type="text" id="textTitle" placeholder="输入标题...">
                </div>
                <div class="form-group"><label>内容</label>
                    <textarea id="textContent" rows="6" placeholder="输入内容..."></textarea>
                </div>
            </div>

            <!-- 关联联系人 -->
            <div class="form-group" style="margin-top:12px;">
                <label>关联联系人（可选，可多选）</label>
                <select id="knowledgeContactSelect" multiple style="width:100%;padding:8px;border:2px solid var(--border);border-radius:10px;min-height:80px;">
                    {contact_options}
                </select>
                <p style="font-size:.75rem;color:var(--text-muted);">按住 Cmd/Ctrl 多选</p>
            </div>

            <!-- 操作按钮 -->
            <div style="display:flex;gap:10px;margin-top:16px;padding-top:12px;border-top:1px solid var(--border);">
                <button class="btn btn-primary" onclick="saveKnowledgeEntry()" id="saveKnowledgeBtn" style="flex:1;">💾 保存</button>
                <button class="btn btn-ghost" onclick="closeQuickAdd()">取消</button>
            </div>
        </div>
    </div>

    <!-- 编辑弹窗 -->
    <div id="editKnowledgeModal" class="modal-overlay" style="display:none;align-items:center;justify-content:center;z-index:600;">
        <div class="modal" style="max-width:540px;width:95%;text-align:left;">
            <h3 style="margin-bottom:16px;">✏️ 编辑随记</h3>
            <input type="hidden" id="editKnowledgeId">
            <div class="form-group"><label>标题</label><input type="text" id="editKnowledgeTitle"></div>
            <div class="form-group"><label>内容</label><textarea id="editKnowledgeContent" rows="5"></textarea></div>
            <div class="form-group"><label>标签（逗号分隔）</label><input type="text" id="editKnowledgeTags"></div>
            <div style="display:flex;gap:10px;justify-content:flex-end;">
                <button class="btn btn-ghost" onclick="closeEditKnowledge()">取消</button>
                <button class="btn btn-primary" onclick="updateKnowledge()">保存</button>
            </div>
        </div>
    </div>

    <!-- 拍照模态框 -->
    <div id="knowledgeCameraModal" class="modal-overlay" style="display:none;align-items:center;justify-content:center;z-index:600;">
        <div class="modal" style="max-width:500px;width:90%;">
            <h3 style="margin-bottom:12px;">📷 拍照</h3>
            <video id="knowledgeCameraVideo" autoplay playsinline style="width:100%;border-radius:12px;box-shadow:var(--shadow);background:#000;"></video>
            <canvas id="knowledgeCameraCanvas" style="display:none;"></canvas>
            <div style="display:flex;gap:10px;margin-top:12px;">
                <button type="button" class="btn btn-primary" onclick="captureKnowledgePhoto()">📸 拍摄</button>
                <button type="button" class="btn btn-ghost" onclick="closeKnowledgeCamera()">✕ 取消</button>
            </div>
        </div>
    </div>

    <style>
    .quick-tab {{
        padding: 10px 16px; border: none; background: transparent; cursor: pointer;
        font-size: .9rem; color: var(--text-muted); border-bottom: 2px solid transparent;
        margin-bottom: -2px; transition: all .15s;
    }}
    .quick-tab:hover {{ color: var(--text); }}
    .quick-tab.active {{ color: var(--primary); border-bottom-color: var(--primary); font-weight: 600; }}
    #fileDropZone:hover {{ border-color: var(--primary); background: #eff6ff; }}
    #fileDropZone.dragover {{ border-color: var(--primary); background: #eff6ff; }}
    </style>

    <script>
    var _knowledgeEntries = {json.dumps([{
        'id': e.id, 'title': e.title, 'content': e.content,
        'entry_type': e.entry_type, 'tags': e.tags or '',
        'created_at': e.created_at.isoformat() if e.created_at else ''
    } for e in entries], ensure_ascii=False)};
    var _knowledgeCameraStream = null;
    var _currentKnowledgePhoto = null;
    var _photoVoiceTranscript = '';

    function filterKnowledge() {{
        var q = (document.getElementById('knowledgeSearch').value || '').trim().toLowerCase();
        var type = document.getElementById('typeFilter').value;
        var filtered = _knowledgeEntries.filter(function(e) {{
            var matchQ = !q || e.title.toLowerCase().indexOf(q) >= 0 || e.content.toLowerCase().indexOf(q) >= 0;
            var matchType = !type || e.entry_type === type;
            return matchQ && matchType;
        }});
        renderKnowledgeList(filtered);
    }}

    function renderKnowledgeList(entries) {{
        var grid = document.getElementById('knowledgeList');
        if (!entries.length) {{
            grid.innerHTML = '<div class="empty-state"><div class="icon">📝</div><h3>没有匹配的随记</h3></div>';
            return;
        }}
        var icons = {{voice:'🎤', file:'📄', photo:'📷', text:'✏️'}};
        grid.innerHTML = entries.map(function(e) {{
            var icon = icons[e.entry_type] || '📝';
            var content = e.content.length > 150 ? e.content.substring(0, 150) + '...' : e.content;
            return '<div class="contact-card" style="flex-direction:column;align-items:flex-start;gap:8px;">'
                + '<div style="display:flex;justify-content:space-between;width:100%;align-items:flex-start;">'
                + '<div style="flex:1;"><div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;">'
                + '<span style="font-size:1.2rem;">' + icon + '</span>'
                + '<strong>' + e.title + '</strong>'
                + '<span style="background:var(--border);color:var(--text-muted);padding:1px 6px;border-radius:4px;font-size:.7rem;">' + e.entry_type + '</span>'
                + '</div><div style="font-size:.85rem;color:var(--text-muted);line-height:1.5;max-height:60px;overflow:hidden;">'
                + content + '</div></div>'
                + '<div style="display:flex;gap:4px;flex-shrink:0;">'
                + '<button class="btn btn-ghost btn-sm" onclick="editKnowledge(' + e.id + ')">✏️</button>'
                + '<button class="btn btn-danger btn-sm" onclick="confirmDeleteKnowledge(' + e.id + ', \\'' + e.title.replace(/'/g, "\\\\'") + '\\')">🗑️</button>'
                + '</div></div></div>';
        }}).join('');
    }}

    function showQuickAdd() {{ document.getElementById('quickAddModal').style.display = 'flex'; switchTab('voice'); }}
    function closeQuickAdd() {{ document.getElementById('quickAddModal').style.display = 'none'; resetQuickPanels(); }}

    function switchTab(tab) {{
        document.querySelectorAll('.quick-tab').forEach(function(b) {{ b.classList.remove('active'); }});
        document.querySelectorAll('.quick-panel').forEach(function(p) {{ p.style.display = 'none'; }});
        document.getElementById('tab-' + tab).classList.add('active');
        document.getElementById('panel-' + tab).style.display = 'block';
    }}

    function resetQuickPanels() {{
        document.getElementById('voiceTranscript').value = '';
        document.getElementById('textTitle').value = '';
        document.getElementById('textContent').value = '';
        document.getElementById('photoAnnotation').value = '';
        document.getElementById('knowledgePhotoPreview').style.display = 'none';
        document.getElementById('fileInterpretResult').style.display = 'none';
        document.getElementById('fileInterpretProgress').style.display = 'none';
        document.getElementById('knowledgeFileInput').value = '';
        _currentKnowledgePhoto = null;
        _photoVoiceTranscript = '';
    }}

    // ── 语音录入 ──────────────────────────────────
    function startVoiceRecord() {{
        var SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognition) {{
            showToast('您的浏览器不支持语音识别，请使用Chrome', 'error'); return;
        }}
        window._voiceRecognition = new SpeechRecognition();
        window._voiceRecognition.lang = 'zh-CN';
        window._voiceRecognition.interimResults = true;
        window._voiceRecognition.continuous = true;
        window._voiceRecognition.onresult = function(event) {{
            var transcript = '';
            for (var i = 0; i < event.results.length; i++) {{
                transcript += event.results[i][0].transcript;
            }}
            document.getElementById('voiceTranscript').value = transcript;
        }};
        window._voiceRecognition.onerror = function(event) {{
            showToast('语音识别出错: ' + event.error, 'error');
            stopVoiceRecord();
        }};
        window._voiceRecognition.start();
        document.getElementById('voiceRecordBtn').style.display = 'none';
        document.getElementById('voiceStopBtn').style.display = 'inline-block';
        document.getElementById('voiceStatus').style.display = 'block';
    }}

    function stopVoiceRecord() {{
        if (window._voiceRecognition) {{
            window._voiceRecognition.stop();
            window._voiceRecognition = null;
        }}
        document.getElementById('voiceRecordBtn').style.display = 'inline-block';
        document.getElementById('voiceStopBtn').style.display = 'none';
        document.getElementById('voiceStatus').style.display = 'none';
    }}

    // ── 文件上传 ──────────────────────────────────
    function handleFileSelect(event) {{
        if (event.target.files.length > 0) processKnowledgeFile(event.target.files[0]); }}
    function handleFileDrop(event) {{
        event.preventDefault();
        document.getElementById('fileDropZone').classList.remove('dragover');
        if (event.dataTransfer.files.length > 0) processKnowledgeFile(event.dataTransfer.files[0]);
    }}
    function handleFileDragOver(event) {{ event.preventDefault(); document.getElementById('fileDropZone').classList.add('dragover'); }}
    function handleFileDragLeave(event) {{ document.getElementById('fileDropZone').classList.remove('dragover'); }}

    async function processKnowledgeFile(file) {{
        document.getElementById('fileInterpretProgress').style.display = 'block';
        document.getElementById('fileInterpretResult').style.display = 'none';
        var formData = new FormData();
        formData.append('file', file);
        try {{
            var resp = await fetch('/web/api/knowledge/interpret-file', {{ method: 'POST', body: formData }});
            var data = await resp.json();
            document.getElementById('fileInterpretProgress').style.display = 'none';
            if (data.error) {{ showToast(data.error, 'error'); return; }}
            document.getElementById('fileInterpretResult').innerHTML =
                '<div style="background:#f0f9ff;border:1px solid #bae6fd;border-radius:10px;padding:12px;margin-bottom:8px;">'
                + '<strong>🤖 AI解读结果</strong><br>'
                + '<strong>标题：</strong>' + (data.title || '') + '<br>'
                + '<strong>摘要：</strong>' + (data.summary || '') + '<br>'
                + '<strong>要点：</strong>' + (data.key_points || []).join('；') + '<br>'
                + '<strong>标签：</strong>' + (data.tags || []).join(', ')
                + '</div>';
            document.getElementById('fileInterpretResult').style.display = 'block';
            document.getElementById('textTitle').value = data.title || file.name;
            document.getElementById('textContent').value = (data.summary || '') + '\\n\\n关键要点：\\n' + (data.key_points || []).map(function(p,i) {{ return (i+1) + '. ' + p; }}).join('\\n');
            if (data.tags && data.tags.length) {{
                document.getElementById('textTitle').dataset.tags = data.tags.join(',');
            }}
        }} catch(e) {{ showToast('解读失败: ' + e.message, 'error'); document.getElementById('fileInterpretProgress').style.display = 'none'; }}
    }}

    // ── 照片 ──────────────────────────────────────
    function previewKnowledgePhoto(input) {{
        if (input.files && input.files[0]) {{
            _currentKnowledgePhoto = input.files[0];
            var reader = new FileReader();
            reader.onload = function(e) {{
                document.getElementById('knowledgePhotoImg').src = e.target.result;
                document.getElementById('knowledgePhotoPreview').style.display = 'block';
            }};
            reader.readAsDataURL(input.files[0]);
        }}
    }}

    async function openKnowledgeCamera() {{
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {{
            showToast('不支持摄像头', 'error'); return;
        }}
        var isSecure = location.protocol === 'https:' || location.hostname === 'localhost';
        if (!isSecure) {{ showToast('需要HTTPS环境', 'error'); return; }}
        try {{
            _knowledgeCameraStream = await navigator.mediaDevices.getUserMedia({{
                video: {{ facingMode: 'environment', width: {{ ideal: 1920 }}, height: {{ ideal: 1080 }} }}
            }});
            document.getElementById('knowledgeCameraVideo').srcObject = _knowledgeCameraStream;
            document.getElementById('knowledgeCameraModal').style.display = 'flex';
        }} catch(e) {{ showToast('无法访问摄像头', 'error'); }}
    }}

    function closeKnowledgeCamera() {{
        if (_knowledgeCameraStream) {{
            _knowledgeCameraStream.getTracks().forEach(function(t) {{ t.stop(); }});
            _knowledgeCameraStream = null;
        }}
        document.getElementById('knowledgeCameraModal').style.display = 'none';
    }}

    function captureKnowledgePhoto() {{
        var video = document.getElementById('knowledgeCameraVideo');
        var canvas = document.getElementById('knowledgeCameraCanvas');
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        canvas.getContext('2d').drawImage(video, 0, 0);
        canvas.toBlob(function(blob) {{
            _currentKnowledgePhoto = new File([blob], 'photo.jpg', {{ type: 'image/jpeg' }});
            document.getElementById('knowledgePhotoImg').src = canvas.toDataURL('image/jpeg');
            document.getElementById('knowledgePhotoPreview').style.display = 'block';
            closeKnowledgeCamera();
        }}, 'image/jpeg', 0.9);
    }}

    function startPhotoVoiceAnnotation() {{
        var SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognition) {{ showToast('不支持语音识别', 'error'); return; }}
        var rec = new SpeechRecognition();
        rec.lang = 'zh-CN';
        rec.interimResults = false;
        rec.onresult = function(event) {{
            _photoVoiceTranscript = event.results[0][0].transcript;
            document.getElementById('photoAnnotation').value = _photoVoiceTranscript;
            showToast('语音注释已识别', 'success');
        }};
        rec.onerror = function() {{ showToast('语音识别失败', 'error'); }};
        rec.start();
        showToast('正在听取语音注释...', 'info');
    }}

    // ── 保存 ──────────────────────────────────────
    async function saveKnowledgeEntry() {{
        var activeTab = document.querySelector('.quick-tab.active');
        var tabType = activeTab ? activeTab.id.replace('tab-', '') : 'text';
        var title, content, entryType = tabType;
        var audioTranscript = null, imageAnnotation = null;

        if (tabType === 'voice') {{
            content = document.getElementById('voiceTranscript').value;
            audioTranscript = content;
            title = content ? content.substring(0, 30) : '语音记录';
            if (!content) {{ showToast('请先录音', 'error'); return; }}
        }} else if (tabType === 'file') {{
            title = document.getElementById('textTitle').value;
            content = document.getElementById('textContent').value;
            if (!content) {{ showToast('请先上传文件进行解读', 'error'); return; }}
            var tags = document.getElementById('textTitle').dataset.tags || '';
        }} else if (tabType === 'photo') {{
            imageAnnotation = document.getElementById('photoAnnotation').value;
            content = imageAnnotation || '图片记录';
            title = content.substring(0, 30);
            if (!_currentKnowledgePhoto) {{ showToast('请先拍照或上传图片', 'error'); return; }}
        }} else {{
            title = document.getElementById('textTitle').value;
            content = document.getElementById('textContent').value;
            if (!title || !content) {{ showToast('请输入标题和内容', 'error'); return; }}
        }}

        var selectedContacts = Array.from(document.getElementById('knowledgeContactSelect').selectedOptions).map(function(o) {{ return parseInt(o.value); }});

        var body = {{
            title: title, content: content, entry_type: entryType,
            audio_transcript: audioTranscript, image_annotation: imageAnnotation,
            tags: (typeof tags !== 'undefined') ? tags : null,
            contact_ids: selectedContacts
        }};

        // 如果有照片，先上传照片再创建条目
        var formData = new FormData();
        if (_currentKnowledgePhoto) formData.append('photo', _currentKnowledgePhoto);
        formData.append('data', JSON.stringify(body));

        try {{
            var resp = await fetch('/web/api/knowledge', {{ method: 'POST', body: formData }});
            var result = await resp.json();
            if (result.error) {{ showToast(result.error, 'error'); return; }}
            showToast('随记已保存！', 'success');
            setTimeout(function() {{ location.reload(); }}, 500);
        }} catch(e) {{ showToast('保存失败: ' + e.message, 'error'); }}
    }}

    // ── 编辑 ──────────────────────────────────────
    function editKnowledge(id) {{
        var e = _knowledgeEntries.find(function(x) {{ return x.id === id; }});
        if (!e) return;
        document.getElementById('editKnowledgeId').value = e.id;
        document.getElementById('editKnowledgeTitle').value = e.title;
        document.getElementById('editKnowledgeContent').value = e.content;
        document.getElementById('editKnowledgeTags').value = e.tags || '';
        document.getElementById('editKnowledgeModal').style.display = 'flex';
    }}
    function closeEditKnowledge() {{ document.getElementById('editKnowledgeModal').style.display = 'none'; }}

    async function updateKnowledge() {{
        var id = document.getElementById('editKnowledgeId').value;
        var body = {{
            title: document.getElementById('editKnowledgeTitle').value,
            content: document.getElementById('editKnowledgeContent').value,
            tags: document.getElementById('editKnowledgeTags').value
        }};
        try {{
            var resp = await fetch('/web/api/knowledge/' + id, {{ method: 'PUT', headers: {{'Content-Type':'application/json'}}, body: JSON.stringify(body) }});
            if (resp.ok) {{ showToast('已更新'); setTimeout(function(){{location.reload();}}, 500); }}
            else {{ showToast('更新失败', 'error'); }}
        }} catch(e) {{ showToast('网络错误', 'error'); }}
    }}

    // ── 删除 ──────────────────────────────────────
    function confirmDeleteKnowledge(id, title) {{
        confirmDelete(id, title);  // 复用已有的确认弹窗
        // 重写doDelete以使用正确的API
        window._doDeleteKnowledge = id;
    }}

    // 点击遮罩关闭
    document.getElementById('quickAddModal').addEventListener('click', function(e) {{ if (e.target === this) closeQuickAdd(); }});
    document.getElementById('editKnowledgeModal').addEventListener('click', function(e) {{ if (e.target === this) closeEditKnowledge(); }});
    document.getElementById('knowledgeCameraModal').addEventListener('click', function(e) {{ if (e.target === this) closeKnowledgeCamera(); }});
    </script>
    """
    return layout("随记知识库", content, active_nav="knowledge")


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
    total_contacts = db.query(Contact).count()

    # 从 Company 表和 Contact.company 字段聚合所有公司名
    company_records = db.query(Company).all()
    company_map = {c.name: c for c in company_records}

    # 获取 Contact 表中所有不重复的公司名
    from sqlalchemy import distinct
    contact_companies = db.query(distinct(Contact.company)).filter(
        Contact.company.isnot(None), Contact.company != ""
    ).all()
    contact_company_names = set(row[0] for row in contact_companies if row[0])

    # 自动为 Contact 中有但 Company 表中缺失的公司名创建 Company 记录
    missing_names = contact_company_names - set(company_map.keys())
    for name in missing_names:
        new_company = Company(name=name)
        db.add(new_company)
        company_map[name] = new_company
    if missing_names:
        db.commit()
        # 重新查询以获取 ID
        company_records = db.query(Company).all()
        company_map = {c.name: c for c in company_records}

    # 合并所有公司名
    all_company_names = set(company_map.keys()) | contact_company_names

    # 统计每个公司下的联系人数量
    from sqlalchemy import func as sa_func
    contact_counts = {}
    if all_company_names:
        counts = db.query(
            Contact.company, sa_func.count(Contact.id)
        ).filter(
            Contact.company.in_(all_company_names)
        ).group_by(Contact.company).all()
        contact_counts = {row[0]: row[1] for row in counts}

    companies_data = []
    for name in sorted(all_company_names):
        comp_record = company_map.get(name)
        companies_data.append({
            "id": comp_record.id if comp_record else None,
            "name": name,
            "description": comp_record.description if comp_record else "",
            "has_record": comp_record is not None,
            "contact_count": contact_counts.get(name, 0),
        })

    total_companies = len(companies_data)

    # 必须在 db.close() 之前提取数据，否则会触发 DetachedInstanceError
    contacts_data = [
        type('obj', (object,), {
            'id': c.id, 'name': c.name, 'company': c.company,
            'department': c.department, 'position': c.position,
            'mobile': c.mobile, 'phone': c.phone, 'email': c.email,
        }) for c in contacts
    ]
    db.close()

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
            {"id": c.id, "name": c.name, "name_en": getattr(c, 'name_en', '') or '',
             "company": c.company, "company_en": getattr(c, 'company_en', '') or '',
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
    name_en: str = Form(""), company: str = Form(""),
    company_en: str = Form(""), department: str = Form(""),
    department_en: str = Form(""), position: str = Form(""),
    position_en: str = Form(""), mobile: str = Form(""),
    phone: str = Form(""), email: str = Form(""),
    company_address: str = Form(""), notes: str = Form(""),
    card_photo: UploadFile = File(None), avatar: UploadFile = File(None),
    card_photo_filename: str = Form(None),
    card_photo_filename_2: str = Form(None)
):
    # 保存上传的图片
    def save_uploaded_file(file_obj, prefix=""):
        if not file_obj or file_obj.filename == "":
            return None
        suffix = Path(file_obj.filename).suffix
        filename = generate_filename(suffix, prefix)
        filepath = Config.PHOTOS_DIR / filename
        with open(filepath, "wb") as buffer:
            buffer.write(file_obj.file.read())
        return filename

    # 优先使用新上传的文件，如果没有则使用OCR时保存的文件名
    card_photo_path = save_uploaded_file(card_photo)
    if not card_photo_path and card_photo_filename:
        card_photo_path = card_photo_filename
    card_photo_path_2 = card_photo_filename_2 or None
    avatar_path = save_uploaded_file(avatar)

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
            contact.name = form_data.name
            contact.name_en = name_en or None
            contact.company = form_data.company
            contact.company_en = company_en or None
            contact.department = form_data.department
            contact.department_en = department_en or None
            contact.position = form_data.position
            contact.position_en = position_en or None
            contact.mobile = form_data.mobile
            contact.phone = form_data.phone
            contact.email = form_data.email
            contact.company_address = form_data.company_address
            contact.notes = form_data.notes
            if card_photo_path:
                contact.business_card_path = card_photo_path
            if card_photo_path_2:
                contact.business_card_path_2 = card_photo_path_2
            if avatar_path:
                contact.avatar_path = avatar_path
            db.commit()
    else:
        # 查重：相同姓名+公司视为重复名片
        existing = db.query(Contact).filter(
            Contact.name == form_data.name,
            Contact.company == (form_data.company or None)
        ).first()
        if existing:
            db.close()
            # 返回提示页面，告知用户已有该名片
            company_text = f" — {existing.company}" if existing.company else ""
            return HTMLResponse(content=f"""
            <div style="max-width:600px;margin:60px auto;text-align:center;padding:40px;">
                <div style="font-size:4rem;margin-bottom:16px;">⚠️</div>
                <h2>名片已存在</h2>
                <p style="color:var(--text-muted);margin:16px 0;">
                    系统中已有 <strong>{existing.name}</strong>{company_text}
                    的名片信息
                </p>
                <div style="display:flex;gap:12px;justify-content:center;margin-top:24px;">
                    <a href="/web/card/{existing.id}" style="color:var(--primary);">查看现有名片</a>
                    <a href="/web/" style="color:var(--primary);">返回首页</a>
                    <a href="/web/edit/{existing.id}" class="btn btn-primary btn-sm">编辑现有名片</a>
                </div>
            </div>
            """)

        # 创建新联系人（含双语字段）
        contact = Contact(
            name=form_data.name,
            name_en=name_en or None,
            company=form_data.company,
            company_en=company_en or None,
            department=form_data.department,
            department_en=department_en or None,
            position=form_data.position,
            position_en=position_en or None,
            mobile=form_data.mobile,
            phone=form_data.phone,
            email=form_data.email,
            company_address=form_data.company_address,
            notes=form_data.notes,
            business_card_path=card_photo_path,
            business_card_path_2=card_photo_path_2,
            avatar_path=avatar_path
        )
        db.add(contact)
        db.commit()
    db.close()
    return RedirectResponse("/web/", status_code=302)


@router.get("/card/{contact_id}", response_class=HTMLResponse)
async def web_card(contact_id: int):
    db = SessionLocal()
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        db.close()
        return RedirectResponse("/web/", status_code=302)

    # 获取公司信息
    company_info = None
    company_news = []
    if contact.company:
        company = db.query(Company).filter(Company.name == contact.company).first()
        if company:
            company_info = {
                "name": company.name,
                "description": company.description or "",
                "business_performance": company.hot_topics or "",
                "website": company.website or "",
            }
            if company.latest_news:
                try:
                    company_news = json.loads(company.latest_news)
                except (json.JSONDecodeError, TypeError):
                    company_news = []
            # 获取组织架构并匹配数据库中的联系人
            org_structure = None
            if company.org_structure:
                try:
                    org_structure = json.loads(company.org_structure)
                except (json.JSONDecodeError, TypeError):
                    org_structure = None

    # 获取关联的随记
    from app.models import Contact as ContactModel
    knowledge_entries = knowledge_crud.get_by_contact(db, contact_id)
    knowledge_data = [{
        "id": e.id, "title": e.title, "content": e.content[:200],
        "entry_type": e.entry_type,
        "created_at": e.created_at.strftime("%Y-%m-%d %H:%M") if e.created_at else "",
        "created_at_iso": e.created_at.isoformat() if e.created_at else "",
    } for e in knowledge_entries]

    # 获取同公司联系人（排除本人），按部门分组
    colleagues = contact_crud.get_by_company(db, contact.company) if contact.company else []
    all_company_contacts = list(colleagues)  # 包含本人的完整列表，用于组织架构匹配
    colleagues = [c for c in colleagues if c.id != contact_id]  # 排除主名片本人

    # 构建联系人姓名索引（用于组织架构匹配）
    contact_name_index = {}  # name -> contact info
    dept_contacts_map = {}   # department -> [contact dicts]
    for c in all_company_contacts:
        info = {"id": c.id, "name": c.name, "position": c.position or "", "department": c.department or ""}
        contact_name_index[c.name] = info
        # 去姓匹配
        if len(c.name) >= 2:
            short = c.name[1:]
            if short not in contact_name_index:
                contact_name_index[short] = info
        # 按部门分组
        dept = c.department.strip() if c.department else "其他"
        if dept not in dept_contacts_map:
            dept_contacts_map[dept] = []
        dept_contacts_map[dept].append(info)

    # 按部门分组
    dept_groups = {}  # {dept_name: [contacts]}
    no_dept = []      # 无部门的联系人
    for c in colleagues:
        dept = c.department.strip() if c.department else None
        if dept:
            dept_groups.setdefault(dept, []).append(c)
        else:
            no_dept.append(c)
    # 转换为有序列表：有部门的在前，无部门的在后
    colleagues_by_dept = []
    for dept in sorted(dept_groups.keys()):
        colleagues_by_dept.append({"department": dept, "contacts": dept_groups[dept]})
    if no_dept:
        colleagues_by_dept.append({"department": None, "contacts": no_dept})
    total_colleagues = len(colleagues)
    generator = CardGenerator()
    output_path = Config.PHOTOS_DIR / f"web_card_{contact.id}.jpg"
    result = generator.create_card(contact, colleagues, output_path=output_path)
    db.close()

    card_filename = f"web_card_{contact.id}.jpg"
    card_exists = result and output_path.exists()
    return HTMLResponse(content=render_card_page(
        contact, card_exists, card_filename,
        company_info=company_info, company_news=company_news,
        knowledge_entries=knowledge_data,
        colleagues_by_dept=colleagues_by_dept,
        total_colleagues=total_colleagues,
        org_structure=org_structure,
        contact_name_index=contact_name_index,
        dept_contacts_map=dept_contacts_map
    ))


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
    suffix = Path(file.filename).suffix if file.filename else ".jpg"
    filename = generate_filename(suffix, "card_")
    save_path = Config.PHOTOS_DIR / filename
    with open(save_path, "wb") as f:
        f.write(await file.read())

    # 调用 OCR
    engine = OCREngine(
        api_base=active_model.api_base,
        api_key=active_model.api_key,
        model_name=active_model.model_name
    )
    result = engine.recognize(save_path)

    # 将照片文件名添加到返回结果中
    if isinstance(result, dict):
        result["card_photo"] = filename

    return result


# ── 人脸搜索 API ───────────────────────────────────────────

@router.post("/api/search-by-face")
async def api_search_by_face(photo: UploadFile = File(...), confidence_threshold: Optional[str] = Form(None)):
    """使用大模型进行人脸比对搜索"""
    # 解析置信度阈值
    threshold = 0.6
    if confidence_threshold:
        try:
            threshold = float(confidence_threshold)
        except ValueError:
            threshold = 0.6

    # 获取当前启用的模型
    db = SessionLocal()
    active_model = ai_model_manager.get_active(db)
    if not active_model:
        db.close()
        return JSONResponse({"error": "没有启用的 AI 模型，请先在模型管理中配置"}, status_code=400)

    # 获取所有联系人
    contacts = db.query(Contact).all()
    db.close()

    # 只保留有人像的联系人
    contacts_with_avatar = [c for c in contacts if c.avatar_path]

    if not contacts_with_avatar:
        return {"error": "没有录入人像的名片", "contacts": []}

    # 保存上传的查询照片
    suffix = Path(photo.filename).suffix if photo.filename else ".jpg"
    filename = generate_filename(suffix, "face_")
    temp_query_path = Config.PHOTOS_DIR / filename
    with open(temp_query_path, "wb") as f:
        f.write(await photo.read())

    try:
        # 初始化人脸搜索引擎
        search_engine = FaceSearchEngine(
            api_base=active_model.api_base,
            api_key=active_model.api_key,
            model_name=active_model.model_name
        )

        # 搜索匹配的人脸
        matches = search_engine.search_matches(
            temp_query_path,
            contacts_with_avatar,
            Config.PHOTOS_DIR,
            confidence_threshold=threshold
        )

        # 清理临时文件
        try:
            temp_query_path.unlink()
        except Exception:
            pass

        # 返回结果
        if not matches:
            return {"contacts": [], "message": "未找到匹配的人脸"}

        return {
            "contacts": [
                {
                    "id": m["contact"].id,
                    "name": m["contact"].name,
                    "company": m["contact"].company,
                    "department": m["contact"].department,
                    "position": m["contact"].position,
                    "mobile": m["contact"].mobile,
                    "phone": m["contact"].phone,
                    "email": m["contact"].email,
                    "confidence": m["confidence"],
                    "reasoning": m["reasoning"]
                }
                for m in matches
            ]
        }

    except Exception as e:
        # 清理临时文件
        try:
            temp_query_path.unlink()
        except Exception:
            pass
        return JSONResponse({"error": f"搜索失败：{str(e)}"}, status_code=500)


# ── 随记知识库页面 ──────────────────────────────────

@router.get("/knowledge", response_class=HTMLResponse)
async def web_knowledge():
    db = SessionLocal()
    entries = knowledge_crud.list_recent(db, limit=50)
    # Attach linked contact names
    from app.models import Contact as ContactModel
    for e in entries:
        linked_ids = knowledge_crud.get_linked_contact_ids(db, e.id)
        e._linked_contacts = db.query(ContactModel).filter(ContactModel.id.in_(linked_ids)).all() if linked_ids else []
    stats = {
        "total": knowledge_crud.count(db),
        "voice": knowledge_crud.count_by_type(db, "voice"),
        "file": knowledge_crud.count_by_type(db, "file"),
        "photo": knowledge_crud.count_by_type(db, "photo"),
        "text": knowledge_crud.count_by_type(db, "text"),
    }
    contacts = db.query(ContactModel).order_by(ContactModel.name).all()
    contacts_data = [{"id": c.id, "name": c.name} for c in contacts]
    db.close()
    return HTMLResponse(content=render_knowledge_page(entries, stats, contacts_data))


# ── 随记知识库 API ──────────────────────────────────

@router.get("/api/knowledge")
async def api_list_knowledge(q: str = None, type: str = None, page: int = 1, limit: int = 20):
    db = SessionLocal()
    if q:
        entries = knowledge_crud.search(db, q, limit=limit)
    elif type:
        entries = knowledge_crud.get_by_type(db, type, limit=limit)
    else:
        offset = (page - 1) * limit
        entries = knowledge_crud.list_recent(db, limit=limit, offset=offset)

    from app.models import Contact as ContactModel
    result = []
    for e in entries:
        linked_ids = knowledge_crud.get_linked_contact_ids(db, e.id)
        linked_contacts = db.query(ContactModel).filter(ContactModel.id.in_(linked_ids)).all() if linked_ids else []
        result.append({
            "id": e.id, "title": e.title, "content": e.content,
            "entry_type": e.entry_type, "file_path": e.file_path,
            "audio_transcript": e.audio_transcript, "image_annotation": e.image_annotation,
            "source_description": e.source_description, "tags": e.tags,
            "created_at": e.created_at.isoformat() if e.created_at else None,
            "updated_at": e.updated_at.isoformat() if e.updated_at else None,
            "linked_contacts": [{"id": c.id, "name": c.name} for c in linked_contacts]
        })
    db.close()
    return {"entries": result, "total": knowledge_crud.count(db) if not (q or type) else len(result)}


@router.post("/api/knowledge")
async def api_create_knowledge(photo: UploadFile = File(None), data: str = Form(None)):
    """创建知识条目。支持可选的图片上传。"""
    body = {}
    if data:
        try:
            body = json.loads(data)
        except json.JSONDecodeError:
            return JSONResponse({"error": "无效的数据格式"}, status_code=400)

    title = body.get("title", "未命名")
    content = body.get("content", "")
    entry_type = body.get("entry_type", "text")
    if entry_type not in ("voice", "file", "photo", "text"):
        entry_type = "text"

    if not content and entry_type != "photo":
        return JSONResponse({"error": "内容不能为空"}, status_code=400)

    db = SessionLocal()
    try:
        # 保存图片
        photo_path = None
        if photo and photo.filename:
            suffix = Path(photo.filename).suffix
            filename = generate_filename(suffix, "knowledge_")
            filepath = Config.PHOTOS_DIR / filename
            with open(filepath, "wb") as f:
                f.write(await photo.read())
            photo_path = filename

        entry = knowledge_crud.create(
            db,
            title=title,
            content=content,
            entry_type=entry_type,
            file_path=photo_path,
            audio_transcript=body.get("audio_transcript"),
            image_annotation=body.get("image_annotation"),
            source_description=body.get("source_description"),
            tags=body.get("tags"),
        )

        # 关联联系人
        contact_ids = body.get("contact_ids", [])
        for cid in contact_ids:
            knowledge_crud.link_contact(db, entry.id, cid)

        db.commit()
        return {"ok": True, "id": entry.id}
    except Exception as e:
        db.rollback()
        return JSONResponse({"error": f"保存失败: {str(e)}"}, status_code=500)
    finally:
        db.close()


@router.get("/api/knowledge/{entry_id}")
async def api_get_knowledge(entry_id: int):
    db = SessionLocal()
    entry = knowledge_crud.get(db, entry_id)
    if not entry:
        db.close()
        return JSONResponse({"error": "条目不存在"}, status_code=404)

    from app.models import Contact as ContactModel
    linked_ids = knowledge_crud.get_linked_contact_ids(db, entry_id)
    linked_contacts = db.query(ContactModel).filter(ContactModel.id.in_(linked_ids)).all() if linked_ids else []
    result = {
        "id": entry.id, "title": entry.title, "content": entry.content,
        "entry_type": entry.entry_type, "file_path": entry.file_path,
        "audio_transcript": entry.audio_transcript, "image_annotation": entry.image_annotation,
        "source_description": entry.source_description, "tags": entry.tags,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
        "updated_at": entry.updated_at.isoformat() if entry.updated_at else None,
        "linked_contacts": [{"id": c.id, "name": c.name} for c in linked_contacts]
    }
    db.close()
    return result


@router.put("/api/knowledge/{entry_id}")
async def api_update_knowledge(entry_id: int, request: Request):
    body = await request.json()
    db = SessionLocal()
    entry = knowledge_crud.get(db, entry_id)
    if not entry:
        db.close()
        return JSONResponse({"error": "条目不存在"}, status_code=404)

    update_data = {k: v for k, v in body.items() if v is not None and k not in ("id", "contact_ids")}
    knowledge_crud.update(db, entry, **update_data)
    db.close()
    return {"ok": True}


@router.delete("/api/knowledge/{entry_id}")
async def api_delete_knowledge(entry_id: int):
    db = SessionLocal()
    ok = knowledge_crud.delete(db, entry_id)
    db.close()
    if not ok:
        return JSONResponse({"error": "条目不存在"}, status_code=404)
    return {"ok": True}


@router.post("/api/knowledge/interpret-file")
async def api_interpret_file(file: UploadFile = File(...)):
    """上传文件，AI 解读并返回结构化知识"""
    db = SessionLocal()
    active_model = ai_model_manager.get_active(db)
    db.close()

    if not active_model:
        return JSONResponse({"error": "没有启用的 AI 模型，请先在模型管理中配置"}, status_code=400)

    # 保存上传的文件
    suffix = Path(file.filename).suffix if file.filename else ".txt"
    filename = generate_filename(suffix, "knowledge_file_")
    save_path = Config.PHOTOS_DIR / filename
    with open(save_path, "wb") as f:
        f.write(await file.read())

    try:
        engine = KnowledgeEngine(
            api_base=active_model.api_base,
            api_key=active_model.api_key,
            model_name=active_model.model_name
        )
        result = engine.interpret_file(save_path)

        # 清理临时文件
        try:
            save_path.unlink()
        except Exception:
            pass

        return result
    except Exception as e:
        try:
            save_path.unlink()
        except Exception:
            pass
        return JSONResponse({"error": f"解读失败: {str(e)}"}, status_code=500)


# ── 联系人关联随记 API ──────────────────────────────

@router.get("/api/contacts/{contact_id}/knowledge")
async def api_contact_knowledge(contact_id: int):
    db = SessionLocal()
    entries = knowledge_crud.get_by_contact(db, contact_id)
    result = [{
        "id": e.id, "title": e.title, "content": e.content[:200],
        "entry_type": e.entry_type, "created_at": e.created_at.isoformat() if e.created_at else None
    } for e in entries]
    db.close()
    return {"entries": result}


@router.post("/api/contacts/{contact_id}/knowledge")
async def api_link_knowledge_to_contact(contact_id: int, request: Request):
    body = await request.json()
    knowledge_id = body.get("knowledge_id")
    if not knowledge_id:
        return JSONResponse({"error": "缺少 knowledge_id"}, status_code=400)
    db = SessionLocal()
    link = knowledge_crud.link_contact(db, knowledge_id, contact_id)
    db.close()
    return {"ok": True, "id": link.id}


@router.delete("/api/contacts/{contact_id}/knowledge/{knowledge_id}")
async def api_unlink_knowledge_from_contact(contact_id: int, knowledge_id: int):
    db = SessionLocal()
    ok = knowledge_crud.unlink_contact(db, knowledge_id, contact_id)
    db.close()
    return {"ok": ok}


# ── 公司研究 API ────────────────────────────────────

@router.post("/api/company/research")
async def api_research_company(request: Request):
    """使用 AI 研究公司信息（简介、经营情况、热点新闻）"""
    body = await request.json()
    company_name = body.get("company_name", "").strip()
    if not company_name:
        return JSONResponse({"error": "公司名称不能为空"}, status_code=400)

    db = SessionLocal()
    active_model = ai_model_manager.get_active(db)
    if not active_model:
        db.close()
        return JSONResponse({"error": "没有启用的 AI 模型"}, status_code=400)

    try:
        engine = KnowledgeEngine(
            api_base=active_model.api_base,
            api_key=active_model.api_key,
            model_name=active_model.model_name
        )
        result = engine.research_company(company_name)

        if "error" not in result and result.get("is_known"):
            # 缓存到 Company 表
            company = db.query(Company).filter(Company.name == company_name).first()
            if company:
                if result.get("company_intro"):
                    company.description = result["company_intro"]
                if result.get("hot_news"):
                    import json as _json
                    company.latest_news = _json.dumps(result["hot_news"], ensure_ascii=False)
                if result.get("business_performance"):
                    company.hot_topics = result["business_performance"]
                if result.get("org_structure"):
                    import json as _json2
                    company.org_structure = _json2.dumps(result["org_structure"], ensure_ascii=False)
                db.commit()

        db.close()
        return result
    except Exception as e:
        db.close()
        return JSONResponse({"error": f"研究失败: {str(e)}"}, status_code=500)


# ── 知识提炼 API ─────────────────────────────────────

@router.post("/api/contacts/{contact_id}/knowledge/summary")
async def api_summarize_contact_knowledge(contact_id: int):
    """对某联系人的所有随记进行AI提炼总结"""
    db = SessionLocal()
    contact = contact_crud.get(db, contact_id)
    if not contact:
        db.close()
        return JSONResponse({"error": "联系人不存在"}, status_code=404)

    entries = knowledge_crud.get_by_contact(db, contact_id)
    db.close()

    if not entries:
        return JSONResponse({"error": "该联系人没有随记内容"}, status_code=400)

    db2 = SessionLocal()
    active_model = ai_model_manager.get_active(db2)
    db2.close()

    if not active_model:
        return JSONResponse({"error": "没有启用的 AI 模型"}, status_code=400)

    try:
        result = summarize_contact_knowledge(
            api_base=active_model.api_base,
            api_key=active_model.api_key,
            model_name=active_model.model_name,
            contact_name=contact.name,
            knowledge_entries=entries
        )
        return result
    except Exception as e:
        return JSONResponse({"error": f"提炼失败: {str(e)}"}, status_code=500)
