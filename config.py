# ==============================================================================
#  vPS Share — Configuration
#  VPS file explorer and file transfer tool by PSTECH
#
#  Edit these settings to configure your server without needing CLI flags!
# ==============================================================================

from pathlib import Path

# 📁 ROOT DIRECTORY
# The root folder you want to explore, upload to, and download from.
# All operations are strictly sandboxed inside this folder.
# Examples:
#   Linux/VPS:   ROOT_DIR = "/home/user/files"  or  ROOT_DIR = "."
#   Windows:     ROOT_DIR = "C:/Users/YourName/Downloads"
ROOT_DIR = "."

# 📡 ACCESS CHANNELS
# Choose one or more channels to enable:
#   "network" -> Accessible over local network or public VPS IP (binds to 0.0.0.0)
#   "local"   -> Accessible only on this machine (binds to 127.0.0.1)
#   "tunnel"  -> Instant encrypted public HTTPS URL via Cloudflare (zero-config, no port forwarding)
#
# Examples:
#   CHANNELS = ["network", "tunnel"]  # Both IP access and public Cloudflare URL
#   CHANNELS = ["network"]            # Only LAN / VPS IP
#   CHANNELS = ["local"]              # Safe localhost-only (e.g. for SSH port forwarding)
#   CHANNELS = ["tunnel"]             # Only Cloudflare tunnel
CHANNELS = ["network"]

# 🔌 PORT CONFIGURATION
PORT = 3000

# ⏳ PORT AUTO-WAIT
# If the port is currently used by another process, wait until it becomes free
AUTO_WAIT_IF_BUSY = True

# 🔒 SECURITY & PERMISSIONS
# If True, disables all upload, delete, rename, and folder creation actions (read & download only)
READONLY = False

# Show or hide hidden files (e.g., .env, .git, dotfiles)
SHOW_HIDDEN_FILES = False

# 🔑 AUTHENTICATION (HTTP Basic Auth)
# IMPORTANT: On a public VPS you MUST enable authentication or the portal
# will be fully accessible (read + write) to anyone who finds the URL.
# Set ENABLE_AUTH = True and pick a strong password below.
ENABLE_AUTH = False
AUTH_USERNAME = "admin"
AUTH_PASSWORD = "change-me-to-a-strong-password"
