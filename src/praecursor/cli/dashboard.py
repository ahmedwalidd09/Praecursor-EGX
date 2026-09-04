import argparse
import datetime
from contextlib import asynccontextmanager
from pathlib import Path
import sys
from typing import Any

from fastapi import BackgroundTasks, FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure") and stream is not None:
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

from praecursor.core.settings import ScannerSettings
from praecursor.data.symbol_mapper import SymbolMapper
from praecursor.reporting.dashboard import DEFAULT_DASHBOARD_REPORT
from praecursor.workflows.scanner import ScannerWorkflow


REPORTS_DIR = DEFAULT_DASHBOARD_REPORT.parent
ARCHIVE_DIR = REPORTS_DIR / "archive"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

scan_status = {
    "running": False,
    "last_completed": None,
    "error": None,
    "processed": 0,
    "total": 0,
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="Praecursor-EGX Dashboard", lifespan=lifespan)


def run_scanner_sync() -> None:
    global scan_status
    scan_status["running"] = True
    scan_status["error"] = None
    try:
        settings = ScannerSettings.from_json()
        workflow = ScannerWorkflow(
            lookback_days=settings.lookback_days,
            consensus_lookback_days=settings.consensus_lookback_days,
            minimum_bars=settings.minimum_bars,
            enable_consensus=settings.enable_consensus,
            enable_history=settings.enable_history,
            enable_archive_reports=settings.enable_archive_reports,
        )
        symbol_mapper = SymbolMapper.from_csv()
        # Scan only enabled symbols
        symbols = symbol_mapper.get_yahoo_symbols(include_disabled=False)
        scan_status["total"] = len(symbols)
        scan_status["processed"] = 0
        
        def progress_callback(processed: int, total: int) -> None:
            scan_status["processed"] = processed
            
        workflow.run(symbols=symbols, progress_callback=progress_callback)
        
        scan_status["last_completed"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    except Exception as error:
        scan_status["error"] = str(error)
    finally:
        scan_status["running"] = False


@app.get("/", response_class=HTMLResponse)
async def get_dashboard() -> HTMLResponse:
    if not DEFAULT_DASHBOARD_REPORT.exists():
        return HTMLResponse(
            "<!doctype html><html><head>"
            "<style>"
            ".loader { border: 4px solid #f3f3f3; border-top: 4px solid #2f80ed; border-radius: 50%; width: 30px; height: 30px; animation: spin 1s linear infinite; display: inline-block; vertical-align: middle; margin-right: 10px; }"
            "@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }"
            "#status-msg { display: none; margin-top: 20px; font-weight: bold; color: #333; }"
            "</style>"
            "</head><body style=\"font-family: sans-serif; padding: 40px;\">"
            "<h1>No dashboard generated yet.</h1>"
            "<p>Run a scan to generate the latest report. It will take 1-2 minutes.</p>"
            "<button id=\"scan-btn\" onclick=\"triggerScan()\" style=\"padding:12px 20px;background-color:#2f80ed;color:white;border:none;border-radius:24px;cursor:pointer;font-weight:bold;\">Run Scan</button>"
            "<div id=\"status-msg\"><div class=\"loader\"></div><span id=\"status-text\">Scanning in progress... Please wait.</span></div>"
            "<script>"
            "function checkStatus() {"
            "  fetch('/api/status').then(r => r.json()).then(data => {"
            "    if(data.running) {"
            "      document.getElementById('scan-btn').style.display = 'none';"
            "      document.getElementById('status-msg').style.display = 'block';"
            "      const pct = data.total > 0 ? Math.round((data.processed / data.total) * 100) : 0;"
            "      document.getElementById('status-text').innerText = `Scanning in progress... ${data.processed}/${data.total} (${pct}%) Please wait.`;"
            "      setTimeout(checkStatus, 2000);"
            "    } else if(document.getElementById('status-msg').style.display === 'block') {"
            "      document.getElementById('status-text').innerText = 'Scan Complete!';"
            "      try {"
            "        const ctx = new (window.AudioContext || window.webkitAudioContext)();"
            "        const osc = ctx.createOscillator();"
            "        const gain = ctx.createGain();"
            "        osc.type = 'sine';"
            "        osc.frequency.setValueAtTime(1046.5, ctx.currentTime);"
            "        gain.gain.setValueAtTime(0.5, ctx.currentTime);"
            "        gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.5);"
            "        osc.connect(gain); gain.connect(ctx.destination); osc.start(); osc.stop(ctx.currentTime + 0.5);"
            "      } catch(e) {}"
            "      setTimeout(() => location.reload(), 1500);"
            "    }"
            "  });"
            "}"
            "checkStatus();"
            "function triggerScan() {"
            "  document.getElementById('scan-btn').style.display = 'none';"
            "  document.getElementById('status-msg').style.display = 'block';"
            "  document.getElementById('status-text').innerText = 'Initializing scan...';"
            "  fetch('/api/scan', {method: 'POST'})"
            "    .then(res => res.json())"
            "    .then(data => { setTimeout(checkStatus, 1000); })"
            "    .catch(e => { alert('Error: ' + e); document.getElementById('scan-btn').style.display = 'block'; document.getElementById('status-msg').style.display = 'none'; });"
            "}"
            "</script>"
            "</body></html>"
        )

    try:
        html = DEFAULT_DASHBOARD_REPORT.read_text(encoding="utf-8", errors="replace")
    except (FileNotFoundError, OSError):
        return HTMLResponse(
            "<!doctype html><html><body style=\"font-family: sans-serif; padding: 40px;\">"
            "<h1>No dashboard generated yet.</h1>"
            "<p>Run a scan to generate the latest report.</p>"
            "</body></html>"
        )
    
    # Inject auto-refresh every 60s
    if "<head>" in html and "http-equiv=\"refresh\"" not in html:
        html = html.replace("<head>", "<head>\n  <meta http-equiv=\"refresh\" content=\"300\" />")

    # Add a floating action button to trigger scan
    fab_html = """
    <script>
    function checkStatusFab() {
        fetch('/api/status').then(r => r.json()).then(data => {
            const btn = document.getElementById('scan-btn');
            if(data.running) {
                const pct = data.total > 0 ? Math.round((data.processed / data.total) * 100) : 0;
                btn.innerText = `Running ${pct}%`;
                btn.disabled = true;
                setTimeout(checkStatusFab, 2000);
            } else if (btn.disabled) {
                btn.innerText = 'Scan Complete';
                try {
                    const ctx = new (window.AudioContext || window.webkitAudioContext)();
                    const gain = ctx.createGain();
                    gain.connect(ctx.destination);
                    gain.gain.setValueAtTime(0, ctx.currentTime);
                    gain.gain.linearRampToValueAtTime(0.7, ctx.currentTime + 0.01);
                    gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 1.5);
                    
                    const osc1 = ctx.createOscillator();
                    osc1.type = 'sine';
                    osc1.frequency.setValueAtTime(1046.5, ctx.currentTime); // C6
                    osc1.connect(gain);
                    osc1.start();
                    osc1.stop(ctx.currentTime + 1.5);
                    
                    const osc2 = ctx.createOscillator();
                    osc2.type = 'sine';
                    osc2.frequency.setValueAtTime(2093, ctx.currentTime); // C7 (octave)
                    osc2.connect(gain);
                    osc2.start();
                    osc2.stop(ctx.currentTime + 1.5);
                } catch(e) {}
                
                // Revert button text, then reload after a short delay
                setTimeout(() => {
                    btn.innerText = 'Run Scan';
                    btn.disabled = false;
                }, 3000);
                setTimeout(() => location.reload(), 3500);
            } else {
                btn.innerText = 'Run Scan';
                btn.disabled = false;
            }
        });
    }
    // Call once on load in case a scan is running
    checkStatusFab();
    
    function triggerScan() {
        const btn = document.getElementById('scan-btn');
        btn.innerText = 'Starting...';
        btn.disabled = true;
        fetch('/api/scan', {method: 'POST'})
            .then(res => res.json())
            .then(data => {
                if(data.status === 'already running') alert('Scan already in progress');
                checkStatusFab();
            })
            .catch(e => { alert('Error: ' + e); btn.innerText = 'Run Scan'; btn.disabled = false; });
    }
    </script>
    <button id="scan-btn" onclick="triggerScan()" style="position:fixed;bottom:20px;right:20px;padding:12px 20px;background-color:#1e88e5;color:white;border:none;border-radius:24px;box-shadow:0 4px 12px rgba(30,136,229,0.3);cursor:pointer;font-weight:bold;z-index:9999;">Run Scan</button>
    </body>
    """
    html = html.replace("</body>", fab_html)

    response = HTMLResponse(html)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.get("/api/status")
async def get_status() -> dict[str, Any]:
    return scan_status


@app.post("/api/scan")
async def trigger_scan(background_tasks: BackgroundTasks) -> dict[str, str]:
    if scan_status["running"]:
        return {"status": "already running"}
    
    background_tasks.add_task(run_scanner_sync)
    return {"status": "started"}


@app.get("/api/reports")
async def list_reports() -> list[str]:
    if not REPORTS_DIR.exists():
        return []
    try:
        return [path.name for path in REPORTS_DIR.iterdir() if path.is_file() and not path.name.startswith(".")]
    except OSError:
        return []


@app.get("/api/reports/archive")
async def list_archive_reports() -> list[str]:
    if not ARCHIVE_DIR.exists():
        return []
    try:
        return [path.name for path in ARCHIVE_DIR.iterdir() if path.is_file() and not path.name.startswith(".")]
    except OSError:
        return []


# Mount static files for easy CSV downloads
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/reports", StaticFiles(directory=str(REPORTS_DIR)), name="reports")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Praecursor-EGX Dashboard server.")
    parser.add_argument("--host", default="127.0.0.1", help="Host IP to bind to.")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to.")
    args = parser.parse_args()

    print(f"Starting Praecursor-EGX Dashboard on http://{args.host}:{args.port}")
    uvicorn.run(
        "praecursor.cli.dashboard:app",
        host=args.host,
        port=args.port,
        log_level="info",
        reload=True,
        reload_dirs=["src"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
