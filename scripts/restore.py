"""
Restores products and settings from backup/ JSON files into Supabase.
Uses upsert (insert or update on conflict) — safe to run multiple times.

Usage:
    SUPABASE_URL=https://xxx.supabase.co SUPABASE_KEY=eyJ... python scripts/restore.py

Or set secrets in .streamlit/secrets.toml and run locally — the script will
fall back to reading from there if env vars are not set.
"""
import os
import json
import sys
from pathlib import Path

# --- credentials ---
url = os.environ.get("SUPABASE_URL", "").strip()
key = os.environ.get("SUPABASE_KEY", "").strip()

if not url or not key:
    # try reading from .streamlit/secrets.toml for local use
    secrets_path = Path(".streamlit/secrets.toml")
    if secrets_path.exists():
        import re
        text = secrets_path.read_text(encoding="utf-8")
        m_url = re.search(r'SUPABASE_URL\s*=\s*"([^"]+)"', text)
        m_key = re.search(r'SUPABASE_KEY\s*=\s*"([^"]+)"', text)
        if m_url:
            url = m_url.group(1).strip()
        if m_key:
            key = m_key.group(1).strip()

if not url or not key:
    raise SystemExit(
        "ERROR: Set SUPABASE_URL and SUPABASE_KEY as environment variables,\n"
        "or add them to .streamlit/secrets.toml before running this script."
    )

from supabase import create_client
sb = create_client(url, key)

# --- restore products ---
products_file = Path("backup/products_backup.json")
if not products_file.exists():
    raise SystemExit("ERROR: backup/products_backup.json not found. Nothing to restore.")

products = json.loads(products_file.read_text(encoding="utf-8"))

if not products:
    print("WARNING: products_backup.json is empty — nothing to restore.")
else:
    # upsert in batches of 50 to stay within request size limits
    batch_size = 50
    restored = 0
    for i in range(0, len(products), batch_size):
        batch = products[i : i + batch_size]
        sb.table("products").upsert(batch, on_conflict="id").execute()
        restored += len(batch)
    print(f"OK Restored {restored} products.")

# --- restore settings ---
settings_file = Path("backup/settings_backup.json")
if settings_file.exists():
    settings = json.loads(settings_file.read_text(encoding="utf-8"))
    if settings:
        sb.table("settings").upsert(settings, on_conflict="id").execute()
        print("OK Restored settings.")
    else:
        print("INFO: settings_backup.json is empty — skipped.")
else:
    print("INFO: backup/settings_backup.json not found — skipped.")

# --- summary ---
manifest_file = Path("backup/manifest.json")
if manifest_file.exists():
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    print(f"INFO: Backup was taken at {manifest.get('timestamp', 'unknown')}")

print("Done.")
