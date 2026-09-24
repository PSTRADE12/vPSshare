#!/usr/bin/env python3
"""vPS Share — FastAPI Backend & Single-Page Explorer.

Branding:
  Name:    vPS Share
  Tagline: VPS file explorer and file transfer tool by PSTECH
"""
import io
import json
import mimetypes
import os
import secrets
import shutil
import socket
import time
import urllib.parse
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import uvicorn
from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel

# ==============================================================================
#  Server Configuration Dataclass
# ==============================================================================
@dataclass
class ServerConfig:
    root_dir: Path
    port: int = 3000
    host: str = "0.0.0.0"
    readonly: bool = False
    show_hidden: bool = False
    enable_auth: bool = False
    auth_user: Optional[str] = None
    auth_pass: Optional[str] = None


# Global configuration instance (initialized on startup)
CONFIG = ServerConfig(
    root_dir=Path.cwd().resolve(),
)

# App Metadata — Locked to PSTECH
APP_NAME = "vPS Share"
TAGLINE = "VPS file explorer and file transfer tool by PSTECH"

app = FastAPI(title=APP_NAME, version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBasic(auto_error=False)


# ==============================================================================
#  Security & Helper Functions
# ==============================================================================
def verify_auth(credentials: Optional[HTTPBasicCredentials] = Depends(security)):
    if not CONFIG.enable_auth or not CONFIG.auth_user or not CONFIG.auth_pass:
        return True
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Basic"},
        )
    is_user = secrets.compare_digest(credentials.username, CONFIG.auth_user)
    is_pass = secrets.compare_digest(credentials.password, CONFIG.auth_pass)
    if not (is_user and is_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return True


def check_writable():
    if CONFIG.readonly:
        raise HTTPException(status_code=403, detail="Server is running in read-only mode")


def safe_resolve(rel_path: str) -> Path:
    """Strict sandboxing: ensure path remains inside canonical CONFIG.root_dir."""
    clean = urllib.parse.unquote(rel_path).strip().lstrip("/").lstrip("\\")
    target = (CONFIG.root_dir / clean).resolve()
    try:
        # Check canonical real path to prevent symlink bypasses
        real_root = os.path.realpath(CONFIG.root_dir)
        real_target = os.path.realpath(target)
        if not real_target.startswith(real_root):
            raise HTTPException(status_code=403, detail="Access denied: outside root directory")
    except Exception:
        raise HTTPException(status_code=403, detail="Invalid path")
    return target


def format_size(bytes_size: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}" if unit != "B" else f"{bytes_size} B"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} PB"


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


# ==============================================================================
#  Pydantic Models
# ==============================================================================
class MkdirRequest(BaseModel):
    path: str = ""
    name: str

class RenameRequest(BaseModel):
    path: str
    new_name: str

class DeleteRequest(BaseModel):
    paths: List[str]

class CopyMoveRequest(BaseModel):
    paths: List[str]
    dest_dir: str
    action: str  # "copy" or "move"

class ZipManifestRequest(BaseModel):
    paths: List[str]


# ==============================================================================
#  Frontend HTML/CSS/JS (Embedded, Zero Heavy Frameworks, Instant Loading)
# ==============================================================================
HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>vPS Share</title>
  <meta name="theme-color" content="#070D1E" />
  <link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🗂️</text></svg>">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #070D1E;
      --card-bg: rgba(16, 26, 49, 0.85);
      --card-border: rgba(255, 255, 255, 0.08);
      --card-border-hover: rgba(56, 189, 248, 0.4);
      --accent: #F59E0B;
      --accent-hover: #FBBF24;
      --accent-glow: rgba(245, 158, 11, 0.25);
      --text: #F8FAFC;
      --text-muted: #94A3B8;
      --blue: #38BDF8;
      --blue-hover: #0ea5e9;
      --emerald: #10B981;
      --danger: #EF4444;
      --purple: #A855F7;
      --font-display: 'Space Grotesk', 'Inter', system-ui, sans-serif;
      --font-body: 'Inter', system-ui, -apple-system, sans-serif;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: var(--font-body);
      -webkit-font-smoothing: antialiased;
      text-rendering: optimizeLegibility;
      background: radial-gradient(circle at 15% 15%, #0F172A 0%, #070D1E 65%, #020617 100%);
      color: var(--text);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }
    ::selection { background: rgba(245, 158, 11, 0.3); }
    .container { max-width: 1280px; width: 100%; margin: 0 auto; padding: 24px 20px 80px; flex: 1; }
    
    /* Header */
    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 24px;
      padding-bottom: 18px;
      border-bottom: 1px solid var(--card-border);
      flex-wrap: wrap;
      gap: 16px;
    }
    .logo-area { display: flex; align-items: center; gap: 14px; }
    .logo-icon {
      width: 48px; height: 48px;
      border-radius: 14px;
      background: linear-gradient(135deg, #F59E0B 0%, #D97706 100%);
      display: flex; align-items: center; justify-content: center;
      font-size: 25px;
      box-shadow: 0 6px 20px var(--accent-glow), inset 0 1px 0 rgba(255,255,255,0.25);
    }
    .brand-title {
      font-family: var(--font-display);
      font-size: 26px; font-weight: 700; letter-spacing: -0.02em;
      display: flex; align-items: center; gap: 10px;
      background: linear-gradient(92deg, #FFFFFF 30%, #93C5FD 100%);
      -webkit-background-clip: text; background-clip: text;
      -webkit-text-fill-color: transparent;
    }
    .brand-subtitle { font-size: 13px; color: var(--text-muted); margin-top: 3px; letter-spacing: 0.01em; }
    
    .stats-badge {
      display: flex; align-items: center; gap: 16px; background: rgba(255, 255, 255, 0.04);
      border: 1px solid var(--card-border); padding: 9px 16px; border-radius: 12px;
      font-size: 13px; backdrop-filter: blur(8px);
    }
    .stats-item { display: flex; align-items: center; gap: 6px; }
    .status-pill {
      font-size: 11px; font-weight: 700; padding: 4px 10px; border-radius: 20px;
      background: rgba(16, 185, 129, 0.15); color: var(--emerald);
      border: 1px solid rgba(16, 185, 129, 0.3);
    }
    .status-pill.readonly {
      background: rgba(239, 68, 68, 0.15); color: var(--danger);
      border-color: rgba(239, 68, 68, 0.3);
    }

    /* Action Toolbar */
    .toolbar {
      display: flex; justify-content: space-between; align-items: center;
      margin-bottom: 20px; flex-wrap: wrap; gap: 14px;
    }
    .toolbar-left, .toolbar-right { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
    
    .btn {
      padding: 9px 16px; border-radius: 10px; font-size: 13px; font-weight: 600;
      border: 1px solid transparent; cursor: pointer; display: inline-flex;
      align-items: center; gap: 8px; transition: all 0.15s ease;
      text-decoration: none; user-select: none; font-family: var(--font-body);
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
    }
    .btn:hover { transform: translateY(-1px); }
    .btn:active { transform: translateY(0); }
    .btn .ico {
      font-size: 15px; line-height: 1; display: inline-flex;
      filter: drop-shadow(0 2px 3px rgba(0, 0, 0, 0.3));
    }
    .btn-primary {
      background: var(--blue); color: #020617; border-color: var(--blue);
    }
    .btn-primary:hover { background: var(--blue-hover); }
    .btn-accent {
      background: var(--accent); color: #020617; border-color: var(--accent);
    }
    .btn-accent:hover { background: var(--accent-hover); }
    .btn-secondary {
      background: rgba(255, 255, 255, 0.06); color: var(--text);
      border: 1px solid var(--card-border);
    }
    .btn-secondary:hover { background: rgba(255, 255, 255, 0.1); border-color: rgba(255, 255, 255, 0.2); }
    .btn-danger {
      background: rgba(239, 68, 68, 0.15); color: var(--danger);
      border: 1px solid rgba(239, 68, 68, 0.3);
    }
    .btn-danger:hover { background: var(--danger); color: #fff; }
    .btn:disabled { opacity: 0.5; cursor: not-allowed; }

    /* Navigation & Search */
    .nav-bar {
      display: flex; justify-content: space-between; align-items: center;
      margin-bottom: 16px; flex-wrap: wrap; gap: 12px;
      background: var(--card-bg); border: 1px solid var(--card-border);
      padding: 10px 14px; border-radius: 14px;
    }
    .breadcrumbs {
      display: flex; align-items: center; gap: 6px; font-size: 14px;
      color: var(--text-muted); flex-wrap: wrap;
    }
    .crumb-btn {
      color: var(--blue); cursor: pointer; text-decoration: none;
      font-weight: 600; padding: 3px 8px; border-radius: 8px;
      transition: background 0.15s, color 0.15s; font-size: 13.5px;
    }
    .crumb-btn:hover { background: rgba(56, 189, 248, 0.15); color: #fff; }
    .crumb-btn.root-crumb {
      color: var(--text); font-family: var(--font-display); font-weight: 700;
      background: linear-gradient(135deg, rgba(245, 158, 11, 0.12), rgba(56, 189, 248, 0.1));
      border: 1px solid rgba(245, 158, 11, 0.25);
      padding: 4px 12px; letter-spacing: 0.01em;
      display: inline-flex; align-items: center; gap: 7px;
    }
    .crumb-btn.root-crumb::before { content: '🗂️'; font-size: 14px; line-height: 1; }
    .crumb-btn.root-crumb:hover { border-color: var(--accent); color: var(--accent); background: rgba(245, 158, 11, 0.15); }
    .fixed-crumb { display: inline-flex; align-items: center; gap: 4px; color: var(--text-muted); }
    .search-box { position: relative; display: flex; align-items: center; }
    .search-box input {
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid var(--card-border);
      padding: 9px 14px 9px 34px; border-radius: 10px;
      color: var(--text); font-size: 13px; outline: none;
      width: 230px; transition: all 0.2s; font-family: var(--font-body);
    }
    .search-box input:focus {
      border-color: var(--blue); width: 280px;
      background: rgba(255, 255, 255, 0.09);
    }
    .search-box::before {
      content: '🔍'; position: absolute; left: 10px; font-size: 13px;
      opacity: 0.6; pointer-events: none;
    }

    /* Clipboard notification banner */
    .clipboard-bar {
      display: none; justify-content: space-between; align-items: center;
      background: rgba(168, 85, 247, 0.12); border: 1px solid rgba(168, 85, 247, 0.3);
      padding: 10px 18px; border-radius: 12px; margin-bottom: 16px;
    }
    .clipboard-text { font-size: 13px; color: #E9D5FF; font-weight: 600; }

    /* Drag & Drop Upload Zone */
    .upload-zone {
      border: 2px dashed rgba(56, 189, 248, 0.35);
      background: linear-gradient(180deg, rgba(56, 189, 248, 0.05), rgba(245, 158, 11, 0.03));
      border-radius: 16px; padding: 26px 22px; text-align: center;
      margin-bottom: 20px; transition: all 0.2s ease; cursor: pointer;
    }
    .upload-zone:hover { border-color: rgba(56, 189, 248, 0.6); }
    .upload-zone.dragover {
      border-color: var(--accent); background: rgba(245, 158, 11, 0.1);
      transform: scale(1.005);
    }
    .upload-icon {
      width: 60px; height: 60px; margin: 0 auto 10px; font-size: 28px;
      display: flex; align-items: center; justify-content: center; border-radius: 18px;
      background: linear-gradient(135deg, rgba(56, 189, 248, 0.16), rgba(245, 158, 11, 0.16));
      border: 1px solid var(--card-border);
      box-shadow: 0 4px 14px rgba(0, 0, 0, 0.25);
    }
    .upload-text { font-size: 15px; font-weight: 700; margin-bottom: 4px; font-family: var(--font-display); letter-spacing: 0.01em; }
    .upload-subtext { font-size: 12.5px; color: var(--text-muted); }
    .upload-progress-container {
      width: 100%; max-width: 480px; margin: 14px auto 0;
      background: rgba(255, 255, 255, 0.08);
      border-radius: 999px; height: 10px; overflow: hidden;
      display: none; position: relative;
    }
    .upload-progress-bar {
      height: 100%; width: 0%;
      background: linear-gradient(90deg, var(--blue), var(--accent));
      border-radius: 999px; transition: width 0.15s ease-out;
    }
    .progress-details {
      font-size: 12px; color: var(--text-muted); margin-top: 6px;
      display: none; font-variant-numeric: tabular-nums;
    }

    /* Table Explorer */
    .table-container {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 14px; overflow: hidden;
      box-shadow: 0 10px 30px rgba(0, 0, 0, 0.35);
    }
    table { width: 100%; border-collapse: collapse; text-align: left; }
    th {
      padding: 13px 18px; font-size: 12px; font-weight: 700;
      color: var(--text-muted); text-transform: uppercase;
      letter-spacing: 0.06em; border-bottom: 1px solid var(--card-border);
      background: rgba(255, 255, 255, 0.025); font-family: var(--font-display);
    }
    td {
      padding: 12px 18px; font-size: 14px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.04);
      vertical-align: middle;
    }
    tr:last-child td { border-bottom: none; }
    tr:hover td { background: rgba(56, 189, 248, 0.045); }
    .item-name {
      display: flex; align-items: center; gap: 11px;
      font-weight: 600; color: var(--text); cursor: pointer;
      text-decoration: none; word-break: break-all; text-align: left;
    }
    .item-name:hover { color: var(--blue); }
    .file-icon {
      width: 32px; height: 32px; flex-shrink: 0; font-size: 16px;
      display: inline-flex; align-items: center; justify-content: center; border-radius: 9px;
      background: rgba(255, 255, 255, 0.05); border: 1px solid var(--card-border);
      box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
    }
    tr:hover .file-icon { border-color: rgba(56, 189, 248, 0.25); }
    .meta-col { font-size: 13px; color: var(--text-muted); white-space: nowrap; }
    
    .action-icons { display: flex; align-items: center; justify-content: flex-end; gap: 7px; flex-wrap: wrap; }
    .mini-btn {
      padding: 6px 12px; border-radius: 8px; font-size: 12.5px; font-weight: 600;
      border: 1px solid var(--card-border); cursor: pointer; text-decoration: none;
      display: inline-flex; align-items: center; gap: 7px; transition: all 0.15s ease;
      background: rgba(255, 255, 255, 0.04); color: var(--text); white-space: nowrap;
      font-family: var(--font-body);
    }
    .mini-btn:hover {
      background: rgba(255, 255, 255, 0.1); border-color: rgba(255, 255, 255, 0.2);
      transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
    }
    .mini-btn .ico {
      font-size: 15px; line-height: 1; display: inline-flex; align-items: center;
      justify-content: center; filter: drop-shadow(0 2px 3px rgba(0, 0, 0, 0.35));
    }
    .mini-btn.preview { color: var(--accent); border-color: rgba(245, 158, 11, 0.35); background: rgba(245, 158, 11, 0.08); }
    .mini-btn.preview:hover { background: rgba(245, 158, 11, 0.18); box-shadow: 0 4px 14px rgba(245, 158, 11, 0.25); }
    .mini-btn.download { color: var(--blue); border-color: rgba(56, 189, 248, 0.35); background: rgba(56, 189, 248, 0.08); }
    .mini-btn.download:hover { background: rgba(56, 189, 248, 0.18); box-shadow: 0 4px 14px rgba(56, 189, 248, 0.25); }
    .mini-btn.danger { color: var(--danger); border-color: rgba(239, 68, 68, 0.35); background: rgba(239, 68, 68, 0.08); }
    .mini-btn.danger:hover { background: var(--danger); color: #fff; box-shadow: 0 4px 14px rgba(239, 68, 68, 0.35); }
    .mini-btn.danger:hover .ico { filter: none; }

    /* Floating Batch Bar */
    .batch-bar {
      position: fixed; bottom: 28px; left: 50%; transform: translateX(-50%);
      background: rgba(15, 23, 42, 0.96); border: 1px solid var(--blue);
      box-shadow: 0 10px 30px rgba(0, 0, 0, 0.6), 0 0 20px rgba(56, 189, 248, 0.25);
      padding: 10px 16px 10px 20px; border-radius: 999px; display: none;
      align-items: center; gap: 10px; z-index: 100; backdrop-filter: blur(12px);
    }
    .batch-count { font-size: 13px; font-weight: 700; color: var(--blue); font-family: var(--font-display); }
    .batch-bar .btn { padding: 7px 13px; font-size: 12.5px; box-shadow: none; }

    /* Modals */
    .modal-backdrop {
      position: fixed; inset: 0; background: rgba(0, 0, 0, 0.85);
      display: none; align-items: center; justify-content: center;
      z-index: 200; padding: 20px;
    }
    .modal-content {
      background: #0D1629; border: 1px solid var(--card-border);
      border-radius: 16px; max-width: 960px; width: 100%; max-height: 90vh;
      display: flex; flex-direction: column; overflow: hidden;
      box-shadow: 0 20px 50px rgba(0, 0, 0, 0.7);
    }
    .modal-sm { max-width: 440px; }
    .modal-header {
      display: flex; justify-content: space-between; align-items: center;
      padding: 16px 20px; border-bottom: 1px solid var(--card-border);
    }
    .modal-title { font-weight: 700; font-size: 16px; font-family: var(--font-display); letter-spacing: -0.01em; }
    .modal-content { animation: modalIn 0.18s ease; }
    @keyframes modalIn { from { opacity: 0; transform: translateY(8px) scale(0.99); } to { opacity: 1; transform: none; } }
    .close-modal { background: none; border: none; font-size: 22px; color: var(--text-muted); cursor: pointer; }
    .close-modal:hover { color: #fff; }
    .modal-body { padding: 20px; overflow: auto; min-height: 180px; }
    .modal-body video, .modal-body img { max-width: 100%; max-height: 70vh; border-radius: 8px; display: block; margin: 0 auto; }
    .modal-body audio { width: 100%; max-width: 480px; display: block; margin: 40px auto; }
    .code-viewer {
      text-align: left; width: 100%; max-height: 70vh; overflow: auto;
      background: #030712; padding: 16px; border-radius: 8px;
      font-size: 13px; font-family: ui-monospace, SFMono-Regular, monospace;
      color: #E2E8F0; line-height: 1.5; white-space: pre; border: 1px solid var(--card-border);
    }
    .modal-footer {
      display: flex; justify-content: flex-end; gap: 10px;
      padding: 14px 20px; border-top: 1px solid var(--card-border);
    }
    .modal-input {
      width: 100%; background: rgba(255, 255, 255, 0.05);
      border: 1px solid var(--card-border); border-radius: 8px;
      padding: 10px 14px; color: #fff; font-size: 14px; outline: none;
      margin-top: 8px;
    }
    .modal-input:focus { border-color: var(--blue); }

    /* Footer */
    footer {
      text-align: center; font-size: 12px; color: var(--text-muted);
      padding: 20px; border-top: 1px solid var(--card-border);
      background: rgba(7, 13, 30, 0.9);
    }
    footer a { color: var(--accent); text-decoration: none; font-weight: 700; }
    footer a:hover { text-decoration: underline; }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div class="logo-area">
        <div class="logo-icon">📁</div>
        <div>
          <div class="brand-title">vPS Share</div>
          <div class="brand-subtitle">VPS file explorer and file transfer tool by PSTECH</div>
        </div>
      </div>
      <div class="stats-badge">
        <div class="stats-item" id="storageWidget">💾 Loading storage...</div>
        {{STATUS_BADGE}}
      </div>
    </header>

    <!-- Action Toolbar -->
    <div class="toolbar">
      <div class="toolbar-left">
        {{TOOLBAR_WRITE_ACTIONS}}
        <button class="btn btn-secondary" onclick="reloadCurrentDir()"><span class="ico">🔄</span> Refresh</button>
      </div>
      <div class="toolbar-right">
        <div class="search-box">
          <input type="text" id="searchInput" placeholder="Filter folder files..." onkeyup="filterFiles()" />
        </div>
      </div>
    </div>

    <!-- Clipboard Bar (For Cut/Copy & Paste) -->
    <div class="clipboard-bar" id="clipboardBar">
      <span class="clipboard-text" id="clipboardText">Clipboard items</span>
      <div style="display: flex; gap: 8px;">
        <button class="btn btn-accent" style="padding: 6px 14px; font-size: 12px;" onclick="pasteClipboard()"><span class="ico">📥</span> Paste into Current Folder</button>
        <button class="btn btn-secondary" style="padding: 6px 10px; font-size: 12px;" onclick="clearClipboard()"><span class="ico">✕</span> Clear</button>
      </div>
    </div>

    <!-- Breadcrumb Bar -->
    <div class="nav-bar">
      <div class="breadcrumbs" id="breadcrumbs">
        <span class="crumb-btn root-crumb" onclick="navigateTo('')">{{ROOT_NAME}}</span>
      </div>
      <div style="font-size: 12px; color: var(--text-muted);" id="itemCount">0 items</div>
    </div>

    <!-- Active-Folder Upload Zone -->
    {{UPLOAD_ZONE_HTML}}

    <!-- File Explorer Table -->
    <div class="table-container">
      <table>
        <thead>
          <tr>
            <th style="width: 40px;"><input type="checkbox" id="selectAll" onclick="toggleSelectAll(this)" /></th>
            <th>Name</th>
            <th>Size</th>
            <th>Modified</th>
            <th style="text-align: right;">Actions</th>
          </tr>
        </thead>
        <tbody id="fileTableBody">
          <tr><td colspan="5" style="text-align:center; padding: 40px; color: var(--text-muted);">Loading files...</td></tr>
        </tbody>
      </table>
    </div>
  </div>

  <!-- Floating Batch Bar -->
  <div class="batch-bar" id="batchBar">
    <span class="batch-count" id="batchCount">0 selected</span>
    <button class="btn btn-primary" onclick="downloadSelectedZipZeroRam()"><span class="ico">⬇️</span> Download ZIP</button>
    {{BATCH_WRITE_ACTIONS}}
  </div>

  <!-- Media & Document Preview Modal -->
  <div class="modal-backdrop" id="previewModal" onclick="closeModal('previewModal', event)">
    <div class="modal-content" onclick="event.stopPropagation()">
      <div class="modal-header">
        <span class="modal-title" id="previewTitle">Preview</span>
        <button class="close-modal" onclick="closeModal('previewModal')">&times;</button>
      </div>
      <div class="modal-body" id="previewBody"></div>
      <div class="modal-footer" id="previewFooter">
        <a id="previewDownloadBtn" class="btn btn-primary" href="#" download><span class="ico">⬇️</span> Download</a>
        <button class="btn btn-secondary" onclick="closeModal('previewModal')">Close</button>
      </div>
    </div>
  </div>

  <!-- New Folder Modal -->
  <div class="modal-backdrop" id="mkdirModal" onclick="closeModal('mkdirModal', event)">
    <div class="modal-content modal-sm" onclick="event.stopPropagation()">
      <div class="modal-header">
        <span class="modal-title">Create New Folder</span>
        <button class="close-modal" onclick="closeModal('mkdirModal')">&times;</button>
      </div>
      <div class="modal-body">
        <label style="font-size: 13px; color: var(--text-muted);">Folder Name:</label>
        <input type="text" id="newFolderName" class="modal-input" placeholder="e.g. documents" />
      </div>
      <div class="modal-footer">
        <button class="btn btn-secondary" onclick="closeModal('mkdirModal')">Cancel</button>
        <button class="btn btn-primary" onclick="confirmMkdir()">Create</button>
      </div>
    </div>
  </div>

  <!-- Rename Modal -->
  <div class="modal-backdrop" id="renameModal" onclick="closeModal('renameModal', event)">
    <div class="modal-content modal-sm" onclick="event.stopPropagation()">
      <div class="modal-header">
        <span class="modal-title">Rename Item</span>
        <button class="close-modal" onclick="closeModal('renameModal')">&times;</button>
      </div>
      <div class="modal-body">
        <label style="font-size: 13px; color: var(--text-muted);">New Name:</label>
        <input type="text" id="renameInput" class="modal-input" />
      </div>
      <div class="modal-footer">
        <button class="btn btn-secondary" onclick="closeModal('renameModal')">Cancel</button>
        <button class="btn btn-primary" onclick="confirmRename()">Rename</button>
      </div>
    </div>
  </div>

  <!-- Generic Confirm Modal -->
  <div class="modal-backdrop" id="confirmModal" onclick="closeModal('confirmModal', event)">
    <div class="modal-content modal-sm" onclick="event.stopPropagation()">
      <div class="modal-header">
        <span class="modal-title" id="confirmTitle">Confirm Action</span>
        <button class="close-modal" onclick="closeModal('confirmModal')">&times;</button>
      </div>
      <div class="modal-body">
        <p id="confirmMessage" style="font-size: 14px; line-height: 1.5; color: var(--text);"></p>
      </div>
      <div class="modal-footer">
        <button class="btn btn-secondary" onclick="closeModal('confirmModal')">Cancel</button>
        <button class="btn btn-danger" id="confirmBtnAction" onclick="">Confirm</button>
      </div>
    </div>
  </div>

  <!-- In-Browser Client-Side ZIP Progress Modal -->
  <div class="modal-backdrop" id="zipProgressModal">
    <div class="modal-content modal-sm" onclick="event.stopPropagation()">
      <div class="modal-header">
        <span class="modal-title">Client-Side Archiving</span>
      </div>
      <div class="modal-body" style="text-align: center;">
        <div style="font-size: 34px; margin-bottom: 10px;">📦</div>
        <div id="zipStatusText" style="font-size: 14px; font-weight: 600; margin-bottom: 6px;">Preparing files...</div>
        <div style="font-size: 12px; color: var(--text-muted);">Streaming directly to your device (Zero VPS RAM load)</div>
        <div style="width: 100%; background: rgba(255,255,255,0.08); border-radius: 999px; height: 8px; margin-top: 14px; overflow: hidden;">
          <div id="zipProgressBar" style="width: 0%; height: 100%; background: var(--blue); transition: width 0.15s;"></div>
        </div>
      </div>
    </div>
  </div>

  <footer>
    vPS Share &bull; VPS file explorer and file transfer tool by <strong>PSTECH</strong>.
  </footer>

  <script>
    let currentPath = '';
    let allEntries = [];
    let clipboard = { action: null, paths: [] };
    let activeRenamePath = '';
    const ROOT_NAME = {{ROOT_NAME_JS}};
    const isReadOnly = {{IS_READONLY}};

    // =========================================================================
    //  Navigation & Directory Browsing
    // =========================================================================
    async function navigateTo(path) {
      currentPath = path;
      const tbody = document.getElementById('fileTableBody');
      tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding: 40px; color: var(--text-muted);">Loading files...</td></tr>';
      
      try {
        const res = await fetch(`/api/browse?path=${encodeURIComponent(path)}`);
        if (!res.ok) throw new Error('Failed to read folder');
        const data = await res.json();
        allEntries = data.items;
        renderBreadcrumbs(path);
        renderTable(allEntries);
        document.getElementById('searchInput').value = '';
        document.getElementById('itemCount').innerText = `${allEntries.length} item${allEntries.length === 1 ? '' : 's'}`;
        updateBatchBar();
      } catch (err) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding: 40px; color: var(--danger);">Error loading directory: ${err.message}</td></tr>`;
      }
    }

    function reloadCurrentDir() {
      navigateTo(currentPath);
      fetchStats();
    }

    function renderBreadcrumbs(path) {
      const bc = document.getElementById('breadcrumbs');
      bc.innerHTML = '<span class="crumb-btn root-crumb" onclick="navigateTo(\'\')">' + ROOT_NAME + '</span>';
      if (!path) return;
      const parts = path.split('/').filter(Boolean);
      let acc = '';
      for (const p of parts) {
        acc += (acc ? '/' : '') + p;
        const cur = acc;
        bc.innerHTML += ` <span>/</span> <span class="crumb-btn" onclick="navigateTo('${cur}')">${p}</span>`;
      }
    }

    function getFileIcon(isDir, name) {
      if (isDir) return '📁';
      const ext = name.split('.').pop().toLowerCase();
      if (['mp4', 'mkv', 'mov', 'webm', 'avi'].includes(ext)) return '🎬';
      if (['mp3', 'wav', 'aac', 'flac', 'ogg', 'm4a'].includes(ext)) return '🎵';
      if (['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg', 'ico'].includes(ext)) return '🖼️';
      if (['zip', 'tar', 'gz', 'rar', '7z', 'bz2'].includes(ext)) return '📦';
      if (['py', 'js', 'ts', 'html', 'css', 'json', 'sh', 'sql', 'yml', 'yaml', 'toml', 'c', 'cpp', 'rs', 'go'].includes(ext)) return '📄';
      if (['md', 'txt', 'log', 'env'].includes(ext)) return '📝';
      return '📄';
    }

    function isPreviewable(name) {
      const ext = name.split('.').pop().toLowerCase();
      const media = ['mp4', 'webm', 'mov', 'mp3', 'wav', 'aac', 'flac', 'ogg', 'jpg', 'jpeg', 'png', 'gif', 'webp', 'svg'];
      const docs = ['txt', 'json', 'py', 'js', 'ts', 'html', 'css', 'sh', 'md', 'yml', 'yaml', 'toml', 'sql', 'log', 'xml'];
      return media.includes(ext) || docs.includes(ext);
    }

    function renderTable(items) {
      const tbody = document.getElementById('fileTableBody');
      if (!items || items.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding: 40px; color: var(--text-muted);">This folder is empty</td></tr>';
        return;
      }

      let html = '';
      if (currentPath) {
        const parent = currentPath.includes('/') ? currentPath.substring(0, currentPath.lastIndexOf('/')) : '';
        html += `
          <tr>
            <td></td>
            <td colspan="4">
              <span class="item-name" onclick="navigateTo('${parent}')">
                <span class="file-icon">📁</span> .. (Up one level)
              </span>
            </td>
          </tr>
        `;
      }

      for (const it of items) {
        const icon = getFileIcon(it.is_dir, it.name);
        const encodedRel = encodeURIComponent(it.rel_path);
        const safeName = it.name.replace(/'/g, "\\'");

        const previewBtn = (!it.is_dir && isPreviewable(it.name))
          ? `<button class="mini-btn preview" onclick="openPreview('${encodedRel}', '${safeName}')"><span class="ico">▶</span> View</button>`
          : '';

        const downloadBtn = !it.is_dir
          ? `<a href="/download?path=${encodedRel}" download class="mini-btn download"><span class="ico">⬇️</span> Download</a>`
          : '';

        const renameBtn = !isReadOnly
          ? `<button class="mini-btn" onclick="openRenameModal('${encodedRel}', '${safeName}')"><span class="ico">✏️</span> Rename</button>`
          : '';

        const deleteBtn = !isReadOnly
          ? `<button class="mini-btn danger" onclick="openDeleteConfirm(['${safeName}'], ['${encodedRel}'])"><span class="ico">🗑️</span> Delete</button>`
          : '';

        html += `
          <tr data-name="${it.name.toLowerCase()}">
            <td><input type="checkbox" class="row-checkbox" value="${it.rel_path}" onchange="updateBatchBar()" /></td>
            <td>
              <span class="item-name" onclick="${it.is_dir ? `navigateTo('${it.rel_path}')` : `openPreview('${encodedRel}', '${safeName}')`}">
                <span class="file-icon">${icon}</span> ${it.name}
              </span>
            </td>
            <td class="meta-col">${it.size_str || '&mdash;'}</td>
            <td class="meta-col">${it.mtime}</td>
            <td style="text-align: right;">
              <div class="action-icons">
                ${downloadBtn}
                ${previewBtn}
                ${renameBtn}
                ${deleteBtn}
              </div>
            </td>
          </tr>
        `;
      }
      tbody.innerHTML = html;
    }

    function filterFiles() {
      const q = document.getElementById('searchInput').value.toLowerCase().trim();
      const rows = document.querySelectorAll('#fileTableBody tr[data-name]');
      rows.forEach(r => {
        const name = r.getAttribute('data-name');
        r.style.display = (!q || name.includes(q)) ? '' : 'none';
      });
    }

    // =========================================================================
    //  Batch Selection & Actions
    // =========================================================================
    function toggleSelectAll(master) {
      document.querySelectorAll('.row-checkbox').forEach(cb => cb.checked = master.checked);
      updateBatchBar();
    }

    function updateBatchBar() {
      const selected = Array.from(document.querySelectorAll('.row-checkbox:checked')).map(cb => cb.value);
      const bar = document.getElementById('batchBar');
      if (selected.length > 0) {
        bar.style.display = 'flex';
        document.getElementById('batchCount').innerText = `${selected.length} item${selected.length > 1 ? 's' : ''} selected`;
      } else {
        bar.style.display = 'none';
        const selectAll = document.getElementById('selectAll');
        if (selectAll) selectAll.checked = false;
      }
    }

    function getSelectedPaths() {
      return Array.from(document.querySelectorAll('.row-checkbox:checked')).map(cb => cb.value);
    }

    // =========================================================================
    //  Uploads (Saved Directly to Active Opened Folder)
    // =========================================================================
    function handleUpload(files) {
      if (!files || files.length === 0 || isReadOnly) return;
      const fileInput = document.getElementById('fileInput');
      const formData = new FormData();
      formData.append('target_path', currentPath);

      let totalBytes = 0;
      for (const f of files) {
        formData.append('files', f);
        totalBytes += f.size;
      }

      const statusEl = document.getElementById('uploadStatus');
      const progressContainer = document.getElementById('uploadProgressContainer');
      const progressBar = document.getElementById('uploadProgressBar');
      const progressDetails = document.getElementById('progressDetails');

      if (progressContainer) progressContainer.style.display = 'block';
      if (progressDetails) {
        progressDetails.style.display = 'block';
        progressDetails.innerText = `0% (0 / ${formatBytes(totalBytes)})`;
      }
      if (progressBar) {
        progressBar.style.background = 'linear-gradient(90deg, var(--blue), var(--accent))';
        progressBar.style.width = '0%';
      }
      if (statusEl) statusEl.innerText = `Uploading ${files.length} file(s) into /${currentPath}...`;

      const xhr = new XMLHttpRequest();
      xhr.open('POST', '/api/upload', true);

      xhr.upload.onprogress = function(e) {
        if (e.lengthComputable) {
          const pct = Math.round((e.loaded / e.total) * 100);
          if (progressBar) progressBar.style.width = `${pct}%`;
          if (progressDetails) {
            progressDetails.innerText = `${pct}% (${formatBytes(e.loaded)} / ${formatBytes(e.total)})`;
          }
          if (pct === 100 && statusEl) {
            statusEl.innerText = 'Writing file(s) to storage...';
          }
        }
      };

      xhr.onload = function() {
        if (fileInput) fileInput.value = '';
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const result = JSON.parse(xhr.responseText);
            if (progressBar) progressBar.style.width = '100%';
            if (statusEl) statusEl.innerText = `Uploaded ${result.files.length} file(s) successfully!`;
            setTimeout(() => {
              if (progressContainer) progressContainer.style.display = 'none';
              if (progressDetails) progressDetails.style.display = 'none';
              if (progressBar) progressBar.style.width = '0%';
              if (statusEl) statusEl.innerText = 'Files upload directly into the folder you are viewing';
            }, 2500);
            reloadCurrentDir();
          } catch (e) {
            reloadCurrentDir();
          }
        } else {
          alert('Upload failed: ' + xhr.responseText);
          if (statusEl) statusEl.innerText = 'Upload failed';
          if (progressBar) progressBar.style.background = 'var(--danger)';
        }
      };

      xhr.onerror = function() {
        if (fileInput) fileInput.value = '';
        alert('Upload failed: Network connection error');
      };

      xhr.send(formData);
    }

    // =========================================================================
    //  Zero-RAM In-Browser Streaming ZIP Engine
    //  (Pure client-side streaming zip writer; VPS memory overhead = 0 MB!)
    // =========================================================================
    class ClientZipWriter {
      constructor() {
        this.entries = [];
        this.offset = 0;
        this.parts = [];
      }

      crc32(buf) {
        let crc = ~0;
        for (let i = 0; i < buf.length; i++) {
          crc ^= buf[i];
          for (let j = 0; j < 8; j++) {
            crc = (crc >>> 1) ^ ((crc & 1) ? 0xEDB88320 : 0);
          }
        }
        return ~crc >>> 0;
      }

      addFile(filename, dataBytes) {
        const nameBytes = new TextEncoder().encode(filename);
        const crc = this.crc32(dataBytes);
        const size = dataBytes.length;
        const now = new Date();
        const dosTime = (now.getHours() << 11) | (now.getMinutes() << 5) | (now.getSeconds() >> 1);
        const dosDate = ((now.getFullYear() - 1980) << 9) | ((now.getMonth() + 1) << 5) | now.getDate();

        // Local file header (30 bytes + name + data)
        const header = new Uint8Array(30);
        const view = new DataView(header.buffer);
        view.setUint32(0, 0x04034b50, true); // Local header signature
        view.setUint16(4, 20, true);         // Version needed
        view.setUint16(6, 0, true);          // General purpose flags
        view.setUint16(8, 0, true);          // Compression method (0 = STORE)
        view.setUint16(10, dosTime, true);
        view.setUint16(12, dosDate, true);
        view.setUint32(14, crc, true);
        view.setUint32(18, size, true);       // Compressed size
        view.setUint32(22, size, true);       // Uncompressed size
        view.setUint16(26, nameBytes.length, true);
        view.setUint16(28, 0, true);         // Extra field length

        const localOffset = this.offset;
        this.parts.push(header);
        this.parts.push(nameBytes);
        this.parts.push(dataBytes);
        this.offset += header.length + nameBytes.length + dataBytes.length;

        this.entries.push({
          nameBytes,
          crc,
          size,
          dosTime,
          dosDate,
          localOffset
        });
      }

      buildBlob() {
        const centralStart = this.offset;
        let centralSize = 0;

        for (const e of this.entries) {
          const cdHeader = new Uint8Array(46);
          const view = new DataView(cdHeader.buffer);
          view.setUint32(0, 0x02014b50, true); // Central directory signature
          view.setUint16(4, 20, true);         // Version made by
          view.setUint16(6, 20, true);         // Version needed
          view.setUint16(8, 0, true);          // Flags
          view.setUint16(10, 0, true);         // Method (0 = STORE)
          view.setUint16(12, e.dosTime, true);
          view.setUint16(14, e.dosDate, true);
          view.setUint32(16, e.crc, true);
          view.setUint32(20, e.size, true);
          view.setUint32(24, e.size, true);
          view.setUint16(28, e.nameBytes.length, true);
          view.setUint16(30, 0, true);         // Extra field len
          view.setUint16(32, 0, true);         // Comment len
          view.setUint16(34, 0, true);         // Disk start
          view.setUint16(36, 0, true);         // Internal attrs
          view.setUint32(38, 0, true);         // External attrs
          view.setUint32(42, e.localOffset, true);

          this.parts.push(cdHeader);
          this.parts.push(e.nameBytes);
          centralSize += cdHeader.length + e.nameBytes.length;
        }

        // End of central directory record (22 bytes)
        const eocd = new Uint8Array(22);
        const eocdView = new DataView(eocd.buffer);
        eocdView.setUint32(0, 0x06054b50, true);
        eocdView.setUint16(4, 0, true);
        eocdView.setUint16(6, 0, true);
        eocdView.setUint16(8, this.entries.length, true);
        eocdView.setUint16(10, this.entries.length, true);
        eocdView.setUint32(12, centralSize, true);
        eocdView.setUint32(16, centralStart, true);
        eocdView.setUint16(20, 0, true);

        this.parts.push(eocd);
        return new Blob(this.parts, { type: 'application/zip' });
      }
    }

    async function downloadSelectedZipZeroRam() {
      const selected = getSelectedPaths();
      if (selected.length === 0) return;

      const modal = document.getElementById('zipProgressModal');
      const statusText = document.getElementById('zipStatusText');
      const progressBar = document.getElementById('zipProgressBar');

      modal.style.display = 'flex';
      statusText.innerText = 'Scanning selection...';
      progressBar.style.width = '5%';

      try {
        // 1. Get manifest of files from VPS
        const res = await fetch('/api/zip-manifest', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ paths: selected })
        });
        if (!res.ok) throw new Error('Failed to create manifest');
        const data = await res.json();
        const files = data.files;

        if (files.length === 0) {
          alert('No files found to archive.');
          modal.style.display = 'none';
          return;
        }

        const zipWriter = new ClientZipWriter();
        let processed = 0;

        for (const file of files) {
          statusText.innerText = `Streaming (${processed + 1}/${files.length}): ${file.zip_path}`;
          const fileResp = await fetch(file.download_url);
          if (!fileResp.ok) continue;
          const arrayBuf = await fileResp.arrayBuffer();
          zipWriter.addFile(file.zip_path, new Uint8Array(arrayBuf));
          processed++;
          progressBar.style.width = `${Math.round((processed / files.length) * 95)}%`;
        }

        statusText.innerText = 'Finalizing ZIP on device...';
        const zipBlob = zipWriter.buildBlob();
        progressBar.style.width = '100%';

        const blobUrl = URL.createObjectURL(zipBlob);
        const a = document.createElement('a');
        a.href = blobUrl;
        a.download = `vps_share_${Date.now()}.zip`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(() => URL.revokeObjectURL(blobUrl), 10000);

        setTimeout(() => { modal.style.display = 'none'; }, 800);
      } catch (err) {
        alert('Archiving failed: ' + err.message);
        modal.style.display = 'none';
      }
    }

    // =========================================================================
    //  Folder Operations (Mkdir, Rename, Delete, Cut/Copy & Paste)
    // =========================================================================
    function openMkdirModal() {
      if (isReadOnly) return;
      document.getElementById('newFolderName').value = '';
      document.getElementById('mkdirModal').style.display = 'flex';
      document.getElementById('newFolderName').focus();
    }

    async function confirmMkdir() {
      const name = document.getElementById('newFolderName').value.trim();
      if (!name) return;
      try {
        const res = await fetch('/api/mkdir', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path: currentPath, name })
        });
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || 'Failed to create folder');
        }
        closeModal('mkdirModal');
        reloadCurrentDir();
      } catch (err) {
        alert(err.message);
      }
    }

    function openRenameModal(encodedRel, currentName) {
      if (isReadOnly) return;
      activeRenamePath = decodeURIComponent(encodedRel);
      document.getElementById('renameInput').value = currentName;
      document.getElementById('renameModal').style.display = 'flex';
      document.getElementById('renameInput').focus();
    }

    async function confirmRename() {
      const newName = document.getElementById('renameInput').value.trim();
      if (!newName || !activeRenamePath) return;
      try {
        const res = await fetch('/api/rename', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path: activeRenamePath, new_name: newName })
        });
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || 'Rename failed');
        }
        closeModal('renameModal');
        reloadCurrentDir();
      } catch (err) {
        alert(err.message);
      }
    }

    function openDeleteConfirm(names, encodedPaths) {
      if (isReadOnly) return;
      const paths = encodedPaths.map(p => decodeURIComponent(p));
      const msg = `Are you sure you want to delete ${paths.length === 1 ? `"${names[0]}"` : `${paths.length} items`}?<br><strong style="color: var(--danger);">This cannot be undone.</strong>`;
      document.getElementById('confirmTitle').innerText = 'Confirm Delete';
      document.getElementById('confirmMessage').innerHTML = msg;
      
      const btn = document.getElementById('confirmBtnAction');
      btn.innerText = 'Delete';
      btn.onclick = async () => {
        try {
          const res = await fetch('/api/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ paths })
          });
          if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Delete failed');
          }
          closeModal('confirmModal');
          reloadCurrentDir();
        } catch (err) {
          alert(err.message);
        }
      };
      document.getElementById('confirmModal').style.display = 'flex';
    }

    function batchDeleteSelected() {
      const paths = getSelectedPaths();
      if (paths.length === 0) return;
      openDeleteConfirm(paths, paths.map(encodeURIComponent));
    }

    // Cut & Copy (Clipboard)
    function setClipboard(action) {
      const selected = getSelectedPaths();
      if (selected.length === 0) return;
      clipboard = { action, paths: selected };
      const bar = document.getElementById('clipboardBar');
      const text = document.getElementById('clipboardText');
      bar.style.display = 'flex';
      text.innerText = `${action === 'cut' ? '✂ Cut' : '📋 Copied'} ${selected.length} item(s). Navigate to target folder and click Paste.`;
      updateBatchBar();
    }

    function clearClipboard() {
      clipboard = { action: null, paths: [] };
      document.getElementById('clipboardBar').style.display = 'none';
    }

    async function pasteClipboard() {
      if (!clipboard.action || clipboard.paths.length === 0) return;
      try {
        const res = await fetch('/api/copy-move', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            paths: clipboard.paths,
            dest_dir: currentPath,
            action: clipboard.action === 'cut' ? 'move' : 'copy'
          })
        });
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || 'Paste operation failed');
        }
        clearClipboard();
        reloadCurrentDir();
      } catch (err) {
        alert(err.message);
      }
    }

    // =========================================================================
    //  Media & Safe Document Previews (Read-Only)
    // =========================================================================
    async function openPreview(encodedRel, filename) {
      const ext = filename.split('.').pop().toLowerCase();
      const modal = document.getElementById('previewModal');
      const title = document.getElementById('previewTitle');
      const body = document.getElementById('previewBody');
      const dlBtn = document.getElementById('previewDownloadBtn');

      const fileUrl = `/view?path=${encodedRel}`;
      dlBtn.href = `/download?path=${encodedRel}`;
      dlBtn.download = filename;

      title.innerText = `Viewing: ${filename}`;
      body.innerHTML = '<div style="text-align:center; padding: 40px; color: var(--text-muted);">Loading media preview...</div>';
      modal.style.display = 'flex';

      if (['mp4', 'webm', 'mov', 'mkv'].includes(ext)) {
        body.innerHTML = `<video src="${fileUrl}" controls autoplay playsinline style="max-height: 70vh; width: 100%; border-radius: 8px;"></video>`;
      } else if (['mp3', 'wav', 'aac', 'flac', 'ogg', 'm4a'].includes(ext)) {
        body.innerHTML = `<audio src="${fileUrl}" controls autoplay style="width: 100%; max-width: 500px;"></audio>`;
      } else if (['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg', 'ico'].includes(ext)) {
        body.innerHTML = `<img src="${fileUrl}" alt="${filename}" />`;
      } else {
        // Read-only text / code viewer
        try {
          const resp = await fetch(fileUrl);
          const txt = await resp.text();
          body.innerHTML = `<div class="code-viewer"><code>${escapeHtml(txt.slice(0, 150000))}</code></div>`;
        } catch (e) {
          body.innerHTML = `<div style="text-align:center; color: var(--danger); padding: 40px;">Unable to display file content</div>`;
        }
      }
    }

    function closeModal(modalId, event) {
      if (event && event.target !== event.currentTarget) return;
      const modal = document.getElementById(modalId);
      if (modal) {
        const video = modal.querySelector('video');
        const audio = modal.querySelector('audio');
        if (video) video.pause();
        if (audio) audio.pause();
        modal.style.display = 'none';
      }
    }

    // =========================================================================
    //  Stats & Utilities
    // =========================================================================
    async function fetchStats() {
      try {
        const res = await fetch('/api/stats');
        if (res.ok) {
          const data = await res.json();
          document.getElementById('storageWidget').innerText = `💾 Free: ${data.free_str} / ${data.total_str}`;
        }
      } catch (_) {}
    }

    function formatBytes(bytes) {
      if (bytes === 0) return '0 B';
      const k = 1024;
      const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
      const i = Math.floor(Math.log(bytes) / Math.log(k));
      return (bytes / Math.pow(k, i)).toFixed(1) + ' ' + sizes[i];
    }

    function escapeHtml(text) {
      return text.replace(/[&<>"']/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' })[m]);
    }

    // Keyboard Shortcuts
    window.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        ['previewModal', 'mkdirModal', 'renameModal', 'confirmModal'].forEach(id => closeModal(id));
      }
    });

    // Initialize DropZone & Navigation
    window.addEventListener('DOMContentLoaded', () => {
      const dropZone = document.getElementById('dropZone');
      const fileInput = document.getElementById('fileInput');

      if (dropZone && fileInput) {
        ['dragenter', 'dragover'].forEach(name => {
          dropZone.addEventListener(name, (e) => { e.preventDefault(); dropZone.classList.add('dragover'); });
        });
        ['dragleave', 'drop'].forEach(name => {
          dropZone.addEventListener(name, (e) => { e.preventDefault(); dropZone.classList.remove('dragover'); });
        });
        dropZone.addEventListener('drop', (e) => {
          handleUpload(e.dataTransfer.files);
        });
        fileInput.addEventListener('change', (e) => {
          handleUpload(e.target.files);
        });
      }

      fetchStats();
      navigateTo('');
    });
  </script>
</body>
</html>
"""


# ==============================================================================
#  API Routes
# ==============================================================================
@app.get("/", response_class=HTMLResponse)
async def index(request: Request, auth=Depends(verify_auth)):
    status_badge = (
        '<div class="status-pill readonly">🔒 Read-Only</div>'
        if CONFIG.readonly
        else '<div class="status-pill">⚡ Active</div>'
    )
    toolbar_write = (
        ""
        if CONFIG.readonly
        else """
        <button class="btn btn-primary" onclick="document.getElementById('fileInput').click()"><span class="ico">⬆️</span> Upload Files</button>
        <button class="btn btn-secondary" onclick="openMkdirModal()"><span class="ico">📁</span> New Folder</button>
        """
    )
    batch_write = (
        ""
        if CONFIG.readonly
        else """
        <button class="btn btn-secondary" onclick="setClipboard('cut')"><span class="ico">✂️</span> Cut</button>
        <button class="btn btn-secondary" onclick="setClipboard('copy')"><span class="ico">📋</span> Copy</button>
        <button class="btn btn-danger" onclick="batchDeleteSelected()"><span class="ico">🗑️</span> Delete</button>
        """
    )
    upload_zone = (
        ""
        if CONFIG.readonly
        else """
        <div class="upload-zone" id="dropZone" onclick="document.getElementById('fileInput').click()">
          <input type="file" id="fileInput" multiple style="display:none;" />
          <div class="upload-icon">☁️</div>
          <div class="upload-text">Drop files here, or click to choose files</div>
          <div class="upload-subtext" id="uploadStatus">Files upload directly into the folder you are viewing</div>
          <div class="upload-progress-container" id="uploadProgressContainer">
            <div class="upload-progress-bar" id="uploadProgressBar"></div>
          </div>
          <div class="progress-details" id="progressDetails">0%</div>
        </div>
        """
    )

    root_name = CONFIG.root_dir.name or CONFIG.root_dir.as_posix()
    html = (
        HTML_TEMPLATE
        .replace("{{STATUS_BADGE}}", status_badge)
        .replace("{{TOOLBAR_WRITE_ACTIONS}}", toolbar_write)
        .replace("{{BATCH_WRITE_ACTIONS}}", batch_write)
        .replace("{{UPLOAD_ZONE_HTML}}", upload_zone)
        .replace("{{IS_READONLY}}", "true" if CONFIG.readonly else "false")
        .replace("{{ROOT_NAME_JS}}", json.dumps(root_name))
        .replace("{{ROOT_NAME}}", root_name)
    )
    return HTMLResponse(content=html)


@app.get("/api/stats")
async def get_stats(auth=Depends(verify_auth)):
    """Return storage stats for the root directory partition."""
    try:
        total, used, free = shutil.disk_usage(CONFIG.root_dir)
        return {
            "total_bytes": total,
            "free_bytes": free,
            "used_bytes": used,
            "total_str": format_size(total),
            "free_str": format_size(free),
            "used_str": format_size(used),
            "percent_used": round((used / total) * 100, 1),
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/browse")
async def browse(
    path: str = Query("", description="Relative path from shared root"),
    auth=Depends(verify_auth),
):
    """List directory contents with metadata."""
    target = safe_resolve(path)
    if not target.exists() or not target.is_dir():
        target = CONFIG.root_dir
        path = ""

    items = []
    try:
        entries = sorted(list(target.iterdir()), key=lambda e: (not e.is_dir(), e.name.lower()))
        for entry in entries:
            # Check hidden file visibility
            if not CONFIG.show_hidden and (entry.name.startswith(".") or entry.name in ["__pycache__", ".git"]):
                continue
            is_dir = entry.is_dir()
            size = entry.stat().st_size if not is_dir else 0
            mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(entry.stat().st_mtime))
            rel = entry.relative_to(CONFIG.root_dir).as_posix()
            items.append({
                "name": entry.name,
                "is_dir": is_dir,
                "size_bytes": size,
                "size_str": format_size(size) if not is_dir else "",
                "mtime": mtime,
                "rel_path": rel,
            })
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied reading directory")

    return {"path": path, "items": items, "readonly": CONFIG.readonly}


@app.get("/download")
async def download_file(
    path: str = Query(..., description="Relative file path"),
    auth=Depends(verify_auth),
):
    """Direct file download as an octet-stream attachment."""
    target = safe_resolve(path)
    if not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        path=str(target),
        filename=target.name,
        media_type="application/octet-stream",
    )


@app.get("/view")
async def view_file(
    path: str = Query(..., description="Relative file path"),
    auth=Depends(verify_auth),
):
    """Stream media or text file with seekable HTTP range support."""
    target = safe_resolve(path)
    if not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    mime, _ = mimetypes.guess_type(str(target))
    return FileResponse(
        path=str(target),
        media_type=mime or "application/octet-stream",
    )


@app.post("/api/upload")
async def upload_files(
    target_path: str = Form(""),
    files: List[UploadFile] = File(...),
    auth=Depends(verify_auth),
):
    """Upload files directly into the active folder currently opened."""
    check_writable()
    dest_dir = safe_resolve(target_path)
    if not dest_dir.exists() or not dest_dir.is_dir():
        dest_dir = CONFIG.root_dir

    uploaded = []
    for file in files:
        safe_name = Path(file.filename).name
        if not safe_name or safe_name in [".", ".."]:
            continue
        dest_file = dest_dir / safe_name
        with open(dest_file, "wb") as f:
            while chunk := await file.read(1024 * 1024):  # 1MB chunks to minimize memory
                f.write(chunk)
        uploaded.append(safe_name)

    return {"status": "ok", "saved_to": str(dest_dir.relative_to(CONFIG.root_dir)), "files": uploaded}


@app.post("/api/mkdir")
async def make_directory(req: MkdirRequest, auth=Depends(verify_auth)):
    """Create a new folder inside specified directory."""
    check_writable()
    parent = safe_resolve(req.path)
    clean_name = req.name.strip().replace("/", "").replace("\\", "")
    if not clean_name or clean_name in [".", ".."]:
        raise HTTPException(status_code=400, detail="Invalid folder name")
    new_dir = parent / clean_name
    if new_dir.exists():
        raise HTTPException(status_code=400, detail="Folder or file already exists")
    new_dir.mkdir(parents=True, exist_ok=True)
    return {"status": "ok", "path": str(new_dir.relative_to(CONFIG.root_dir))}


@app.post("/api/rename")
async def rename_item(req: RenameRequest, auth=Depends(verify_auth)):
    """Rename a file or folder."""
    check_writable()
    target = safe_resolve(req.path)
    if not target.exists():
        raise HTTPException(status_code=404, detail="Item not found")
    clean_new_name = req.new_name.strip().replace("/", "").replace("\\", "")
    if not clean_new_name or clean_new_name in [".", ".."]:
        raise HTTPException(status_code=400, detail="Invalid new name")
    dest = target.parent / clean_new_name
    if dest.exists():
        raise HTTPException(status_code=400, detail="An item with this name already exists")
    target.rename(dest)
    return {"status": "ok", "new_path": str(dest.relative_to(CONFIG.root_dir))}


@app.post("/api/delete")
async def delete_items(req: DeleteRequest, auth=Depends(verify_auth)):
    """Batch delete files or directories."""
    check_writable()
    deleted = []
    for p in req.paths:
        target = safe_resolve(p)
        if target == CONFIG.root_dir:
            continue  # Prevent deleting root folder itself
        if target.is_dir():
            shutil.rmtree(target)
            deleted.append(p)
        elif target.is_file():
            target.unlink()
            deleted.append(p)
    return {"status": "ok", "deleted": deleted}


@app.post("/api/copy-move")
async def copy_move_items(req: CopyMoveRequest, auth=Depends(verify_auth)):
    """Batch copy or move files/folders into a destination folder."""
    check_writable()
    dest_dir = safe_resolve(req.dest_dir)
    if not dest_dir.is_dir():
        raise HTTPException(status_code=400, detail="Destination must be a directory")

    action = req.action.lower()
    processed = []

    for p in req.paths:
        src = safe_resolve(p)
        if not src.exists() or src == CONFIG.root_dir:
            continue
        dest_item = dest_dir / src.name

        # Prevent copying or moving a directory into itself
        if src.is_dir() and str(dest_dir).startswith(str(src)):
            continue

        if action == "move":
            shutil.move(str(src), str(dest_item))
            processed.append(src.name)
        elif action == "copy":
            if src.is_dir():
                shutil.copytree(str(src), str(dest_item), dirs_exist_ok=True)
            else:
                shutil.copy2(str(src), str(dest_item))
            processed.append(src.name)

    return {"status": "ok", "action": action, "items": processed}


@app.post("/api/zip-manifest")
async def zip_manifest(req: ZipManifestRequest, auth=Depends(verify_auth)):
    """Return recursive file tree with download URLs for zero-RAM client-side ZIP building."""
    files = []
    for p in req.paths:
        target = safe_resolve(p)
        if target.is_file():
            rel_root = target.name
            files.append({
                "zip_path": rel_root,
                "download_url": f"/download?path={urllib.parse.quote(target.relative_to(CONFIG.root_dir).as_posix())}"
            })
        elif target.is_dir():
            parent_dir = target.parent
            for root, _, dirfiles in os.walk(target):
                for df in dirfiles:
                    fp = Path(root) / df
                    rel_zip = fp.relative_to(parent_dir).as_posix()
                    files.append({
                        "zip_path": rel_zip,
                        "download_url": f"/download?path={urllib.parse.quote(fp.relative_to(CONFIG.root_dir).as_posix())}"
                    })
    return {"files": files}


# ==============================================================================
#  Server Launch Routine
# ==============================================================================
def run_app(config: ServerConfig):
    global CONFIG
    CONFIG = config

    print("=" * 68)
    print(f"📁 {APP_NAME} — {TAGLINE}")
    print("=" * 68)
    print(f"🚀 Server Address:    http://{CONFIG.host}:{CONFIG.port}")
    print(f"📂 Shared Root:       {CONFIG.root_dir}")
    print(f"🔒 Access Mode:       {'Read-Only' if CONFIG.readonly else 'Full Access (Read / Upload / Manage)'}")
    if CONFIG.enable_auth:
        print(f"🔑 Authentication:    Enabled (Username: {CONFIG.auth_user})")
    print("=" * 68)

    uvicorn.run(app, host=CONFIG.host, port=CONFIG.port, log_level="warning")


if __name__ == "__main__":
    run_app(CONFIG)
