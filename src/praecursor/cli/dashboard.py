import argparse
from contextlib import asynccontextmanager
import datetime
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import time
import socket
from typing import Any

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
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
from praecursor.security.access_gate import (
    check_telegram_approval,
    get_short_node_id,
    is_machine_whitelisted,
    send_telegram_access_request,
)
from praecursor.workflows.scanner import ScannerWorkflow

PROJECT_ROOT = DEFAULT_DASHBOARD_REPORT.parent.parent
REPORTS_DIR = DEFAULT_DASHBOARD_REPORT.parent
ARCHIVE_DIR = REPORTS_DIR / "archive"
DATA_DIR = PROJECT_ROOT / "data"
STATUS_FILE = DATA_DIR / "scan_status.json"

REPORTS_DIR.mkdir(parents=True, exist_ok=True)
ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

scan_status: dict[str, Any] = {
    "running": False,
    "last_completed": None,
    "error": None,
    "processed": 0,
    "total": 0,
}

pipeline_proc: subprocess.Popen | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="Praecursor-EGX Mission Control & Dashboard", lifespan=lifespan)


def read_status_file() -> dict[str, Any]:
    """Read latest status from data/scan_status.json if it exists."""
    if STATUS_FILE.exists():
        try:
            with open(STATUS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
    return {}


def run_pipeline_subprocess() -> None:
    """Execute full autonomous pipeline (stages 1-4) in background subprocess."""
    global scan_status, pipeline_proc
    scan_status["running"] = True
    scan_status["error"] = None

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    initial_status = {
        "running": True,
        "stage": 1,
        "stage_name": "Market Data & Symbol Scanner",
        "processed": 0,
        "total": 0,
        "percent": 0.0,
        "current_symbol": None,
        "elapsed_seconds": 0,
        "eta_seconds": 0,
        "telegram_status": "Queued for Stage 4",
        "error": None,
        "completed": False,
    }
    try:
        tmp_f = STATUS_FILE.with_suffix(".tmp")
        with open(tmp_f, "w", encoding="utf-8") as f:
            json.dump(initial_status, f, indent=2)
        os.replace(tmp_f, STATUS_FILE)
    except Exception:
        pass

    try:
        pipeline_script = PROJECT_ROOT / "tools" / "run_autonomous_pipeline.py"
        cmd = [sys.executable, str(pipeline_script), "--force"]
        pipeline_proc = subprocess.Popen(
            cmd,
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        try:
            stdout, _ = pipeline_proc.communicate(timeout=2400)
        except subprocess.TimeoutExpired:
            pipeline_proc.kill()
            stdout, _ = pipeline_proc.communicate()
            scan_status["error"] = "Pipeline execution timed out after 40 minutes and was terminated."
        
        if pipeline_proc.returncode != 0 and not scan_status.get("error"):
            scan_status["error"] = f"Pipeline finished with returncode {pipeline_proc.returncode}"
    except Exception as e:
        scan_status["error"] = str(e)
    finally:
        pipeline_proc = None
        scan_status["running"] = False
        scan_status["last_completed"] = datetime.datetime.now(datetime.timezone.utc).isoformat()


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


MISSION_CONTROL_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PRAECURSOR // EGX — Mission Control</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg-dark: #070913;
      --bg-card: rgba(13, 18, 36, 0.72);
      --bg-card-hover: rgba(18, 25, 51, 0.85);
      --cyan-neon: #00f2fe;
      --cyan-glow: rgba(0, 242, 254, 0.35);
      --blue-accent: #4facfe;
      --emerald-neon: #10b981;
      --emerald-glow: rgba(16, 185, 129, 0.35);
      --purple-accent: #8b5cf6;
      --amber-accent: #f59e0b;
      --border-subtle: rgba(56, 189, 248, 0.18);
      --border-active: rgba(0, 242, 254, 0.6);
      --text-main: #f8fafc;
      --text-muted: #94a3b8;
      --font-mono: 'JetBrains Mono', monospace;
      --font-sans: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      background-color: var(--bg-dark);
      background-image: 
        radial-gradient(ellipse at 50% 10%, rgba(0, 242, 254, 0.08) 0%, transparent 60%),
        radial-gradient(circle at 90% 80%, rgba(139, 92, 246, 0.05) 0%, transparent 50%),
        linear-gradient(to right, rgba(255, 255, 255, 0.02) 1px, transparent 1px),
        linear-gradient(to bottom, rgba(255, 255, 255, 0.02) 1px, transparent 1px);
      background-size: 100% 100%, 100% 100%, 36px 36px, 36px 36px;
      color: var(--text-main);
      font-family: var(--font-sans);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 24px 20px 40px;
      overflow-x: hidden;
    }

    /* Top Navigation Header */
    .header-bar {
      width: 100%;
      max-width: 1080px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 16px 24px;
      background: var(--bg-card);
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      border: 1px solid var(--border-subtle);
      border-radius: 18px;
      box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
      margin-bottom: 28px;
    }

    .brand-group {
      display: flex;
      align-items: center;
      gap: 14px;
    }

    .brand-title {
      font-family: var(--font-mono);
      font-size: 20px;
      font-weight: 800;
      letter-spacing: 1.5px;
      color: #fff;
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .brand-accent {
      color: var(--cyan-neon);
      text-shadow: 0 0 14px var(--cyan-glow);
    }

    .badge-alpha {
      font-family: var(--font-mono);
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.5px;
      padding: 4px 10px;
      background: rgba(0, 242, 254, 0.12);
      color: var(--cyan-neon);
      border: 1px solid rgba(0, 242, 254, 0.35);
      border-radius: 20px;
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }

    .pulse-dot {
      width: 6px;
      height: 6px;
      background: var(--cyan-neon);
      border-radius: 50%;
      box-shadow: 0 0 8px var(--cyan-neon);
      animation: pulse-glow 2s infinite ease-in-out;
    }

    @keyframes pulse-glow {
      0%, 100% { opacity: 0.4; transform: scale(0.8); }
      50% { opacity: 1; transform: scale(1.3); }
    }

    .header-telemetry {
      display: flex;
      align-items: center;
      gap: 16px;
    }

    .telemetry-chip {
      font-family: var(--font-mono);
      font-size: 12px;
      font-weight: 600;
      padding: 6px 14px;
      background: rgba(15, 23, 42, 0.6);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 12px;
      color: var(--text-muted);
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .chip-regime {
      color: #34d399;
      border-color: rgba(52, 211, 153, 0.25);
      background: rgba(6, 78, 59, 0.25);
    }

    .regime-dot {
      width: 7px;
      height: 7px;
      background: #10b981;
      border-radius: 50%;
      box-shadow: 0 0 8px #10b981;
    }

    /* Main Mission Control Container */
    .mission-container {
      width: 100%;
      max-width: 1080px;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 24px;
    }

    .hero-card {
      width: 100%;
      background: var(--bg-card);
      backdrop-filter: blur(20px);
      -webkit-backdrop-filter: blur(20px);
      border: 1px solid var(--border-subtle);
      border-radius: 24px;
      padding: 44px 32px;
      box-shadow: 0 20px 60px rgba(0, 0, 0, 0.6), inset 0 1px 1px rgba(255, 255, 255, 0.08);
      display: flex;
      flex-direction: column;
      align-items: center;
      text-align: center;
      position: relative;
      overflow: hidden;
    }

    .hero-card::before {
      content: '';
      position: absolute;
      top: -100px;
      left: 50%;
      transform: translateX(-50%);
      width: 450px;
      height: 200px;
      background: radial-gradient(ellipse, rgba(0, 242, 254, 0.15), transparent 70%);
      pointer-events: none;
    }

    .hero-title {
      font-size: 32px;
      font-weight: 800;
      letter-spacing: -0.5px;
      margin-bottom: 8px;
      background: linear-gradient(135deg, #ffffff 0%, #cbd5e1 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }

    .hero-subtitle {
      font-size: 15px;
      color: var(--text-muted);
      max-width: 580px;
      margin-bottom: 32px;
      line-height: 1.6;
    }

    /* Big Glowing Action Button */
    .scan-action-wrapper {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 18px;
      margin-bottom: 24px;
    }

    .btn-run-scan {
      font-family: var(--font-mono);
      font-size: 18px;
      font-weight: 800;
      letter-spacing: 2px;
      color: #fff;
      background: linear-gradient(135deg, #00d2ff 0%, #0072ff 100%);
      border: 1px solid rgba(255, 255, 255, 0.35);
      border-radius: 50px;
      padding: 20px 48px;
      cursor: pointer;
      box-shadow: 0 0 35px var(--cyan-glow), inset 0 0 15px rgba(255, 255, 255, 0.25);
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      display: inline-flex;
      align-items: center;
      gap: 14px;
      position: relative;
    }

    .btn-run-scan:hover:not(:disabled) {
      transform: translateY(-2px) scale(1.03);
      box-shadow: 0 0 50px rgba(0, 242, 254, 0.6), inset 0 0 20px rgba(255, 255, 255, 0.4);
    }

    .btn-run-scan:active:not(:disabled) {
      transform: translateY(1px) scale(0.99);
    }

    .btn-run-scan.scanning {
      background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
      border-color: var(--cyan-neon);
      color: var(--cyan-neon);
      cursor: not-allowed;
      animation: radar-pulse 2s infinite ease-in-out;
    }

    @keyframes radar-pulse {
      0% { box-shadow: 0 0 15px var(--cyan-glow); }
      50% { box-shadow: 0 0 40px var(--cyan-glow), 0 0 80px rgba(0, 242, 254, 0.2); }
      100% { box-shadow: 0 0 15px var(--cyan-glow); }
    }

    .browse-link {
      font-size: 14px;
      font-weight: 600;
      color: var(--blue-accent);
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 10px 22px;
      background: rgba(30, 41, 59, 0.5);
      border: 1px solid rgba(56, 189, 248, 0.2);
      border-radius: 30px;
      transition: all 0.2s ease;
    }

    .browse-link:hover {
      background: rgba(30, 41, 59, 0.9);
      border-color: var(--blue-accent);
      transform: translateY(-1px);
    }

    /* Live Scanner Progress Section */
    .progress-section {
      width: 100%;
      margin-top: 16px;
      display: none;
      flex-direction: column;
      align-items: center;
      gap: 28px;
      animation: fadeIn 0.4s ease;
    }

    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(10px); }
      to { opacity: 1; transform: translateY(0); }
    }

    /* Circular Progress Ring */
    .radial-container {
      position: relative;
      width: 140px;
      height: 140px;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .radial-svg {
      transform: rotate(-90deg);
      width: 140px;
      height: 140px;
    }

    .radial-bg {
      fill: none;
      stroke: rgba(255, 255, 255, 0.06);
      stroke-width: 10;
    }

    .radial-progress {
      fill: none;
      stroke: url(#cyan-grad);
      stroke-width: 10;
      stroke-linecap: round;
      stroke-dasharray: 339.292;
      stroke-dashoffset: 339.292;
      transition: stroke-dashoffset 0.6s ease;
    }

    .radial-center-text {
      position: absolute;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
    }

    .radial-pct {
      font-family: var(--font-mono);
      font-size: 28px;
      font-weight: 800;
      color: #fff;
    }

    .radial-label {
      font-family: var(--font-mono);
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 1px;
      color: var(--cyan-neon);
      margin-top: -2px;
    }

    /* Stage Checklist */
    .stages-card {
      width: 100%;
      max-width: 720px;
      background: rgba(10, 15, 30, 0.6);
      border: 1px solid var(--border-subtle);
      border-radius: 18px;
      padding: 20px 24px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    .stage-item {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 10px 14px;
      border-radius: 12px;
      background: rgba(255, 255, 255, 0.02);
      border: 1px solid transparent;
      transition: all 0.25s ease;
    }

    .stage-item.active {
      background: rgba(0, 242, 254, 0.07);
      border-color: rgba(0, 242, 254, 0.3);
    }

    .stage-item.completed {
      background: rgba(16, 185, 129, 0.05);
      border-color: rgba(16, 185, 129, 0.2);
    }

    .stage-left {
      display: flex;
      align-items: center;
      gap: 14px;
      text-align: left;
    }

    .stage-dot {
      width: 14px;
      height: 14px;
      border-radius: 50%;
      border: 2px solid #475569;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: all 0.3s ease;
    }

    .stage-item.active .stage-dot {
      border-color: var(--cyan-neon);
      background: var(--cyan-neon);
      box-shadow: 0 0 12px var(--cyan-neon);
      animation: pulse-glow 1.5s infinite;
    }

    .stage-item.completed .stage-dot {
      border-color: var(--emerald-neon);
      background: var(--emerald-neon);
      box-shadow: 0 0 10px var(--emerald-neon);
    }

    .stage-dot svg {
      display: none;
      width: 10px;
      height: 10px;
      stroke: #070913;
      stroke-width: 3;
    }

    .stage-item.completed .stage-dot svg {
      display: block;
    }

    .stage-title {
      font-size: 14px;
      font-weight: 600;
      color: #e2e8f0;
    }

    .stage-subtitle {
      font-family: var(--font-mono);
      font-size: 11px;
      color: var(--text-muted);
      margin-top: 2px;
    }

    .stage-badge {
      font-family: var(--font-mono);
      font-size: 11px;
      font-weight: 700;
      padding: 3px 10px;
      border-radius: 20px;
      background: rgba(255, 255, 255, 0.04);
      color: var(--text-muted);
    }

    .stage-item.active .stage-badge {
      background: rgba(0, 242, 254, 0.15);
      color: var(--cyan-neon);
    }

    .stage-item.completed .stage-badge {
      background: rgba(16, 185, 129, 0.15);
      color: var(--emerald-neon);
    }

    /* Telemetry 4-Card Strip */
    .telemetry-grid {
      width: 100%;
      max-width: 720px;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 14px;
    }

    .metric-card {
      background: rgba(10, 15, 30, 0.6);
      border: 1px solid var(--border-subtle);
      border-radius: 16px;
      padding: 14px 18px;
      text-align: left;
    }

    .metric-title {
      font-family: var(--font-mono);
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.5px;
      color: var(--text-muted);
      margin-bottom: 6px;
      text-transform: uppercase;
      display: flex;
      align-items: center;
      gap: 6px;
    }

    .metric-value {
      font-family: var(--font-mono);
      font-size: 16px;
      font-weight: 700;
      color: #fff;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    /* Celebration Toast */
    .toast-banner {
      display: none;
      position: fixed;
      top: 28px;
      background: rgba(6, 78, 59, 0.92);
      border: 1px solid #10b981;
      border-radius: 16px;
      padding: 14px 28px;
      box-shadow: 0 10px 40px rgba(16, 185, 129, 0.4);
      backdrop-filter: blur(12px);
      z-index: 10000;
      animation: slideDown 0.4s ease;
      text-align: center;
    }

    @keyframes slideDown {
      from { transform: translateY(-40px); opacity: 0; }
      to { transform: translateY(0); opacity: 1; }
    }

    .toast-title {
      font-size: 15px;
      font-weight: 700;
      color: #fff;
    }

    .toast-sub {
      font-size: 12px;
      color: #a7f3d0;
      margin-top: 3px;
    }
  </style>
</head>
<body>

  <!-- Top Navigation Header -->
  <header class="header-bar">
    <div class="brand-group">
      <div class="brand-title">PRAECURSOR <span class="brand-accent">// EGX</span></div>
      <div class="badge-alpha"><span class="pulse-dot"></span> v6.3 Institutional Alpha</div>
    </div>
    <div class="header-telemetry">
      <div class="telemetry-chip chip-regime"><span class="regime-dot"></span> EGX30: BULLISH EXPANSION</div>
      <div class="telemetry-chip" id="cairo-clock">--:--:-- CAIRO</div>
    </div>
  </header>

  <!-- Notification Toast -->
  <div class="toast-banner" id="toast-banner">
    <div class="toast-title">🎉 SCAN COMPLETE &amp; TELEGRAM BROADCAST DELIVERED!</div>
    <div class="toast-sub">Redirecting to Institutional Dashboard in 1.5 seconds...</div>
  </div>

  <!-- Main Hero Card -->
  <main class="mission-container">
    <section class="hero-card">
      <h1 class="hero-title">Mission Control Terminal</h1>
      <p class="hero-subtitle" id="hero-status-desc">Autonomous 227-symbol scanner, quantitative ML model retraining, institutional report builder, and real-time Telegram intelligence broadcast.</p>

      <!-- Center Action Button -->
      <div class="scan-action-wrapper">
        <button id="run-scan-btn" class="btn-run-scan" onclick="triggerScan()">
          <span>▶ RUN SCAN</span>
        </button>
        <a href="/dashboard" class="browse-link" id="browse-dash-link">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6M15 3h6v6M10 14L21 3"/></svg>
          Browse Previous Scan Dashboard
        </a>
      </div>

      <!-- Live Multi-Stage Progress View -->
      <div class="progress-section" id="progress-section">
        
        <!-- Radial Circular Progress Ring -->
        <div class="radial-container">
          <svg class="radial-svg" viewBox="0 0 120 120">
            <defs>
              <linearGradient id="cyan-grad" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stop-color="#00f2fe" />
                <stop offset="100%" stop-color="#4facfe" />
              </linearGradient>
            </defs>
            <circle class="radial-bg" cx="60" cy="60" r="54" />
            <circle id="radial-circle" class="radial-progress" cx="60" cy="60" r="54" />
          </svg>
          <div class="radial-center-text">
            <span class="radial-pct" id="radial-pct-text">0%</span>
            <span class="radial-label">PROGRESS</span>
          </div>
        </div>

        <!-- 5-Stage Checklist -->
        <div class="stages-card">
          <div class="stage-item" id="stage-1-item">
            <div class="stage-left">
              <div class="stage-dot"><svg viewBox="0 0 24 24" fill="none"><polyline points="20 6 9 17 4 12"></polyline></svg></div>
              <div>
                <div class="stage-title">Stage 1: Market Data &amp; Symbol Scanner</div>
                <div class="stage-subtitle" id="stage-1-detail">Pending 227 symbols...</div>
              </div>
            </div>
            <div class="stage-badge" id="stage-1-badge">WAITING</div>
          </div>

          <div class="stage-item" id="stage-15-item">
            <div class="stage-left">
              <div class="stage-dot"><svg viewBox="0 0 24 24" fill="none"><polyline points="20 6 9 17 4 12"></polyline></svg></div>
              <div>
                <div class="stage-title">Stage 1.5: Historical Outcome Backfill</div>
                <div class="stage-subtitle">Evaluating prior prediction accuracy against fresh prints</div>
              </div>
            </div>
            <div class="stage-badge" id="stage-15-badge">WAITING</div>
          </div>

          <div class="stage-item" id="stage-2-item">
            <div class="stage-left">
              <div class="stage-dot"><svg viewBox="0 0 24 24" fill="none"><polyline points="20 6 9 17 4 12"></polyline></svg></div>
              <div>
                <div class="stage-title">Stage 2: XGBoost &amp; LightGBM Model Retraining</div>
                <div class="stage-subtitle">Optimizing ensemble meta-weights and decision boundaries</div>
              </div>
            </div>
            <div class="stage-badge" id="stage-2-badge">WAITING</div>
          </div>

          <div class="stage-item" id="stage-3-item">
            <div class="stage-left">
              <div class="stage-dot"><svg viewBox="0 0 24 24" fill="none"><polyline points="20 6 9 17 4 12"></polyline></svg></div>
              <div>
                <div class="stage-title">Stage 3: Institutional Dashboard Generation</div>
                <div class="stage-subtitle">Compiling interactive HTML terminal, ranking tables &amp; charts</div>
              </div>
            </div>
            <div class="stage-badge" id="stage-3-badge">WAITING</div>
          </div>

          <div class="stage-item" id="stage-4-item">
            <div class="stage-left">
              <div class="stage-dot"><svg viewBox="0 0 24 24" fill="none"><polyline points="20 6 9 17 4 12"></polyline></svg></div>
              <div>
                <div class="stage-title">Stage 4: Telegram Summary Broadcast</div>
                <div class="stage-subtitle">Delivering high-conviction alpha alerts &amp; regime summary</div>
              </div>
            </div>
            <div class="stage-badge" id="stage-4-badge">WAITING</div>
          </div>
        </div>

        <!-- Live Telemetry Strip -->
        <div class="telemetry-grid">
          <div class="metric-card">
            <div class="metric-title">⏱️ Elapsed Time</div>
            <div class="metric-value" id="tel-elapsed">0m 00s</div>
          </div>
          <div class="metric-card">
            <div class="metric-title">⏳ Time Remaining</div>
            <div class="metric-value" id="tel-eta">Calculating...</div>
          </div>
          <div class="metric-card">
            <div class="metric-title">⚡ Current Symbol</div>
            <div class="metric-value" id="tel-symbol">—</div>
          </div>
          <div class="metric-card">
            <div class="metric-title">📡 Telegram Status</div>
            <div class="metric-value" id="tel-telegram">Queued</div>
          </div>
        </div>

      </div>
    </section>
  </main>

  <script>
    // Live Cairo Clock
    function updateCairoClock() {
      try {
        const formatter = new Intl.DateTimeFormat('en-GB', {
          timeZone: 'Africa/Cairo',
          hour: '2-digit', minute: '2-digit', second: '2-digit',
          hour12: false
        });
        const el = document.getElementById('cairo-clock');
        if (el) el.innerText = formatter.format(new Date()) + ' CAIRO';
      } catch (e) {}
    }
    setInterval(updateCairoClock, 1000);
    updateCairoClock();

    // Futuristic Dual Sine Synthesizer Chime
    function playSuccessChime() {
      try {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (!AudioCtx) return;
        const ctx = new AudioCtx();
        const now = ctx.currentTime;

        const gain = ctx.createGain();
        gain.connect(ctx.destination);
        gain.gain.setValueAtTime(0, now);
        gain.gain.linearRampToValueAtTime(0.35, now + 0.04);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 1.6);

        // Root note C6 (1046.5 Hz) -> ramp to E6 (1318.5 Hz)
        const osc1 = ctx.createOscillator();
        osc1.type = 'sine';
        osc1.frequency.setValueAtTime(1046.5, now);
        osc1.frequency.exponentialRampToValueAtTime(1318.5, now + 0.25);
        osc1.connect(gain);
        osc1.start(now);
        osc1.stop(now + 1.6);

        // Harmonic octave C7 (2093 Hz) -> ramp to G6 (1567.9 Hz)
        const osc2 = ctx.createOscillator();
        osc2.type = 'triangle';
        osc2.frequency.setValueAtTime(2093.0, now);
        osc2.frequency.exponentialRampToValueAtTime(1567.9, now + 0.35);
        osc2.connect(gain);
        osc2.start(now);
        osc2.stop(now + 1.6);
      } catch (e) {
        console.log('Web Audio notification error:', e);
      }
    }

    let isScanRunning = false;
    let scanInitiatedInSession = false;
    let pollTimer = null;
    const CIRCLE_CIRCUMFERENCE = 339.292;

    function formatSeconds(sec) {
      if (sec === null || sec === undefined || isNaN(sec) || sec <= 0) return '0m 00s';
      const m = Math.floor(sec / 60);
      const s = Math.floor(sec % 60);
      return `${m}m ${s < 10 ? '0' : ''}${s}s`;
    }

    function updateRadialProgress(pct) {
      const circle = document.getElementById('radial-circle');
      const text = document.getElementById('radial-pct-text');
      const clamped = Math.max(0, Math.min(100, pct));
      const offset = CIRCLE_CIRCUMFERENCE - (clamped / 100) * CIRCLE_CIRCUMFERENCE;
      if (circle) circle.style.strokeDashoffset = offset;
      if (text) text.innerText = Math.round(clamped) + '%';
    }

    function setStageUI(stageId, state, badgeText, detailText) {
      const item = document.getElementById(`stage-${stageId}-item`);
      const badge = document.getElementById(`stage-${stageId}-badge`);
      const detail = document.getElementById(`stage-${stageId}-detail`);
      if (!item) return;

      item.className = 'stage-item ' + state;
      if (badge && badgeText) badge.innerText = badgeText;
      if (detail && detailText) detail.innerText = detailText;
    }

    function checkPipelineStatus() {
      fetch('/api/status')
        .then(res => res.json())
        .then(data => {
          const btn = document.getElementById('run-scan-btn');
          const progressSec = document.getElementById('progress-section');
          const heroDesc = document.getElementById('hero-status-desc');

          if (data.running) {
            isScanRunning = true;
            progressSec.style.display = 'flex';
            btn.classList.add('scanning');
            btn.disabled = true;

            const pct = typeof data.percent === 'number' ? data.percent : 0;
            btn.innerHTML = `<span>SCANNING IN PROGRESS [ ${Math.round(pct)}% ]</span>`;
            heroDesc.innerText = `Currently executing: Stage ${data.stage} — ${data.stage_name || ''}`;

            updateRadialProgress(pct);

            // Telemetry
            document.getElementById('tel-elapsed').innerText = formatSeconds(data.elapsed_seconds);
            document.getElementById('tel-eta').innerText = data.eta_seconds > 0 ? '~' + formatSeconds(data.eta_seconds) : 'Analyzing...';
            document.getElementById('tel-symbol').innerText = data.current_symbol ? `Scanning ${data.current_symbol}...` : 'Processing...';
            document.getElementById('tel-telegram').innerText = data.telegram_status || 'Queued';

            // Multi-Stage Checklist Logic
            const st = parseFloat(data.stage) || 1.0;

            // Stage 1
            if (st === 1.0) {
              const processed = data.processed || 0;
              const total = data.total || 227;
              setStageUI('1', 'active', 'ACTIVE', `Scanned ${processed}/${total} symbols (${pct.toFixed(1)}%)`);
              setStageUI('15', '', 'WAITING', null);
              setStageUI('2', '', 'WAITING', null);
              setStageUI('3', '', 'WAITING', null);
              setStageUI('4', '', 'WAITING', null);
            } else if (st === 1.5) {
              setStageUI('1', 'completed', 'DONE', `227 symbols analyzed`);
              setStageUI('15', 'active', 'ACTIVE', 'Backfilling outcomes against historical signals...');
              setStageUI('2', '', 'WAITING', null);
              setStageUI('3', '', 'WAITING', null);
              setStageUI('4', '', 'WAITING', null);
            } else if (st === 2.0) {
              setStageUI('1', 'completed', 'DONE', null);
              setStageUI('15', 'completed', 'DONE', null);
              setStageUI('2', 'active', 'ACTIVE', 'Retraining XGBoost & LightGBM classifiers...');
              setStageUI('3', '', 'WAITING', null);
              setStageUI('4', '', 'WAITING', null);
            } else if (st === 3.0) {
              setStageUI('1', 'completed', 'DONE', null);
              setStageUI('15', 'completed', 'DONE', null);
              setStageUI('2', 'completed', 'DONE', null);
              setStageUI('3', 'active', 'ACTIVE', 'Building reports/dashboard.html...');
              setStageUI('4', '', 'WAITING', null);
            } else if (st >= 4.0) {
              setStageUI('1', 'completed', 'DONE', null);
              setStageUI('15', 'completed', 'DONE', null);
              setStageUI('2', 'completed', 'DONE', null);
              setStageUI('3', 'completed', 'DONE', null);
              setStageUI('4', 'active', 'ACTIVE', data.telegram_status || 'Delivering...');
            }

            pollTimer = setTimeout(checkPipelineStatus, 1000);
          } else if ((isScanRunning || scanInitiatedInSession) && data.completed) {
            // Completed scan sequence!
            isScanRunning = false;
            scanInitiatedInSession = false;

            btn.classList.remove('scanning');
            btn.innerHTML = `<span>SCAN COMPLETE [ 100% ]</span>`;
            updateRadialProgress(100);

            // Mark all stages completed
            setStageUI('1', 'completed', 'DONE', '227 symbols scanned');
            setStageUI('15', 'completed', 'DONE', 'Historical outcomes updated');
            setStageUI('2', 'completed', 'DONE', 'Models updated & verified');
            setStageUI('3', 'completed', 'DONE', 'Terminal dashboard generated');
            setStageUI('4', 'completed', 'DELIVERED', 'Telegram summary published');

            document.getElementById('tel-symbol').innerText = 'All Symbols Analyzed';
            document.getElementById('tel-eta').innerText = '0m 00s';
            document.getElementById('tel-telegram').innerText = 'Delivered ✅';

            // Play futuristic success audio chime
            playSuccessChime();

            // Display Green Celebration Toast
            const toast = document.getElementById('toast-banner');
            if (toast) toast.style.display = 'block';

            // Auto-forward to Institutional Dashboard after 1.5s
            setTimeout(() => {
              window.location.href = '/dashboard';
            }, 1500);
          } else {
            // Idle state
            btn.classList.remove('scanning');
            btn.disabled = false;
            btn.innerHTML = `<span>▶ RUN SCAN</span>`;
            pollTimer = setTimeout(checkPipelineStatus, 3000);
          }
        })
        .catch(err => {
          console.error('Status check error:', err);
          pollTimer = setTimeout(checkPipelineStatus, 3000);
        });
    }

    function triggerScan() {
      const btn = document.getElementById('run-scan-btn');
      btn.disabled = true;
      btn.innerHTML = `<span>INITIALIZING SCAN...</span>`;
      scanInitiatedInSession = true;

      fetch('/api/scan', { method: 'POST' })
        .then(res => res.json())
        .then(data => {
          if (data.status === 'already running') {
            console.log('Scan already running in background.');
          }
          if (pollTimer) clearTimeout(pollTimer);
          setTimeout(checkPipelineStatus, 600);
        })
        .catch(err => {
          alert('Failed to trigger scan: ' + err);
          btn.disabled = false;
          btn.innerHTML = `<span>▶ RUN SCAN</span>`;
        });
    }

    // Initialize check on page load
    checkPipelineStatus();
  </script>
</body>
</html>
"""


def render_access_gate_html() -> str:
    node_id = get_short_node_id()
    hostname = socket.gethostname()
    username = os.environ.get("USERNAME", "Unknown")

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PRAECURSOR // EGX — Institutional Access Gate</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg-dark: #07090e;
      --bg-card: rgba(13, 18, 36, 0.78);
      --cyan-neon: #00f2fe;
      --cyan-glow: rgba(0, 242, 254, 0.35);
      --blue-accent: #4facfe;
      --emerald-neon: #10b981;
      --red-accent: #ef4444;
      --border-subtle: rgba(56, 189, 248, 0.22);
      --border-active: rgba(0, 242, 254, 0.65);
      --text-main: #f8fafc;
      --text-muted: #94a3b8;
      --font-mono: 'JetBrains Mono', monospace;
      --font-sans: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    }}

    * {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      background-color: var(--bg-dark);
      background-image: 
        radial-gradient(ellipse at 50% 15%, rgba(0, 242, 254, 0.08) 0%, transparent 65%),
        radial-gradient(circle at 85% 85%, rgba(79, 172, 254, 0.05) 0%, transparent 50%),
        linear-gradient(to right, rgba(255, 255, 255, 0.02) 1px, transparent 1px),
        linear-gradient(to bottom, rgba(255, 255, 255, 0.02) 1px, transparent 1px);
      background-size: 100% 100%, 100% 100%, 36px 36px, 36px 36px;
      color: var(--text-main);
      font-family: var(--font-sans);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 24px 20px;
    }}

    .gate-container {{
      width: 100%;
      max-width: 620px;
      background: var(--bg-card);
      backdrop-filter: blur(20px);
      -webkit-backdrop-filter: blur(20px);
      border: 1px solid var(--border-subtle);
      border-radius: 24px;
      padding: 38px 36px;
      box-shadow: 0 25px 60px rgba(0, 0, 0, 0.8), 0 0 45px rgba(0, 242, 254, 0.08);
      position: relative;
      overflow: hidden;
    }}

    .gate-container::before {{
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 3px;
      background: linear-gradient(90deg, transparent, var(--cyan-neon), transparent);
    }}

    .top-badge {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      background: rgba(0, 242, 254, 0.12);
      border: 1px solid rgba(0, 242, 254, 0.35);
      color: var(--cyan-neon);
      font-family: var(--font-mono);
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 1px;
      padding: 4px 12px;
      border-radius: 20px;
      margin-bottom: 18px;
    }}

    .top-badge .dot {{
      width: 6px;
      height: 6px;
      background: var(--cyan-neon);
      border-radius: 50%;
      box-shadow: 0 0 8px var(--cyan-neon);
    }}

    h1.gate-header {{
      font-family: var(--font-mono);
      font-size: 20px;
      font-weight: 800;
      letter-spacing: 0.5px;
      color: #fff;
      line-height: 1.4;
      margin-bottom: 8px;
      display: flex;
      align-items: center;
      gap: 10px;
    }}

    p.gate-sub {{
      color: var(--text-muted);
      font-size: 13.5px;
      line-height: 1.5;
      margin-bottom: 24px;
    }}

    .terminal-card {{
      background: rgba(7, 10, 20, 0.65);
      border: 1px solid rgba(56, 189, 248, 0.16);
      border-radius: 14px;
      padding: 18px 20px;
      margin-bottom: 24px;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }}

    .card-row {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 13px;
    }}

    .card-label {{
      color: var(--text-muted);
      font-family: var(--font-sans);
      font-weight: 500;
    }}

    .card-value {{
      font-family: var(--font-mono);
      font-weight: 600;
      color: #fff;
    }}

    .card-value.highlight-cyan {{
      color: var(--cyan-neon);
      text-shadow: 0 0 10px rgba(0, 242, 254, 0.4);
    }}

    .card-value.status-locked {{
      color: #f87171;
      background: rgba(239, 68, 68, 0.15);
      border: 1px solid rgba(239, 68, 68, 0.3);
      padding: 2px 8px;
      border-radius: 6px;
      font-size: 11px;
    }}

    .card-value.status-ok {{
      color: #34d399;
      background: rgba(16, 185, 129, 0.15);
      border: 1px solid rgba(16, 185, 129, 0.3);
      padding: 2px 8px;
      border-radius: 6px;
      font-size: 11px;
    }}

    .btn {{
      width: 100%;
      padding: 13px 20px;
      border-radius: 12px;
      font-family: var(--font-mono);
      font-size: 13.5px;
      font-weight: 700;
      letter-spacing: 0.5px;
      cursor: pointer;
      display: inline-flex;
      justify-content: center;
      align-items: center;
      gap: 10px;
      transition: all 0.25s ease;
      outline: none;
    }}

    .btn-telegram {{
      background: linear-gradient(135deg, rgba(14, 165, 233, 0.2), rgba(2, 132, 199, 0.3));
      border: 1px solid rgba(56, 189, 248, 0.4);
      color: #38bdf8;
      box-shadow: 0 4px 18px rgba(2, 132, 199, 0.2);
      margin-bottom: 22px;
    }}

    .btn-telegram:hover:not(:disabled) {{
      background: linear-gradient(135deg, rgba(14, 165, 233, 0.35), rgba(2, 132, 199, 0.5));
      border-color: var(--cyan-neon);
      color: #fff;
      box-shadow: 0 0 20px rgba(0, 242, 254, 0.35);
      transform: translateY(-1px);
    }}

    .btn-verify {{
      background: linear-gradient(135deg, #0284c7, #2563eb);
      border: 1px solid rgba(56, 189, 248, 0.5);
      color: #fff;
      box-shadow: 0 4px 20px rgba(37, 99, 235, 0.35);
    }}

    .btn-verify:hover:not(:disabled) {{
      background: linear-gradient(135deg, #00f2fe, #4facfe);
      color: #070913;
      box-shadow: 0 0 25px rgba(0, 242, 254, 0.5);
      transform: translateY(-1px);
    }}

    .btn:disabled {{
      opacity: 0.6;
      cursor: not-allowed;
      transform: none !important;
    }}

    .input-group {{
      display: flex;
      flex-direction: column;
      gap: 10px;
      margin-bottom: 22px;
    }}

    .pin-input {{
      width: 100%;
      background: rgba(7, 10, 20, 0.85);
      border: 1px solid rgba(56, 189, 248, 0.3);
      border-radius: 12px;
      padding: 13px 18px;
      color: #fff;
      font-family: var(--font-mono);
      font-size: 15px;
      letter-spacing: 2px;
      outline: none;
      transition: all 0.2s ease;
      text-align: center;
    }}

    .pin-input:focus {{
      border-color: var(--cyan-neon);
      box-shadow: 0 0 16px rgba(0, 242, 254, 0.3);
      background: rgba(13, 18, 36, 0.95);
    }}

    .pin-input::placeholder {{
      color: #64748b;
      letter-spacing: 0.5px;
      font-size: 13.5px;
    }}

    .helper-text {{
      font-size: 12.5px;
      color: #94a3b8;
      text-align: center;
      line-height: 1.5;
      font-style: italic;
    }}

    .toast-msg {{
      display: none;
      padding: 12px 16px;
      border-radius: 10px;
      font-size: 13px;
      margin-bottom: 18px;
      text-align: center;
      font-weight: 500;
    }}

    .toast-success {{
      background: rgba(16, 185, 129, 0.15);
      border: 1px solid rgba(16, 185, 129, 0.4);
      color: #34d399;
    }}

    .toast-error {{
      background: rgba(239, 68, 68, 0.15);
      border: 1px solid rgba(239, 68, 68, 0.4);
      color: #f87171;
    }}

    .toast-info {{
      background: rgba(0, 242, 254, 0.12);
      border: 1px solid rgba(0, 242, 254, 0.35);
      color: var(--cyan-neon);
    }}
  </style>
</head>
<body>
  <div class="gate-container">
    <div class="top-badge"><div class="dot"></div> CRYPTO-GATE // HARDWARE RESTRICTED</div>
    <h1 class="gate-header">🔒 PRAECURSOR-EGX // INSTITUTIONAL ACCESS GATE</h1>
    <p class="gate-sub">This terminal workstation is not currently authorized. An institutional cryptographic permission slip is required to unlock Mission Control.</p>

    <div class="terminal-card">
      <div class="card-row">
        <span class="card-label">Node ID:</span>
        <span class="card-value highlight-cyan" id="disp-node">{node_id}</span>
      </div>
      <div class="card-row">
        <span class="card-label">Host:</span>
        <span class="card-value">{hostname}</span>
      </div>
      <div class="card-row">
        <span class="card-label">User:</span>
        <span class="card-value">{username}</span>
      </div>
      <div class="card-row">
        <span class="card-label">Platform:</span>
        <span class="card-value">Windows x64 (HMAC-SHA256)</span>
      </div>
      <div class="card-row">
        <span class="card-label">Terminal Status:</span>
        <span class="card-value status-locked" id="disp-status">LOCKED (UNAUTHORIZED)</span>
      </div>
    </div>

    <div id="toast" class="toast-msg"></div>

    <button id="req-btn" class="btn btn-telegram" onclick="requestTelegramAccess()">
      🚀 Request Access via Telegram
    </button>

    <div class="input-group">
      <input type="text" id="pin-input" class="pin-input" placeholder="Enter Permission Slip PIN Code" autofocus />
      <button id="verify-btn" class="btn btn-verify" onclick="verifyPin()">
        🔑 Verify & Unlock Terminal
      </button>
    </div>

    <p class="helper-text">
      Your request is sent to the Administrator. Enter the PIN provided to permanently authorize this terminal.
    </p>
  </div>

  <script>
    function showToast(msg, type) {{
      const t = document.getElementById('toast');
      t.innerText = msg;
      t.className = 'toast-msg ' + (type === 'success' ? 'toast-success' : type === 'error' ? 'toast-error' : 'toast-info');
      t.style.display = 'block';
    }}

    function requestTelegramAccess() {{
      const btn = document.getElementById('req-btn');
      btn.disabled = true;
      btn.innerText = 'DISPATCHING ACCESS REQUEST...';
      showToast('Transmitting access request to Administrator Telegram...', 'info');

      fetch('/api/access/request', {{ method: 'POST' }})
        .then(r => r.json())
        .then(d => {{
          if (d.ok) {{
            showToast('✅ Access request dispatched to Telegram! Reply to message or enter PIN below.', 'success');
            btn.innerText = '✅ Request Sent via Telegram';
          }} else {{
            showToast('❌ ' + (d.message || 'Failed to dispatch request.'), 'error');
            btn.disabled = false;
            btn.innerText = '🚀 Request Access via Telegram';
          }}
        }})
        .catch(err => {{
          showToast('❌ Network error: ' + err, 'error');
          btn.disabled = false;
          btn.innerText = '🚀 Request Access via Telegram';
        }});
    }}

    function verifyPin() {{
      const pin = document.getElementById('pin-input').value.trim();
      const btn = document.getElementById('verify-btn');
      btn.disabled = true;
      btn.innerText = 'VERIFYING CREDENTIALS...';
      showToast('Validating Telegram approval & HMAC license...', 'info');

      fetch('/api/access/verify', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ pin: pin }})
      }})
        .then(r => r.json())
        .then(d => {{
          if (d.ok) {{
            showToast('🎉 ' + (d.message || 'PIN verified! Terminal whitelisted permanently.'), 'success');
            btn.innerText = '✅ TERMINAL UNLOCKED';
            const stat = document.getElementById('disp-status');
            stat.className = 'card-value status-ok';
            stat.innerText = 'AUTHORIZED // WHITELISTED';
            setTimeout(() => {{
              window.location.reload();
            }}, 1200);
          }} else {{
            showToast('❌ ' + (d.message || 'PIN verification failed.'), 'error');
            btn.disabled = false;
            btn.innerText = '🔑 Verify & Unlock Terminal';
          }}
        }})
        .catch(err => {{
          showToast('❌ Error: ' + err, 'error');
          btn.disabled = false;
          btn.innerText = '🔑 Verify & Unlock Terminal';
        }});
    }}

    document.getElementById('pin-input').addEventListener('keypress', function(e) {{
      if (e.key === 'Enter') {{
        verifyPin();
      }}
    }});
  </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def get_mission_control() -> HTMLResponse:
    """Serve the dedicated Cyberpunk Mission Control Launch Screen or Access Gate."""
    if not is_machine_whitelisted():
        response = HTMLResponse(render_access_gate_html())
    else:
        response = HTMLResponse(MISSION_CONTROL_HTML)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard_terminal() -> Any:
    """Serve the full terminal dashboard (reports/dashboard.html) or Access Gate."""
    if not is_machine_whitelisted():
        response = HTMLResponse(render_access_gate_html())
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    if not DEFAULT_DASHBOARD_REPORT.exists():
        return RedirectResponse(url="/", status_code=303)

    try:
        html = DEFAULT_DASHBOARD_REPORT.read_text(encoding="utf-8", errors="replace")
    except (FileNotFoundError, OSError):
        return RedirectResponse(url="/", status_code=303)

    # Inject auto-refresh every 300s
    if "<head>" in html and "http-equiv=\"refresh\"" not in html:
        html = html.replace("<head>", "<head>\n  <meta http-equiv=\"refresh\" content=\"300\" />")

    # Seamless bottom-right Mission Control navigation bar
    fab_html = """
    <div style="position:fixed;bottom:24px;right:24px;display:flex;gap:12px;z-index:9999;">
        <a href="/" style="display:inline-flex;align-items:center;gap:8px;padding:12px 20px;background:rgba(15,23,42,0.9);backdrop-filter:blur(10px);border:1px solid rgba(56,189,248,0.4);border-radius:30px;color:#38bdf8;text-decoration:none;font-weight:700;font-size:13px;letter-spacing:0.5px;box-shadow:0 8px 24px rgba(0,0,0,0.6);transition:all 0.2s ease;">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
            MISSION CONTROL
        </a>
        <button id="scan-btn" onclick="triggerScanFab()" style="display:inline-flex;align-items:center;gap:8px;padding:12px 22px;background:linear-gradient(135deg,#0284c7,#2563eb);border:1px solid rgba(56,189,248,0.5);border-radius:30px;color:#fff;font-weight:700;font-size:13px;letter-spacing:0.5px;cursor:pointer;box-shadow:0 8px 24px rgba(2,132,199,0.4);transition:all 0.2s ease;">
            ▶ RUN SCAN
        </button>
    </div>
    <script>
    function triggerScanFab() {
        const btn = document.getElementById('scan-btn');
        btn.innerText = 'STARTING...';
        btn.disabled = true;
        fetch('/api/scan', {method: 'POST'})
            .then(r => r.json())
            .then(d => {
                window.location.href = '/';
            })
            .catch(e => {
                alert('Error: ' + e);
                btn.innerText = '▶ RUN SCAN';
                btn.disabled = false;
            });
    }
    </script>
    </body>
    """
    html = html.replace("</body>", fab_html)

    response = HTMLResponse(html)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.get("/api/access/status")
async def get_access_status() -> dict[str, Any]:
    return {
        "whitelisted": is_machine_whitelisted(),
        "node_id": get_short_node_id(),
    }


@app.post("/api/access/request")
async def request_access() -> dict[str, Any]:
    ok, message = send_telegram_access_request()
    return {"ok": ok, "message": message}


@app.post("/api/access/verify")
async def verify_access(request: Request) -> dict[str, Any]:
    pin = ""
    try:
        body = await request.json()
        if isinstance(body, dict):
            pin = str(body.get("pin", "")).strip()
    except Exception:
        pass
    if not pin:
        pin = request.query_params.get("pin", "").strip()
    ok, message = check_telegram_approval(entered_pin=pin)
    return {"ok": ok, "message": message}


@app.get("/api/status")
async def get_status() -> dict[str, Any]:
    """Return unified status from data/scan_status.json merged with in-memory state."""
    file_status = read_status_file()
    status: dict[str, Any] = {
        "running": scan_status.get("running", False),
        "stage": 1,
        "stage_name": "Market Data & Symbol Scanner",
        "processed": scan_status.get("processed", 0),
        "total": scan_status.get("total", 0),
        "percent": 0.0,
        "current_symbol": None,
        "elapsed_seconds": 0,
        "eta_seconds": 0,
        "telegram_status": "Queued for Stage 4",
        "error": scan_status.get("error", None),
        "completed": False,
    }

    if file_status:
        status.update(file_status)

    if scan_status.get("running"):
        status["running"] = True
    if scan_status.get("error"):
        status["error"] = scan_status["error"]

    return status


@app.post("/api/scan")
async def trigger_scan(background_tasks: BackgroundTasks) -> dict[str, str]:
    """Launch full autonomous pipeline via background subprocess."""
    current_stat = await get_status()
    if current_stat.get("running"):
        return {"status": "already running"}

    scan_status["running"] = True
    scan_status["error"] = None
    background_tasks.add_task(run_pipeline_subprocess)
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
