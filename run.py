#!/usr/bin/env python3
"""vPS Share — Entrypoint & Channel Dispatcher.

VPS file explorer and file transfer tool by PSTECH.
Loads default settings from config.py and starts network/tunnel channels.
"""
import argparse
import os
import signal
import sys
import threading
import time
from pathlib import Path

# Load project configuration
import config
from server import APP_NAME, TAGLINE, ServerConfig, is_port_in_use, run_app
from tunnel import CloudflareTunnel


def parse_args():
    parser = argparse.ArgumentParser(
        description=f"{APP_NAME} — {TAGLINE}",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--dir",
        type=str,
        default=None,
        help=f"Root directory to share (default: '{config.ROOT_DIR}')",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help=f"Port to bind (default: {config.PORT})",
    )
    parser.add_argument(
        "--channel",
        type=str,
        default=None,
        help="Access channels comma-separated: 'network', 'local', 'tunnel' (default from config.py)",
    )
    parser.add_argument(
        "--readonly",
        action="store_true",
        default=None,
        help="Enable read-only mode (disable upload/delete/rename)",
    )
    parser.add_argument(
        "--auth",
        type=str,
        default=None,
        help="Enable HTTP Basic Auth in format 'username:password'",
    )
    parser.add_argument(
        "--wait",
        action="store_true",
        default=None,
        help="Wait automatically if the port is busy",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # 1. Resolve Root Directory
    raw_root = args.dir if args.dir is not None else config.ROOT_DIR
    root_path = Path(raw_root).resolve()
    if not root_path.exists() or not root_path.is_dir():
        print(f"[Error] Root directory '{root_path}' does not exist or is not a directory.")
        sys.exit(1)

    # 2. Resolve Port & Auto-Wait
    port = args.port if args.port is not None else config.PORT
    auto_wait = args.wait if args.wait is not None else getattr(config, "AUTO_WAIT_IF_BUSY", True)

    # 3. Resolve Channels & Host
    if args.channel is not None:
        channels = [c.strip().lower() for c in args.channel.split(",") if c.strip()]
    else:
        channels = [c.lower() for c in getattr(config, "CHANNELS", ["network", "tunnel"])]

    bind_host = "0.0.0.0" if "network" in channels else "127.0.0.1"
    enable_tunnel = "tunnel" in channels

    # 4. Resolve Permissions & Auth
    readonly = args.readonly if args.readonly is not None else getattr(config, "READONLY", False)
    show_hidden = getattr(config, "SHOW_HIDDEN_FILES", False)

    auth_enabled = False
    auth_user, auth_pass = None, None

    if args.auth is not None:
        if ":" not in args.auth:
            print("[Error] --auth must be in format 'username:password'")
            sys.exit(1)
        auth_user, auth_pass = args.auth.split(":", 1)
        auth_enabled = True
    elif getattr(config, "ENABLE_AUTH", False):
        auth_enabled = True
        auth_user = getattr(config, "AUTH_USERNAME", "admin")
        auth_pass = getattr(config, "AUTH_PASSWORD", "password123")

    # 5. Check Port Availability
    if is_port_in_use(port, bind_host):
        if auto_wait:
            print(f"[{APP_NAME}] Port {port} is in use. Waiting for it to become free...")
            while is_port_in_use(port, bind_host):
                time.sleep(2)
            print(f"[{APP_NAME}] Port {port} is now free!")
        else:
            print(f"[Error] Port {port} is already in use by another process.")
            print(f"Tip: Set AUTO_WAIT_IF_BUSY = True in config.py or specify another port.")
            sys.exit(1)

    server_cfg = ServerConfig(
        root_dir=root_path,
        port=port,
        host=bind_host,
        readonly=readonly,
        show_hidden=show_hidden,
        enable_auth=auth_enabled,
        auth_user=auth_user,
        auth_pass=auth_pass,
    )

    # 6. Optional Cloudflare Tunnel Channel
    tunnel = None
    if enable_tunnel:
        tunnel = CloudflareTunnel(port=port, host="127.0.0.1")

        def run_tunnel():
            time.sleep(1.2)
            try:
                public_url = tunnel.start()
                print("\n" + "=" * 68)
                print(f"🌐 PUBLIC CLOUDFLARE HTTPS TUNNEL ACTIVE:")
                print(f"👉 {public_url}")
                print("=" * 68 + "\n")
            except Exception as e:
                print(f"\n[Notice] Cloudflare tunnel not active: {e}")
                print(f"Local & network access remains available.\n")

        tunnel_thread = threading.Thread(target=run_tunnel, daemon=True)
        tunnel_thread.start()

    # 7. Clean Shutdown Signals
    def handle_exit(sig, frame):
        print(f"\n[{APP_NAME}] Shutting down cleanly...")
        if tunnel:
            tunnel.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    try:
        run_app(server_cfg)
    finally:
        if tunnel:
            tunnel.stop()


if __name__ == "__main__":
    main()
