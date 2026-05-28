import streamlit as st
import json
import uuid
import io
import base64
import os
from pathlib import Path
from datetime import datetime, date

try:
    import anthropic as _anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

def _wood_texture_b64():
    # SVG from cellar-handoff/direction-cellar.jsx
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' width='1800' height='1200' viewBox='0 0 1800 1200'>"
        "<defs>"
        "<filter id='w' x='0' y='0' width='100%' height='100%'>"
        "<feTurbulence type='turbulence' baseFrequency='0.012 0.55' numOctaves='3' seed='7'/>"
        "<feColorMatrix values='0 0 0 0 0.30  0 0 0 0 0.16  0 0 0 0 0.09  0 0 0 1.2 -0.15'/>"
        "</filter>"
        "<filter id='knots' x='0' y='0' width='100%' height='100%'>"
        "<feTurbulence type='turbulence' baseFrequency='0.6' numOctaves='1' seed='3'/>"
        "<feColorMatrix values='0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 0.25 0'/>"
        "</filter>"
        "</defs>"
        "<rect width='100%' height='100%' fill='#3a2014'/>"
        "<rect width='100%' height='100%' filter='url(#w)' opacity='0.85'/>"
        "<rect width='100%' height='100%' filter='url(#knots)'/>"
        "<g stroke='#150806' stroke-opacity='0.55' stroke-width='1'>"
        "<line x1='0' y1='240' x2='1800' y2='240'/>"
        "<line x1='0' y1='630' x2='1800' y2='630'/>"
        "<line x1='0' y1='960' x2='1800' y2='960'/>"
        "</g>"
        "<g stroke='#150806' stroke-opacity='0.25' stroke-width='1'>"
        "<line x1='0' y1='241' x2='1800' y2='241'/>"
        "<line x1='0' y1='631' x2='1800' y2='631'/>"
        "<line x1='0' y1='961' x2='1800' y2='961'/>"
        "</g>"
        "</svg>"
    )
    return base64.b64encode(svg.encode()).decode()

def _load_asset_b64(filename):
    p = Path(__file__).parent / "assets" / filename
    if not p.exists():
        return None
    with open(p, "rb") as f:
        return base64.b64encode(f.read()).decode()

try:
    import qrcode
    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False

st.set_page_config(
    page_title="VineLabel · EU Wine Labels",
    page_icon="🍷",
    layout="centered",
    initial_sidebar_state="collapsed",
)

PRODUCER_NAME = "Madeli"  # placeholder — replace with auth user profile

DATA_DIR = Path(__file__).parent / "data"
PRODUCTS_FILE = DATA_DIR / "products.json"
DATA_DIR.mkdir(exist_ok=True)

# ── Supabase client ───────────────────────────────────────────────────────────
@st.cache_resource
def _get_supabase():
    try:
        from supabase import create_client
        url = st.secrets.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL", "")
        key = st.secrets.get("SUPABASE_KEY") or os.environ.get("SUPABASE_KEY", "")
        if url and key:
            return create_client(url, key)
    except Exception:
        pass
    return None

# ── Data ──────────────────────────────────────────────────────────────────────
def _local_load_products():
    if not PRODUCTS_FILE.exists():
        return []
    try:
        with open(PRODUCTS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, ValueError):
        return []

def _local_save_products(products):
    tmp = PRODUCTS_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(products, f, indent=2, ensure_ascii=False)
    tmp.replace(PRODUCTS_FILE)

@st.cache_data(ttl=30)
def load_products():
    sb = _get_supabase()
    if sb:
        try:
            rows = sb.table("products").select("data").order("created_at").execute()
            products = [r["data"] for r in rows.data]
            _sync_static_products(products)
            return products
        except Exception:
            pass
    return _local_load_products()

def save_products(products):
    sb = _get_supabase()
    if sb:
        try:
            rows = [_product_to_row(p) for p in products]
            sb.table("products").upsert(rows).execute()
            load_products.clear()
            _sync_static_products(products)
            return
        except Exception:
            pass
    _local_save_products(products)
    _sync_static_products(products)

def upsert_product(product):
    sb = _get_supabase()
    if sb:
        try:
            sb.table("products").upsert(_product_to_row(product)).execute()
            load_products.clear()
            _sync_static_products(load_products())
            return
        except Exception:
            pass
    # Local fallback
    products = _local_load_products()
    for i, p in enumerate(products):
        if p["id"] == product["id"]:
            products[i] = product
            load_products.clear()
            _local_save_products(products)
            _sync_static_products(products)
            return
    load_products.clear()
    products.append(product)
    _local_save_products(products)
    _sync_static_products(products)

def get_product(pid):
    sb = _get_supabase()
    if sb:
        try:
            rows = sb.table("products").select("data").eq("id", pid).execute()
            return rows.data[0]["data"] if rows.data else None
        except Exception:
            pass
    return next((p for p in _local_load_products() if p["id"] == pid), None)

def _product_to_row(p):
    return {
        "id": p.get("id", ""),
        "name": p.get("name", ""),
        "vintage": p.get("vintage", ""),
        "variety": p.get("variety", ""),
        "region": p.get("region", ""),
        "producer_name": p.get("producer_name", ""),
        "collection": p.get("collection", ""),
        "status": p.get("status", "draft"),
        "data": p,
        "updated_at": datetime.now().isoformat(),
    }

def _sync_static_products(products):
    static_dir = Path(__file__).parent / "static"
    if not static_dir.exists():
        return
    out = [{"id": p.get("id",""), "name": p.get("name",""), "variety": p.get("variety",""),
            "region": p.get("region",""), "vintage": p.get("vintage",""),
            "type": p.get("type","Red"), "status": p.get("status","draft")} for p in products]
    try:
        tmp = static_dir / "products_data.json.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False)
        tmp.replace(static_dir / "products_data.json")
    except Exception:
        pass

SETTINGS_FILE = DATA_DIR / "settings.json"

def load_settings():
    sb = _get_supabase()
    if sb:
        try:
            rows = sb.table("settings").select("data").eq("id", "default").execute()
            return rows.data[0]["data"] if rows.data else {}
        except Exception:
            pass
    if not SETTINGS_FILE.exists():
        return {}
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, ValueError):
        return {}

def save_settings(settings):
    sb = _get_supabase()
    if sb:
        try:
            sb.table("settings").upsert({
                "id": "default",
                "data": settings,
                "updated_at": datetime.now().isoformat(),
            }).execute()
            return
        except Exception:
            pass
    tmp = SETTINGS_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)
    tmp.replace(SETTINGS_FILE)

# ── Compliance ────────────────────────────────────────────────────────────────
COMPLIANCE = {
    "EU e-label": {
        "reg": "Reg. EU 2021/2117", "color": "#003399",
        "fields": [
            ("name", "Wine name"), ("product_category", "Product category"),
            ("producer_name", "Producer name"), ("producer_address", "Producer address"),
            ("country", "Country"), ("abv", "ABV %"),
            ("net_quantity", "Net quantity"), ("lot_number", "Lot number"),
            ("ingredients", "Ingredients"), ("allergens", "Allergens"),
            ("nutrition.energy_kj", "Energy kJ"), ("nutrition.energy_kcal", "Energy kcal"),
            ("nutrition.fat_g", "Fat"), ("nutrition.carbohydrate_g", "Carbohydrate"),
            ("nutrition.protein_g", "Protein"), ("nutrition.salt_g", "Salt"),
        ],
    },
    "Packaging": {
        "reg": "PPWR 2025", "color": "#2d6a4f",
        "fields": [
            ("packaging.bottle_material", "Bottle material"),
            ("packaging.closure_type", "Closure type"),
            ("packaging.label_material", "Label material"),
            ("packaging.recycled_content_pct", "Recycled content %"),
            ("packaging.recycling_instructions", "Recycling instructions"),
        ],
    },
    "DPP Carbon": {
        "reg": "ESPR 2026", "color": "#c8964c",
        "fields": [
            ("sustainability.carbon_footprint_kg", "Carbon footprint"),
            ("supply_chain.vineyard_name", "Vineyard name"),
            ("supply_chain.vineyard_country", "Vineyard country"),
        ],
    },
}

def _get(obj, path):
    for key in path.split("."):
        if not isinstance(obj, dict):
            return None
        obj = obj.get(key)
    if obj is None:
        return None
    if isinstance(obj, list):
        return obj or None
    if isinstance(obj, str):
        return obj.strip() or None
    return obj

def _fmt_date(d):
    if not d:
        return None
    try:
        return date.fromisoformat(d).strftime("%d %b %Y")
    except (ValueError, TypeError):
        return d

def compliance_score(product):
    results = {}
    for section, info in COMPLIANCE.items():
        passed, failed = [], []
        for path, label in info["fields"]:
            (passed if _get(product, path) is not None else failed).append(label)
        results[section] = {
            "reg": info["reg"], "color": info["color"],
            "passed": passed, "failed": failed,
            "score": len(passed), "total": len(info["fields"]),
        }
    return results

# ── QR ────────────────────────────────────────────────────────────────────────
def get_label_url(pid):
    saved = (st.session_state.get("base_url") or load_settings().get("base_url", "")).rstrip("/")
    if saved:
        return f"{saved}/?label={pid}"
    # Auto-detect from request Host header so QR codes work on any deployment
    try:
        host = st.context.headers.get("Host", "")
        if host and not host.startswith("localhost") and not host.startswith("127.0.0.1"):
            return f"https://{host}/?label={pid}"
    except Exception:
        pass
    return f"http://localhost:8501/?label={pid}"

def make_qr_image(url):
    if not QR_AVAILABLE:
        return None
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1a1a2e", back_color="#faf9f7")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

# ── AI helpers ────────────────────────────────────────────────────────────────
def _get_api_key():
    try:
        return st.secrets.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    except Exception:
        return os.environ.get("ANTHROPIC_API_KEY")

def ai_detect_allergens(ingredients):
    if not ANTHROPIC_AVAILABLE or not _get_api_key():
        return []
    try:
        client = _anthropic.Anthropic(api_key=_get_api_key())
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=150,
            messages=[{"role": "user", "content": (
                "You are an EU food labelling expert. Given these wine ingredients, "
                "identify which EU-regulated allergens must be declared.\n\n"
                f"Ingredients: {', '.join(ingredients)}\n\n"
                "EU allergens relevant to wine: Sulphites (from sulfur dioxide, "
                "potassium metabisulphite, etc.), Eggs (albumin, lysozyme), "
                "Milk (casein, lactose), Fish (isinglass).\n\n"
                "Reply with ONLY a JSON array using these exact strings where applicable: "
                '["Sulphites", "Egg (albumin fining agent)", '
                '"Milk (casein fining agent)", "Fish (isinglass fining agent)"]. '
                "Return [] if none detected."
            )}]
        )
        return json.loads(msg.content[0].text.strip())
    except Exception:
        return []

def ai_translate_label(product, languages=("de", "fr", "it", "es")):
    if not ANTHROPIC_AVAILABLE or not _get_api_key():
        return {}, "Anthropic library or API key not available."
    LANG_NAMES = {"de": "German", "fr": "French", "it": "Italian", "es": "Spanish"}
    to_translate = {}
    if product.get("ingredients"):
        to_translate["ingredients"] = ", ".join(product["ingredients"])
    if product.get("allergens"):
        to_translate["allergens"] = ", ".join(product["allergens"])
    pkg = product.get("packaging", {})
    if pkg and pkg.get("recycling_instructions"):
        to_translate["recycling_instructions"] = pkg["recycling_instructions"]
    if product.get("storage_info"):
        to_translate["storage_info"] = product["storage_info"]
    if not to_translate:
        return {}, "No translatable content found — add ingredients, allergens, or storage info first."
    results = {}
    last_error = None
    client = _anthropic.Anthropic(api_key=_get_api_key())
    for lang in languages:
        try:
            msg = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                messages=[{"role": "user", "content": (
                    f"Translate the following wine label fields into {LANG_NAMES[lang]} "
                    "for EU regulatory compliance labelling.\n"
                    "Rules: keep E-numbers (E220, E334, etc.) unchanged. "
                    "Keep brand names and proper nouns unchanged. "
                    "Be precise — this is regulatory text.\n\n"
                    f"Fields:\n{json.dumps(to_translate, ensure_ascii=False)}\n\n"
                    f"Reply with ONLY a JSON object with the same keys, values in {LANG_NAMES[lang]}."
                )}]
            )
            raw = msg.content[0].text.strip()
            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[-2] if "```" in raw[3:] else raw
                raw = raw.lstrip("json").strip()
            results[lang] = json.loads(raw)
        except Exception as e:
            last_error = str(e)
            results[lang] = {}
    return results, last_error

# ── Design ────────────────────────────────────────────────────────────────────
C = {
    # Design tokens from design_handoff_vinelabel
    "wine":    "#7a1d24",
    "wine2":   "#9c2731",
    "wineDim": "#5a1520",
    "bg":      "#f6efe0",
    "paper":   "#f3ead9",
    "paperCard":"#f6efe0",
    "paperDeep":"#ece1c8",
    "paperEdge":"#e0d4b8",
    "cream":   "#f3ead9",
    "ink":     "#15110d",
    "inkSoft": "#2a221a",
    "ink2":    "#6e5a3d",
    "ink3":    "#b7a786",
    "ink60":   "rgba(21,17,13,0.6)",
    "ink12":   "rgba(40,28,18,0.12)",
    "ink08":   "rgba(40,28,18,0.08)",
    "gold":    "#c89a5a",
    "goldSoft":"#f1e6cd",
    "green":   "#4f6b3a",
    "greenSoft":"#e6e8d8",
    "eu":      "#2A4F6B",
    "red":     "#A93527",
    "woodDark":"#0c0907",
    "muted":   "#b7a786",
    "mutedDark":"#6e5a3d",
}

# Static translations for fixed EU-label UI strings (not product data)
_LABEL_UI = {
    "Ingredients":            {"de": "Zutaten",            "fr": "Ingrédients",                "it": "Ingredienti",          "es": "Ingredientes"},
    "Contains Allergens":     {"de": "Enthält Allergene",  "fr": "Contient des allergènes",     "it": "Contiene allergeni",   "es": "Contiene alérgenos"},
    "Nutrition · per 100 mL": {"de": "Nährwerte · je 100 mL", "fr": "Valeurs nutritionnelles · pour 100 mL", "it": "Valori nutrizionali · per 100 mL", "es": "Información nutricional · por 100 mL"},
    "Energy":                 {"de": "Energie",             "fr": "Énergie",                    "it": "Energia",              "es": "Energía"},
    "Fat":                    {"de": "Fett",                "fr": "Matières grasses",            "it": "Grassi",               "es": "Grasas"},
    "of which saturates":     {"de": "davon ges. Fettsäuren", "fr": "dont acides gras saturés", "it": "di cui acidi grassi saturi", "es": "de las cuales saturadas"},
    "Carbohydrate":           {"de": "Kohlenhydrate",       "fr": "Glucides",                   "it": "Carboidrati",          "es": "Hidratos de carbono"},
    "of which sugars":        {"de": "davon Zucker",        "fr": "dont sucres",                "it": "di cui zuccheri",      "es": "de los cuales azúcares"},
    "Protein":                {"de": "Eiweiß",              "fr": "Protéines",                  "it": "Proteine",             "es": "Proteínas"},
    "Salt":                   {"de": "Salz",                "fr": "Sel",                        "it": "Sale",                 "es": "Sal"},
    "Packaging & Recycling":  {"de": "Verpackung & Recycling", "fr": "Emballage & Recyclage",  "it": "Imballaggio & Riciclaggio", "es": "Envase & Reciclaje"},
    "Carbon Footprint":       {"de": "CO₂-Fußabdruck",     "fr": "Empreinte carbone",          "it": "Impronta carbonica",   "es": "Huella de carbono"},
    "Provenance":             {"de": "Herkunft",            "fr": "Provenance",                 "it": "Provenienza",          "es": "Procedencia"},
    "Certifications":         {"de": "Zertifizierungen",   "fr": "Certifications",             "it": "Certificazioni",       "es": "Certificaciones"},
    "Storage:":               {"de": "Lagerung:",           "fr": "Conservation :",             "it": "Conservazione:",       "es": "Almacenamiento:"},
    # Packaging material display phrases
    "Glass bottle":           {"de": "Glasflasche",         "fr": "Bouteille en verre",         "it": "Bottiglia di vetro",   "es": "Botella de vidrio"},
    "Aluminium bottle":       {"de": "Aluminiumflasche",    "fr": "Bouteille en aluminium",     "it": "Bottiglia di alluminio","es": "Botella de aluminio"},
    "Natural cork":           {"de": "Naturkorken",         "fr": "Liège naturel",              "it": "Sughero naturale",     "es": "Corcho natural"},
    "Screwcap":               {"de": "Schraubverschluss",   "fr": "Capsule à vis",              "it": "Tappo a vite",         "es": "Tapón de rosca"},
    "Synthetic cork":         {"de": "Kunststoffkorken",    "fr": "Bouchon synthétique",        "it": "Tappo sintetico",      "es": "Corcho sintético"},
    "Tin":                    {"de": "Zinn",                "fr": "Étain",                      "it": "Stagno",               "es": "Estaño"},
    "Aluminium":              {"de": "Aluminium",           "fr": "Aluminium",                  "it": "Alluminio",            "es": "Aluminio"},
    "Paper label":            {"de": "Papieretikett",       "fr": "Étiquette en papier",        "it": "Etichetta in carta",   "es": "Etiqueta de papel"},
    "Tin capsule":            {"de": "Zinnkapsel",          "fr": "Capsule en étain",           "it": "Capsula in stagno",    "es": "Cápsula de estaño"},
    "Aluminium capsule":      {"de": "Aluminiumkapsel",     "fr": "Capsule en aluminium",       "it": "Capsula in alluminio", "es": "Cápsula de aluminio"},
    "PVC capsule":            {"de": "PVC-Kapsel",          "fr": "Capsule en PVC",             "it": "Capsula in PVC",       "es": "Cápsula de PVC"},
    # Recycling tips
    "Recycle at glass bank":              {"de": "Im Glascontainer recyceln",        "fr": "Recycler en conteneur à verre",    "it": "Riciclare al cassonetto del vetro",   "es": "Reciclar en contenedor de vidrio"},
    "Compost or cork recycling program":  {"de": "Kompostieren oder Korkrecycling",  "fr": "Composter ou recycler le liège",   "it": "Compostare o riciclaggio del sughero","es": "Compostar o reciclar el corcho"},
    "Recycle with metals":                {"de": "Mit Metall recyceln",              "fr": "Recycler avec les métaux",         "it": "Riciclare con i metalli",             "es": "Reciclar con metales"},
    "General waste":                      {"de": "Allgemeiner Abfall",               "fr": "Déchets généraux",                 "it": "Rifiuti generali",                    "es": "Residuos generales"},
    "Remove label before recycling bottle":{"de": "Etikett vor dem Recyceln entfernen","fr": "Retirer l'étiquette avant recyclage","it": "Rimuovere l'etichetta prima del riciclaggio","es": "Retirar la etiqueta antes de reciclar"},
    "General waste — not recyclable":     {"de": "Allgemeiner Abfall — nicht recycelbar","fr": "Déchets — non recyclable",    "it": "Rifiuti — non riciclabile",           "es": "Residuos — no reciclable"},
    "% recycled glass content":           {"de": "% Recyclingglas-Anteil",           "fr": "% de verre recyclé",              "it": "% di vetro riciclato",                "es": "% de vidrio reciclado"},
}

def load_hero():
    for name in ["cellar-hero.png", "hero.png"]:
        hero = Path(__file__).parent / "assets" / name
        if hero.exists():
            with open(hero, "rb") as f:
                return base64.b64encode(f.read()).decode()
    return None

def show_landing():
    wine_bg = _load_asset_b64("wine-bg.jpg")
    bg_img  = f'url("data:image/jpeg;base64,{wine_bg}")' if wine_bg else "none"
    st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Caveat:wght@500;600;700&family=Gloock&family=Inter:wght@400;500;600;700&display=swap');
html{{
    background-image:
        radial-gradient(ellipse at center,transparent 55%,rgba(0,0,0,0.55) 100%),
        linear-gradient(95deg,rgba(12,8,6,0.92) 0%,rgba(12,8,6,0.78) 28%,rgba(12,8,6,0.25) 55%,rgba(12,8,6,0.05) 80%),
        radial-gradient(ellipse at 18% 50%,rgba(0,0,0,0.55) 0%,transparent 60%),
        {bg_img}!important;
    background-size:cover!important;
    background-position:center right!important;
    background-color:#1a0f08!important;
    background-repeat:no-repeat!important;
    background-attachment:fixed!important;
}}
body,
[data-testid="stApp"],
[data-testid="stAppViewContainer"],
[data-testid="stAppViewBlockContainer"],
[data-testid="stMain"],
[data-testid="stMainBlockContainer"],
[data-testid="stVerticalBlock"],
[data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stHorizontalBlock"],
[data-testid="stColumn"],
[data-testid="stBottom"],
.main,.block-container{{
    background:none!important;
    background-color:transparent!important;
    background-image:none!important;
    box-shadow:none!important;
    padding:0!important;
    max-width:100%!important;
}}
#MainMenu,footer,[data-testid="stHeader"],[data-testid="stToolbar"],[data-testid="stDecoration"]{{display:none!important;}}
::-webkit-scrollbar{{display:none!important;}}
html{{-ms-overflow-style:none!important;scrollbar-width:none!important;}}
</style>
<nav style="position:relative;z-index:3;display:flex;align-items:center;justify-content:space-between;padding:16px 56px;">
  <div style="display:flex;align-items:center;gap:14px;">
    <div style="width:40px;height:40px;border-radius:8px;background:#7a1d24;color:#f3ead9;display:grid;place-items:center;font-family:Gloock,serif;font-size:20px;box-shadow:inset 0 0 0 1px rgba(255,255,255,0.08),0 4px 14px rgba(0,0,0,0.4);">V</div>
    <div style="line-height:1.1;">
      <div style="font-family:Gloock,serif;font-size:20px;color:#f3ead9;letter-spacing:0.005em;">VineLabel</div>
      <div style="font-size:10px;letter-spacing:0.28em;text-transform:uppercase;color:#b7a786;margin-top:2px;">EU DPP Studio</div>
    </div>
  </div>
  <div style="display:flex;align-items:center;gap:14px;">
    <a href="?signin=1" style="font-family:Inter,sans-serif;font-weight:500;font-size:13.5px;padding:9px 16px;border-radius:8px;border:1px solid rgba(243,234,217,0.22);background:rgba(243,234,217,0.04);color:#f3ead9;text-decoration:none;">Sign in</a>
    <a href="?signin=1" style="font-family:Inter,sans-serif;font-weight:500;font-size:13.5px;padding:9px 16px;border-radius:8px;background:#7a1d24;color:#f3ead9;text-decoration:none;box-shadow:0 6px 18px rgba(122,29,36,0.45),inset 0 1px 0 rgba(255,255,255,0.08);">Start free →</a>
  </div>
</nav>
<main style="position:relative;z-index:2;display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.05fr);padding:0 56px 24px;align-items:start;gap:40px;">
  <div style="max-width:620px;">
    <div style="display:inline-flex;align-items:center;gap:10px;padding:5px 12px 5px 8px;border-radius:999px;background:rgba(243,234,217,0.06);border:1px solid rgba(243,234,217,0.14);font-size:11px;letter-spacing:0.18em;text-transform:uppercase;color:#b7a786;margin-bottom:6px;">
      <span style="width:7px;height:7px;border-radius:50%;background:#c89a5a;box-shadow:0 0 0 3px rgba(200,154,90,0.18);display:inline-block;"></span>AI-Powered · EU Reg. 2021/2117 · Built for Australia
    </div>
    <div style="font-family:Caveat,cursive;font-size:24px;color:#c89a5a;line-height:1.1;margin:0 0 2px;display:flex;align-items:center;gap:14px;">
      <span style="width:38px;height:1px;background:#c89a5a;opacity:0.7;display:inline-block;"></span>the only wine label tool with built-in AI
    </div>
    <h1 style="font-family:Gloock,serif;font-weight:400;font-size:clamp(36px,4vw,58px);line-height:1.05;letter-spacing:-0.01em;margin:0 0 2px;color:#f3ead9;">
      Your EU label,<br>
      <span style="font-family:Caveat,cursive;font-weight:700;color:#c89a5a;font-size:0.82em;display:block;margin-top:4px;white-space:nowrap;">approved before it ships.</span>
    </h1>
    <p style="font-size:17px;line-height:1.55;color:rgba(243,234,217,0.82);margin:0 0 16px;max-width:52ch;">
      A <strong style="color:#f3ead9;font-weight:500;">wrong allergen declaration</strong> can hold your shipment at EU customs.
      A <strong style="color:#f3ead9;font-weight:500;">missing translation</strong> can get your label rejected at the importer.
      VineLabel catches both — automatically — before you print a single QR code.
    </p>
    <ul style="display:flex;flex-direction:column;gap:9px;margin:0 0 20px;padding:0;list-style:none;">
      <li style="display:flex;align-items:flex-start;gap:12px;font-size:16px;color:rgba(243,234,217,0.92);line-height:1.4;">
        <span style="flex:0 0 22px;width:22px;height:22px;border-radius:50%;background:rgba(200,154,90,0.14);border:1px solid rgba(200,154,90,0.55);display:grid;place-items:center;color:#c89a5a;font-size:12px;">✓</span>
        <span><b style="color:#f3ead9;font-weight:500;">AI allergen scan</b> — paste your ingredients; we flag every allergen you're legally required to declare under EU law.</span>
      </li>
      <li style="display:flex;align-items:flex-start;gap:12px;font-size:16px;color:rgba(243,234,217,0.92);line-height:1.4;">
        <span style="flex:0 0 22px;width:22px;height:22px;border-radius:50%;background:rgba(200,154,90,0.14);border:1px solid rgba(200,154,90,0.55);display:grid;place-items:center;color:#c89a5a;font-size:12px;">✓</span>
        <span><b style="color:#f3ead9;font-weight:500;">One-click translation</b> to German, French, Italian &amp; Spanish — no translators, no copy-pasting, no extra fees.</span>
      </li>
      <li style="display:flex;align-items:flex-start;gap:12px;font-size:16px;color:rgba(243,234,217,0.92);line-height:1.4;">
        <span style="flex:0 0 22px;width:22px;height:22px;border-radius:50%;background:rgba(200,154,90,0.14);border:1px solid rgba(200,154,90,0.55);display:grid;place-items:center;color:#c89a5a;font-size:12px;">✓</span>
        <span><b style="color:#f3ead9;font-weight:500;">Live compliance score</b> — know exactly what's missing across Reg. 2021/2117, PPWR 2025, and ESPR 2026.</span>
      </li>
      <li style="display:flex;align-items:flex-start;gap:12px;font-size:16px;color:rgba(243,234,217,0.92);line-height:1.4;">
        <span style="flex:0 0 22px;width:22px;height:22px;border-radius:50%;background:rgba(200,154,90,0.14);border:1px solid rgba(200,154,90,0.55);display:grid;place-items:center;color:#c89a5a;font-size:12px;">✓</span>
        <span><b style="color:#f3ead9;font-weight:500;">Winery profile pre-fill</b> — enter your producer and importer details once; every new label auto-populates them.</span>
      </li>
    </ul>
    <div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap;">
      <a href="?signin=1" style="background:linear-gradient(180deg,#9c2731,#7a1d24);color:#f3ead9;font-family:Inter,sans-serif;font-size:14.5px;font-weight:600;padding:12px 24px;border-radius:10px;text-decoration:none;display:inline-block;box-shadow:0 6px 18px rgba(122,29,36,0.45),inset 0 1px 0 rgba(255,255,255,0.08);letter-spacing:0.01em;">Start free — 2 labels included</a>
      <span style="font-size:13px;color:#b7a786;">No credit card. Cancel any time.</span>
    </div>
  </div>
  <aside style="position:relative;height:100%;min-height:420px;" aria-hidden="true">
    <div style="position:absolute;top:28%;left:52%;transform:translateX(-50%) rotate(-3deg);color:#fff;font-family:Caveat,cursive;font-size:26px;line-height:1.05;text-align:center;width:220px;text-shadow:0 2px 12px rgba(0,0,0,0.7);">
      every bottle gets one<br><span style="display:block;font-size:44px;margin-top:4px;line-height:1;">↓</span>
    </div>
    <div role="img" aria-label="AI-powered EU DPP" style="position:absolute;top:6%;right:4%;width:148px;height:148px;border-radius:50%;border:3px solid #fff;color:#fff;display:grid;place-items:center;text-align:center;transform:rotate(-14deg);background:radial-gradient(circle at 35% 30%,rgba(255,255,255,0.18),rgba(0,0,0,0) 70%);box-shadow:0 0 0 1.5px rgba(255,255,255,0.5) inset,0 0 36px rgba(0,0,0,0.6);padding:14px;">
      <div style="position:absolute;inset:7px;border-radius:50%;border:1.5px dashed rgba(255,255,255,0.75);"></div>
      <div>
        <div style="font-size:12.5px;letter-spacing:0.32em;text-transform:uppercase;font-family:Inter,sans-serif;font-weight:700;">AI-Powered</div>
        <div style="font-family:Gloock,serif;font-weight:700;font-size:32px;line-height:1.0;margin:4px 0 2px;">EU&nbsp;DPP</div>
        <div style="font-size:13.5px;letter-spacing:0.24em;text-transform:uppercase;font-family:Inter,sans-serif;font-weight:700;">Compliant</div>
      </div>
    </div>
  </aside>
</main>
<div style="position:relative;z-index:2;display:flex;align-items:center;gap:18px;padding:0 56px 28px;">
  <span style="flex:1;height:1px;background:rgba(243,234,217,0.14);display:block;"></span>
  <span style="font-family:Caveat,cursive;font-size:20px;color:#c89a5a;">pour a glass · take your time</span>
  <span style="flex:1;height:1px;background:rgba(243,234,217,0.14);display:block;"></span>
</div>
""", unsafe_allow_html=True)

    if st.session_state.get("show_login"):
        _landing_login()

@st.dialog("Welcome to VineLabel")
def _landing_login():
    st.markdown("""
<div style="text-align:center;margin-bottom:8px;">
  <div style="font-family:Gloock,serif;font-size:22px;color:#15110d;margin-bottom:4px;">Sign in or get started</div>
  <div style="font-size:14px;color:#6e5a3d;">Enter your winery name to continue. Your first 2 labels are free.</div>
</div>
""", unsafe_allow_html=True)
    winery = st.text_input("Winery name", placeholder="e.g. Barossa Valley Estate")
    email  = st.text_input("Email address", placeholder="you@yourwinery.com.au")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Continue →", type="primary", use_container_width=True):
            if winery.strip():
                st.session_state["winery_name"]  = winery.strip()
                st.session_state["winery_email"] = email.strip()
                st.session_state["show_login"]   = False
                st.query_params["page"] = "dashboard"
                st.rerun()
            else:
                st.error("Please enter your winery name.")
    with col2:
        if st.button("Cancel", type="secondary", use_container_width=True):
            st.session_state["show_login"] = False; st.rerun()

def inject_css():
    _wood_svg   = _wood_texture_b64()
    _wood_photo = _load_asset_b64("wood-bg.png")
    _photo_layer = f'url("data:image/png;base64,{_wood_photo}"),' if _wood_photo else ""
    st.markdown('<link href="https://fonts.googleapis.com/css2?family=Caveat:wght@500;600;700&family=Gloock&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">', unsafe_allow_html=True)
    st.markdown(f"""
<style>

/* ── 1. Single background on html only ── */
html{{
    background-color:{C['woodDark']}!important;
    background-image:
        radial-gradient(ellipse at top,rgba(0,0,0,0) 0%,rgba(0,0,0,0.35) 80%),
        {_photo_layer}
        url("data:image/svg+xml;base64,{_wood_svg}")!important;
    background-size:cover!important;
    background-repeat:no-repeat!important;
    background-attachment:fixed!important;
    font-family:'Inter',system-ui,sans-serif;
    color:{C['ink']};
}}

/* ── 2. Every Streamlit container: transparent, no background ── */
body,
[data-testid="stApp"],
[data-testid="stAppViewContainer"],
[data-testid="stAppViewBlockContainer"],
[data-testid="stMain"],
[data-testid="stMainBlockContainer"],
[data-testid="stVerticalBlock"],
[data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stHorizontalBlock"],
[data-testid="stColumn"],
[data-testid="stBottom"],
.main, .block-container{{
    background:none!important;
    background-color:transparent!important;
    background-image:none!important;
    box-shadow:none!important;
}}

/* ── 3. Hide Streamlit chrome ── */
#MainMenu,footer,[data-testid="stHeader"],[data-testid="stToolbar"],
[data-testid="stDecoration"]{{display:none!important;}}
[data-testid="stHorizontalBlock"]{{flex-direction:row!important;flex-wrap:nowrap!important;}}

/* ── 4. Buttons ── */
[data-testid="stBaseButton-primary"],[data-testid="stBaseButton-primary"] button,
[data-testid="stBaseButton-primaryFormSubmit"],[data-testid="stBaseButton-primaryFormSubmit"] button{{
    background:linear-gradient(180deg,{C['wine2']},{C['wineDim']})!important;
    border:none!important;border-radius:10px!important;color:{C['cream']}!important;
    box-shadow:0 1px 0 rgba(255,255,255,0.12) inset,0 6px 14px -6px rgba(122,31,43,0.6)!important;
}}
[data-testid="stBaseButton-primary"] p,[data-testid="stBaseButton-primaryFormSubmit"] p{{color:{C['cream']}!important;font-weight:600!important;}}
/* Secondary buttons default: cream text for dark wood background (e.g. back arrow) */
[data-testid="stBaseButton-secondary"],[data-testid="stBaseButton-secondary"] button{{
    background:rgba(250,246,240,0.1)!important;border:1.5px solid rgba(250,246,240,0.35)!important;
    border-radius:10px!important;color:{C['cream']}!important;
}}
[data-testid="stBaseButton-secondary"] p{{color:{C['cream']}!important;font-weight:600!important;}}
/* Form submit buttons (secondaryFormSubmit) — always on parchment, use ink style */
[data-testid="stBaseButton-secondaryFormSubmit"],[data-testid="stBaseButton-secondaryFormSubmit"] button{{
    background:transparent!important;border:1px solid {C['paperEdge']}!important;
    border-radius:10px!important;color:{C['ink']}!important;
}}
[data-testid="stBaseButton-secondaryFormSubmit"] p{{color:{C['ink']}!important;font-weight:600!important;}}
/* Inside forms and expanders (parchment bg): revert to dark ink */
[data-testid="stForm"] [data-testid="stBaseButton-secondary"],
[data-testid="stForm"] [data-testid="stBaseButton-secondary"] button,
[data-testid="stExpander"] [data-testid="stBaseButton-secondary"],
[data-testid="stExpander"] [data-testid="stBaseButton-secondary"] button{{
    background:transparent!important;border:1px solid {C['paperEdge']}!important;color:{C['ink']}!important;
}}
[data-testid="stForm"] [data-testid="stBaseButton-secondary"] p,
[data-testid="stExpander"] [data-testid="stBaseButton-secondary"] p{{color:{C['ink']}!important;font-weight:600!important;}}

/* ── 5. Typography ── */
h1,h2,h3{{font-family:'Gloock',serif!important;letter-spacing:-0.01em!important;}}
.caveat{{font-family:'Caveat',cursive!important;}}

/* ── 6. Card elements ── */
[data-testid="stForm"]{{background:{C['paper']}!important;border:1px solid {C['paperEdge']}!important;border-left:4px solid {C['wine2']}!important;border-radius:14px!important;padding:20px!important;box-shadow:0 1px 0 rgba(255,255,255,0.6) inset,0 18px 38px -16px rgba(0,0,0,0.45),0 4px 10px -4px rgba(0,0,0,0.3)!important;}}
[data-testid="stExpander"]{{background:{C['paper']}!important;border:1px solid {C['paperEdge']}!important;border-radius:14px!important;box-shadow:0 4px 18px -8px rgba(0,0,0,0.4)!important;}}
[data-testid="stFileUploader"]{{background:transparent!important;border-radius:10px!important;}}
[data-testid="stFileUploaderDropzone"]{{
    background:{C['cream']}!important;
    border:1.5px dashed {C['ink12']}!important;
    border-radius:10px!important;
}}
[data-testid="stFileUploaderDropzone"]:hover{{
    border-color:{C['gold']}!important;
    background:{C['goldSoft']}!important;
}}
[data-testid="stFileUploaderDropzone"] *{{color:{C['ink2']}!important;}}
[data-testid="stFileUploaderDropzone"] button{{
    background:{C['wine']}!important;color:{C['cream']}!important;
    border:none!important;border-radius:8px!important;
}}
section[data-testid="stSidebar"]{{background:{C['woodDark']}!important;}}

/* ── 7. Form inputs — light backgrounds so text is readable ── */
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stDateInput"] input{{
    background:{C['cream']}!important;color:{C['ink']}!important;
    border:1px solid {C['ink12']}!important;border-radius:8px!important;
}}
[data-testid="stDateInput"] [data-baseweb="input"],
[data-testid="stDateInput"] [data-baseweb="base-input"]{{
    background:{C['cream']}!important;border-color:{C['ink12']}!important;border-radius:8px!important;
}}
[data-testid="stDateInput"] button{{
    background:{C['cream']}!important;color:{C['ink2']}!important;
}}
/* Date picker calendar popup */
[data-baseweb="calendar"],
[data-baseweb="calendar"] *,
[data-baseweb="datepicker"],
[data-baseweb="datepicker"] *{{
    background:{C['cream']}!important;
    color:{C['ink']}!important;
    border-color:{C['paperEdge']}!important;
}}
/* Empty / out-of-month / disabled cells — transparent, not dark */
[data-baseweb="calendar"] td,
[data-baseweb="calendar"] tr,
[data-baseweb="calendar"] table{{
    background:transparent!important;
}}
[data-baseweb="calendar"] button[disabled],
[data-baseweb="calendar"] [aria-disabled="true"],
[data-baseweb="calendar"] [aria-disabled="true"] *{{
    background:transparent!important;
    color:{C['ink60']}!important;
}}
/* Selected date */
[data-baseweb="calendar"] [aria-selected="true"],
[data-baseweb="calendar"] [aria-selected="true"] *{{
    background:{C['wine']}!important;
    color:{C['cream']}!important;
}}
/* Today highlight */
[data-baseweb="calendar"] [aria-current="date"]{{
    border:2px solid {C['wine']}!important;
    border-radius:50%!important;
}}
/* Hover */
[data-baseweb="calendar"] button:not([disabled]):hover,
[data-baseweb="calendar"] [role="option"]:hover{{
    background:{C['goldSoft']}!important;
    color:{C['ink']}!important;
}}
/* Number input: stepper container, stepper buttons */
[data-testid="stNumberInput"] [data-baseweb="input"],
[data-testid="stNumberInput"] [data-baseweb="base-input"]{{
    background:{C['cream']}!important;border-color:{C['ink12']}!important;border-radius:8px!important;
}}
[data-testid="stNumberInput"] button{{
    background:{C['cream']}!important;color:{C['ink2']}!important;
    border-left:1px solid {C['ink12']}!important;
}}
[data-testid="stNumberInput"] button:hover{{
    background:{C['goldSoft']}!important;color:{C['ink']}!important;
}}
[data-testid="stTextArea"] textarea{{
    background:{C['cream']}!important;color:{C['ink']}!important;
    border:1px solid {C['ink12']}!important;border-radius:8px!important;
}}
[data-testid="stSelectbox"] [data-baseweb="select"]>div,
[data-testid="stMultiSelect"] [data-baseweb="select"]>div{{
    background:{C['cream']}!important;color:{C['ink']}!important;
    border:1px solid {C['ink12']}!important;border-radius:8px!important;
}}
[data-testid="stSelectbox"] [data-baseweb="select"] span,
[data-testid="stMultiSelect"] [data-baseweb="select"] span{{color:{C['ink']}!important;}}
/* Multiselect tags */
[data-testid="stMultiSelect"] [data-baseweb="tag"]{{
    background:{C['wine']}!important;color:{C['cream']}!important;border-radius:6px!important;
}}
[data-testid="stMultiSelect"] [data-baseweb="tag"] span{{color:{C['cream']}!important;}}
[data-baseweb="popover"],
[data-baseweb="popover"] > div,
[data-baseweb="popover"] [role="listbox"],
[data-baseweb="menu"]{{
    background:{C['paper']}!important;
    border:1px solid {C['paperEdge']}!important;
    border-radius:10px!important;
}}
[data-baseweb="menu"] li,
[data-baseweb="menu"] [role="option"],
[data-baseweb="popover"] [role="option"]{{
    background:{C['paper']}!important;
    color:{C['ink']}!important;
}}
[data-baseweb="menu"] li:hover,
[data-baseweb="menu"] [role="option"]:hover,
[data-baseweb="popover"] [role="option"]:hover{{
    background:{C['goldSoft']}!important;
    color:{C['ink']}!important;
}}
[data-testid="stWidgetLabel"] p,[data-testid="stWidgetLabel"] label{{color:{C['ink']}!important;}}
/* Checkbox */
[data-testid="stCheckbox"] label p{{color:{C['ink']}!important;}}
[data-testid="stCheckbox"] input+div{{
    background:{C['cream']}!important;border-color:{C['ink12']}!important;
}}
[data-testid="stFileUploader"] label p{{color:{C['ink']}!important;}}

/* ── 8. Highlight / focus / selection ── */
/* Replace browser-blue focus rings with gold */
*:focus-visible{{outline:2px solid {C['gold']}!important;outline-offset:2px!important;}}
button:focus-visible,a:focus-visible{{outline:2px solid {C['wine']}!important;}}
/* Expander hover: subtle gold tint, no blue */
[data-testid="stExpander"] summary,
[data-testid="stExpander"] summary:hover{{
    background-color:transparent!important;
    color:{C['ink']}!important;
}}
[data-testid="stExpander"] summary:hover{{
    background-color:rgba(184,148,85,0.07)!important;
}}
/* Streamlit default accent / primary colour → wine */
:root{{
    --primary-color:{C['wine']}!important;
    --background-color:transparent!important;
    --secondary-background-color:transparent!important;
    --text-color:{C['ink']}!important;
}}
/* Text selection */
::selection{{background:rgba(184,148,85,0.28)!important;color:{C['ink']}!important;}}

/* ── 9. QR, Edit & Public label pages — single white container ── */
[data-testid="stMainBlockContainer"]:has(.edit-page-marker),
[data-testid="stMainBlockContainer"]:has(.qr-page-marker),
[data-testid="stMainBlockContainer"]:has(.public-label-marker){{
    background:{C['paper']}!important;
    border-radius:18px!important;
    border:1px solid {C['paperEdge']}!important;
    box-shadow:0 1px 0 rgba(255,255,255,0.6) inset,0 22px 48px -16px rgba(0,0,0,0.55),0 4px 12px -4px rgba(0,0,0,0.35)!important;
    margin-top:16px!important;
    margin-bottom:16px!important;
    padding:0!important;
}}
/* Inside white containers: strip brown parchment from inner cards */
[data-testid="stMainBlockContainer"]:has(.edit-page-marker) [data-testid="stForm"],
[data-testid="stMainBlockContainer"]:has(.edit-page-marker) [data-testid="stExpander"],
[data-testid="stMainBlockContainer"]:has(.qr-page-marker) [data-testid="stExpander"]{{
    background:transparent!important;
    box-shadow:none!important;
    border-left:1px solid {C['paperEdge']}!important;
}}

/* Inside white containers: secondary buttons use dark ink */
[data-testid="stMainBlockContainer"]:has(.qr-page-marker) [data-testid="stBaseButton-secondary"],
[data-testid="stMainBlockContainer"]:has(.qr-page-marker) [data-testid="stBaseButton-secondary"] button,
[data-testid="stMainBlockContainer"]:has(.edit-page-marker) [data-testid="stBaseButton-secondary"],
[data-testid="stMainBlockContainer"]:has(.edit-page-marker) [data-testid="stBaseButton-secondary"] button{{
    background:transparent!important;border:1px solid {C['paperEdge']}!important;color:{C['ink']}!important;
}}
[data-testid="stMainBlockContainer"]:has(.qr-page-marker) [data-testid="stBaseButton-secondary"] p,
[data-testid="stMainBlockContainer"]:has(.edit-page-marker) [data-testid="stBaseButton-secondary"] p{{
    color:{C['ink']}!important;font-weight:600!important;
}}
</style>""", unsafe_allow_html=True)

def mlabel(text, color=None):
    col = color or C["ink2"]
    return (f'<div style="font-family:Inter,system-ui,sans-serif;font-size:10px;font-weight:700;'
            f'letter-spacing:0.22em;text-transform:uppercase;color:{col};margin:20px 0 8px;">{text}</div>')

def compliance_badges(product):
    html = '<div style="display:flex;flex-wrap:wrap;gap:4px;margin:6px 0 10px;">'
    scores = compliance_score(product)
    for section, d in scores.items():
        pct = int(d["score"] / d["total"] * 100) if d["total"] else 0
        col = d["color"] if pct == 100 else (C["gold"] if pct >= 60 else C["red"])
        icon = "✓" if pct == 100 else ("!" if pct >= 60 else "✗")
        html += (f'<div style="display:inline-flex;align-items:center;gap:5px;background:{col}18;'
                 f'border:1px solid {col}40;border-radius:999px;padding:3px 10px;">'
                 f'<span style="font-weight:700;color:{col};">{icon}</span>'
                 f'<span style="font-family:JetBrains Mono,monospace;font-size:9px;font-weight:700;'
                 f'letter-spacing:0.1em;color:{col};text-transform:uppercase;">{section} {pct}%</span></div>')
    st.markdown(html + "</div>", unsafe_allow_html=True)

# ── Public label ──────────────────────────────────────────────────────────────
def show_public_label(pid, is_preview=False):
    p = get_product(pid)
    if not p:
        st.error("Label not found.")
        return
    st.markdown(f"""<style>
.block-container {{
    background:{C["paper"]}!important;
    border-radius:18px!important;
    box-shadow:0 12px 40px rgba(0,0,0,0.4),0 2px 8px rgba(0,0,0,0.25)!important;
    padding:0!important;
    margin-top:2rem!important;
    max-width:520px!important;
}}
.block-container > div:first-child {{ margin-top:-3rem!important; padding-top:0!important; }}
.block-container > div > div:first-child {{ margin-top:0!important; padding-top:0!important; }}
</style>""", unsafe_allow_html=True)
    st.markdown('<div class="public-label-marker" style="display:none;"></div>', unsafe_allow_html=True)

    if is_preview:
        st.markdown(
            f'<div style="display:flex;justify-content:flex-end;margin-bottom:8px;">'
            f'<a href="?page=edit&id={pid}" style="display:inline-flex;align-items:center;gap:6px;'
            f'background:{C["paper"]};border:1px solid {C["ink12"]};border-radius:8px;'
            f'padding:6px 14px;font-family:Space Grotesk,sans-serif;font-size:13px;font-weight:600;'
            f'color:{C["ink"]};text-decoration:none;">✕ Close</a></div>',
            unsafe_allow_html=True
        )

    region_line = " · ".join(filter(None, [p.get("product_category"), p.get("variety"), p.get("region"), str(p.get("vintage", ""))]))
    st.markdown(f"""
    <div style="background:{C['wine']};padding:28px 20px 22px;margin:-1rem -1rem 0;border-radius:18px 18px 0 0;">
      <div style="font-family:JetBrains Mono,monospace;font-size:10px;font-weight:700;letter-spacing:0.2em;color:rgba(255,255,255,0.6);text-transform:uppercase;margin-bottom:6px;">{region_line}</div>
      <div style="font-family:Space Grotesk,sans-serif;font-size:28px;font-weight:700;color:#fff;line-height:1.1;margin-bottom:6px;">{p['name']}</div>
      <div style="font-family:Space Grotesk,sans-serif;font-size:14px;color:rgba(255,255,255,0.72);">{p.get('producer_name','')} · {p.get('country','Australia')}</div>
    </div>
    <div style="padding:0 20px;">
    <div style="height:16px;"></div>""", unsafe_allow_html=True)

    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:10px;padding:10px 14px;background:{C['eu']}12;border:1px solid {C['eu']}28;border-radius:10px;margin-bottom:14px;">
      <div style="font-size:20px;">🇪🇺</div>
      <div>
        <div style="font-family:JetBrains Mono,monospace;font-size:9px;font-weight:700;letter-spacing:0.15em;color:{C['eu']};text-transform:uppercase;">EU Compliant Digital Label</div>
        <div style="font-family:Space Grotesk,sans-serif;font-size:12px;color:{C['ink60']};">Regulation EU 2021/2117 · e-label</div>
      </div>
    </div>""", unsafe_allow_html=True)

    # Language selector — server-side browser language detection via Accept-Language header
    _translations = p.get("translations", {})
    _LANG_MAP = {"🇬🇧 English": "en", "🇩🇪 Deutsch": "de", "🇫🇷 Français": "fr", "🇮🇹 Italiano": "it", "🇪🇸 Español": "es"}
    _avail = {k: v for k, v in _LANG_MAP.items() if v == "en" or (v in _translations and _translations[v])}
    _avail_keys = list(_avail.keys())
    _avail_values = list(_avail.values())

    # Read Accept-Language header — e.g. "fr-FR,fr;q=0.9,en-US;q=0.8" → "fr"
    try:
        _accept = st.context.headers.get("Accept-Language", "")
        _browser_lang = _accept.split(",")[0].split(";")[0].split("-")[0].lower().strip()
        if _browser_lang not in ["en", "de", "fr", "it", "es"]:
            _browser_lang = "en"
    except Exception:
        _browser_lang = "en"

    # Priority: browser language (if translation exists) → product default → English
    _product_lang = p.get("label_language", "en")
    _label_lang = next((l for l in [_browser_lang, _product_lang, "en"] if l in _avail_values), "en")

    if len(_avail) > 1:
        st.markdown(
            f'<div style="background:{C["paper"]};border:1px solid {C["ink08"]};border-radius:10px;'
            f'padding:10px 14px;margin-bottom:14px;display:flex;align-items:center;gap:10px;">'
            f'<span style="font-size:18px;">🌐</span>'
            f'<span style="font-size:13px;font-weight:600;color:{C["ink"]};">View label in another language:</span>'
            f'</div>',
            unsafe_allow_html=True
        )
        _default_key = next((k for k, v in _LANG_MAP.items() if v == _label_lang and k in _avail), _avail_keys[0])
        _default_idx = _avail_keys.index(_default_key)
        _sel = st.selectbox("View label in", _avail_keys, index=_default_idx, key="label_lang_sel")
        _label_lang = _avail[_sel]
    def _t(field):
        if _label_lang == "en" or _label_lang not in _translations:
            return None
        return _translations[_label_lang].get(field)

    def _ui(text):
        if _label_lang == "en":
            return text
        return _LABEL_UI.get(text, {}).get(_label_lang, text)

    # Product image
    if p.get("product_image"):
        _img_ext = (p.get("product_image_filename") or "").rsplit(".", 1)[-1].lower()
        _img_mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}.get(_img_ext, "image/jpeg")
        st.markdown(f'<div style="text-align:center;margin-bottom:16px;"><img src="data:{_img_mime};base64,{p["product_image"]}" style="max-width:100%;max-height:320px;border-radius:14px;box-shadow:0 4px 18px rgba(26,26,46,0.12);" /></div>', unsafe_allow_html=True)

    # PDO/PGI badge
    if p.get("pdo_pgi"):
        st.markdown(f'<div style="display:inline-flex;align-items:center;gap:6px;background:{C["gold"]}14;border:1px solid {C["gold"]}30;border-radius:999px;padding:4px 12px;margin-bottom:14px;"><span style="font-family:JetBrains Mono,monospace;font-size:9px;font-weight:700;letter-spacing:0.14em;color:{C["gold"]};text-transform:uppercase;">PDO/PGI</span><span style="font-family:Space Grotesk,sans-serif;font-size:12px;font-weight:600;color:{C["ink"]};">{p["pdo_pgi"]}</span></div>', unsafe_allow_html=True)

    # Key facts strip
    facts = [(l, v) for l, v in [
        ("ABV", f'{p["abv"]}%' if p.get("abv") else None),
        ("Net qty", p.get("net_quantity") or None),
        ("Lot", p.get("lot_number") or None),
        ("Sweetness", p.get("sweetness_descriptor") or None),
        ("Dosage", p.get("sparkling_dosage") or None),
        ("Best before", _fmt_date(p.get("best_before_date"))),
    ] if v]
    if facts:
        cells = "".join([
            f'<div style="text-align:center;padding:12px 8px;border-right:1px solid {C["ink08"]};border-bottom:1px solid {C["ink08"]};">'
            f'<div style="font-family:JetBrains Mono,monospace;font-size:9px;font-weight:700;letter-spacing:0.15em;color:{C["ink60"]};text-transform:uppercase;">{l}</div>'
            f'<div style="font-family:Space Grotesk,sans-serif;font-size:16px;font-weight:700;color:{C["ink"]};margin-top:2px;">{v}</div></div>'
            for l, v in facts])
        st.markdown(f'<div style="display:grid;grid-template-columns:1fr 1fr;background:{C["paper"]};border-radius:12px;border:1px solid {C["ink08"]};overflow:hidden;margin-bottom:14px;">{cells}</div>', unsafe_allow_html=True)

    # Market pricing
    _market_prices = p.get("market_prices", [])
    if _market_prices:
        st.markdown(mlabel(_ui("Pricing")), unsafe_allow_html=True)
        _mp_rows = "".join([
            f'<div style="display:flex;justify-content:space-between;align-items:center;padding:9px 14px;background:{C["paper"] if i%2==0 else C["bg"]};">'
            f'<div style="font-family:Space Grotesk,sans-serif;font-size:13px;color:{C["ink60"]};">{mp["market"]}</div>'
            f'<div style="font-family:Space Grotesk,sans-serif;font-size:14px;font-weight:700;color:{C["ink"]};">{mp["currency"]} {float(mp["price"]):.2f}</div>'
            f'</div>'
            for i, mp in enumerate(_market_prices)
        ])
        st.markdown(f'<div style="background:{C["paper"]};border:1px solid {C["ink08"]};border-radius:12px;overflow:hidden;margin-bottom:14px;">{_mp_rows}</div>', unsafe_allow_html=True)
    elif p.get("price_rrp") and p.get("price_currency"):
        st.markdown(mlabel(_ui("Pricing")), unsafe_allow_html=True)
        st.markdown(f'<div style="font-family:Space Grotesk,sans-serif;font-size:14px;font-weight:700;color:{C["ink"]};padding:10px 14px;background:{C["paper"]};border:1px solid {C["ink08"]};border-radius:12px;margin-bottom:14px;">{p["price_currency"]} {p["price_rrp"]:.2f}</div>', unsafe_allow_html=True)

    # Ingredients
    ingredients = p.get("ingredients", [])
    allergens_raw = [a.split(" ")[0].lower() for a in p.get("allergens", [])]
    if ingredients:
        st.markdown(mlabel(_ui("Ingredients")), unsafe_allow_html=True)
        _ing_text = _t("ingredients")
        if _ing_text:
            st.markdown(f'<div style="font-family:Space Grotesk,sans-serif;font-size:14px;line-height:1.7;color:{C["ink"]};background:{C["paper"]};border-radius:12px;padding:14px;border:1px solid {C["ink08"]};margin-bottom:10px;">{_ing_text}</div>', unsafe_allow_html=True)
        else:
            parts = [f'<strong style="color:{C["ink"]};">{i}</strong>' if any(a in i.lower() for a in allergens_raw) else i for i in ingredients]
            st.markdown(f'<div style="font-family:Space Grotesk,sans-serif;font-size:14px;line-height:1.7;color:{C["ink"]};background:{C["paper"]};border-radius:12px;padding:14px;border:1px solid {C["ink08"]};margin-bottom:10px;">' + ", ".join(parts) + "</div>", unsafe_allow_html=True)

    if p.get("allergens"):
        _all_text = _t("allergens") or ", ".join(p["allergens"])
        st.markdown(f'<div style="background:#fff8f0;border-left:3px solid {C["gold"]};border-radius:0 8px 8px 0;padding:10px 14px;margin-bottom:14px;"><div style="font-family:JetBrains Mono,monospace;font-size:9px;font-weight:700;letter-spacing:0.15em;color:{C["gold"]};text-transform:uppercase;margin-bottom:3px;">{_ui("Contains Allergens")}</div><div style="font-family:Space Grotesk,sans-serif;font-size:13px;font-weight:600;color:{C["ink"]};">{_all_text}</div></div>', unsafe_allow_html=True)

    # Nutrition
    nu = p.get("nutrition", {})
    if nu and any(nu.values()):
        st.markdown(mlabel(_ui("Nutrition · per 100 mL")), unsafe_allow_html=True)
        rows = [
            (_ui("Energy"), f'{nu.get("energy_kj",0):.0f} kJ / {nu.get("energy_kcal",0):.0f} kcal', False),
            (_ui("Fat"), f'{nu.get("fat_g",0):.1f} g', False),
            (_ui("of which saturates"), f'{nu.get("saturated_fat_g",0):.1f} g', True),
            (_ui("Carbohydrate"), f'{nu.get("carbohydrate_g",0):.1f} g', False),
            (_ui("of which sugars"), f'{nu.get("sugars_g",0):.1f} g', True),
            (_ui("Protein"), f'{nu.get("protein_g",0):.1f} g', False),
            (_ui("Salt"), f'{nu.get("salt_g",0):.2f} g', False),
        ]
        rows_html = "".join([
            f'<div style="display:flex;justify-content:space-between;padding:8px 14px;background:{C["paper"] if i%2==0 else C["bg"]};{"padding-left:24px;" if sub else ""}">'
            f'<div style="font-family:Space Grotesk,sans-serif;font-size:{"12" if sub else "13"}px;color:{C["ink"]};">{label}</div>'
            f'<div style="font-family:Space Grotesk,sans-serif;font-size:{"12" if sub else "13"}px;font-weight:600;color:{C["ink"]};">{val}</div></div>'
            for i, (label, val, sub) in enumerate(rows)])
        st.markdown(f'<div style="border-radius:12px;border:1px solid {C["ink08"]};overflow:hidden;margin-bottom:14px;">{rows_html}</div>', unsafe_allow_html=True)

    # Packaging & recycling
    pkg = p.get("packaging", {})
    if pkg and any(v for v in pkg.values() if v):
        st.markdown(mlabel(_ui("Packaging & Recycling")), unsafe_allow_html=True)
        RECYCLING = {
            "Glass": ("♻️", "Recycle at glass bank"),
            "Natural cork": ("🌿", "Compost or cork recycling program"),
            "Screwcap": ("♻️", "Recycle with metals"),
            "Synthetic cork": ("🗑️", "General waste"),
            "Tin": ("♻️", "Recycle with metals"),
            "Aluminium": ("♻️", "Recycle with metals"),
            "Paper": ("♻️", "Remove label before recycling bottle"),
            "PVC": ("⚠️", "General waste — not recyclable"),
        }
        pkg_rows = []
        for key, suffix in [("bottle_material", " bottle"), ("closure_type", ""), ("label_material", " label"), ("capsule_material", " capsule")]:
            val = pkg.get(key)
            if val and val != "None":
                icon, tip = RECYCLING.get(val, ("♻️", ""))
                phrase = val + suffix
                pkg_rows.append((icon, _ui(phrase), _ui(tip)))
        if pkg.get("recycled_content_pct"):
            pct = pkg["recycled_content_pct"]
            pkg_rows.append(("🔄", f'{pct}{_ui("% recycled glass content")}', ""))
        rows_html = "".join([
            f'<div style="display:flex;align-items:center;gap:12px;padding:10px 14px;background:{C["paper"] if i%2==0 else C["bg"]};">'
            f'<div style="font-size:20px;">{icon}</div><div>'
            f'<div style="font-family:Space Grotesk,sans-serif;font-size:13px;font-weight:600;color:{C["ink"]};">{mat}</div>'
            + (f'<div style="font-family:Space Grotesk,sans-serif;font-size:12px;color:{C["ink60"]};">{tip}</div>' if tip else "")
            + '</div></div>'
            for i, (icon, mat, tip) in enumerate(pkg_rows)])
        st.markdown(f'<div style="border-radius:12px;border:1px solid {C["ink08"]};overflow:hidden;margin-bottom:10px;">{rows_html}</div>', unsafe_allow_html=True)
        if pkg.get("recycling_instructions"):
            _rec_text = _t("recycling_instructions") or pkg["recycling_instructions"]
            st.markdown(f'<div style="font-family:Space Grotesk,sans-serif;font-size:13px;color:{C["ink60"]};padding:10px 14px;background:{C["ink08"]};border-radius:10px;margin-bottom:14px;">{_rec_text}</div>', unsafe_allow_html=True)

    # Carbon
    sus = p.get("sustainability", {})
    if sus and sus.get("carbon_footprint_kg"):
        st.markdown(mlabel(_ui("Carbon Footprint")), unsafe_allow_html=True)
        st.markdown(f'<div style="display:flex;align-items:center;gap:12px;background:{C["green"]}10;border:1px solid {C["green"]}28;border-radius:12px;padding:14px;margin-bottom:14px;"><div style="font-size:28px;">🌱</div><div><div style="font-family:Space Grotesk,sans-serif;font-size:22px;font-weight:700;color:{C["green"]};">{sus["carbon_footprint_kg"]} kg CO₂e</div><div style="font-family:JetBrains Mono,monospace;font-size:9px;font-weight:700;letter-spacing:0.15em;color:{C["green"]}80;text-transform:uppercase;">per bottle · cradle to gate</div></div></div>', unsafe_allow_html=True)

    # Supply chain
    sc = p.get("supply_chain", {})
    sc_rows = [(k, v) for k, v in [("Vineyard", sc.get("vineyard_name")), ("Vineyard region", sc.get("vineyard_region")), ("Vineyard country", sc.get("vineyard_country")), ("Bottled by", sc.get("bottling_facility")), ("Bottling location", sc.get("bottling_location")), ("EU importer", sc.get("importer_name"))] if v]
    if sc_rows:
        st.markdown(mlabel(_ui("Provenance")), unsafe_allow_html=True)
        rows_html = "".join([f'<div style="display:flex;justify-content:space-between;padding:8px 14px;background:{C["paper"] if i%2==0 else C["bg"]};"><div style="font-family:Space Grotesk,sans-serif;font-size:13px;color:{C["ink60"]};">{k}</div><div style="font-family:Space Grotesk,sans-serif;font-size:13px;font-weight:600;color:{C["ink"]};">{v}</div></div>' for i, (k, v) in enumerate(sc_rows)])
        st.markdown(f'<div style="border-radius:12px;border:1px solid {C["ink08"]};overflow:hidden;margin-bottom:14px;">{rows_html}</div>', unsafe_allow_html=True)

    # Certifications
    certs = p.get("certifications", [])
    cert_docs = p.get("certificates", [])
    if certs or cert_docs:
        st.markdown(mlabel(_ui("Certifications")), unsafe_allow_html=True)
        if certs:
            chips = "".join([f'<span style="background:{C["green"]}18;color:{C["green"]};border:1px solid {C["green"]}30;border-radius:999px;padding:4px 12px;font-family:JetBrains Mono,monospace;font-size:10px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;">{c}</span>' for c in certs])
            st.markdown(f'<div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px;">{chips}</div>', unsafe_allow_html=True)
        for _di, doc in enumerate(cert_docs):
            if doc.get("data"):
                fname = doc.get("filename", "certificate.pdf")
                ext   = fname.rsplit(".", 1)[-1].lower() if "." in fname else "pdf"
                mime  = "application/vnd.openxmlformats-officedocument.wordprocessingml.document" if ext == "docx" else ("application/msword" if ext == "doc" else "application/pdf")
                _dl_key = f"dl_{doc.get('id') or _di}"
                st.download_button(f"📄 {doc.get('name','Certificate')}" + (f" — {doc['issuer']}" if doc.get("issuer") else ""), data=base64.b64decode(doc["data"]), file_name=fname, mime=mime, key=_dl_key)

    if p.get("storage_info"):
        _sto_text = _t("storage_info") or p["storage_info"]
        st.markdown(f'<div style="font-family:Space Grotesk,sans-serif;font-size:13px;color:{C["ink60"]};padding:10px 14px;background:{C["ink08"]};border-radius:10px;margin-bottom:14px;"><strong>{_ui("Storage:")}</strong> {_sto_text}</div>', unsafe_allow_html=True)

    if p.get("producer_address"):
        st.markdown(f'<div style="font-family:Space Grotesk,sans-serif;font-size:12px;color:{C["ink60"]};margin-bottom:14px;">{p.get("producer_name","")} · {p["producer_address"]}</div>', unsafe_allow_html=True)

    if p.get("pregnancy_warning"):
        st.markdown(f'<div style="display:flex;align-items:flex-start;gap:12px;background:#fff8f0;border:1px solid {C["gold"]}40;border-radius:12px;padding:14px;margin-bottom:14px;"><div style="font-size:24px;line-height:1;">🤰</div><div><div style="font-family:Space Grotesk,sans-serif;font-size:13px;font-weight:700;color:{C["ink"]};">Pregnancy warning</div><div style="font-family:Space Grotesk,sans-serif;font-size:12px;color:{C["ink60"]};margin-top:3px;">Drinking during pregnancy, even in small amounts, can harm your baby.</div></div></div>', unsafe_allow_html=True)

    if p.get("responsible_drinking"):
        st.markdown(f'<div style="font-family:Space Grotesk,sans-serif;font-size:12px;color:{C["ink60"]};text-align:center;padding:10px 14px;margin-bottom:14px;">🍷 Please drink responsibly.</div>', unsafe_allow_html=True)

    st.markdown(f'<div style="margin-top:24px;padding:14px;border-top:1px solid {C["ink08"]};text-align:center;"><div style="font-family:JetBrains Mono,monospace;font-size:9px;font-weight:700;letter-spacing:0.15em;color:{C["ink60"]};text-transform:uppercase;">VineLabel · EU e-label Reg. 2021/2117</div></div></div>', unsafe_allow_html=True)


def inject_dashboard_css():
    wine_b64 = _load_asset_b64("wine-bg.jpg")
    bg_img = f'url("data:image/jpeg;base64,{wine_b64}")' if wine_b64 else "none"
    st.markdown('<link href="https://fonts.googleapis.com/css2?family=Caveat:wght@500;600;700&family=Gloock&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">', unsafe_allow_html=True)
    st.markdown(f"""<style>
html {{
    background-image:
        linear-gradient(95deg,rgba(12,8,6,0.96) 0%,rgba(12,8,6,0.86) 38%,rgba(12,8,6,0.45) 62%,rgba(12,8,6,0.15) 82%),
        radial-gradient(ellipse at center,transparent 60%,rgba(0,0,0,0.55) 100%),
        {bg_img}!important;
    background-size:cover!important;
    background-position:center right!important;
    background-color:#1a0f08!important;
    background-repeat:no-repeat!important;
    background-attachment:fixed!important;
}}
body,[data-testid="stApp"],[data-testid="stAppViewContainer"],[data-testid="stMain"],
[data-testid="stMainBlockContainer"],.main {{
    background:none!important;
    background-color:transparent!important;
    background-image:none!important;
    box-shadow:none!important;
}}
[data-testid="stMainBlockContainer"] {{
    padding-left:0!important;
    padding-right:0!important;
    max-width:100%!important;
}}
.block-container {{
    background:none!important;
    background-color:transparent!important;
    max-width:780px!important;
    margin-left:56px!important;
    margin-right:auto!important;
    padding-top:2rem!important;
    padding-bottom:4rem!important;
}}
[data-testid="stExpander"] {{
    background:{C["paperCard"]}!important;
    border:none!important;
    border-radius:14px!important;
    box-shadow:0 12px 30px rgba(0,0,0,0.35),0 2px 6px rgba(0,0,0,0.2)!important;
    overflow:hidden!important;
}}
[data-testid="stExpander"] summary {{
    color:{C["wine"]}!important;
    font-family:'Inter',sans-serif!important;
    font-weight:600!important;
    font-size:16px!important;
}}
[data-testid="stForm"] {{
    background:{C["paperCard"]}!important;
    border:none!important;
    border-radius:10px!important;
    padding:0!important;
}}
[data-testid="stButton"] button,[data-testid="stFormSubmitButton"] button {{
    border-radius:8px!important;
}}
#MainMenu,footer,[data-testid="stHeader"],[data-testid="stToolbar"],[data-testid="stDecoration"]{{display:none!important;}}
</style>""", unsafe_allow_html=True)


# ── Dashboard ─────────────────────────────────────────────────────────────────
def _product_card(p):
    pid = p["id"]
    exp_key = f"card_{pid}"
    is_expanded = st.session_state.get(exp_key, False)
    is_pub = p.get("status") == "published"

    scol = C["green"] if is_pub else C["gold"]
    slbl = (p.get("status") or "draft").upper()
    if p.get("market_prices"):
        _price = " · " + " / ".join(f'{mp["currency"]} {float(mp["price"]):.0f}' for mp in p["market_prices"][:3])
        if len(p["market_prices"]) > 3: _price += " …"
    elif p.get("price_rrp") and p.get("price_currency"):
        _price = f' · {p["price_currency"]} {p["price_rrp"]:.2f}'
    else:
        _price = ""
    _th_ext  = (p.get("product_image_filename") or "").rsplit(".", 1)[-1].lower()
    _th_mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}.get(_th_ext, "image/jpeg")
    _thumb = (f'<img src="data:{_th_mime};base64,{p["product_image"]}" style="width:52px;height:52px;object-fit:cover;border-radius:8px;flex-shrink:0;" />'
              if p.get("product_image") else
              f'<div style="width:52px;height:52px;border-radius:8px;background:{C["wine"]}18;display:flex;align-items:center;justify-content:center;font-size:22px;flex-shrink:0;">🍷</div>')

    # Product info + toggle row
    info_col, ctrl_col = st.columns([0.68, 0.32])
    with info_col:
        st.markdown(
            f'<div style="display:flex;align-items:flex-start;gap:12px;">'
            f'{_thumb}'
            f'<div style="flex:1;min-width:0;">'
            f'<div style="font-family:Gloock,serif;font-size:20px;font-weight:600;color:{C["ink"]};line-height:1.2;letter-spacing:-0.01em;">{p["name"]} {p.get("vintage","")}</div>'
            f'<div style="font-family:Inter,sans-serif;font-size:13px;color:{C["ink2"]};margin-top:3px;">{p.get("variety","")} · {p.get("region","")}{_price}</div>'
            f'</div></div>',
            unsafe_allow_html=True
        )
    with ctrl_col:
        btn_col, badge_col = st.columns([0.52, 0.48])
        with btn_col:
            if st.button("▴ Close" if is_expanded else "▾ Actions", key=f"toggle_{pid}", use_container_width=True, type="secondary"):
                st.session_state[exp_key] = not is_expanded
                st.rerun()
        with badge_col:
            st.markdown(
                f'<div style="text-align:right;padding-top:8px;">'
                f'<span style="font-family:Inter,sans-serif;font-size:9px;font-weight:700;letter-spacing:0.12em;'
                f'color:{scol};border:1px solid {scol}40;border-radius:999px;padding:3px 9px;white-space:nowrap;">{slbl}</span>'
                f'</div>',
                unsafe_allow_html=True
            )

    # Action buttons — shown when expanded
    if is_expanded:
        st.markdown(f'<div style="border-top:1px solid {C["paperEdge"]};margin:6px 0;"></div>', unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("Edit", key=f"edit_{pid}", use_container_width=True):
                st.query_params.update({"page": "edit", "id": pid}); st.rerun()
        with c2:
            if st.button("QR Code", key=f"qr_{pid}", use_container_width=True):
                st.query_params.update({"page": "qr", "id": pid}); st.rerun()
        with c3:
            if st.button("Unpublish" if is_pub else "Publish", key=f"pub_{pid}", use_container_width=True, type="primary"):
                cur = get_product(pid)
                if cur:
                    cur["status"] = "draft" if is_pub else "published"
                    upsert_product(cur)
                st.rerun()

    st.markdown('<div style="height:8px;"></div>', unsafe_allow_html=True)


def _group_header(name, group_products):
    total     = len(group_products)
    pub_count = sum(1 for p in group_products if p.get("status") == "published")
    scores    = [compliance_score(p) for p in group_products]
    fully_compliant = sum(
        1 for s in scores
        if all(d["score"] == d["total"] for d in s.values())
    )
    meta = f'{total} product{"s" if total != 1 else ""} · {pub_count} published · {fully_compliant} fully compliant'
    return (
        f'<div style="display:flex;align-items:baseline;justify-content:space-between;margin-bottom:2px;">'
        f'<span style="font-family:Space Grotesk,sans-serif;font-size:16px;font-weight:700;color:{C["ink"]};">{name}</span>'
        f'<span style="font-family:JetBrains Mono,monospace;font-size:9px;font-weight:700;letter-spacing:0.12em;'
        f'color:{C["ink60"]};text-transform:uppercase;">{meta}</span>'
        f'</div>'
    )


def show_dashboard():
    from collections import defaultdict

    # Single white card containing all dashboard content
    st.markdown(f"""<style>
.block-container {{
    background:{C["paper"]}!important;
    border-radius:18px!important;
    box-shadow:0 12px 40px rgba(0,0,0,0.4),0 2px 8px rgba(0,0,0,0.25)!important;
    padding:0.25rem 2rem 3rem!important;
    margin-top:2rem!important;
    max-width:780px!important;
}}
.block-container > div:first-child {{ margin-top:0!important; padding-top:0!important; }}
</style>""", unsafe_allow_html=True)

    products  = load_products()
    published = sum(1 for p in products if p.get("status") == "published")
    drafts    = len(products) - published

    winery = st.session_state.get("winery_name", "")
    st.markdown(
        f'<div style="display:flex;align-items:baseline;justify-content:space-between;margin-bottom:22px;padding-top:4px;">'
        f'<h1 style="font-family:Gloock,serif;font-size:36px;line-height:1.1;margin:0;color:{C["ink"]};letter-spacing:-0.005em;">Your products</h1>'
        + (f'<span style="font-family:Caveat,cursive;color:{C["gold"]};font-size:22px;">welcome back, {winery}</span>' if winery else '')
        + f'</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        f'<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px;margin-bottom:18px;">'
        f'<div style="background:{C["paperCard"]};border-radius:14px;padding:22px 18px 18px;text-align:center;box-shadow:0 2px 8px rgba(0,0,0,0.08);"><div style="font-family:Gloock,serif;font-size:56px;line-height:1;color:{C["wine"]};margin-bottom:10px;">{len(products)}</div><div style="font-family:Inter,sans-serif;font-size:11px;font-weight:600;letter-spacing:0.32em;color:{C["mutedDark"]};text-transform:uppercase;">Products</div></div>'
        f'<div style="background:{C["paperCard"]};border-radius:14px;padding:22px 18px 18px;text-align:center;box-shadow:0 2px 8px rgba(0,0,0,0.08);"><div style="font-family:Gloock,serif;font-size:56px;line-height:1;color:{C["green"]};margin-bottom:10px;">{published}</div><div style="font-family:Inter,sans-serif;font-size:11px;font-weight:600;letter-spacing:0.32em;color:{C["mutedDark"]};text-transform:uppercase;">Published</div></div>'
        f'<div style="background:{C["paperCard"]};border-radius:14px;padding:22px 18px 18px;text-align:center;box-shadow:0 2px 8px rgba(0,0,0,0.08);"><div style="font-family:Gloock,serif;font-size:56px;line-height:1;color:{C["inkSoft"]};margin-bottom:10px;">{drafts}</div><div style="font-family:Inter,sans-serif;font-size:11px;font-weight:600;letter-spacing:0.32em;color:{C["mutedDark"]};text-transform:uppercase;">Drafts</div></div>'
        f'</div>',
        unsafe_allow_html=True
    )

    if products:
        # Group by collection — named groups alphabetically, Uncategorised last
        groups = defaultdict(list)
        for p in products:
            key = (p.get("collection") or "").strip() or "Uncategorised"
            groups[key].append(p)
        sorted_groups = [(k, groups[k]) for k in sorted(groups) if k != "Uncategorised"]
        if "Uncategorised" in groups:
            sorted_groups.append(("Uncategorised", groups["Uncategorised"]))

        for group_name, group_products in sorted_groups:
            header_html = _group_header(group_name, group_products)
            exp_key = f"grp_{group_name}"
            with st.expander(group_name, expanded=st.session_state.get(exp_key, True)):
                st.markdown(header_html, unsafe_allow_html=True)
                st.markdown(f'<div style="height:8px;"></div>', unsafe_allow_html=True)
                for p in group_products:
                    _product_card(p)
    else:
        st.markdown(
            f'<div style="background:{C["paper"]};border:1px solid {C["paperEdge"]};border-radius:14px;'
            f'box-shadow:0 1px 0 rgba(255,255,255,0.6) inset,0 18px 38px -16px rgba(0,0,0,0.45);'
            f'text-align:center;padding:48px 20px;">'
            f'<div style="font-size:44px;margin-bottom:14px;">🍷</div>'
            f'<div style="font-family:Gloock,serif;font-size:20px;font-weight:600;color:{C["ink"]};">No products yet</div>'
            f'<div style="font-family:Inter,sans-serif;font-size:14px;color:{C["ink2"]};margin-top:6px;">Add your first wine to generate an EU-compliant digital label.</div>'
            f'</div>',
            unsafe_allow_html=True
        )

    if st.button("+ New Product", type="primary", use_container_width=True):
        st.query_params["page"] = "add"; st.rerun()

    st.markdown('<div style="height:8px;"></div>', unsafe_allow_html=True)

    settings = load_settings()
    if not settings.get("producer_name"):
        st.markdown(
            f'<div style="background:{C["goldSoft"]};border:1px solid {C["gold"]}40;border-radius:12px;'
            f'padding:14px 18px;margin-bottom:16px;display:flex;align-items:center;gap:14px;">'
            f'<div style="font-size:20px;">👋</div>'
            f'<div><div style="font-family:Inter,sans-serif;font-size:14px;font-weight:600;color:{C["ink"]};">Set up your winery profile</div>'
            f'<div style="font-family:Inter,sans-serif;font-size:13px;color:{C["ink2"]};margin-top:2px;">'
            f'Add your details once — they\'ll pre-fill every new label automatically.</div></div></div>',
            unsafe_allow_html=True
        )

    with st.expander("⚙️ Winery Profile & Settings"):
        with st.form("winery_profile_form"):
            st.markdown(mlabel("Winery Details"), unsafe_allow_html=True)
            prof_name    = st.text_input("Winery / producer name", value=settings.get("producer_name", ""), placeholder="e.g. Penfolds")
            prof_address = st.text_input("Producer address", value=settings.get("producer_address", ""), placeholder="30 Tanunda Road, Nuriootpa SA 5355")
            pc1, pc2 = st.columns(2)
            with pc1: prof_country = st.text_input("Country", value=settings.get("country", "Australia"))
            with pc2: prof_website = st.text_input("Website", value=settings.get("website", ""), placeholder="https://www.winery.com.au")

            st.markdown(mlabel("Default Packaging"), unsafe_allow_html=True)
            st.markdown(f'<div style="font-family:Inter,sans-serif;font-size:12px;color:{C["ink2"]};margin-bottom:8px;">Pre-fills new products — override per wine if needed.</div>', unsafe_allow_html=True)
            dp = settings.get("default_packaging", {})
            dp1, dp2 = st.columns(2)
            with dp1:
                prof_bottle    = st.selectbox("Bottle material", BOTTLE_MATERIALS, index=BOTTLE_MATERIALS.index(dp.get("bottle_material", "Glass")) if dp.get("bottle_material") in BOTTLE_MATERIALS else 0)
                prof_label_mat = st.selectbox("Label material",  LABEL_MATERIALS,  index=LABEL_MATERIALS.index(dp.get("label_material", "Paper"))  if dp.get("label_material")  in LABEL_MATERIALS  else 0)
            with dp2:
                prof_closure = st.selectbox("Closure type",     CLOSURE_TYPES,     index=CLOSURE_TYPES.index(dp.get("closure_type", "Natural cork"))   if dp.get("closure_type")   in CLOSURE_TYPES   else 0)
                prof_capsule = st.selectbox("Capsule material", CAPSULE_MATERIALS, index=CAPSULE_MATERIALS.index(dp.get("capsule_material", "Tin")) if dp.get("capsule_material") in CAPSULE_MATERIALS else 0)

            st.markdown(mlabel("EU Importer"), unsafe_allow_html=True)
            prof_imp_name = st.text_input("EU importer name",    value=settings.get("eu_importer_name", ""),    placeholder="e.g. Wine Imports GmbH")
            prof_imp_addr = st.text_input("EU importer address", value=settings.get("eu_importer_address", ""), placeholder="Weinstraße 12, 10115 Berlin, Germany")

            st.markdown(mlabel("App Settings"), unsafe_allow_html=True)
            current_url = st.session_state.get("base_url") or settings.get("base_url", "")
            prof_url = st.text_input("Published app URL", value=current_url, placeholder="https://vinelabel-app.streamlit.app", help="QR codes link to this URL")

            if st.form_submit_button("Save Profile", type="primary", use_container_width=True):
                s = load_settings()
                s["producer_name"]     = prof_name.strip()
                s["producer_address"]  = prof_address.strip()
                s["country"]           = prof_country.strip()
                s["website"]           = prof_website.strip()
                s["default_packaging"] = {
                    "bottle_material":  prof_bottle,
                    "closure_type":     prof_closure,
                    "capsule_material": prof_capsule,
                    "label_material":   prof_label_mat,
                }
                s["eu_importer_name"]    = prof_imp_name.strip()
                s["eu_importer_address"] = prof_imp_addr.strip()
                url_clean = (prof_url or "").rstrip("/")
                s["base_url"] = url_clean
                st.session_state["base_url"] = url_clean
                save_settings(s)
                st.success("Profile saved.")
                st.rerun()


# ── Product form ──────────────────────────────────────────────────────────────
COMMON_INGREDIENTS = ["Grapes", "Concentrated grape must", "Sulfur dioxide (E220)", "Potassium metabisulphite (E224)", "Yeast", "Tartaric acid (E334)", "Bentonite", "Metatartaric acid (E353)"]
COMMON_ALLERGENS   = ["Sulphites", "Egg (albumin fining agent)", "Milk (casein fining agent)", "Fish (isinglass fining agent)"]
FINING_AGENTS      = ["Egg albumin (ovalbumin)", "Casein (milk protein)", "Isinglass (fish)", "Gelatin (animal)", "Bentonite (clay — allergen-free)", "Activated charcoal", "Silica gel", "Kaolin"]
SWEETNESS_DESCRIPTORS = ["— Not specified —", "Dry", "Medium-dry", "Medium-sweet", "Sweet"]
TRADITIONAL_TERMS  = ["— None —", "Chateau", "Cru", "Grand Cru", "Premier Cru", "Reserva", "Riserva", "Classico", "Superiore", "Vintage", "Late Harvest", "Noble Late Harvest", "Tawny", "Ruby", "Colheita"]
COMMON_CERTS       = ["Organic", "Biodynamic", "Vegan", "Vegetarian", "Sustainable"]
BOTTLE_MATERIALS   = ["Glass", "PET plastic", "Other"]
CLOSURE_TYPES      = ["Natural cork", "Screwcap", "Synthetic cork", "Crown cap", "Glass stopper"]
LABEL_MATERIALS    = ["Paper", "Plastic (PP)", "None"]
CAPSULE_MATERIALS  = ["Tin", "Aluminium", "PVC", "Wax", "None"]
PRODUCT_CATEGORIES = ["Wine", "Sparkling Wine", "Rosé", "Dessert Wine", "Fortified Wine", "De-alcoholized Wine", "Other"]
SPARKLING_DOSAGE   = ["Brut Nature (0–3 g/L)", "Extra Brut (0–6 g/L)", "Brut (0–12 g/L)", "Extra Dry (12–17 g/L)", "Dry (17–32 g/L)", "Semi-Sweet (32–50 g/L)", "Sweet (>50 g/L)"]
PHYSICAL_LABEL_FIELDS = ["Wine name", "Net quantity", "ABV %", "Lot number", "Producer name & address", "Country of origin", "PDO / PGI designation", "Sweetness descriptor", "Sparkling dosage", "Importer name & address"]


def show_product_form(existing=None):
    p  = existing or {}
    _s = {} if existing else load_settings()
    _dp = _s.get("default_packaging", {})

    # Wrap everything in a single paper-white card on the wine-photo background
    st.markdown(f"""<style>
[data-testid="stMainBlockContainer"] {{
    padding-left:0!important;
    padding-right:0!important;
    max-width:100%!important;
}}
.block-container {{
    background:{C["paper"]}!important;
    border-radius:18px!important;
    box-shadow:0 12px 40px rgba(0,0,0,0.4),0 2px 8px rgba(0,0,0,0.25)!important;
    padding:0.25rem 2rem 3rem!important;
    margin-top:2rem!important;
    margin-left:56px!important;
    margin-right:auto!important;
    max-width:780px!important;
}}
.block-container > div:first-child {{ margin-top:0!important; padding-top:0!important; }}
/* Back button and top-level secondary buttons: dark ink on white */
.block-container > div > div > div [data-testid="stBaseButton-secondary"],
.block-container > div > div > div [data-testid="stBaseButton-secondary"] button {{
    background:transparent!important;
    border:1px solid {C["paperEdge"]}!important;
    color:{C["ink"]}!important;
}}
.block-container > div > div > div [data-testid="stBaseButton-secondary"] p {{
    color:{C["ink"]}!important;
}}
</style>""", unsafe_allow_html=True)

    st.markdown('<div class="edit-page-marker" style="display:none;"></div>', unsafe_allow_html=True)
    bc, tc = st.columns([0.12, 0.88])
    with bc:
        if st.button("←", type="secondary"):
            st.query_params["page"] = "dashboard"; st.rerun()
    with tc:
        _heading = (p.get("name") or "Edit Product") if existing else "New Product"
        st.markdown(f'<div style="font-family:Gloock,serif;font-size:26px;font-weight:600;color:{C["ink"]};padding:6px 0;letter-spacing:-0.01em;">{_heading}</div>', unsafe_allow_html=True)

    _form_errors = st.session_state.pop("_form_errors", [])
    if _form_errors:
        fields = " and ".join(f"**{f}**" for f in _form_errors)
        st.error(f"Please fill in the required fields: {fields}", icon="⚠️")
        _highlight_css = "".join(
            f'input[aria-label="{lbl}"] {{ border: 2px solid #e53e3e !important; background: #fff5f5 !important; border-radius: 6px !important; }}'
            for lbl in (["Wine name *"] if "Wine name" in _form_errors else [])
                     + (["Winery / producer *"] if "Winery / producer" in _form_errors else [])
        )
        if _highlight_css:
            st.markdown(f"<style>{_highlight_css}</style>", unsafe_allow_html=True)

    if not existing:
        st.markdown(f'<div style="background:rgba(200,154,90,0.1);border:1px solid rgba(200,154,90,0.35);border-radius:8px;padding:10px 14px;margin:4px 0 12px;font-size:13px;color:#7a5a1a;">Fill in the details below and click <b>Save Product</b> — then EU language translation will unlock automatically.</div>', unsafe_allow_html=True)

    if existing:
        with st.expander("Compliance status"):
            scores = compliance_score(existing)
            for section, d in scores.items():
                pct = int(d["score"] / d["total"] * 100) if d["total"] else 0
                col = d["color"] if pct == 100 else (C["gold"] if pct >= 60 else C["red"])
                missing_str = (", ".join(d["failed"][:3]) + ("…" if len(d["failed"]) > 3 else "")) if d["failed"] else ""
                st.markdown(
                    f'<div style="margin-bottom:10px;">'
                    f'<div style="display:flex;justify-content:space-between;margin-bottom:3px;">'
                    f'<span style="font-family:JetBrains Mono,monospace;font-size:10px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:{col};">{section} — {d["reg"]}</span>'
                    f'<span style="font-family:JetBrains Mono,monospace;font-size:10px;font-weight:700;color:{col};">{d["score"]}/{d["total"]}</span></div>'
                    f'<div style="background:{C["ink12"]};border-radius:4px;height:4px;overflow:hidden;"><div style="background:{col};width:{pct}%;height:100%;border-radius:4px;"></div></div>'
                    + (f'<div style="font-family:Space Grotesk,sans-serif;font-size:11px;color:{C["ink60"]};margin-top:3px;">Missing: {missing_str}</div>' if missing_str else "")
                    + '</div>', unsafe_allow_html=True)

        # Translation — language selector
        LANG_OPTIONS = {
            "German (DE)":  "de",
            "French (FR)":  "fr",
            "Italian (IT)": "it",
            "Spanish (ES)": "es",
            "All 4 languages": "all",
        }
        existing_langs = existing.get("translations", {})
        done_labels = [k for k, v in LANG_OPTIONS.items() if v != "all" and v in existing_langs]

        st.markdown(f'<div style="font-size:13px;font-weight:600;color:{C["ink"]};margin:6px 0 2px;">🌐 EU Language Translation</div>', unsafe_allow_html=True)
        st.markdown(f'<div style="font-size:12px;color:{C["ink2"]};margin-bottom:8px;">Choose a language — this will update the text shown on your consumer label for that language.</div>', unsafe_allow_html=True)

        if done_labels:
            st.success(f"Already translated: {', '.join(done_labels)}", icon="✅")

        # Check what fields can actually be translated
        _can_translate = any([
            existing.get("ingredients"),
            existing.get("allergens"),
            existing.get("packaging", {}).get("recycling_instructions"),
            existing.get("storage_info"),
        ])

        if not ANTHROPIC_AVAILABLE or not _get_api_key():
            st.info("🔑 Add your Anthropic API key to `.streamlit/secrets.toml` to enable translation.", icon="ℹ️")
        elif not _can_translate:
            st.warning("Fill in Ingredients, Allergens, or Storage info first — those are the fields that get translated onto the consumer label.", icon="ℹ️")
        else:
            t_col1, t_col2 = st.columns([2, 1])
            with t_col1:
                chosen_label = st.selectbox("Select language", list(LANG_OPTIONS.keys()), key="lang_select", label_visibility="collapsed")
            with t_col2:
                if st.button("Translate →", key="translate_top_btn", type="primary", use_container_width=True):
                    lang_code = LANG_OPTIONS[chosen_label]
                    langs = ("de","fr","it","es") if lang_code == "all" else (lang_code,)
                    with st.spinner(f"Translating to {chosen_label}…"):
                        cur = get_product(existing["id"])
                        new_translations, _err = ai_translate_label(cur, languages=langs)
                    # Check that at least one language got real content
                    has_content = any(bool(v) for v in new_translations.values())
                    if has_content:
                        cur.setdefault("translations", {}).update(new_translations)
                        upsert_product(cur)
                        st.success(f"✅ Label updated in {chosen_label}. Click 'View Label' below to see it.")
                        st.rerun()
                    else:
                        st.error(f"Translation failed: {_err or 'Empty response from API.'}")

    if existing:
        st.markdown('<div style="height:4px;"></div>', unsafe_allow_html=True)
        if st.button("👁 View Label", key="view_label_btn", use_container_width=True):
            st.query_params.update({"label": existing["id"], "preview": "1"}); st.rerun()
        st.markdown('<div style="height:8px;"></div>', unsafe_allow_html=True)


    # ── 1 · Product Identity ──────────────────────────────────────────────
    with st.expander("1 · Product Identity", expanded=False):
        c1, c2 = st.columns([3, 1])
        with c1: name = st.text_input("Wine name *", value=p.get("name", ""), placeholder="e.g. Barossa Valley Shiraz")
        with c2: vintage = st.text_input("Vintage", value=str(p.get("vintage", "")), placeholder="2022")
        pc1, pc2 = st.columns(2)
        with pc1:
            product_category = st.selectbox("Product category *", PRODUCT_CATEGORIES, index=PRODUCT_CATEGORIES.index(p.get("product_category", "Wine")) if p.get("product_category") in PRODUCT_CATEGORIES else 0, help="Required by EU Reg. 2021/2117")
        with pc2:
            _trad_saved = p.get("traditional_term", "— None —")
            _trad_idx = TRADITIONAL_TERMS.index(_trad_saved) if _trad_saved in TRADITIONAL_TERMS else 0
            traditional_term = st.selectbox("Traditional term", TRADITIONAL_TERMS, index=_trad_idx, help="Regulated terms under EU Reg. 2019/33 — only use if legally entitled")
        c3, c4 = st.columns(2)
        with c3: variety = st.text_input("Grape variety", value=p.get("variety", ""), placeholder="Shiraz, Grenache")
        with c4: region = st.text_input("Region / appellation", value=p.get("region", ""), placeholder="Barossa Valley")
        pdo_pgi = st.text_input("PDO / PGI designation", value=p.get("pdo_pgi", ""), placeholder="e.g. Barossa Valley GI · Protected Geographical Indication", help="Required if claimed on physical label")
        c5, c6 = st.columns(2)
        with c5: producer_name = st.text_input("Winery / producer *", value=p.get("producer_name") or _s.get("producer_name", ""), placeholder="e.g. Penfolds")
        with c6: country = st.text_input("Country of origin", value=p.get("country") or _s.get("country", "Australia"))
        producer_address = st.text_input("Producer address", value=p.get("producer_address") or _s.get("producer_address", ""), placeholder="Street, City, State, Postcode")
        existing_collections = sorted({
            prod.get("collection","").strip()
            for prod in load_products()
            if prod.get("collection","").strip() and prod["id"] != p.get("id","")
        })
        curr_collection = (p.get("collection") or "").strip()
        if existing_collections:
            UNCATEGORISED = "— Uncategorised —"
            NEW_OPT       = "+ New collection"
            options       = [UNCATEGORISED] + existing_collections + [NEW_OPT]
            if curr_collection in existing_collections:
                default_idx = options.index(curr_collection)
            elif curr_collection:
                default_idx = len(options) - 1
            else:
                default_idx = 0
            coll_select = st.selectbox("Range / Collection", options, index=default_idx)
            if coll_select == NEW_OPT:
                collection = st.text_input("New collection name", value=curr_collection if curr_collection not in existing_collections else "", placeholder="e.g. Reserve Range")
            elif coll_select == UNCATEGORISED:
                collection = ""
            else:
                collection = coll_select
        else:
            collection = st.text_input("Range / Collection", value=curr_collection, placeholder="e.g. Reserve Range · Single Vineyard · Classic Series", help="Groups products together on the dashboard.")

    # ── 2 · Label Basics ──────────────────────────────────────────────────
    with st.expander("2 · Label Basics", expanded=False):
        c7, c8, c9 = st.columns(3)
        with c7: abv = st.number_input("ABV %", min_value=0.0, max_value=100.0, value=float(p.get("abv", 13.5)), step=0.1, format="%.1f")
        with c8: net_quantity = st.text_input("Net quantity", value=p.get("net_quantity", "750 mL"))
        with c9: lot_number = st.text_input("Lot number", value=p.get("lot_number", ""), placeholder="L2022-001", help="Must be preceded by 'L' under EU Directive 89/396/EEC")
        lb1, lb2 = st.columns(2)
        with lb1:
            _sw_saved = p.get("sweetness_descriptor", "— Not specified —")
            _sw_idx = SWEETNESS_DESCRIPTORS.index(_sw_saved) if _sw_saved in SWEETNESS_DESCRIPTORS else 0
            sweetness_descriptor = st.selectbox("Sweetness descriptor (still wines)", SWEETNESS_DESCRIPTORS, index=_sw_idx, help="Dry / Medium-dry / Medium-sweet / Sweet — EU Reg. 2019/33")
        with lb2:
            _dosage_opts = ["— Not applicable —"] + SPARKLING_DOSAGE
            sparkling_dosage = st.selectbox("Sparkling wine dosage", _dosage_opts, index=_dosage_opts.index(p.get("sparkling_dosage", "— Not applicable —")) if p.get("sparkling_dosage") in _dosage_opts else 0, help="Mandatory for sparkling wines — EU Reg. 2021/2117")
        _bbd_raw = p.get("best_before_date")
        _bbd_val = None
        if _bbd_raw:
            try: _bbd_val = date.fromisoformat(_bbd_raw)
            except (ValueError, TypeError): pass
        best_before_date = st.date_input("Best before date", value=_bbd_val, min_value=date(2020, 1, 1), max_value=date(2040, 12, 31), format="DD/MM/YYYY", help="Mandatory for de-alcoholised wines. Leave blank for standard wines.")

    # ── 3 · Ingredients & Allergens ───────────────────────────────────────
    with st.expander("3 · Ingredients & Allergens", expanded=False):
        existing_ings = p.get("ingredients", ["Grapes", "Sulfur dioxide (E220)", "Yeast"])
        selected_common = st.multiselect("Common wine ingredients", COMMON_INGREDIENTS, default=[i for i in existing_ings if i in COMMON_INGREDIENTS])
        custom_ings = st.text_area("Additional ingredients (one per line)", value="\n".join(i for i in existing_ings if i not in COMMON_INGREDIENTS), placeholder="Potassium sorbate (E202)\nAscorbic acid (E300)", height=60)
        st.markdown(f'<div style="font-size:12px;font-weight:600;color:{C["ink"]};margin:10px 0 4px;">Fining Agents</div>', unsafe_allow_html=True)
        st.markdown(f'<div style="font-size:12px;color:{C["ink2"]};margin-bottom:6px;">Egg, milk and fish fining agents must be declared as allergens under EU Reg. 1169/2011.</div>', unsafe_allow_html=True)
        existing_fining = p.get("fining_agents", [])
        selected_fining = st.multiselect("Fining agents used", FINING_AGENTS, default=[f for f in existing_fining if f in FINING_AGENTS])
        st.markdown(f'<div style="font-size:12px;font-weight:600;color:{C["ink"]};margin:10px 0 4px;">Allergen Declarations</div>', unsafe_allow_html=True)
        existing_allergens = p.get("allergens", ["Sulphites"])
        selected_allergens = st.multiselect("Declared allergens", COMMON_ALLERGENS, default=[a for a in existing_allergens if a in COMMON_ALLERGENS])
        so2_col1, so2_col2 = st.columns([1, 2])
        with so2_col1:
            so2_level = st.number_input("SO₂ level (mg/L)", min_value=0, max_value=400, value=int(p.get("so2_level") or 0), step=1, help="Must declare 'Contains sulphites' if >10 mg/L — EU Reg. 1169/2011")
        with so2_col2:
            if so2_level > 10:
                st.markdown(f'<div style="margin-top:28px;font-size:12px;color:{C["wine"]};font-weight:600;">⚠ Must declare sulphites on label (>10 mg/L)</div>', unsafe_allow_html=True)
            elif so2_level > 0:
                st.markdown(f'<div style="margin-top:28px;font-size:12px;color:{C["green"]};">✓ Below declaration threshold</div>', unsafe_allow_html=True)

    # ── 4 · Nutrition (per 100 mL) ────────────────────────────────────────
    with st.expander("4 · Nutrition (per 100 mL)", expanded=False):
        st.markdown(f'<div style="font-size:12px;color:{C["ink2"]};margin-bottom:8px;">Dry wine ≈ 70 kcal / 293 kJ per 100 mL.</div>', unsafe_allow_html=True)
        auto_calc_energy = st.checkbox("Auto-calculate energy from ABV & carbohydrates (EU formula)", value=p.get("auto_calc_energy", False), help="Energy (kJ) = (ABV% × 0.789 × 29) + (carbs × 17) + (protein × 17) + (fat × 37)")
        nu = p.get("nutrition", {})
        n1, n2 = st.columns(2)
        with n1:
            energy_kj   = st.number_input("Energy (kJ)",     value=float(nu.get("energy_kj", 293)), step=1.0)
            fat_g       = st.number_input("Fat (g)",          value=float(nu.get("fat_g", 0.0)), step=0.1, format="%.1f")
            carb_g      = st.number_input("Carbohydrate (g)", value=float(nu.get("carbohydrate_g", 2.6)), step=0.1, format="%.1f")
            protein_g   = st.number_input("Protein (g)",      value=float(nu.get("protein_g", 0.1)), step=0.1, format="%.1f")
        with n2:
            energy_kcal = st.number_input("Energy (kcal)",    value=float(nu.get("energy_kcal", 70)), step=1.0)
            sat_fat_g   = st.number_input("Sat. fat (g)",     value=float(nu.get("saturated_fat_g", 0.0)), step=0.1, format="%.1f")
            sugars_g    = st.number_input("Sugars (g)",       value=float(nu.get("sugars_g", 1.8)), step=0.1, format="%.1f")
            salt_g      = st.number_input("Salt (g)",         value=float(nu.get("salt_g", 0.02)), step=0.01, format="%.2f")

    # ── 5 · Packaging & Recycling ─────────────────────────────────────────
    with st.expander("5 · Packaging & Recycling", expanded=False):
        st.markdown(f'<div style="font-size:12px;color:{C["ink2"]};margin-bottom:8px;">Required for DPP packaging compliance (PPWR 2025).</div>', unsafe_allow_html=True)
        pkg = p.get("packaging", {})
        _bot_def = pkg.get("bottle_material")  or _dp.get("bottle_material",  "Glass")
        _clo_def = pkg.get("closure_type")     or _dp.get("closure_type",     "Natural cork")
        _lbl_def = pkg.get("label_material")   or _dp.get("label_material",   "Paper")
        _cap_def = pkg.get("capsule_material") or _dp.get("capsule_material", "Tin")
        pa1, pa2 = st.columns(2)
        with pa1:
            bottle_material = st.selectbox("Bottle material", BOTTLE_MATERIALS, index=BOTTLE_MATERIALS.index(_bot_def) if _bot_def in BOTTLE_MATERIALS else 0)
            label_material  = st.selectbox("Label material",  LABEL_MATERIALS,  index=LABEL_MATERIALS.index(_lbl_def)  if _lbl_def  in LABEL_MATERIALS  else 0)
        with pa2:
            closure_type     = st.selectbox("Closure type",     CLOSURE_TYPES,     index=CLOSURE_TYPES.index(_clo_def)     if _clo_def     in CLOSURE_TYPES     else 0)
            capsule_material = st.selectbox("Capsule material", CAPSULE_MATERIALS, index=CAPSULE_MATERIALS.index(_cap_def) if _cap_def in CAPSULE_MATERIALS else 0)
        recycled_pct = st.number_input("Recycled glass content %", min_value=0, max_value=100, value=int(pkg.get("recycled_content_pct") or 0), step=1)
        recycling_instructions = st.text_area("Recycling instructions", value=pkg.get("recycling_instructions", ""), placeholder="Rinse bottle before recycling at glass bank. Remove cork and recycle separately.", height=60)

    # ── 6 · Supply Chain & Provenance ─────────────────────────────────────
    with st.expander("6 · Supply Chain & Provenance", expanded=False):
        sc = p.get("supply_chain", {})
        sc1, sc2 = st.columns(2)
        with sc1:
            vineyard_name       = st.text_input("Vineyard name",           value=sc.get("vineyard_name", ""),           placeholder="e.g. Block 42 Estate")
            vineyard_region     = st.text_input("Vineyard region",          value=sc.get("vineyard_region", ""),         placeholder="e.g. Barossa Valley, SA")
            vineyard_country    = st.text_input("Vineyard country",         value=sc.get("vineyard_country", "Australia"))
            grape_origin_country = st.text_input("Country of grape origin", value=sc.get("grape_origin_country", ""),   placeholder="If different from vineyard country", help="State separately if grapes sourced from multiple EU countries")
        with sc2:
            bottling_facility   = st.text_input("Bottled by (name)",        value=sc.get("bottling_facility", ""),       placeholder="e.g. Penfolds Magill Estate")
            bottling_location   = st.text_input("Bottling address",         value=sc.get("bottling_location", ""),       placeholder="e.g. Nuriootpa SA 5355, Australia", help="Required if different from producer address")
            importer_name       = st.text_input("EU importer name",         value=sc.get("importer_name") or _s.get("eu_importer_name", ""),    placeholder="Required for EU sales")
            importer_address    = st.text_input("EU importer address",      value=sc.get("importer_address") or _s.get("eu_importer_address", ""), placeholder="Street, City, Country")

    # ── 7 · Carbon & Sustainability ───────────────────────────────────────
    with st.expander("7 · Carbon & Sustainability", expanded=False):
        st.markdown(f'<div style="font-size:12px;color:{C["ink2"]};margin-bottom:8px;">Optional now — required under ESPR 2026. Leave at 0 if not yet measured.</div>', unsafe_allow_html=True)
        sus = p.get("sustainability", {})
        s1, s2 = st.columns(2)
        with s1: carbon_footprint = st.number_input("Carbon footprint (kg CO₂e / bottle)", min_value=0.0, value=float(sus.get("carbon_footprint_kg") or 0.0), step=0.01, format="%.2f")
        with s2: water_usage = st.number_input("Water usage (L / bottle)", min_value=0.0, value=float(sus.get("water_usage_l") or 0.0), step=0.1, format="%.1f")
        renewable_energy = st.checkbox("Produced using renewable energy", value=sus.get("renewable_energy", False))

    # ── 8 · Certifications ────────────────────────────────────────────────
    with st.expander("8 · Certifications", expanded=False):
        selected_certs = st.multiselect("Certification badges", COMMON_CERTS, default=[c for c in COMMON_CERTS if c in p.get("certifications", [])])
        custom_certs   = st.text_input("Other certifications (comma-separated)", value=", ".join(c for c in p.get("certifications", []) if c not in COMMON_CERTS))

    # ── 9 · Compliance & Warnings ─────────────────────────────────────────
    with st.expander("9 · Compliance & Warnings", expanded=False):
        st.markdown(f'<div style="font-size:12px;font-weight:600;color:{C["ink"]};margin-bottom:4px;">Physical Bottle Label</div>', unsafe_allow_html=True)
        st.markdown(f'<div style="font-size:12px;color:{C["ink2"]};margin-bottom:8px;">EU Reg. 2021/2117 requires certain fields on the physical label — not just the e-label. Tick what appears on your printed label.</div>', unsafe_allow_html=True)
        _saved_physical = p.get("physical_label_fields", [])
        physical_label_fields = st.multiselect("Fields present on physical bottle label", PHYSICAL_LABEL_FIELDS, default=[f for f in _saved_physical if f in PHYSICAL_LABEL_FIELDS])
        st.markdown(f'<div style="font-size:12px;font-weight:600;color:{C["ink"]};margin:12px 0 4px;">Health & Responsible Drinking</div>', unsafe_allow_html=True)
        w1, w2 = st.columns(2)
        with w1: pregnancy_warning    = st.checkbox("Include pregnancy warning",         value=p.get("pregnancy_warning", False),    help="Recommended for EU market — becoming mandatory in several member states")
        with w2: responsible_drinking = st.checkbox("Include responsible drinking statement", value=p.get("responsible_drinking", False), help="'Drink responsibly' — voluntary but strongly recommended")

    # ── 10 · Optional ─────────────────────────────────────────────────────
    _rm_price = {}
    with st.expander("10 · Optional", expanded=False):
        storage_info = st.text_input("Storage information", value=p.get("storage_info", ""), placeholder="Store in a cool, dark place. Serve at 16–18°C.")
        website      = st.text_input("Producer website", value=p.get("website", ""), placeholder="https://www.winery.com.au")
        _LABEL_LANG_OPTIONS = {"English": "en", "Deutsch (DE)": "de", "Français (FR)": "fr", "Italiano (IT)": "it", "Español (ES)": "es"}
        _saved_lang = p.get("label_language", "en")
        _lang_idx = list(_LABEL_LANG_OPTIONS.values()).index(_saved_lang) if _saved_lang in _LABEL_LANG_OPTIONS.values() else 0
        label_language = st.selectbox("Default label language", list(_LABEL_LANG_OPTIONS.keys()), index=_lang_idx, help="Pre-selects the language on the consumer label based on the product's primary market.")

        st.markdown(f'<div style="height:8px;"></div>', unsafe_allow_html=True)
        st.markdown(mlabel("Market Pricing"), unsafe_allow_html=True)
        st.markdown(f'<div style="font-family:Space Grotesk,sans-serif;font-size:12px;color:{C["ink60"]};margin-bottom:8px;">Set an RRP per market — all prices are shown on the consumer label.</div>', unsafe_allow_html=True)
        for _pi, _mp in enumerate(p.get("market_prices", [])):
            _mpid = _mp.get("id") or str(_pi)
            pc1, pc2 = st.columns([5, 1])
            with pc1:
                st.markdown(f'<div style="padding:6px 0;font-family:Space Grotesk,sans-serif;font-size:13px;">🌍 <strong>{_mp["market"]}</strong> &nbsp;·&nbsp; {_mp["currency"]} {float(_mp["price"]):.2f}</div>', unsafe_allow_html=True)
            with pc2:
                _rm_price[_mpid] = st.button("Remove", key=f"rmp_{_mpid}", type="secondary")
        if p.get("id"):
            with st.form("price_add_form", clear_on_submit=True):
                pa1, pa2, pa3 = st.columns([3, 1, 2])
                with pa1: _p_market   = st.text_input("Market / Country", placeholder="e.g. Australia")
                with pa2: _p_currency = st.selectbox("Currency", ["AUD", "EUR", "USD", "GBP", "NZD", "CAD", "CHF", "DKK", "SEK", "NOK"])
                with pa3: _p_price    = st.number_input("RRP", min_value=0.0, step=0.50, format="%.2f")
                if st.form_submit_button("+ Add Market Price", type="primary"):
                    if _p_market.strip() and _p_price > 0:
                        entry = {"id": str(uuid.uuid4())[:8], "market": _p_market.strip(), "currency": _p_currency, "price": _p_price}
                        cur = get_product(p["id"])
                        cur.setdefault("market_prices", []).append(entry)
                        upsert_product(cur)
                        st.rerun()
                    else:
                        st.warning("Please enter a market name and a price greater than 0.")

    # ── 11 · Product Image & Certificates ────────────────────────────────────
    _rm_img = False
    _rm_cert = {}
    _img_file = None

    with st.expander("11 · Product Image & Certificates", expanded=False):
        st.markdown(mlabel("Product Image"), unsafe_allow_html=True)
        st.markdown(f'<div style="font-family:Space Grotesk,sans-serif;font-size:12px;color:{C["ink60"]};margin-bottom:8px;">Upload a bottle or label photo — displayed on the consumer e-label page.</div>', unsafe_allow_html=True)
        _cur_img = p.get("product_image")
        if _cur_img:
            _thumb_ext = (p.get("product_image_filename") or "").rsplit(".", 1)[-1].lower()
            _thumb_mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}.get(_thumb_ext, "image/jpeg")
            img_col, btn_col = st.columns([3, 1])
            with img_col:
                st.markdown(f'<img src="data:{_thumb_mime};base64,{_cur_img}" style="width:100%;max-width:280px;border-radius:12px;border:1px solid {C["ink08"]};" />', unsafe_allow_html=True)
            with btn_col:
                _rm_img = st.button("Remove image", key="rm_img_btn", type="secondary")
        _img_file = st.file_uploader("Upload product image", type=["png", "jpg", "jpeg", "webp"], label_visibility="collapsed", key="img_upload")

        st.markdown(f'<div style="height:12px;"></div>', unsafe_allow_html=True)
        st.markdown(mlabel("Certificate Documents"), unsafe_allow_html=True)
        st.markdown(f'<div style="font-family:Space Grotesk,sans-serif;font-size:12px;color:{C["ink60"]};margin-bottom:8px;">Upload PDFs — organic certificates, lab reports, export documents. Downloadable on the public label.</div>', unsafe_allow_html=True)
        for _ci, _cert in enumerate(p.get("certificates", [])):
            _cid = _cert.get("id") or str(_ci)
            cc1, cc2 = st.columns([4, 1])
            with cc1:
                st.markdown(f'<div style="padding:8px 0;font-family:Space Grotesk,sans-serif;font-size:13px;">📄 <strong>{_cert.get("name","")}</strong>' + (f' — {_cert["issuer"]}' if _cert.get("issuer") else "") + (f' · expires {_cert["expiry"]}' if _cert.get("expiry") else "") + '</div>', unsafe_allow_html=True)
            with cc2:
                _rm_cert[_cid] = st.button("Remove", key=f"rm_{_cid}", type="secondary")
        if p.get("id"):
            with st.form("cert_upload_form", clear_on_submit=True):
                cf1, cf2, cf3 = st.columns(3)
                with cf1: _cert_name   = st.text_input("Certificate name", placeholder="Organic Certificate")
                with cf2: _cert_issuer = st.text_input("Issuer",           placeholder="ACO Certification")
                with cf3: _cert_expiry = st.text_input("Expiry date",      placeholder="2026-12-31")
                _cert_file = st.file_uploader("Upload certificate (PDF or Word)", type=["pdf", "doc", "docx"], label_visibility="collapsed")
                if st.form_submit_button("Attach Certificate", type="primary"):
                    if _cert_file and _cert_name.strip():
                        entry = {"id": str(uuid.uuid4())[:8], "name": _cert_name.strip(), "issuer": _cert_issuer.strip(), "expiry": _cert_expiry.strip(), "filename": _cert_file.name, "data": base64.b64encode(_cert_file.read()).decode()}
                        cur = get_product(p["id"])
                        cur.setdefault("certificates", []).append(entry)
                        upsert_product(cur)
                        st.rerun()
                    else:
                        st.warning("Please enter a certificate name and select a file.")

    st.markdown('<div style="height:12px;"></div>', unsafe_allow_html=True)
    submitted = st.button("Save Product", type="primary", use_container_width=True)

    # Section 10 & 11 actions — handled before save so rerun exits early
    if p.get("id"):
        for _mpid, _mp_clicked in _rm_price.items():
            if _mp_clicked:
                cur = get_product(p["id"])
                cur["market_prices"] = [mp for mp in cur.get("market_prices", []) if (mp.get("id") or "") != _mpid]
                upsert_product(cur)
                st.rerun()
        if _rm_img:
            cur = get_product(p["id"])
            cur.pop("product_image", None)
            cur.pop("product_image_filename", None)
            upsert_product(cur)
            st.rerun()
        for _cid, _clicked in _rm_cert.items():
            if _clicked:
                cur = get_product(p["id"])
                cur["certificates"] = [c for c in cur.get("certificates", []) if (c.get("id") or "") != _cid]
                upsert_product(cur)
                st.rerun()

    if submitted:
        _errs = []
        if not name.strip(): _errs.append("Wine name")
        if not producer_name.strip(): _errs.append("Winery / producer")
        if _errs:
            st.session_state["_form_errors"] = _errs
            st.rerun()
        else:
            custom_list = [l.strip() for l in custom_ings.splitlines() if l.strip()]
            all_ings    = selected_common + [i for i in custom_list if i not in selected_common]
            all_certs   = selected_certs + [c.strip() for c in custom_certs.split(",") if c.strip() and c.strip() not in selected_certs]
            if auto_calc_energy:
                calc_kj   = round((abv * 0.789 * 29) + (carb_g * 17) + (protein_g * 17) + (fat_g * 37))
                calc_kcal = round(calc_kj / 4.184)
                energy_kj, energy_kcal = float(calc_kj), float(calc_kcal)
            _new_img      = base64.b64encode(_img_file.read()).decode() if _img_file is not None else p.get("product_image")
            _new_img_name = _img_file.name if _img_file is not None else p.get("product_image_filename")
            product = {
                "id": p.get("id", str(uuid.uuid4())[:8]),
                "name": (name or "").strip(), "vintage": (vintage or "").strip(), "variety": (variety or "").strip(),
                "product_category": product_category, "pdo_pgi": (pdo_pgi or "").strip(),
                "traditional_term": traditional_term if traditional_term != "— None —" else None,
                "region": (region or "").strip(), "producer_name": (producer_name or "").strip(),
                "collection": (collection or "").strip(),
                "country": (country or "").strip(), "producer_address": (producer_address or "").strip(),
                "abv": round(abv, 1), "net_quantity": (net_quantity or "").strip(), "lot_number": (lot_number or "").strip(),
                "sweetness_descriptor": sweetness_descriptor if sweetness_descriptor != "— Not specified —" else None,
                "sparkling_dosage": sparkling_dosage if sparkling_dosage != "— Not applicable —" else None,
                "best_before_date": best_before_date.isoformat() if best_before_date else None,
                "auto_calc_energy": auto_calc_energy,
                "ingredients": all_ings, "fining_agents": selected_fining, "allergens": selected_allergens,
                "so2_level": so2_level or None,
                "nutrition": {"energy_kj": energy_kj, "energy_kcal": energy_kcal, "fat_g": fat_g, "saturated_fat_g": sat_fat_g, "carbohydrate_g": carb_g, "sugars_g": sugars_g, "protein_g": protein_g, "salt_g": salt_g},
                "packaging": {"bottle_material": bottle_material, "closure_type": closure_type, "label_material": label_material, "capsule_material": capsule_material, "recycled_content_pct": recycled_pct or None, "recycling_instructions": (recycling_instructions or "").strip() or None},
                "sustainability": {"carbon_footprint_kg": carbon_footprint or None, "water_usage_l": water_usage or None, "renewable_energy": renewable_energy},
                "supply_chain": {"vineyard_name": (vineyard_name or "").strip() or None, "vineyard_region": (vineyard_region or "").strip() or None, "vineyard_country": (vineyard_country or "").strip() or None, "grape_origin_country": (grape_origin_country or "").strip() or None, "bottling_facility": (bottling_facility or "").strip() or None, "bottling_location": (bottling_location or "").strip() or None, "importer_name": (importer_name or "").strip() or None, "importer_address": (importer_address or "").strip() or None},
                "certifications": all_certs, "certificates": p.get("certificates", []),
                "physical_label_fields": physical_label_fields,
                "pregnancy_warning": pregnancy_warning, "responsible_drinking": responsible_drinking,
                "storage_info": (storage_info or "").strip(), "website": (website or "").strip(),
                "market_prices": p.get("market_prices", []),
                "price_rrp": p.get("price_rrp"), "price_currency": p.get("price_currency"),
                "label_language": _LABEL_LANG_OPTIONS[label_language],
                "product_image": _new_img, "product_image_filename": _new_img_name,
                "status": p.get("status", "draft"),
                "created_at": p.get("created_at", datetime.now().isoformat()),
                "updated_at": datetime.now().isoformat(),
            }
            upsert_product(product)
            if ANTHROPIC_AVAILABLE and _get_api_key() and all_ings:
                with st.spinner("🤖 Checking allergens..."):
                    detected = ai_detect_allergens(all_ings)
                missing = [a for a in detected if a not in (selected_allergens or [])]
                if missing:
                    st.session_state["_allergen_suggestions"] = {"pid": product["id"], "new": missing}
            st.session_state["_saved"] = True
            st.query_params.update({"page": "edit", "id": product["id"]})
            st.rerun()

    # ── Post-save feedback
    if p.get("id"):
        if st.session_state.pop("_saved", False):
            st.success("Product saved.")
            sugg = st.session_state.pop("_allergen_suggestions", None)
            if sugg and sugg.get("pid") == p.get("id"):
                st.warning(f"🤖 AI detected allergens not yet declared: **{', '.join(sugg['new'])}**")
                if st.button("Add to allergens", key="add_allergens_btn", type="primary"):
                    cur = get_product(p["id"])
                    cur["allergens"] = list(set((cur.get("allergens") or []) + sugg["new"]))
                    upsert_product(cur); st.rerun()

        st.markdown('<div style="height:8px;"></div>', unsafe_allow_html=True)
        if st.button("← Back to Dashboard", key="bottom_back_btn", type="secondary", use_container_width=True):
            st.query_params["page"] = "dashboard"
            st.rerun()


# ── QR page ───────────────────────────────────────────────────────────────────
def _compliance_badges_html(product):
    scores = compliance_score(product)
    html = '<div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:10px;">'
    for section, d in scores.items():
        pct = int(d["score"] / d["total"] * 100) if d["total"] else 0
        col = d["color"] if pct == 100 else (C["gold"] if pct >= 60 else C["red"])
        icon = "✓" if pct == 100 else ("!" if pct >= 60 else "✗")
        html += (f'<div style="display:inline-flex;align-items:center;gap:5px;background:{col}18;'
                 f'border:1px solid {col}40;border-radius:999px;padding:3px 10px;">'
                 f'<span style="font-weight:700;color:{col};">{icon}</span>'
                 f'<span style="font-family:JetBrains Mono,monospace;font-size:9px;font-weight:700;'
                 f'letter-spacing:0.1em;color:{col};text-transform:uppercase;">{section} {pct}%</span></div>')
    return html + '</div>'

def show_qr_page(pid):
    p = get_product(pid)
    if not p:
        st.query_params["page"] = "dashboard"; st.rerun(); return

    st.markdown(f"""<style>
[data-testid="stMainBlockContainer"] {{
    padding-left:0!important;
    padding-right:0!important;
    max-width:100%!important;
}}
.block-container {{
    background:{C["paper"]}!important;
    border-radius:18px!important;
    box-shadow:0 12px 40px rgba(0,0,0,0.4),0 2px 8px rgba(0,0,0,0.25)!important;
    padding:0.25rem 2rem 3rem!important;
    margin-top:2rem!important;
    margin-left:56px!important;
    margin-right:auto!important;
    max-width:520px!important;
}}
.block-container > div:first-child {{ margin-top:0!important; padding-top:0!important; }}
.block-container > div > div > div [data-testid="stBaseButton-secondary"],
.block-container > div > div > div [data-testid="stBaseButton-secondary"] button {{
    background:transparent!important;
    border:1px solid {C["paperEdge"]}!important;
    color:{C["ink"]}!important;
}}
.block-container > div > div > div [data-testid="stBaseButton-secondary"] p {{
    color:{C["ink"]}!important;
}}
</style>""", unsafe_allow_html=True)
    st.markdown('<div class="qr-page-marker" style="display:none;"></div>', unsafe_allow_html=True)

    # Header — dark ink now that we're on white
    bc, tc = st.columns([0.12, 0.88])
    with bc:
        if st.button("←", type="secondary"):
            st.query_params["page"] = "dashboard"; st.rerun()
    with tc:
        st.markdown(f'<div style="font-family:Gloock,serif;font-size:26px;font-weight:600;color:{C["ink"]};padding:6px 0;letter-spacing:-0.01em;">QR Code</div>', unsafe_allow_html=True)

    st.markdown(f'<div style="border-bottom:1px solid {C["paperEdge"]};margin:4px 0 16px;"></div>', unsafe_allow_html=True)

    label_url = get_label_url(pid)

    # Pre-compute QR bytes so we can embed image + use download button
    qr_bytes = make_qr_image(label_url) if QR_AVAILABLE else None
    qr_img_html = ""
    eu_notice_html = ""
    if qr_bytes:
        b64 = base64.b64encode(qr_bytes).decode()
        qr_img_html = f'<img src="data:image/png;base64,{b64}" style="width:200px;height:200px;border-radius:10px;display:block;" />'
        eu_notice_html = (
            f'<div style="background:{C["cream"]};border:1px solid {C["eu"]}40;border-radius:10px;padding:10px 14px;margin-top:16px;">'
            f'<span style="font-family:JetBrains Mono,monospace;font-size:9px;font-weight:700;letter-spacing:0.12em;color:{C["eu"]};text-transform:uppercase;">EU Print Requirement</span>'
            f'<div style="font-family:Inter,sans-serif;font-size:12px;color:{C["ink"]};margin-top:3px;">Minimum print size: <strong>13 × 13 mm at 300 DPI</strong> as required by EU Reg. 2021/2117.</div>'
            f'</div>'
        )
    elif QR_AVAILABLE:
        qr_img_html = f'<div style="font-family:Inter,sans-serif;font-size:13px;color:{C["red"]};margin:12px 0;">Could not generate QR code.</div>'

    # Thumbnail next to product name (if image uploaded)
    _thumb_html = (
        f'<img src="data:image/jpeg;base64,{p["product_image"]}" '
        f'style="width:80px;height:80px;object-fit:cover;border-radius:10px;flex-shrink:0;'
        f'box-shadow:0 2px 8px rgba(0,0,0,0.12);border:1px solid {C["paperEdge"]};" />'
    ) if p.get("product_image") else ""

    # All content in a single flat HTML block
    st.markdown(
        # Product info row — thumbnail left, name/producer right
        f'<div style="display:flex;align-items:flex-start;gap:14px;'
        f'border-left:3px solid {C["wine2"]};padding-left:14px;margin-bottom:14px;">'
        f'{_thumb_html}'
        f'<div style="flex:1;min-width:0;">'
        f'<div style="font-family:Gloock,serif;font-size:20px;font-weight:600;color:{C["ink"]};letter-spacing:-0.01em;">{p["name"]} {p.get("vintage","")}</div>'
        f'<div style="font-family:Inter,sans-serif;font-size:13px;color:{C["ink2"]};margin-top:2px;">{p.get("producer_name","")}</div>'
        f'{_compliance_badges_html(p)}'
        f'</div>'
        f'</div>'
        f'<div style="border-top:1px solid {C["paperEdge"]};margin:0 0 16px;"></div>'
        # QR code centred
        f'<div style="display:flex;justify-content:center;padding:8px 0;">{qr_img_html}</div>'
        # EU notice below QR
        f'{eu_notice_html}'
        # Label URL
        f'<div style="border-top:1px solid {C["paperEdge"]};margin:16px 0 14px;"></div>'
        f'<div style="font-family:JetBrains Mono,monospace;font-size:9px;font-weight:700;letter-spacing:0.15em;color:{C["ink2"]};text-transform:uppercase;margin-bottom:6px;">Label URL</div>'
        f'<div style="font-family:JetBrains Mono,monospace;font-size:12px;color:{C["ink"]};word-break:break-all;">{label_url}</div>',
        unsafe_allow_html=True
    )

    # Interactive buttons
    if qr_bytes:
        st.markdown('<div style="height:14px;"></div>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            st.download_button("Download QR", data=qr_bytes, file_name=f"vinelabel-{p['name'].lower().replace(' ','-')}-{p.get('vintage','')}.png", mime="image/png", use_container_width=True, type="primary")
        with col2:
            if st.button("Preview Label", use_container_width=True, type="secondary"):
                st.query_params.update({"label": pid, "preview": "1"}); st.rerun()
    elif not QR_AVAILABLE:
        st.warning("Run `pip install qrcode[pil]` to enable QR codes.")

    st.markdown('<div style="height:8px;"></div>', unsafe_allow_html=True)
    if st.button("Edit Product", type="secondary", use_container_width=True):
        st.query_params.update({"page": "edit", "id": pid}); st.rerun()


# ── Router ────────────────────────────────────────────────────────────────────
def main():
    if "label" in st.query_params:
        inject_dashboard_css()
        show_public_label(st.query_params["label"], is_preview="preview" in st.query_params)
        return
    if "signin" in st.query_params:
        st.session_state["show_login"] = True
        st.query_params.clear()
        st.rerun()
    # Route directly from query params — survives browser refresh
    qp   = st.query_params.get("page", "")
    qp_id = st.query_params.get("id", "")

    if "dashboard" in st.query_params or qp == "dashboard":
        inject_dashboard_css(); show_dashboard()
    elif qp == "add":
        inject_dashboard_css(); show_product_form()
    elif qp == "edit":
        inject_dashboard_css()
        show_product_form(existing=get_product(qp_id) if qp_id else None)
    elif qp == "qr":
        inject_dashboard_css(); show_qr_page(qp_id)
    else:
        show_landing()

if __name__ == "__main__":
    main()
