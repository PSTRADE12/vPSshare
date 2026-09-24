# 📁 vPS Share

> **VPS file explorer and file transfer tool by PSTECH**

[![Python Version](https://img.shields.io/badge/Python-3.8%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![RAM Footprint](https://img.shields.io/badge/Memory_Footprint-~25--30_MB-10B981.svg)](#-why-vps-share)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Linux_%7C_macOS_%7C_Windows-F59E0B.svg)](#-quick-start)
[![Dependencies](https://img.shields.io/badge/Dependencies-3_packages-38BDF8.svg)](#%EF%B8%8F-technology-stack)

**vPS Share** is an ultra-lightweight, self-hosted web file manager and media
transfer portal. Built for speed and minimal resource usage, it consumes only
**~25–30 MB RAM** while providing a modern single-page web UI, instant search,
drag-and-drop uploads to the active folder, seekable video streaming, and
**zero-RAM browser-side ZIP downloads**.

---

## 💡 Why vPS Share?

| Feature | Python `http.server` | Nextcloud / ownCloud | Filebrowser | **vPS Share** |
|:---|:---:|:---:|:---:|:---:|
| **Memory Usage (RAM)** | ~20 MB | 500 MB – 2 GB+ | ~40 MB | **⚡ ~25–30 MB** |
| **Setup Complexity** | Zero | High (DB + PHP + Web Server) | Medium | **🚀 1-Click (`./start.sh`)** |
| **Active-Folder Uploads** | ❌ No | ✅ Yes | ✅ Yes | **✅ Drag & Drop to active folder** |
| **Multi-File ZIP Archiving** | ❌ No | ⚠️ High VPS RAM Load | ⚠️ High VPS RAM Load | **📦 Zero-RAM (client-side streaming)** |
| **Seekable Video Scrubbing** | ❌ No | ✅ Yes | ⚠️ Partial | **🎬 Yes (full HTTP `Range: bytes=`)** |
| **Zero-Config Public Tunnel** | ❌ No | ❌ No | ❌ No | **🌐 1-click Cloudflare Tunnel** |
| **File Management** | ❌ None | ✅ Yes | ✅ Yes | **📁 Mkdir, Rename, Delete, Cut/Copy/Paste** |

---

## ✨ Features

- **⚡ Ultra-low resource usage** — Pure Python + FastAPI + Uvicorn. Idle footprint
  is ~25–30 MB, safe to run on the smallest VPS instances (512 MB / 1 GB RAM).
- **📦 Zero-RAM ZIP archiving** — Download multiple files or full directory trees as
  `.zip` archives built **on-the-fly inside the browser**. The VPS only streams the
  raw bytes — **0 MB RAM and no temp disk** consumed on the server.
- **📂 Active-folder uploads** — Drop files anywhere on the page, or click the upload
  zone. Files save directly into the folder you are currently viewing.
- **📁 Full file management**
  - `+ New Folder` — create subdirectories instantly
  - `✏️ Rename` — rename files and folders inline
  - `🗑️ Delete` — single or batch deletion with a confirmation safeguard
  - `✂️ Cut` / `📋 Copy` & `📥 Paste` — move or duplicate files between folders
  - `⬇️ Download ZIP` — batch-download selected items as one archive
- **🎬 Seekable media & document previews (read-only)**
  - Videos: `.mp4`, `.webm`, `.mov`, `.mkv` with HTTP `Range: bytes=` scrubbing
  - Audio: `.mp3`, `.wav`, `.aac`, `.flac`, `.ogg`, `.m4a`
  - Images: `.jpg`, `.png`, `.webp`, `.gif`, `.svg`, `.ico`
  - Code & text: safe, read-only inspector for `.py`, `.js`, `.json`, `.md`, `.sh`, etc.
- **🌐 3 flexible access channels**
  - `network` — reachable over LAN or the VPS public IP (`0.0.0.0`)
  - `local` — bound only to `127.0.0.1` for private SSH tunnels
  - `tunnel` — one-flag encrypted public HTTPS link (`https://*.trycloudflare.com`)
    with no firewall ports opened and no domain needed
- **🎨 Modern, responsive UI** — dark glassmorphic design, Space Grotesk + Inter
  typography, labeled action buttons, active-folder breadcrumbs showing the root
  share name, instant client-side filtering.
- **🔒 Path-traversal-sandboxed** — every request is canonicalized with
  `os.path.realpath()`; `../` and symlink escapes are rejected with `HTTP 403`.
- **🪟 Cross-platform** — one-click launchers for Linux & macOS (`start.sh`) and
  Windows (`start.bat`).

---

## 🚀 Quick Start

### 1. Prerequisites

- **Python 3.8+**
- **`cloudflared`** (only if you want the public HTTPS tunnel — see
  [Cloudflare downloads](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/))

### 2. Installation

```bash
git clone https://github.com/PSTRADE12/vPSshare.git
cd vps-share
pip install -r requirements.txt
```

> Only **3 dependencies**: `fastapi`, `uvicorn`, `python-multipart`.

### 3. Run

#### 🐧 Linux & 🍎 macOS

```bash
chmod +x start.sh
./start.sh
```

#### 🪟 Windows

```cmd
start.bat
```

#### 🐍 Direct Python

```bash
python run.py
```

Open **`http://localhost:3000`** in your browser.

---

## 🔐 Enabling Authentication

By default, vPS Share starts **without** a password so it is immediately usable
locally. **If you expose it on the internet, you MUST enable auth:**

1. Open `config.py`
2. Set `ENABLE_AUTH = True`
3. Set a strong `AUTH_PASSWORD`
4. Restart the server

```python
ENABLE_AUTH = True
AUTH_USERNAME = "admin"
AUTH_PASSWORD = "use-a-strong-password"
```

Without auth, anyone who reaches the URL can read **and** write files.

---

## 💻 Accessing from Your PC via SSH Port Forwarding

If the VPS firewall is closed, or you chose `CHANNELS = ["local"]` for maximum
privacy, forward the port to your local machine:

```bash
# Local port 3000 -> VPS port 3000
ssh -N -L 3000:127.0.0.1:3000 user@YOUR_VPS_IP

# With an SSH key and a custom SSH port
ssh -N -L 3000:127.0.0.1:3000 -i ~/.ssh/id_rsa -p 2222 user@YOUR_VPS_IP
```

Then open **`http://localhost:3000`**. Press `Ctrl + C` to disconnect.

---

## ⚙️ Configuration (`config.py`)

Everything is configured in **`config.py`** — no terminal flags needed:

```python
# 📁 Root folder to share (strictly sandboxed)
ROOT_DIR = "."

# 📡 Access channels: "network", "local", "tunnel" (combinable)
CHANNELS = ["network"]

# 🔌 Port to bind
PORT = 3000

# ⏳ Auto-wait if the port is already in use
AUTO_WAIT_IF_BUSY = True

# 🔒 Read-only mode (disables upload/delete/rename)
READONLY = False

# 👁️ Show hidden files (.env, .git, ...)
SHOW_HIDDEN_FILES = False

# 🔑 HTTP Basic Authentication
ENABLE_AUTH = False
AUTH_USERNAME = "admin"
AUTH_PASSWORD = "change-me"
```

---

## 🛠️ Optional Command-Line Overrides

Temporary overrides without touching `config.py`:

```bash
# Share a specific directory
python run.py --dir /var/www/media

# Change the port
python run.py --port 8080

# Restrict to local SSH tunnel only
python run.py --channel local

# Enable authentication on the fly
python run.py --auth admin:SecretPass123

# Run in read-only mode
python run.py --readonly
```

Flag arguments take precedence over `config.py`.

---

## 🌐 Zero-Configuration Cloudflare Tunnel

No open ports, no DNS changes, no domain required:

```bash
# 1. Install cloudflared (https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/)
# 2. Let vPS Share find it on your PATH (or put the binary next to run.py)
# 3. Start with the tunnel channel:
python run.py --channel tunnel
```

You will get a temporary public URL in the console, e.g.:
`https://random-name.trycloudflare.com`. The tunnel stays alive while the server
runs and disappears on exit.

> The free `trycloudflare` tunnel is **unauthenticated by default** — enable auth
> (`--auth admin:secret` or `ENABLE_AUTH = True`) before exposing it publicly.

---

## 🛡️ Security Architecture

1. **Path-traversal sandboxing** — every requested path is canonicalized with
   `os.path.realpath()` and checked against the shared root. `../` escape attempts
   and symlink hops are rejected with `HTTP 403`.
2. **Safe previews** — code/markdown files render as read-only, HTML-escaped text.
   There is no server-side execution of uploaded content.
3. **Timing-safe auth** — as configured, credentials are compared with
   `secrets.compare_digest()`.
4. **Read-only mode** — `READONLY = True` disables every write operation while
   leaving browsing & downloads functional.
5. **No secrets in code** — credentials are set via `config.py` or CLI; nothing is
   hard-coded. See [`SECURITY.md`](SECURITY.md) for responsibilities and reporting.

### Hardening checklist

- [ ] Set a strong `AUTH_PASSWORD`
- [ ] Prefer `CHANNELS = ["local"]` + SSH forwarding, or `"tunnel"` with auth, over a
      raw `network` exposure
- [ ] Run under a low-privilege OS user whose home is the shared root
- [ ] Keep `ROOT_DIR` outside the project folder
- [ ] Set `READONLY = True` for a pure download/share box

---

## 📡 API Overview

| Method | Endpoint | Description |
|:---|:---|:---|
| `GET`  | `/` | Single-page UI |
| `GET`  | `/api/browse?path=` | List directory contents |
| `GET`  | `/api/stats` | Disk usage for the shared partition |
| `POST` | `/api/upload` | Multipart upload (`target_path` + `files`) |
| `POST` | `/api/mkdir` | Create a folder |
| `POST` | `/api/rename` | Rename a file/folder |
| `POST` | `/api/delete` | Delete one or many paths |
| `POST` | `/api/copy-move` | Copy or move selected paths |
| `POST` | `/api/zip-manifest` | Streaming ZIP manifest (client-side build) |
| `GET`  | `/download?path=` | Stream a file (supports `Range: bytes=`) |
| `GET`  | `/view?path=` | Render a file for in-browser preview |

---

## 📜 Project Structure

```
vps-share/
├── config.py          # ⚙️ All runtime settings live here
├── run.py             # 🚀 Entrypoint, port handling, channel dispatcher
├── server.py          # ⚡ FastAPI backend + embedded single-page UI
├── tunnel.py          # 🌐 Cloudflare Tunnel manager
├── start.sh           # 🐧 One-click launcher: Linux & macOS
├── start.bat          # 🪟 One-click launcher: Windows
├── requirements.txt   # 📦 Minimal dependencies
├── LICENSE            # 📄 MIT License
└── README.md          # 📖 This file
```

---

## 🖥️ Technology Stack

- **Backend** — [FastAPI](https://fastapi.tiangolo.com/) + [Uvicorn](https://www.uvicorn.org/)
- **Frontend** — Embedded HTML/CSS/JS (zero frameworks, zero build step — instant loading)
- **Tunneling** — [Cloudflare `cloudflared`](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/)

---

## 👤 Author & Credits

**vPS Share** is designed and crafted by **PSTECH**.

Licensed under the [MIT License](LICENSE) — free for personal and commercial use.
Maintenance and feature requests are tracked as GitHub issues.