from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from src.database import SessionLocal, ThreadMemory, ListingOpportunity
from src.gaper_scraper import get_brand_profile, scrape_gaper_brand
from src.discovery import discover_threads
from src.pipeline import approve_and_queue_post, run_pipeline, trigger_outreach_pitch, run_global_discovery
from src.brain import qa_loop, evaluate_seo_geo_aeo
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

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: 'Outfit', sans-serif;
        }

        body {
            background: linear-gradient(135deg, #050508 0%, #0b0c10 50%, #120e2e 100%);
            color: var(--text-main);
            min-height: 100vh;
            overflow-x: hidden;
        }

        .container {
            max-width: 1300px;
            margin: 0 auto;
            padding: 20px;
        }

        /* Glassmorphism Navigation */
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 20px 30px;
            background: var(--glass-bg);
            backdrop-filter: blur(12px);
            border-radius: 16px;
            border: 1px solid var(--glass-border);
            margin-bottom: 30px;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        }

        .logo-section h1 {
            font-family: 'Space Grotesk', sans-serif;
            font-weight: 800;
            background: linear-gradient(to right, var(--text-main), var(--accent));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-size: 24px;
            letter-spacing: 1px;
        }

        .logo-section span {
            color: var(--secondary);
            font-weight: 800;
        }

        .api-badge {
            background: rgba(138, 43, 226, 0.15);
            border: 1px solid var(--primary);
            color: var(--text-main);
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 13px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .api-badge::before {
            content: '';
            display: inline-block;
            width: 8px;
            height: 8px;
            background: var(--success);
            border-radius: 50%;
            box-shadow: 0 0 10px var(--success);
        }

        /* Tabs Control */
        .tabs {
            display: flex;
            gap: 15px;
            margin-bottom: 25px;
        }

        .tab-btn {
            background: transparent;
            border: none;
            color: var(--text-muted);
            padding: 12px 24px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            border-radius: 10px;
            transition: all 0.3s ease;
            border: 1px solid transparent;
        }

        .tab-btn:hover {
            color: var(--text-main);
            background: rgba(255, 255, 255, 0.05);
        }

        .tab-btn.active {
            color: var(--text-main);
            background: var(--glass-bg);
            border: 1px solid var(--glass-border);
            box-shadow: 0 0 15px rgba(138, 43, 226, 0.3);
        }

        /* Content Panel Layout */
        .panel {
            display: none;
        }

        .panel.active {
            display: block;
            animation: fadeIn 0.5s ease-out;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        /* Grid elements */
        .grid-2 {
            display: grid;
            grid-template-columns: 1fr 1.5fr;
            gap: 25px;
        }

        .glass-card {
            background: var(--glass-bg);
            backdrop-filter: blur(12px);
            border: 1px solid var(--glass-border);
            border-radius: 16px;
            padding: 24px;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.25);
            margin-bottom: 25px;
        }

        .glass-card h2 {
            font-family: 'Space Grotesk', sans-serif;
            margin-bottom: 20px;
            font-size: 20px;
            border-bottom: 1px solid var(--glass-border);
            padding-bottom: 10px;
            color: var(--accent);
        }

        /* Metrics Display */
        .scores-wrapper {
            display: flex;
            justify-content: space-around;
            margin: 20px 0;
        }

        .score-circle {
            text-align: center;
            position: relative;
        }

        .score-val {
            font-size: 32px;
            font-weight: 800;
            font-family: 'Space Grotesk', sans-serif;
            color: var(--accent);
            text-shadow: 0 0 10px rgba(0, 255, 255, 0.5);
        }

        .score-label {
            font-size: 12px;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-top: 5px;
        }

        /* Forms and Inputs */
        .form-group {
            margin-bottom: 15px;
        }

        label {
            display: block;
            font-size: 13px;
            color: var(--text-muted);
            margin-bottom: 6px;
            font-weight: 600;
        }

        textarea, input[type="text"] {
            width: 100%;
            background: rgba(0, 0, 0, 0.4);
            border: 1px solid var(--glass-border);
            border-radius: 8px;
            padding: 12px;
            color: var(--text-main);
            font-size: 14px;
            outline: none;
            transition: all 0.3s;
        }

        textarea:focus, input[type="text"]:focus {
            border-color: var(--accent);
            box-shadow: 0 0 10px rgba(0, 255, 255, 0.2);
        }

        /* Buttons */
        .btn {
            background: linear-gradient(135deg, var(--primary) 0%, #4b0082 100%);
            border: none;
            color: #fff;
            padding: 12px 20px;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            text-shadow: 0 1px 2px rgba(0, 0, 0, 0.5);
            display: inline-flex;
            align-items: center;
            gap: 10px;
        }

        .btn:hover {
            box-shadow: 0 0 15px rgba(138, 43, 226, 0.6);
            transform: translateY(-2px);
        }

        .btn-sec {
            background: linear-gradient(135deg, var(--secondary) 0%, #b22222 100%);
        }

        .btn-accent {
            background: transparent;
            border: 1px solid var(--accent);
            color: var(--accent);
        }

        .btn-accent:hover {
            background: var(--accent);
            color: var(--bg-color);
            box-shadow: 0 0 15px var(--accent);
        }

        .btn-sm {
            padding: 6px 12px;
            font-size: 12px;
        }

        /* Lists & Items styling */
        .item-list {
            display: flex;
            flex-direction: column;
            gap: 15px;
        }

        .list-item {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 12px;
            padding: 18px;
            transition: all 0.3s;
        }

        .list-item:hover {
            border-color: var(--glass-border);
            background: rgba(255, 255, 255, 0.05);
        }

        .list-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 12px;
        }

        .list-title {
            font-weight: 600;
            font-size: 16px;
            color: var(--text-main);
            text-decoration: none;
        }

        .list-title:hover {
            color: var(--accent);
        }

        .badge {
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
        }

        .badge-pending { background: rgba(255, 183, 3, 0.15); color: var(--warning); border: 1px solid var(--warning); }
        .badge-posted { background: rgba(57, 255, 20, 0.15); color: var(--success); border: 1px solid var(--success); }
        .badge-ghost { background: rgba(160, 165, 192, 0.15); color: var(--text-muted); border: 1px solid var(--text-muted); }
        
        .draft-preview {
            background: rgba(0, 0, 0, 0.5);
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid var(--primary);
            font-size: 14px;
            line-height: 1.6;
            margin: 15px 0;
            white-space: pre-wrap;
        }

        .meta-info {
            display: flex;
            gap: 15px;
            font-size: 12px;
            color: var(--text-muted);
            margin-top: 10px;
        }

        .actions-bar {
            display: flex;
            gap: 10px;
            justify-content: flex-end;
            margin-top: 15px;
        }

        /* Brand profile section */
        .profile-logo {
            width: 80px;
            height: 80px;
            border-radius: 50%;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--glass-border);
            padding: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 15px;
        }

        .profile-logo img {
            max-width: 100%;
            max-height: 100%;
        }

        .logs-window {
            background: #000;
            border: 1px solid var(--glass-border);
            border-radius: 12px;
            padding: 15px;
            height: 300px;
            overflow-y: auto;
            font-family: monospace;
            font-size: 12px;
            color: var(--success);
            line-height: 1.5;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="logo-section">
                <h1>Gaper <span>Backlink Agent V2</span></h1>
            </div>
            <div class="api-badge">Gemini Pipeline Active</div>
        </header>

        <div class="tabs">
            <button class="tab-btn active" onclick="switchTab('dashboard')">Overview</button>
            <button class="tab-btn" onclick="switchTab('approvals')">QA Approvals</button>
            <button class="tab-btn" onclick="switchTab('listings')">Listing Pitcher</button>
            <button class="tab-btn" onclick="switchTab('discovery')">Logs & Discovery</button>
        </div>

        <!-- DASHBOARD TAB -->
        <div id="dashboard" class="panel active">
            <div class="grid-2">
                <div>
                    <div class="glass-card">
                        <h2>Gaper.io Scraped Brand Profile</h2>
                        <div class="profile-logo" id="logoContainer">
                            <img src="" alt="Gaper Logo" id="brandLogo">
                        </div>
                        <div class="form-group">
                            <label>Scraped Description</label>
                            <textarea id="brandDesc" rows="4" readonly></textarea>
                        </div>
                        <div class="form-group">
                            <label>Scraped USPs</label>
                            <textarea id="brandUsps" rows="5" readonly></textarea>
                        </div>
                        <button class="btn btn-accent btn-sm" onclick="triggerScrapeBrand()">Rescrape Gaper.io</button>
                    </div>
                </div>

                <div>
                    <div class="glass-card">
                        <h2>System Stats</h2>
                        <div class="scores-wrapper">
                            <div class="score-circle">
                                <div class="score-val" id="statPending">0</div>
                                <div class="score-label">Pending Approval</div>
                            </div>
                            <div class="score-circle">
                                <div class="score-val" id="statPosted">0</div>
                                <div class="score-label">Citations Posted</div>
                            </div>
                            <div class="score-circle">
                                <div class="score-val" id="statOpps">0</div>
                                <div class="score-label">Directories Missing</div>
                            </div>
                        </div>
                    </div>

                    <div class="glass-card">
                        <h2>Run Manual Pipeline URL</h2>
                        <div class="form-group">
                            <label>Target Thread / Blog URL</label>
                            <input type="text" id="manualUrl" placeholder="https://www.indiehackers.com/post/...">
                        </div>
                        <button class="btn" onclick="runManualPipeline()">Process Target URL</button>
                    </div>
                </div>
            </div>
        </div>

        <!-- QA APPROVALS TAB -->
        <div id="approvals" class="panel">
            <div class="glass-card">
                <h2>Pending Comment / Citation Approvals</h2>
                <div class="item-list" id="approvalsList">
                    <!-- Dynamic rendering -->
                </div>
            </div>
        </div>

        <!-- LISTING PITCHER TAB -->
        <div id="listings" class="panel">
            <div class="glass-card">
                <h2>Directory Listing Gaps (Gaper missing where competitors are listed)</h2>
                <div class="item-list" id="opportunitiesList">
                    <!-- Dynamic rendering -->
                </div>
            </div>
        </div>

        <!-- LOGS & DISCOVERY TAB -->
        <div id="discovery" class="panel">
            <div class="glass-card">
                <h2>Run Discovery Pipeline</h2>
                <p style="margin-bottom:15px; font-size:14px; color:var(--text-muted);">
                    This will run the SERP (Google Search) and RSS feed parsers to locate backlink and gap listing opportunities.
                </p>
                <button class="btn btn-accent" onclick="runDiscoveryJob()">Trigger Global Discovery Job</button>
            </div>

            <div class="glass-card">
                <h2>System Logs & Outputs</h2>
                <div class="logs-window" id="logsWindow">
                    [System Initialized]<br>
                    [DB connection loaded automatically: gaper_agent.db]<br>
                    [Waiting for actions...]
                </div>
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

        function addLog(message) {
            const win = document.getElementById('logsWindow');
            win.innerHTML += `<br>[${new Date().toLocaleTimeString()}] ${message}`;
            win.scrollTop = win.scrollHeight;
        }

        async function loadStatsAndBrand() {
            try {
                const brandRes = await fetch('/api/brand-profile');
                const brand = await brandRes.json();
                document.getElementById('brandLogo').src = brand.logo_url;
                document.getElementById('brandDesc').value = brand.description;
                document.getElementById('brandUsps').value = brand.usps;

                const threadsRes = await fetch('/api/threads');
                const threads = await threadsRes.json();
                
                const oppsRes = await fetch('/api/opportunities');
                const opps = await oppsRes.json();

                document.getElementById('statPending').innerText = threads.filter(t => t.status === 'pending_approval').length;
                document.getElementById('statPosted').innerText = threads.filter(t => t.status === 'posted').length;
                document.getElementById('statOpps').innerText = opps.filter(o => o.status === 'discovered' || o.status === 'pitch_generated').length;
            } catch (err) {
                console.error(err);
            }
        }

        async function triggerScrapeBrand() {
            addLog("Triggering dynamic rescrape of Gaper.io website...");
            const res = await fetch('/api/rescrape-brand', { method: 'POST' });
            if (res.ok) {
                addLog("Gaper.io scraped successfully!");
                loadStatsAndBrand();
            }
        }

        async function runManualPipeline() {
            const url = document.getElementById('manualUrl').value;
            if (!url) return alert("Please specify a target URL");
            addLog(`Ingesting and generating draft reply for: ${url}`);
            
            const res = await fetch('/api/run-pipeline', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: new URLSearchParams({ url })
            });
            
            if (res.ok) {
                addLog("Pipeline processing completed! Draft created and pending approval.");
                document.getElementById('manualUrl').value = '';
                loadStatsAndBrand();
            } else {
                addLog("Pipeline run encountered a failure.");
            }
        }

        async function loadApprovals() {
            const res = await fetch('/api/threads');
            const threads = await res.json();
            const container = document.getElementById('approvalsList');
            container.innerHTML = '';

            const pending = threads.filter(t => t.status === 'pending_approval');
            if (pending.length === 0) {
                container.innerHTML = '<div style="color:var(--text-muted)">No pending citation drafts found.</div>';
                return;
            }

            pending.forEach(t => {
                const seo = t.seo_score || 0;
                const geo = t.geo_score || 0;
                const aeo = t.aeo_score || 0;
                
                const html = `
                    <div class="list-item" id="thread-${t.id}">
                        <div class="list-header">
                            <div>
                                <a href="${t.url}" target="_blank" class="list-title">${t.url}</a>
                                <span class="badge ${t.is_ghost ? 'badge-ghost' : 'badge-pending'}">${t.is_ghost ? 'Ghost Post (No Links)' : 'Backlink Citation'}</span>
                            </div>
                            <div style="font-size:12px; color:var(--text-muted)">Type: ${t.platform}</div>
                        </div>
                        
                        <div class="scores-wrapper" style="margin: 10px 0; background:rgba(0,0,0,0.2); padding:10px; border-radius:8px;">
                            <div><span class="score-val" style="font-size:20px">${seo}%</span><br><span class="score-label" style="font-size:9px">SEO</span></div>
                            <div><span class="score-val" style="font-size:20px">${geo}%</span><br><span class="score-label" style="font-size:9px">GEO</span></div>
                            <div><span class="score-val" style="font-size:20px">${aeo}%</span><br><span class="score-label" style="font-size:9px">AEO</span></div>
                        </div>

                        <textarea id="reply-text-${t.id}" rows="8" style="margin-top:10px;">${t.generated_reply}</textarea>
                        
                        <div class="actions-bar">
                            <button class="btn btn-sm btn-accent" onclick="saveDraft(${t.id})">Save Edit</button>
                            <button class="btn btn-sm btn-sec" onclick="rejectDraft(${t.id})">Regenerate</button>
                            <button class="btn btn-sm" onclick="approveDraft(${t.id})">Approve & Post</button>
                        </div>
                    </div>
                `;
                container.innerHTML += html;
            });
        }

        async function saveDraft(id) {
            const text = document.getElementById(`reply-text-${id}`).value;
            const res = await fetch(`/api/save/${id}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ reply_text: text })
            });
            if (res.ok) {
                addLog(`Saved draft edits for Thread ID ${id}`);
                loadApprovals();
            }
        }

        async function approveDraft(id) {
            addLog(`Approving and queuing post task for Thread ID ${id}...`);
            const res = await fetch(`/api/approve/${id}`, { method: 'POST' });
            if (res.ok) {
                addLog(`Thread ID ${id} approved and sent to broker pipeline!`);
                loadApprovals();
            }
        }

        async function rejectDraft(id) {
            const feedback = prompt("Please provide feedback for regeneration:");
            if (!feedback) return;
            addLog(`Regenerating draft for Thread ID ${id} with feedback: "${feedback}"`);
            
            const res = await fetch(`/api/reject/${id}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ feedback })
            });
            if (res.ok) {
                addLog(`Regeneration complete for Thread ID ${id}`);
                loadApprovals();
            }
        }

        async function loadOpportunities() {
            const res = await fetch('/api/opportunities');
            const opps = await res.json();
            const container = document.getElementById('opportunitiesList');
            container.innerHTML = '';

            if (opps.length === 0) {
                container.innerHTML = '<div style="color:var(--text-muted)">No directory listing gaps detected yet. Run discovery.</div>';
                return;
            }

            opps.forEach(o => {
                const pitch = o.generated_pitch || "Outreach Pitch not generated yet.";
                const html = `
                    <div class="list-item">
                        <div class="list-header">
                            <div>
                                <a href="${o.url}" target="_blank" class="list-title">${o.url}</a>
                                <div style="font-size:12px; color:var(--text-muted); margin-top:4px;">Competitors Found: <b style="color:var(--secondary)">${o.competitors_found}</b></div>
                            </div>
                            <span class="badge ${o.status === 'outreach_sent' ? 'badge-posted' : 'badge-pending'}">${o.status}</span>
                        </div>
                        <div class="draft-preview">${pitch}</div>
                        <div class="actions-bar">
                            <button class="btn btn-sm" onclick="triggerOutreach(${o.id})">${o.status === 'outreach_sent' ? 'Resend Outreach' : 'Generate & Send Pitch'}</button>
                        </div>
                    </div>
                `;
                container.innerHTML += html;
            });
        }

        async function triggerOutreach(id) {
            addLog(`Generating webmaster listing pitch and dispatching email for opportunity ${id}...`);
            const res = await fetch(`/api/outreach/${id}`, { method: 'POST' });
            if (res.ok) {
                addLog(`Outreach email pitch dispatched successfully for opportunity ${id}!`);
                loadOpportunities();
            }
        }

        async function runDiscoveryJob() {
            addLog("Executing global discovery job (SERP & RSS sweeps). Please wait...");
            const res = await fetch('/api/discover', { method: 'POST' });
            if (res.ok) {
                const data = await res.json();
                addLog(`Discovery job finished. Found ${data.count} new opportunities!`);
                loadStatsAndBrand();
            } else {
                addLog("Discovery job encountered an issue.");
            }
        }

        // Initialize Page
        loadStatsAndBrand();
    </script>
</body>
</html>
"""

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
                "id": t.id,
                "url": t.url,
                "platform": t.platform,
                "status": t.status,
                "generated_reply": t.generated_reply,
                "is_ghost": t.is_ghost,
                "seo_score": scores["seo"],
                "geo_score": scores["geo"],
                "aeo_score": scores["aeo"]
            })
        return result
    finally:
        db.close()

@app.get("/api/opportunities")
def api_opportunities():
    db = SessionLocal()
    try:
        opps = db.query(ListingOpportunity).all()
        return opps
    finally:
        db.close()

@app.post("/api/discover")
def api_discover():
    count = run_global_discovery()
    return {"count": count}

@app.post("/api/run-pipeline")
def api_run_pipeline(url: str = Form(...)):
    try:
        res = run_pipeline(url)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/save/{thread_id}")
def api_save_draft(thread_id: int, edit: DraftEdit):
    db = SessionLocal()
    try:
        thread = db.query(ThreadMemory).filter(ThreadMemory.id == thread_id).first()
        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")
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
    res = qa_loop(thread_id, feedback.feedback, feedback.iteration)
    return res

@app.post("/api/outreach/{opp_id}")
def api_outreach_pitch(opp_id: int):
    trigger_outreach_pitch(opp_id)
    return {"status": "success"}
