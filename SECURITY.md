# Security Policy for vPS Share

vPS Share is a self-hosted file manager. Because it can expose server
filesystem contents over the network, your deployment is only as secure as
your configuration. Please read this policy before exposing the server.

## Supported Configuration

| Threat model                              | Recommended setup                                                                  |
|:------------------------------------------|:-----------------------------------------------------------------------------------|
| Local / personal use (localhost)          | `CHANNELS = ["local"]` or SSH forwarded port; auth optional                       |
| Private LAN or VPN                        | `CHANNELS = ["network"]` + strong `AUTH_PASSWORD`                                 |
| Public internet (IP or `trycloudflare`)   | Enable auth with a strong password; prefer `CHANNELS = ["tunnel"]` over raw `network` |

> ⚠️ The free `trycloudflare.com` tunnel issues a **public, random URL**. Anyone
> with the link reaches your server. Always pair it with `ENABLE_AUTH = True`.

## Reporting a Vulnerability

Please **do not** open a public GitHub issue for security flaws.

Email the maintainer (PSTECH) or use GitHub's **private vulnerability reporting**
flow on the repository. When reporting, include:

1. The exact version / commit you tested
2. Steps to reproduce
3. Impact description
4. Any suggested fix (optional)

We aim to acknowledge reports within **72 hours**.

## Known Considerations & Hardening Checklist

- **HTTP Basic Auth over plain HTTP** — credentials travel base64-encoded.
  Use `"tunnel"` (HTTPS), an SSH tunnel, or a reverse proxy with TLS for any
  non-local deployment.
- **Read-write by default** — with auth disabled, anyone can upload/rename/delete.
  Set `READONLY = True` for a share-only box.
- **Sandbox scope** — every request is `realpath()`-checked against `ROOT_DIR`.
  Symlinks that resolve outside the root are denied. This is enforced, but the
  practical boundary is your chosen `ROOT_DIR` — keep it minimal.
- **Run as a low-privilege user** — don't run the server as `root`/Administrator.
- **Credentials in `config.py`** — this file holds plain-text secrets; protect its
  permissions (`chmod 600`) and never commit real credentials.