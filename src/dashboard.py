from typing import Optional
from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from src.database import (
    SessionLocal, ThreadMemory, ListingOpportunity,
    PostedBacklink, get_posted_backlinks, update_backlink_record,
    get_article_drafts, get_article_draft
)
from src.gaper_scraper import get_brand_profile, scrape_gaper_brand
from src.discovery import discover_threads
from src.pipeline import approve_and_queue_post, run_pipeline, run_global_discovery
from src.brain import qa_loop, evaluate_seo_geo_aeo
from src.generic_listing_agent import start_generic_listing, confirm_generic_listing, cancel_generic_listing
from src.notion_backlink_manager import edit_live_notion_page, delete_live_notion_page
from src.backlink_health import check_overdue_backlinks
import config
import src.article_studio as article_studio
# Only these platforms are in active use right now - Articles tab and its
# approvals are scoped to just these two, per current focus (other
# adapters exist in code but aren't part of the active workflow yet).
ACTIVE_ARTICLE_PLATFORMS = ["contra", "notion"]

app = FastAPI(title="Gaper SEO/GEO/AEO AI Backlink Agent Dashboard")

class DraftEdit(BaseModel):
    reply_text: str

class RejectFeedback(BaseModel):
    feedback: str
    iteration: int = 1

class BacklinkEdit(BaseModel):
    content: str

class DraftGenerate(BaseModel):
    platform: str  # 'contra' or 'notion'
    topic: str = ""
    target_url: Optional[str] = None

class DraftEditContent(BaseModel):
    content: str
    title: Optional[str] = None

class DraftFeedback(BaseModel):
    feedback: str

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Gaper AI Backlink & Citation Assembly Line</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=Space+Grotesk:wght@400;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #0b0c10;
            --glass-bg: rgba(22, 24, 37, 0.7);
            --glass-border: rgba(138, 43, 226, 0.2);
            --primary: #8a2be2;
            --secondary: #ff007f;
            --accent: #00ffff;
            --text-main: #f5f6fa;
            --text-muted: #a0a5c0;
            --success: #39ff14;
            --warning: #ffb703;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Outfit', sans-serif; }
        body {
            background: linear-gradient(135deg, #050508 0%, #0b0c10 50%, #120e2e 100%);
            color: var(--text-main);
            min-height: 100vh;
        }
        .container { max-width: 1300px; margin: 0 auto; padding: 20px; }
        header {
            display: flex; justify-content: space-between; align-items: center;
            padding: 20px 30px; background: var(--glass-bg); backdrop-filter: blur(12px);
            border-radius: 16px; border: 1px solid var(--glass-border);
            margin-bottom: 30px; box-shadow: 0 8px 32px 0 rgba(0,0,0,0.37);
        }
        .logo-section h1 {
            font-family: 'Space Grotesk', sans-serif; font-weight: 800;
            background: linear-gradient(to right, var(--text-main), var(--accent));
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
            font-size: 24px;
        }
        .logo-section span { color: var(--secondary); font-weight: 800; }
        .api-badge {
            background: rgba(138,43,226,0.15); border: 1px solid var(--primary);
            color: var(--text-main); padding: 6px 14px; border-radius: 20px;
            font-size: 13px; font-weight: 600; display: flex; align-items: center; gap: 8px;
        }
        .api-badge::before {
            content: ''; display: inline-block; width: 8px; height: 8px;
            background: var(--success); border-radius: 50%; box-shadow: 0 0 10px var(--success);
        }
        .tabs { display: flex; gap: 15px; margin-bottom: 25px; flex-wrap: wrap; }
        .tab-btn {
            background: transparent; border: none; color: var(--text-muted);
            padding: 12px 24px; font-size: 16px; font-weight: 600; cursor: pointer;
            border-radius: 10px; transition: all 0.3s ease; border: 1px solid transparent;
        }
        .tab-btn:hover { color: var(--text-main); background: rgba(255,255,255,0.05); }
        .tab-btn.active {
            color: var(--text-main); background: var(--glass-bg);
            border: 1px solid var(--glass-border); box-shadow: 0 0 15px rgba(138,43,226,0.3);
        }
        .panel { display: none; }
        .panel.active { display: block; animation: fadeIn 0.5s ease-out; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        .grid-2 { display: grid; grid-template-columns: 1fr 1.5fr; gap: 25px; }
        .glass-card {
            background: var(--glass-bg); backdrop-filter: blur(12px);
            border: 1px solid var(--glass-border); border-radius: 16px;
            padding: 24px; box-shadow: 0 8px 32px 0 rgba(0,0,0,0.25);
            margin-bottom: 25px;
        }
        .glass-card h2 {
            font-family: 'Space Grotesk', sans-serif; margin-bottom: 20px;
            font-size: 20px; border-bottom: 1px solid var(--glass-border);
            padding-bottom: 10px; color: var(--accent);
        }
        .scores-wrapper { display: flex; justify-content: space-around; margin: 20px 0; }
        .score-circle { text-align: center; }
        .score-val {
            font-size: 32px; font-weight: 800; font-family: 'Space Grotesk', sans-serif;
            color: var(--accent); text-shadow: 0 0 10px rgba(0,255,255,0.5);
        }
        .score-label { font-size: 12px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 1px; margin-top: 5px; }
        .form-group { margin-bottom: 15px; }
        label { display: block; font-size: 13px; color: var(--text-muted); margin-bottom: 6px; font-weight: 600; }
        textarea, input[type="text"] {
            width: 100%; background: rgba(0,0,0,0.4); border: 1px solid var(--glass-border);
            border-radius: 8px; padding: 12px; color: var(--text-main); font-size: 14px;
            outline: none; transition: all 0.3s;
        }
        textarea:focus, input[type="text"]:focus { border-color: var(--accent); box-shadow: 0 0 10px rgba(0,255,255,0.2); }
        .btn {
            background: linear-gradient(135deg, var(--primary) 0%, #4b0082 100%);
            border: none; color: #fff; padding: 12px 20px; border-radius: 8px;
            font-weight: 600; cursor: pointer; transition: all 0.3s ease;
            display: inline-flex; align-items: center; gap: 10px;
        }
        .btn:hover { box-shadow: 0 0 15px rgba(138,43,226,0.6); transform: translateY(-2px); }
        .btn-sec { background: linear-gradient(135deg, var(--secondary) 0%, #b22222 100%); }
        .btn-accent { background: transparent; border: 1px solid var(--accent); color: var(--accent); }
        .btn-accent:hover { background: var(--accent); color: var(--bg-color); box-shadow: 0 0 15px var(--accent); }
        .btn-sm { padding: 6px 12px; font-size: 12px; }
        .btn-success { background: linear-gradient(135deg, var(--success) 0%, #00aa00 100%); color: #000; }
        .btn-success:hover { box-shadow: 0 0 15px var(--success); }
        .item-list { display: flex; flex-direction: column; gap: 15px; max-height: 600px; overflow-y: auto; }
        .list-item {
            background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.05);
            border-radius: 12px; padding: 18px; transition: all 0.3s;
        }
        .list-item:hover { border-color: var(--glass-border); background: rgba(255,255,255,0.05); }
        .list-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; flex-wrap: wrap; gap: 10px; }
        .list-title { font-weight: 600; font-size: 14px; color: var(--text-main); text-decoration: none; word-break: break-all; }
        .list-title:hover { color: var(--accent); }
        .badge {
            padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: 600;
            text-transform: uppercase; white-space: nowrap;
        }
        .badge-pending { background: rgba(255,183,3,0.15); color: var(--warning); border: 1px solid var(--warning); }
        .badge-posted { background: rgba(57,255,20,0.15); color: var(--success); border: 1px solid var(--success); }
        .badge-ghost { background: rgba(160,165,192,0.15); color: var(--text-muted); border: 1px solid var(--text-muted); }
        .badge-listed { background: rgba(57,255,20,0.15); color: var(--success); border: 1px solid var(--success); }
        .badge-failed { background: rgba(255,0,64,0.15); color: #ff0040; border: 1px solid #ff0040; }
        .draft-preview {
            background: rgba(0,0,0,0.5); padding: 15px; border-radius: 8px;
            border-left: 4px solid var(--primary); font-size: 14px; line-height: 1.6;
            margin: 15px 0; white-space: pre-wrap; max-height: 200px; overflow-y: auto;
        }
        .meta-info { display: flex; gap: 15px; font-size: 12px; color: var(--text-muted); margin-top: 10px; flex-wrap: wrap; }
        .actions-bar { display: flex; gap: 10px; justify-content: flex-end; margin-top: 15px; flex-wrap: wrap; }
        .profile-logo {
            width: 80px; height: 80px; border-radius: 50%; background: rgba(255,255,255,0.05);
            border: 1px solid var(--glass-border); padding: 10px;
            display: flex; align-items: center; justify-content: center; margin-bottom: 15px;
        }
        .profile-logo img { max-width: 100%; max-height: 100%; }
        .logs-window {
            background: #000; border: 1px solid var(--glass-border); border-radius: 12px;
            padding: 15px; height: 300px; overflow-y: auto; font-family: monospace;
            font-size: 12px; color: var(--success); line-height: 1.5;
        }
        .status-msg { padding: 10px 15px; border-radius: 8px; margin: 10px 0; }
        .status-success { background: rgba(57,255,20,0.1); border: 1px solid var(--success); color: var(--success); }
        .status-error { background: rgba(255,0,64,0.1); border: 1px solid #ff0040; color: #ff0040; }
        .status-info { background: rgba(0,255,255,0.1); border: 1px solid var(--accent); color: var(--accent); }
        @media (max-width: 768px) { .grid-2 { grid-template-columns: 1fr; } header { flex-direction: column; gap: 15px; text-align: center; } }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="logo-section"><h1>Gaper <span>Backlink Agent V2</span></h1></div>
            <div class="api-badge">Gemini Pipeline Active</div>
        </header>
        <div class="tabs">
            <button class="tab-btn active" onclick="switchTab('dashboard')">📊 Overview</button>
            <button class="tab-btn" onclick="switchTab('articles')">📝 Articles (Contra/Notion)</button>
            <button class="tab-btn" onclick="switchTab('backlinks')">🔗 New Backlinks</button>
            <button class="tab-btn" onclick="switchTab('listings')">📋 Listing Pitcher</button>
            <button class="tab-btn" onclick="switchTab('discovery')">🔍 Logs & Discovery</button>
        </div>

        <div id="dashboard" class="panel active">
            <div class="grid-2">
                <div>
                    <div class="glass-card">
                        <h2>Gaper.io Brand Profile</h2>
                        <div class="profile-logo"><img src="" alt="Gaper Logo" id="brandLogo"></div>
                        <div class="form-group"><label>Description</label><textarea id="brandDesc" rows="4" readonly></textarea></div>
                        <div class="form-group"><label>USPs</label><textarea id="brandUsps" rows="5" readonly></textarea></div>
                        <button class="btn btn-accent btn-sm" onclick="triggerScrapeBrand()">🔄 Rescrape</button>
                    </div>
                </div>
                <div>
                    <div class="glass-card">
                        <h2>System Stats</h2>
                        <div class="scores-wrapper">
                            <div class="score-circle"><div class="score-val" id="statPending">0</div><div class="score-label">Pending Approval</div></div>
                            <div class="score-circle"><div class="score-val" id="statPosted">0</div><div class="score-label">Citations Posted</div></div>
                            <div class="score-circle"><div class="score-val" id="statOpps">0</div><div class="score-label">Directories Missing</div></div>
                            <div class="score-circle"><div class="score-val" id="statListed">0</div><div class="score-label">Gaper Listed</div></div>
                            <div class="score-circle"><div class="score-val" id="statBacklinks">0</div><div class="score-label">Live Backlinks</div></div>
                        </div>
                    </div>
                    <div class="glass-card">
                        <h2>Run Manual Pipeline</h2>
                        <div class="form-group"><label>Target URL</label><input type="text" id="manualUrl" placeholder="https://www.indiehackers.com/post/..."></div>
                        <button class="btn" onclick="runManualPipeline()">🚀 Process URL</button>
                    </div>
                </div>
            </div>
        </div>

        <div id="articles" class="panel">
            <div class="glass-card">
                <h2>✍️ Generate New Draft</h2>
                <div class="form-group">
                    <label>Platform</label>
                    <select id="draftPlatform" onchange="toggleTargetUrlField()" style="width:100%;background:rgba(0,0,0,0.4);border:1px solid var(--glass-border);border-radius:8px;padding:12px;color:#fff;">
                        <option value="contra">Contra </option>
                        <option value="notion">Notion (standalone article)</option>
                    </select>
                </div>
                <div class="form-group"><label>Topic</label><input type="text" id="draftTopic" placeholder="e.g. hiring remote developers fast"></div>
                <div class="form-group" id="targetUrlGroup"><label>Target Thread URL (Contra only)</label><input type="text" id="draftTargetUrl" placeholder="https://contra.com/community/for-you?r=khadija_asim_t85rggyo"></div>
                <button class="btn" onclick="generateDraft()">🤖 Generate with Gemini</button>
            </div>
            <div class="glass-card">
                <h2>📝 Drafts — Review, Edit, Improve, Submit</h2>
                <button class="btn btn-sm btn-accent" onclick="loadDrafts()">🔄 Refresh</button>
                <div class="item-list" id="draftsList" style="margin-top:15px;"></div>
            </div>
        </div>

        <div id="backlinks" class="panel">
            <div class="glass-card">
                <h2>🔗 New Backlinks — Live on Contra &amp; Notion</h2>
                <p style="font-size:13px;color:var(--text-muted);margin-bottom:15px;">Every backlink actually posted live. Notion edits/deletes hit the real Notion page via API. Contra has no edit/delete API — those update the local record only, with a note.</p>
                <button class="btn btn-sm btn-accent" onclick="loadBacklinks()">🔄 Refresh</button>
                <button class="btn btn-sm" onclick="checkOverdueBacklinks()">🕐 Check 7-Day Link Health</button>
                <div id="backlinkCheckStatus" style="display:none;" class="status-msg status-info"></div>
                <div class="item-list" id="backlinksList" style="margin-top:15px;"></div>
            </div>
        </div>

        <div id="listings" class="panel">
            <div class="glass-card">
                <h2>📋 Gaper Listing - Platforms Where Missing</h2>
                <div style="margin-bottom:15px; display:flex; gap:10px; flex-wrap:wrap;">
                    <button class="btn btn-sm btn-accent" onclick="listAllPlatforms()">🚀 List on ALL Remaining Platforms</button>
                    <button class="btn btn-sm btn-sec" onclick="loadOpportunities()">🔄 Refresh</button>
                </div>
                <div id="listStatus" style="display:none;" class="status-msg status-info"></div>
                <div style="margin:15px 0; display:flex; gap:8px;">
                    <button class="tab-btn active" id="oppSubtabRemaining" onclick="switchOppSubtab('remaining')">⏳ Remaining (<span id="oppRemainingCount">0</span>)</button>
                    <button class="tab-btn" id="oppSubtabHistory" onclick="switchOppSubtab('history')">📜 History (<span id="oppHistoryCount">0</span>)</button>
                </div>
                <div class="item-list" id="opportunitiesListRemaining"></div>
                <div class="item-list" id="opportunitiesListHistory" style="display:none;"></div>
            </div>
        </div>

        <div id="discovery" class="panel">
            <div class="glass-card">
                <h2>Run Discovery — Listing Platforms Only</h2>
                <p style="margin-bottom:15px; font-size:14px; color:var(--text-muted);">Finds directories/platforms where Gaper can be submitted as a product listing. Article/thread discovery for Contra replies happens separately from the Articles tab (generate by topic).</p>
                <button class="btn btn-accent" onclick="runDiscoveryJob()">🔍 Find Listing Platforms</button>
            </div>
            <div class="glass-card">
                <h2>System Logs</h2>
                <div class="logs-window" id="logsWindow">[System Initialized]<br>[Waiting for actions...]</div>
            </div>
        </div>
    </div>

    <script>
        function switchTab(tabId) {
            document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.getElementById(tabId).classList.add('active');
            event.target.classList.add('active');
            if (tabId === 'dashboard') loadStatsAndBrand();
            if (tabId === 'articles') loadDrafts();
            if (tabId === 'backlinks') loadBacklinks();
            if (tabId === 'listings') loadOpportunities();
        }

        function toggleTargetUrlField() {
            const platform = document.getElementById('draftPlatform').value;
            document.getElementById('targetUrlGroup').style.display = platform === 'contra' ? 'block' : 'none';
            if (platform === 'contra') {
                const saved = localStorage.getItem('gaper_last_contra_url');
                const field = document.getElementById('draftTargetUrl');
                if (saved && !field.value) field.value = saved;
            }
        }

        async function generateDraft() {
    const platform = document.getElementById('draftPlatform').value;
    const topic = document.getElementById('draftTopic').value;
    const target_url = document.getElementById('draftTargetUrl').value;
    
    // Don't require topic - it can auto-generate
    // if (!topic) return alert('Enter a topic');  // REMOVE THIS LINE
    
    if (platform === 'contra' && !target_url) {
        return alert('Contra needs a target thread URL');
    }
    if (platform === 'contra' && target_url) {
        localStorage.setItem('gaper_last_contra_url', target_url);
    }
    
    addLog(`Generating ${platform} draft...`);
    
    const res = await fetch('/api/drafts/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
            platform: platform, 
            topic: topic || "",  // Send empty string if no topic
            target_url: platform === 'contra' ? target_url : null 
        })
    });
    
    const data = await res.json();
    addLog(data.status === 'success' ? '✅ Draft generated' : `❌ ${data.detail}`);
    loadDrafts();
}

        async function loadDrafts() {
            const drafts = await (await fetch('/api/drafts')).json();
            const container = document.getElementById('draftsList');
            container.innerHTML = '';
            const active = drafts.filter(d => d.status === 'draft' || d.status === 'failed' || d.status === 'awaiting_confirm');
            if (!active.length) { container.innerHTML = '<div style="color:var(--text-muted)">No drafts yet - generate one above.</div>'; return; }
            active.forEach(d => {
                const badgeClass = d.status === 'failed' ? 'badge-failed' : d.status === 'awaiting_confirm' ? 'badge-ghost' : 'badge-pending';
                const waitingOnYou = d.status === 'awaiting_confirm';
                container.innerHTML += `
                    <div class="list-item" id="draft-${d.id}">
                        <div class="list-header">
                            <span class="list-title">[${d.platform.toUpperCase()}] ${d.title || d.topic}</span>
                            <span class="badge ${badgeClass}">${waitingOnYou ? 'waiting on your Publish' : d.status}</span>
                        </div>
                        ${d.target_url ? `<div style="font-size:12px;color:var(--text-muted);">Target: ${d.target_url}</div>` : ''}
                        ${d.detail && !waitingOnYou ? `<div style="font-size:11px;color:var(--warning);">${d.detail}</div>` : ''}
                        ${waitingOnYou ? `<div style="font-size:12px;color:var(--accent);margin-top:6px;">Browser is open with this typed into your workspace. Review it, click Publish yourself in Notion, then confirm below.</div>` : ''}
                        <textarea id="draft-content-${d.id}" rows="6" style="width:100%;background:rgba(0,0,0,0.4);border:1px solid var(--glass-border);border-radius:8px;padding:12px;color:#fff;margin-top:10px;" ${waitingOnYou ? 'disabled' : ''}>${d.content || ''}</textarea>
                        <div class="actions-bar">
                            ${waitingOnYou ? `
                                <button class="btn btn-sm btn-success" onclick="confirmNotionPublish(${d.id})">✅ Confirm Published</button>
                                <button class="btn btn-sm" style="background:rgba(255,0,64,0.15);color:#ff0040;border:1px solid #ff0040;" onclick="discardDraft(${d.id})">🗑️ Discard</button>
                            ` : `
                                <button class="btn btn-sm btn-accent" onclick="saveDraftEdit(${d.id})">💾 Save Edit</button>
                                <button class="btn btn-sm btn-sec" onclick="improveDraft(${d.id})">🔄 Improve</button>
                                <button class="btn btn-sm" style="background:rgba(255,0,64,0.15);color:#ff0040;border:1px solid #ff0040;" onclick="discardDraft(${d.id})">🗑️ Discard</button>
                                <button class="btn btn-sm btn-success" onclick="submitDraft(${d.id})">✅ Submit — Post Live</button>
                            `}
                        </div>
                    </div>
                `;
            });
        }

        async function saveDraftEdit(id) {
            const content = document.getElementById(`draft-content-${id}`).value;
            await fetch(`/api/drafts/${id}/edit`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content })
            });
            addLog(`Saved edit for draft ${id}`);
        }

        async function improveDraft(id) {
            const feedback = prompt('What should change about this draft?');
            if (!feedback) return;
            addLog(`Improving draft ${id}...`);
            await fetch(`/api/drafts/${id}/improve`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ feedback })
            });
            loadDrafts();
        }

        async function discardDraft(id) {
            if (!confirm('Discard this draft?')) return;
            await fetch(`/api/drafts/${id}`, { method: 'DELETE' });
            addLog(`Discarded draft ${id}`);
            loadDrafts();
        }

        async function submitDraft(id) {
            if (!confirm('Post this LIVE now to your real account?')) return;
            addLog(`Submitting draft ${id}...`);
            const res = await fetch(`/api/drafts/${id}/submit`, { method: 'POST' });
            const data = await res.json();
            addLog(data.status === 'success' ? `✅ ${data.detail}` : `❌ ${data.detail}`);
            loadDrafts();
            loadBacklinks();
        }

        async function confirmNotionPublish(id) {
            if (!confirm('Have you already clicked Publish in the Notion browser window?')) return;
            addLog(`Confirming draft ${id} as published...`);
            const res = await fetch(`/api/drafts/${id}/confirm-notion`, { method: 'POST' });
            const data = await res.json();
            addLog(data.status === 'success' ? `✅ ${data.detail}` : `❌ ${data.detail}`);
            loadDrafts();
            loadBacklinks();
        }

        function addLog(msg) {
            const win = document.getElementById('logsWindow');
            win.innerHTML += `<br>[${new Date().toLocaleTimeString()}] ${msg}`;
            win.scrollTop = win.scrollHeight;
        }

        function showStatus(msg, type='info') {
            const el = document.getElementById('listStatus');
            el.style.display = 'block';
            el.className = `status-msg status-${type}`;
            el.textContent = msg;
        }

        async function loadStatsAndBrand() {
            try {
                const brand = await (await fetch('/api/brand-profile')).json();
                document.getElementById('brandLogo').src = brand.logo_url || '';
                document.getElementById('brandDesc').value = brand.description || '';
                document.getElementById('brandUsps').value = brand.usps || '';
                const threads = await (await fetch('/api/threads')).json();
                const opps = await (await fetch('/api/opportunities')).json();
                const backlinks = await (await fetch('/api/backlinks')).json();
                document.getElementById('statPending').innerText = threads.filter(t => t.status === 'pending_approval').length;
                document.getElementById('statPosted').innerText = threads.filter(t => t.status === 'posted').length;
                document.getElementById('statOpps').innerText = opps.filter(o => o.status === 'discovered' || o.status === 'pending_listing').length;
                document.getElementById('statListed').innerText = opps.filter(o => o.status === 'listed').length;
                document.getElementById('statBacklinks').innerText = backlinks.filter(b => b.status !== 'deleted').length;
            } catch(e) { console.error(e); }
        }

        async function triggerScrapeBrand() {
            addLog("Rescraping Gaper.io...");
            await fetch('/api/rescrape-brand', { method: 'POST' });
            addLog("Done!");
            loadStatsAndBrand();
        }

        async function runManualPipeline() {
            const url = document.getElementById('manualUrl').value;
            if (!url) return alert("Enter a URL");
            addLog(`Processing: ${url}`);
            const res = await fetch('/api/run-pipeline', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: new URLSearchParams({ url })
            });
            if (res.ok) { addLog("Done! Check QA Approvals."); loadStatsAndBrand(); }
            else { addLog("Failed."); }
        }

        async function loadApprovals() {
            const threads = await (await fetch('/api/threads')).json();
            const container = document.getElementById('approvalsList');
            container.innerHTML = '';
            const activePlatforms = ['contra', 'notion'];
            const pending = threads.filter(t => t.status === 'pending_approval' &&
                activePlatforms.some(p => (t.platform || '').toLowerCase().includes(p)));
            if (!pending.length) { container.innerHTML = '<div style="color:var(--text-muted)">No pending approvals.</div>'; return; }
            pending.forEach(t => {
                container.innerHTML += `
                    <div class="list-item">
                        <div class="list-header">
                            <a href="${t.url}" target="_blank" class="list-title">${t.url}</a>
                            <span class="badge ${t.is_ghost ? 'badge-ghost' : 'badge-pending'}">${t.is_ghost ? 'Ghost' : 'Citation'}</span>
                        </div>
                        <div class="scores-wrapper" style="margin:10px 0;background:rgba(0,0,0,0.2);padding:10px;border-radius:8px;">
                            <div><span class="score-val" style="font-size:20px">${t.seo_score||0}%</span><br><span class="score-label" style="font-size:9px">SEO</span></div>
                            <div><span class="score-val" style="font-size:20px">${t.geo_score||0}%</span><br><span class="score-label" style="font-size:9px">GEO</span></div>
                            <div><span class="score-val" style="font-size:20px">${t.aeo_score||0}%</span><br><span class="score-label" style="font-size:9px">AEO</span></div>
                        </div>
                        <textarea id="reply-${t.id}" rows="6" style="width:100%;background:rgba(0,0,0,0.4);border:1px solid var(--glass-border);border-radius:8px;padding:12px;color:#fff;">${t.generated_reply||''}</textarea>
                        <div class="actions-bar">
                            <button class="btn btn-sm btn-accent" onclick="saveDraft(${t.id})">💾 Save</button>
                            <button class="btn btn-sm btn-sec" onclick="rejectDraft(${t.id})">🔄 Regenerate</button>
                            <button class="btn btn-sm btn-success" onclick="approveDraft(${t.id})">✅ Approve & Post</button>
                        </div>
                    </div>
                `;
            });
        }

        async function saveDraft(id) {
            const text = document.getElementById(`reply-${id}`).value;
            await fetch(`/api/save/${id}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ reply_text: text })
            });
            addLog(`Saved draft ${id}`);
        }

        async function approveDraft(id) {
            addLog(`Approving ${id}...`);
            await fetch(`/api/approve/${id}`, { method: 'POST' });
            addLog(`Posted!`);
            loadApprovals();
            loadStatsAndBrand();
        }

        async function rejectDraft(id) {
            const feedback = prompt("Feedback for regeneration:");
            if (!feedback) return;
            addLog(`Regenerating ${id}...`);
            await fetch(`/api/reject/${id}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ feedback })
            });
            loadApprovals();
        }

        async function loadBacklinks() {
            const links = await (await fetch('/api/backlinks')).json();
            const container = document.getElementById('backlinksList');
            container.innerHTML = '';
            if (!links.length) { container.innerHTML = '<div style="color:var(--text-muted)">No backlinks posted yet.</div>'; return; }
            links.forEach(b => {
                const statusClass = b.status === 'deleted' ? 'badge-failed' : b.status === 'edited' ? 'badge-pending' : 'badge-posted';
                const linkCheck = b.link_check_status === 'still_live' ? '<span class="badge badge-listed">✅ Link still live</span>'
                    : b.link_check_status === 'link_missing' ? '<span class="badge badge-failed">⚠️ Link missing - check manually</span>'
                    : b.follow_up_due_at ? '<span class="badge badge-pending">🕐 Follow-up pending</span>' : '';
                container.innerHTML += `
                    <div class="list-item" id="bl-${b.id}">
                        <div class="list-header">
                            <a href="${b.target_url}" target="_blank" class="list-title">[${b.platform.toUpperCase()}] ${b.target_url}</a>
                            <span class="badge ${statusClass}">${b.status}</span>
                        </div>
                        <textarea id="bl-content-${b.id}" rows="4" style="width:100%;background:rgba(0,0,0,0.4);border:1px solid var(--glass-border);border-radius:8px;padding:12px;color:#fff;" ${b.status === 'deleted' ? 'disabled' : ''}>${b.content || ''}</textarea>
                        ${b.note ? `<div style="font-size:11px;color:var(--warning);margin-top:6px;">⚠️ ${b.note}</div>` : ''}
                        <div class="meta-info"><span>Posted: ${new Date(b.created_at).toLocaleString()}</span> ${linkCheck}</div>
                        <div class="actions-bar">
                            ${b.status !== 'deleted' ? `
                                <button class="btn btn-sm btn-accent" onclick="editBacklink(${b.id}, '${b.platform}')">💾 Save Edit</button>
                                <button class="btn btn-sm btn-sec" onclick="deleteBacklink(${b.id}, '${b.platform}')">🗑️ Delete Live</button>
                            ` : ''}
                        </div>
                    </div>
                `;
            });
        }

        async function checkOverdueBacklinks() {
            const statusEl = document.getElementById('backlinkCheckStatus');
            statusEl.style.display = 'block';
            statusEl.textContent = '🕐 Checking backlinks that passed their 7-day mark...';
            const res = await fetch('/api/backlinks/check-overdue', { method: 'POST' });
            const data = await res.json();
            statusEl.textContent = `✅ Checked ${data.checked} — ${data.still_live} still live, ${data.missing} missing/need a look.`;
            addLog(`Backlink health check: ${data.checked} checked, ${data.still_live} still live, ${data.missing} missing.`);
            loadBacklinks();
        }

        async function editBacklink(id, platform) {
            const content = document.getElementById(`bl-content-${id}`).value;
            addLog(`Editing ${platform} backlink ${id}...`);
            const res = await fetch(`/api/backlinks/${id}/edit`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content })
            });
            const data = await res.json();
            addLog(data.status === 'success' ? `✅ ${data.detail}` : `❌ ${data.detail}`);
            loadBacklinks();
        }

        async function deleteBacklink(id, platform) {
            if (!confirm(`Delete this live ${platform} backlink? This cannot always be undone.`)) return;
            addLog(`Deleting ${platform} backlink ${id}...`);
            const res = await fetch(`/api/backlinks/${id}/delete`, { method: 'POST' });
            const data = await res.json();
            addLog(data.status === 'success' ? `✅ ${data.detail}` : `❌ ${data.detail}`);
            loadBacklinks();
        }

        function switchOppSubtab(which) {
            document.getElementById('oppSubtabRemaining').classList.toggle('active', which === 'remaining');
            document.getElementById('oppSubtabHistory').classList.toggle('active', which === 'history');
            document.getElementById('opportunitiesListRemaining').style.display = which === 'remaining' ? '' : 'none';
            document.getElementById('opportunitiesListHistory').style.display = which === 'history' ? '' : 'none';
        }

        async function loadOpportunities() {
            const opps = await (await fetch('/api/opportunities')).json();
            const remainingContainer = document.getElementById('opportunitiesListRemaining');
            const historyContainer = document.getElementById('opportunitiesListHistory');
            remainingContainer.innerHTML = '';
            historyContainer.innerHTML = '';

            // Remaining = only platforms Gaper is NOT listed on yet (discovered or mid-review).
            // History = every platform ever attempted (listed OR failed) - nothing here ever
            // gets deleted, it just moves out of the Remaining list once it's actually done.
            const remaining = opps.filter(o => o.status !== 'listed' && o.status !== 'failed');
            const history = opps.filter(o => o.status === 'listed' || o.status === 'failed');

            document.getElementById('oppRemainingCount').textContent = remaining.length;
            document.getElementById('oppHistoryCount').textContent = history.length;

            if (!remaining.length) {
                remainingContainer.innerHTML = '<div style="color:var(--text-muted)">No platforms left to list on right now. Run discovery to find more.</div>';
            }
            remaining.sort((a, b) => (b.relevance_score || 0) - (a.relevance_score || 0));
            remaining.forEach(o => {
                const statusClass = o.status === 'pending_listing' ? 'badge-pending' : 'badge-pending';
                const statusLabel = o.status === 'pending_listing' ? '📝 Form Filled - Review' : '⏳ Discovered';
                const score = o.relevance_score || 0;
                const scoreColor = score >= 60 ? 'var(--success)' : score >= 35 ? 'var(--warning)' : 'var(--text-muted)';
                remainingContainer.innerHTML += `
                    <div class="list-item">
                        <div class="list-header">
                            <a href="${o.url}" target="_blank" class="list-title">${o.url}</a>
                            <span class="badge ${statusClass}">${statusLabel}</span>
                        </div>
                        <div style="font-size:12px;color:var(--text-muted);">Competitors: ${o.competitors_found || 'None'} &nbsp;|&nbsp; Relevance: <b style="color:${scoreColor}">${score}/100</b></div>
                        <div class="draft-preview">${o.generated_pitch || 'Not generated yet.'}</div>
                        <div class="actions-bar">
                            ${o.status === 'pending_listing' ? `
                                <button class="btn btn-sm btn-success" onclick="confirmListing(${o.id})">✅ Confirm Submit</button>
                                <button class="btn btn-sm btn-sec" onclick="cancelListing(${o.id})">❌ Cancel</button>
                            ` : `<button class="btn btn-sm" onclick="listGaper(${o.id})">🚀 Auto-fill Form</button>`}
                        </div>
                    </div>
                `;
            });

            if (!history.length) {
                historyContainer.innerHTML = '<div style="color:var(--text-muted)">Nothing submitted yet.</div>';
            }
            history.sort((a, b) => new Date(b.updated_at || 0) - new Date(a.updated_at || 0));
            history.forEach(o => {
                const statusClass = o.status === 'listed' ? 'badge-listed' : 'badge-failed';
                const statusLabel = o.status === 'listed' ? '✅ Listed' : '❌ Failed';
                historyContainer.innerHTML += `
                    <div class="list-item">
                        <div class="list-header">
                            <a href="${o.url}" target="_blank" class="list-title">${o.url}</a>
                            <span class="badge ${statusClass}">${statusLabel}</span>
                        </div>
                        <div class="draft-preview">${o.generated_pitch || ''}</div>
                        ${o.posted_url ? `<div style="margin-top:6px;"><a href="${o.posted_url}" target="_blank" class="btn btn-sm btn-accent">🔗 View Live Listing</a></div>` : ''}
                    </div>
                `;
            });
        }

        async function confirmListing(oppId) {
            addLog(`Submitting listing ${oppId}...`);
            const res = await fetch(`/api/confirm-listing/${oppId}`, { method: 'POST' });
            const data = await res.json();
            addLog(data.status === 'success' ? `✅ ${data.detail}` : `❌ ${data.detail}`);
            loadOpportunities();
        }

        async function cancelListing(oppId) {
            addLog(`Cancelling listing ${oppId}...`);
            const res = await fetch(`/api/cancel-listing/${oppId}`, { method: 'POST' });
            const data = await res.json();
            addLog(`Cancelled.`);
            loadOpportunities();
        }

        async function listGaper(id) {
            addLog(`🚀 Listing Gaper...`);
            showStatus('Processing...', 'info');
            const res = await fetch(`/api/list/${id}`, { method: 'POST' });
            const data = await res.json();
            if (data.status === 'success') {
                addLog(`✅ Session: ${data.session_id}`);
                showStatus(`✅ Ready! Session: ${data.session_id}`, 'success');
                alert(`✅ Listing prepared!\nSession: ${data.session_id}\nCheck browser window!`);
            } else {
                addLog(`❌ Failed: ${data.detail}`);
                showStatus(`❌ ${data.detail}`, 'error');
            }
            loadOpportunities();
            loadStatsAndBrand();
        }

        let listingAll = false;
        async function listAllPlatforms() {
            if (listingAll) return;
            if (!confirm('List Gaper on ALL discovered platforms?')) return;
            listingAll = true;
            showStatus('🚀 Listing all platforms...', 'info');
            addLog('🚀 Bulk listing started...');
            const res = await fetch('/api/list-all', { method: 'POST' });
            const data = await res.json();
            if (data.status === 'success') {
                addLog(`✅ ${data.count} platforms processed`);
                showStatus(`✅ ${data.count} platforms done!`, 'success');
                alert(`✅ ${data.count} platforms processed!\nCheck browser windows.`);
            } else {
                addLog(`❌ Failed: ${data.detail}`);
                showStatus(`❌ ${data.detail}`, 'error');
            }
            listingAll = false;
            loadOpportunities();
            loadStatsAndBrand();
        }

        async function runDiscoveryJob() {
            addLog("🔍 Searching for listing platforms...");
            const res = await fetch('/api/discover-listings', { method: 'POST' });
            const data = await res.json();
            addLog(`✅ Found ${data.count} new listing platforms!`);
            loadStatsAndBrand();
            loadOpportunities();
        }

        loadStatsAndBrand();
        loadApprovals();
        toggleTargetUrlField();
        loadOpportunities();
    </script>
</body>
</html>
"""

# ============ API ENDPOINTS ============

@app.get("/", response_class=HTMLResponse)
def get_dashboard(request: Request):
    return HTMLResponse(content=HTML_TEMPLATE, status_code=200)

@app.get("/api/brand-profile")
def api_brand_profile():
    return get_brand_profile()

@app.post("/api/rescrape-brand")
def api_rescrape_brand():
    return scrape_gaper_brand()

@app.get("/api/threads")
def api_threads():
    db = SessionLocal()
    try:
        threads = db.query(ThreadMemory).all()
        result = []
        for t in threads:
            scores = evaluate_seo_geo_aeo(t.generated_reply or "", t.is_ghost)
            result.append({
                "id": t.id, "url": t.url, "platform": t.platform,
                "status": t.status, "generated_reply": t.generated_reply,
                "is_ghost": t.is_ghost,
                "seo_score": scores["seo"], "geo_score": scores["geo"], "aeo_score": scores["aeo"]
            })
        return result
    finally:
        db.close()

@app.get("/api/opportunities")
def api_opportunities():
    db = SessionLocal()
    try:
        return db.query(ListingOpportunity).all()
    finally:
        db.close()

@app.post("/api/discover")
def api_discover():
    count = run_global_discovery()
    return {"count": count}

@app.post("/api/discover-listings")
def api_discover_listings():
    """Discovery scoped to ONLY product-listing directories (Track B) - no article/thread discovery mixed in."""
    from src.discovery import discover_listing_platforms
    new_listings = discover_listing_platforms()
    return {"count": len(new_listings)}

@app.post("/api/run-pipeline")
def api_run_pipeline(url: str = Form(...)):
    try:
        return run_pipeline(url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/save/{thread_id}")
def api_save_draft(thread_id: int, edit: DraftEdit):
    db = SessionLocal()
    try:
        thread = db.query(ThreadMemory).filter(ThreadMemory.id == thread_id).first()
        if not thread:
            raise HTTPException(status_code=404, detail="Not found")
        thread.generated_reply = edit.reply_text
        db.commit()
        return {"status": "success"}
    finally:
        db.close()

@app.post("/api/approve/{thread_id}")
def api_approve_draft(thread_id: int):
    approve_and_queue_post(thread_id)
    return {"status": "success"}

@app.post("/api/reject/{thread_id}")
def api_reject_draft(thread_id: int, feedback: RejectFeedback):
    return qa_loop(thread_id, feedback.feedback, feedback.iteration)

# ============ NEW: GAPER LISTING APIS (Outreach removed) ============

# @app.post("/api/list/{opp_id}")
# def api_list_gaper(opp_id: int):
#     from src.generic_listing_agent import start_generic_listing
#     db = SessionLocal()
#     opp = db.query(ListingOpportunity).filter(ListingOpportunity.id == opp_id).first()
#     if not opp:
#         db.close()
#         return {"status": "failed", "detail": "Platform not found"}
    
#     result = start_generic_listing(
#         url=opp.url,
#         platform_name=opp.domain or opp.url.split("/")[2]
#     )
    
#     if result['status'] == 'awaiting_approval':
#         opp.status = 'pending_listing'
#         opp.generated_pitch = f"Session: {result['session_id']}\nScreenshot: {result.get('screenshot_path', 'N/A')}"
#         db.commit()
#         db.close()
#         return {
#             "status": "success",
#             "detail": f"Listing prepared for {opp.url}",
#             "session_id": result['session_id'],
#             "screenshot": result.get('screenshot_path')
#         }
#     db.close()
#     return result
@app.post("/api/list/{opp_id}")
def api_list_gaper(opp_id: int):
    """List Gaper on a specific platform using generic_listing_agent"""
    from src.generic_listing_agent import start_generic_listing
    from src.database import SessionLocal, ListingOpportunity
    
    db = SessionLocal()
    opp = db.query(ListingOpportunity).filter(ListingOpportunity.id == opp_id).first()
    
    if not opp:
        db.close()
        return {"status": "failed", "detail": "Platform not found"}
    
    # ✅ FIX: opp.platform ki jagah opp.domain use karo
    platform_name = opp.domain or opp.url.split("/")[2]
    
    result = start_generic_listing(
        url=opp.url,
        platform_name=platform_name,
        # use_proxy=True,
        # use_captcha=True
    )

    if result['status'] == 'awaiting_approval':
        opp.status = 'pending_listing'
        opp.generated_pitch = f"Session: {result['session_id']}\nScreenshot: {result.get('screenshot_path', 'N/A')}\nStatus: Awaiting approval"
        opp_url = opp.url
        db.commit()
        db.close()
        return {
            "status": "success",
            "detail": f"Listing prepared for {opp_url}",
            "session_id": result['session_id'],
            "screenshot": result.get('screenshot_path')
        }
    
    # if result['status'] == 'awaiting_approval':
    #     opp.status = 'pending_listing'
    #     opp.generated_pitch = f"Session: {result['session_id']}\nScreenshot: {result.get('screenshot_path', 'N/A')}\nStatus: Awaiting approval"
    #     db.commit()
    #     db.close()
    #     return {
    #         "status": "success",
    #         "detail": f"Listing prepared for {opp.url}",
    #         "session_id": result['session_id'],
    #         "screenshot": result.get('screenshot_path')
    #     }
    else:
        db.close()
        return result
@app.post("/api/list-all")
def api_list_all_platforms():
    from src.generic_listing_agent import start_generic_listing
    import time
    db = SessionLocal()
    platforms = db.query(ListingOpportunity).filter(
        ListingOpportunity.status == 'discovered'
    ).all()
    
    if not platforms:
        db.close()
        return {"status": "failed", "detail": "No platforms found"}
    
    count = 0
    for platform in platforms:
        try:
            result = start_generic_listing(
                url=platform.url,
                platform_name=platform.domain or platform.url.split("/")[2]
            )
            if result['status'] == 'awaiting_approval':
                platform.status = 'pending_listing'
                platform.generated_pitch = f"Session: {result['session_id']}"
                count += 1
            else:
                platform.status = 'failed'
                platform.generated_pitch = f"Failed: {result.get('detail', 'Unknown')}"
            db.commit()
            time.sleep(3)
        except Exception as e:
            platform.status = 'failed'
            platform.generated_pitch = f"Error: {str(e)}"
            db.commit()
    
    db.close()
    return {"status": "success", "count": count}

def _extract_session_id(generated_pitch: str) -> str:
    """generated_pitch stores 'Session: abc123\\n...' - pull the id back out."""
    if not generated_pitch:
        return None
    for line in generated_pitch.split("\n"):
        if line.strip().startswith("Session:"):
            return line.split("Session:", 1)[1].strip()
    return None


@app.post("/api/confirm-listing/{opp_id}")
def api_confirm_listing(opp_id: int):
    """Human clicked 'Confirm Submit' after reviewing the auto-filled form screenshot."""
    db = SessionLocal()
    try:
        opp = db.query(ListingOpportunity).filter(ListingOpportunity.id == opp_id).first()
        if not opp:
            raise HTTPException(status_code=404, detail="Listing opportunity not found")

        session_id = _extract_session_id(opp.generated_pitch)
        if not session_id:
            return {"status": "failed", "detail": "No active browser session found for this listing - it may have expired. Click 'Auto-fill Form' again."}

        result = confirm_generic_listing(session_id)
        if result.get("status") == "success":
            opp.status = "listed"
            opp.posted_url = result.get("posted_url")
            opp.generated_pitch = f"✅ Submitted: {result.get('detail')}"
        else:
            opp.status = "failed"
            opp.generated_pitch = f"❌ Submit failed: {result.get('detail')}"
        db.commit()
        return result
    finally:
        db.close()


@app.post("/api/cancel-listing/{opp_id}")
def api_cancel_listing(opp_id: int):
    """Human clicked 'Cancel' - closes the open browser without submitting."""
    db = SessionLocal()
    try:
        opp = db.query(ListingOpportunity).filter(ListingOpportunity.id == opp_id).first()
        if not opp:
            raise HTTPException(status_code=404, detail="Listing opportunity not found")

        session_id = _extract_session_id(opp.generated_pitch)
        if session_id:
            cancel_generic_listing(session_id)

        opp.status = "discovered"
        opp.generated_pitch = "Cancelled by user - not submitted."
        db.commit()
        return {"status": "cancelled"}
    finally:
        db.close()


# ============ ARTICLE DRAFT STUDIO APIS (Contra/Notion only) ============

@app.post("/api/drafts/generate")
def api_generate_draft(draft: DraftGenerate):
    # If topic is empty, send None (triggers auto-generate in article_studio)
    topic = draft.topic if draft.topic and draft.topic.strip() else None
    
    print(f"📥 Received: platform={draft.platform}, topic='{draft.topic}', resolved_topic={topic}")
    
    result = article_studio.generate_draft(
        platform=draft.platform,
        topic=topic,  # ✅ Use the resolved topic, not draft.topic
        target_url=draft.target_url
    )
    
    if result.get("status") != "success":
        raise HTTPException(status_code=400, detail=result.get("detail", "Generation failed"))
    
    return result

@app.get("/api/drafts")
def api_get_drafts():
    drafts = get_article_drafts()
    return [{
        "id": d.id, "platform": d.platform, "topic": d.topic,
        "target_url": d.target_url, "title": d.title, "content": d.content,
        "status": d.status, "detail": d.detail,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    } for d in drafts]


@app.post("/api/drafts/{draft_id}/edit")
def api_edit_draft(draft_id: int, edit: DraftEditContent):
    from src.database import update_article_draft
    if not get_article_draft(draft_id):
        raise HTTPException(status_code=404, detail="Draft not found")
    update_article_draft(draft_id, content=edit.content, title=edit.title)
    return {"status": "success"}


@app.post("/api/drafts/{draft_id}/improve")
def api_improve_draft(draft_id: int, fb: DraftFeedback):
    result = article_studio.regenerate_draft(draft_id, fb.feedback)
    if result.get("status") != "success":
        raise HTTPException(status_code=400, detail=result.get("detail", "Regeneration failed"))
    return result


@app.delete("/api/drafts/{draft_id}")
def api_delete_draft(draft_id: int):
    article_studio.discard_draft(draft_id)
    return {"status": "success"}


@app.post("/api/drafts/{draft_id}/submit")
def api_submit_draft(draft_id: int):
    """Posts LIVE using the same saved session Contra/Notion already use."""
    return article_studio.submit_draft(draft_id)


@app.post("/api/drafts/{draft_id}/confirm-notion")
def api_confirm_notion_publish(draft_id: int):
    """Call only after manually clicking Publish in the Notion browser window."""
    return article_studio.confirm_notion_publish(draft_id)


# ============ NEW BACKLINKS APIS (live edit/delete) ============

@app.get("/api/backlinks")
def api_get_backlinks():
    links = get_posted_backlinks()
    return [{
        "id": l.id, "platform": l.platform, "target_url": l.target_url,
        "content": l.content, "status": l.status, "note": l.note,
        "created_at": l.created_at.isoformat() if l.created_at else None,
        "follow_up_due_at": l.follow_up_due_at.isoformat() if l.follow_up_due_at else None,
        "link_check_status": l.link_check_status,
        "last_checked_at": l.last_checked_at.isoformat() if l.last_checked_at else None,
    } for l in links]


@app.post("/api/backlinks/check-overdue")
def api_check_overdue_backlinks():
    result = check_overdue_backlinks(days=7)
    return result
@app.post("/api/backlinks/{backlink_id}/edit")
def api_edit_backlink(backlink_id: int, edit: BacklinkEdit):
    db = SessionLocal()
    try:
        link = db.query(PostedBacklink).filter(PostedBacklink.id == backlink_id).first()
        if not link:
            raise HTTPException(status_code=404, detail="Backlink not found")

        if link.platform == "notion" and link.platform_post_id:
            result = edit_live_notion_page(link.platform_post_id, edit.content)
            if result["status"] == "success":
                update_backlink_record(backlink_id, content=edit.content, status="edited")
            return result
        else:
            # Contra (and anything else without a live edit API): local record only,
            # matches the documented limitation in adapters.ContraAdapter.
            note = "Local record only - this platform has no API to edit the live post. Edit it manually on the site."
            update_backlink_record(backlink_id, content=edit.content, status="edited", note=note)
            return {"status": "success", "detail": f"Local record updated. {note}"}
    finally:
        db.close()


@app.post("/api/backlinks/{backlink_id}/delete")
def api_delete_backlink(backlink_id: int):
    db = SessionLocal()
    try:
        link = db.query(PostedBacklink).filter(PostedBacklink.id == backlink_id).first()
        if not link:
            raise HTTPException(status_code=404, detail="Backlink not found")

        if link.platform == "notion" and link.platform_post_id:
            result = delete_live_notion_page(link.platform_post_id)
            if result["status"] == "success":
                update_backlink_record(backlink_id, status="deleted")
            return result
        else:
            note = "Local record only - this platform has no API to delete the live post. Delete it manually on the site."
            update_backlink_record(backlink_id, status="deleted", note=note)
            return {"status": "success", "detail": f"Local record marked deleted. {note}"}
    finally:
        db.close()