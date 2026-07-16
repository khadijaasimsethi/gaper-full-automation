from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from src.database import SessionLocal, ThreadMemory, ListingOpportunity
from src.gaper_scraper import get_brand_profile, scrape_gaper_brand
from src.discovery import discover_threads
from src.pipeline import approve_and_queue_post, run_pipeline, run_global_discovery
from src.brain import qa_loop, evaluate_seo_geo_aeo
from src.generic_listing_agent import start_generic_listing
import config

app = FastAPI(title="Gaper SEO/GEO/AEO AI Backlink Agent Dashboard")

class DraftEdit(BaseModel):
    reply_text: str

class RejectFeedback(BaseModel):
    feedback: str
    iteration: int = 1

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
            <button class="tab-btn" onclick="switchTab('approvals')">✅ QA Approvals</button>
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

        <div id="approvals" class="panel">
            <div class="glass-card">
                <h2>Pending Approvals</h2>
                <div class="item-list" id="approvalsList"></div>
            </div>
        </div>

        <div id="listings" class="panel">
            <div class="glass-card">
                <h2>📋 Gaper Listing - Platforms Where Missing</h2>
                <div style="margin-bottom:15px; display:flex; gap:10px; flex-wrap:wrap;">
                    <button class="btn btn-sm btn-accent" onclick="listAllPlatforms()">🚀 List on ALL Platforms</button>
                    <button class="btn btn-sm btn-sec" onclick="loadOpportunities()">🔄 Refresh</button>
                </div>
                <div id="listStatus" style="display:none;" class="status-msg status-info"></div>
                <div class="item-list" id="opportunitiesList"></div>
            </div>
        </div>

        <div id="discovery" class="panel">
            <div class="glass-card">
                <h2>Run Discovery</h2>
                <p style="margin-bottom:15px; font-size:14px; color:var(--text-muted);">Find new platforms where Gaper is missing.</p>
                <button class="btn btn-accent" onclick="runDiscoveryJob()">🔍 Run Discovery</button>
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
            if (tabId === 'approvals') loadApprovals();
            if (tabId === 'listings') loadOpportunities();
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
                document.getElementById('statPending').innerText = threads.filter(t => t.status === 'pending_approval').length;
                document.getElementById('statPosted').innerText = threads.filter(t => t.status === 'posted').length;
                document.getElementById('statOpps').innerText = opps.filter(o => o.status === 'discovered' || o.status === 'pending_listing').length;
                document.getElementById('statListed').innerText = opps.filter(o => o.status === 'listed').length;
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
            const pending = threads.filter(t => t.status === 'pending_approval');
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

        async function loadOpportunities() {
            const opps = await (await fetch('/api/opportunities')).json();
            const container = document.getElementById('opportunitiesList');
            container.innerHTML = '';
            if (!opps.length) { container.innerHTML = '<div style="color:var(--text-muted)">No platforms found. Run discovery.</div>'; return; }
            opps.forEach(o => {
                const statusClass = o.status === 'listed' ? 'badge-listed' : o.status === 'failed' ? 'badge-failed' : 'badge-pending';
                const statusLabel = o.status === 'listed' ? '✅ Listed' : o.status === 'failed' ? '❌ Failed' : '⏳ Discovered';
                container.innerHTML += `
                    <div class="list-item">
                        <div class="list-header">
                            <a href="${o.url}" target="_blank" class="list-title">${o.url}</a>
                            <span class="badge ${statusClass}">${statusLabel}</span>
                        </div>
                        <div style="font-size:12px;color:var(--text-muted);">Competitors: ${o.competitors_found || 'None'}</div>
                        <div class="draft-preview">${o.generated_pitch || 'Not generated yet.'}</div>
                        <div class="actions-bar">
                            ${o.status !== 'listed' ? `<button class="btn btn-sm" onclick="listGaper(${o.id})">🚀 List Gaper</button>` : `<span style="color:var(--success)">✅ Already Listed</span>`}
                        </div>
                    </div>
                `;
            });
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
            addLog("🔍 Running discovery...");
            const res = await fetch('/api/discover', { method: 'POST' });
            const data = await res.json();
            addLog(`✅ Found ${data.count} new platforms!`);
            loadStatsAndBrand();
            loadOpportunities();
        }

        loadStatsAndBrand();
        loadApprovals();
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

# @app.post("/api/confirm-listing/{session_id}")
# def api_confirm_listing(session_id: str, opp_id: int = Form(...)):
#     from src.generic_listing_agent import confirm_generic_listing
#     result = confirm_generic_listing(session_id)

#     db = SessionLocal()
#     try:
#         opp = db.query(ListingOpportunity).filter(ListingOpportunity.id == opp_id).first()
#         if opp:
#             if result.get("status") == "success":
#                 opp.status = "listed"
#                 opp.generated_pitch = f"✅ Submitted: {result.get('detail')}"
#             else:
#                 opp.status = "failed"
#                 opp.generated_pitch = f"❌ Submit failed: {result.get('detail')}"
#             db.commit()
#     finally:
#         db.close()

#     return result


# @app.post("/api/cancel-listing/{session_id}")
# def api_cancel_listing(session_id: str, opp_id: int = Form(...)):
#     from src.generic_listing_agent import cancel_generic_listing
#     result = cancel_generic_listing(session_id)

#     db = SessionLocal()
#     try:
#         opp = db.query(ListingOpportunity).filter(ListingOpportunity.id == opp_id).first()
#         if opp:
#             opp.status = "discovered"
#             opp.generated_pitch = "Cancelled by user - not submitted."
#             db.commit()
#     finally:
#         db.close()

#     return result