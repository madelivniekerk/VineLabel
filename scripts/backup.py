"""
Exports all products and settings from Supabase to JSON files in backup/.
Run by GitHub Actions every 30 minutes.
"""
import os
import json
from pathlib import Path
from datetime import datetime, timezone

from supabase import create_client

url = os.environ["SUPABASE_URL"]
key = os.environ["SUPABASE_KEY"]
sb  = create_client(url, key)

Path("backup").mkdir(exist_ok=True)

# Products
rows     = sb.table("products").select("data").order("created_at").execute()
products = [r["data"] for r in rows.data]
with open("backup/products_backup.json", "w", encoding="utf-8") as f:
    json.dump(products, f, indent=2, ensure_ascii=False)

# Settings
s_rows   = sb.table("settings").select("data").eq("id", "default").execute()
settings = s_rows.data[0]["data"] if s_rows.data else {}
with open("backup/settings_backup.json", "w", encoding="utf-8") as f:
    json.dump(settings, f, indent=2, ensure_ascii=False)

# Manifest
manifest = {
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "product_count": len(products),
}
with open("backup/manifest.json", "w") as f:
    json.dump(manifest, f, indent=2)

print(f"✓ Backed up {len(products)} products — {manifest['timestamp']}")
