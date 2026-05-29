"""
Exports all products and settings from Supabase to JSON files in backup/.
Run by GitHub Actions every 30 minutes.
"""
import os
import json
from pathlib import Path
from datetime import datetime, timezone

url = os.environ.get("SUPABASE_URL", "").strip()
key = os.environ.get("SUPABASE_KEY", "").strip()

if not url or not key:
    raise SystemExit("ERROR: SUPABASE_URL and SUPABASE_KEY must be set in GitHub secrets.")

if "supabase.com/dashboard" in url:
    raise SystemExit(
        f"ERROR: SUPABASE_URL looks like a browser URL, not an API URL.\n"
        f"  Got:      {url}\n"
        f"  Expected: https://<project-id>.supabase.co"
    )

from supabase import create_client
sb = create_client(url, key)

Path("backup").mkdir(exist_ok=True)

# Products — order by updated_at (created_at may not be a table column)
rows     = sb.table("products").select("*").order("updated_at").execute()
products = [r["data"] for r in rows.data if r.get("data")]
with open("backup/products_backup.json", "w", encoding="utf-8") as f:
    json.dump(products, f, indent=2, ensure_ascii=False)

# Settings
s_rows   = sb.table("settings").select("data").eq("id", "default").execute()
settings = s_rows.data[0]["data"] if s_rows.data else {}
with open("backup/settings_backup.json", "w", encoding="utf-8") as f:
    json.dump(settings, f, indent=2, ensure_ascii=False)

# Manifest
manifest = {
    "timestamp":     datetime.now(timezone.utc).isoformat(),
    "product_count": len(products),
    "supabase_url":  url,
}
with open("backup/manifest.json", "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2)

print(f"OK Backed up {len(products)} products at {manifest['timestamp']}")
