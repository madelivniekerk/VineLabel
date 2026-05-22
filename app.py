import streamlit as st
import json
import uuid
import io
import base64
from pathlib import Path
from datetime import datetime, date

def _wood_texture_b64():
    # SVG from cellar-handoff/direction-cellar.jsx
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' width='1200' height='800' viewBox='0 0 1200 800'>"
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
        "<line x1='0' y1='160' x2='1200' y2='160'/>"
        "<line x1='0' y1='420' x2='1200' y2='420'/>"
        "<line x1='0' y1='640' x2='1200' y2='640'/>"
        "</g>"
        "<g stroke='#150806' stroke-opacity='0.25' stroke-width='1'>"
        "<line x1='0' y1='161' x2='1200' y2='161'/>"
        "<line x1='0' y1='421' x2='1200' y2='421'/>"
        "<line x1='0' y1='641' x2='1200' y2='641'/>"
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

DATA_DIR = Path(__file__).parent / "data"
PRODUCTS_FILE = DATA_DIR / "products.json"
DATA_DIR.mkdir(exist_ok=True)

# ── Data ──────────────────────────────────────────────────────────────────────
def load_products():
    if not PRODUCTS_FILE.exists():
        return []
    with open(PRODUCTS_FILE, encoding="utf-8") as f:
        return json.load(f)

def save_products(products):
    with open(PRODUCTS_FILE, "w", encoding="utf-8") as f:
        json.dump(products, f, indent=2, ensure_ascii=False)

SETTINGS_FILE = DATA_DIR / "settings.json"

def load_settings():
    if not SETTINGS_FILE.exists():
        return {}
    with open(SETTINGS_FILE, encoding="utf-8") as f:
        return json.load(f)

def save_settings(settings):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)

def get_product(pid):
    return next((p for p in load_products() if p["id"] == pid), None)

def upsert_product(product):
    products = load_products()
    for i, p in enumerate(products):
        if p["id"] == product["id"]:
            products[i] = product
            save_products(products)
            return
    products.append(product)
    save_products(products)

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
    base = st.session_state.get("base_url") or load_settings().get("base_url", "http://localhost:8501")
    return f"{base}/?label={pid}"

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

# ── Design ────────────────────────────────────────────────────────────────────
C = {
    # Cellar palette from direction-cellar.jsx
    "wine":    "#7A1F2B",   # burgundy
    "wine2":   "#9C2A38",   # burgundy2
    "wineDim": "#5C1620",   # burgundyDim
    "bg":      "#F6EFE0",   # parchment paper
    "paper":   "#F6EFE0",
    "paperEdge":"#E8DBC1",
    "cream":   "#FAF6F0",
    "ink":     "#2A1F16",
    "ink2":    "#6E5F4E",
    "ink3":    "#9C8E7D",
    "ink60":   "rgba(42,31,22,0.6)",
    "ink12":   "rgba(42,31,22,0.12)",
    "ink08":   "rgba(42,31,22,0.08)",
    "gold":    "#B89455",
    "goldSoft":"#F1E6CD",
    "green":   "#5C6B3A",   # olive
    "greenSoft":"#E6E8D8",
    "eu":      "#2A4F6B",
    "red":     "#A93527",
    "woodDark":"#2a1a10",
}

def load_hero():
    for name in ["cellar-hero.png", "hero.png"]:
        hero = Path(__file__).parent / "assets" / name
        if hero.exists():
            with open(hero, "rb") as f:
                return base64.b64encode(f.read()).decode()
    return None

def inject_css():
    _wood_svg   = _wood_texture_b64()
    _wood_photo = _load_asset_b64("wood-bg.png")
    _photo_layer = f'url("data:image/png;base64,{_wood_photo}"),' if _wood_photo else ""
    st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600;9..144,700&family=DM+Sans:wght@400;500;600;700&display=swap');

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
    font-family:'DM Sans',system-ui,sans-serif;
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
h1,h2,h3{{font-family:'Fraunces',serif!important;letter-spacing:-0.01em!important;}}

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
    return (f'<div style="font-family:DM Sans,system-ui,sans-serif;font-size:10px;font-weight:700;'
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
def show_public_label(pid):
    p = get_product(pid)
    if not p:
        st.error("Label not found.")
        return
    inject_css()
    st.markdown('<div class="public-label-marker" style="display:none;"></div>', unsafe_allow_html=True)

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

    # Product image
    if p.get("product_image"):
        st.markdown(f'<div style="text-align:center;margin-bottom:16px;"><img src="data:image/jpeg;base64,{p["product_image"]}" style="max-width:100%;max-height:320px;border-radius:14px;box-shadow:0 4px 18px rgba(26,26,46,0.12);" /></div>', unsafe_allow_html=True)

    # PDO/PGI badge
    if p.get("pdo_pgi"):
        st.markdown(f'<div style="display:inline-flex;align-items:center;gap:6px;background:{C["gold"]}14;border:1px solid {C["gold"]}30;border-radius:999px;padding:4px 12px;margin-bottom:14px;"><span style="font-family:JetBrains Mono,monospace;font-size:9px;font-weight:700;letter-spacing:0.14em;color:{C["gold"]};text-transform:uppercase;">PDO/PGI</span><span style="font-family:Space Grotesk,sans-serif;font-size:12px;font-weight:600;color:{C["ink"]};">{p["pdo_pgi"]}</span></div>', unsafe_allow_html=True)

    # Key facts strip
    _price_str = f'{p["price_currency"]} {p["price_rrp"]:.2f}' if p.get("price_rrp") and p.get("price_currency") else None
    facts = [(l, v) for l, v in [
        ("ABV", f'{p["abv"]}%' if p.get("abv") else None),
        ("Net qty", p.get("net_quantity") or None),
        ("Lot", p.get("lot_number") or None),
        ("Dosage", p.get("sparkling_dosage") or None),
        ("Best before", (lambda d: date.fromisoformat(d).strftime("%d %b %Y") if d else None)(p.get("best_before_date"))),
        ("RRP", _price_str),
    ] if v]
    if facts:
        cells = "".join([
            f'<div style="flex:1;text-align:center;padding:10px 6px;border-right:1px solid {C["ink08"]};">'
            f'<div style="font-family:JetBrains Mono,monospace;font-size:9px;font-weight:700;letter-spacing:0.15em;color:{C["ink60"]};text-transform:uppercase;">{l}</div>'
            f'<div style="font-family:Space Grotesk,sans-serif;font-size:16px;font-weight:700;color:{C["ink"]};margin-top:2px;">{v}</div></div>'
            for l, v in facts])
        st.markdown(f'<div style="display:flex;background:{C["paper"]};border-radius:12px;border:1px solid {C["ink08"]};overflow:hidden;margin-bottom:14px;">{cells}</div>', unsafe_allow_html=True)

    # Ingredients
    ingredients = p.get("ingredients", [])
    allergens = [a.split(" ")[0].lower() for a in p.get("allergens", [])]
    if ingredients:
        st.markdown(mlabel("Ingredients"), unsafe_allow_html=True)
        parts = [f'<strong style="color:{C["ink"]};">{i}</strong>' if any(a in i.lower() for a in allergens) else i for i in ingredients]
        st.markdown(f'<div style="font-family:Space Grotesk,sans-serif;font-size:14px;line-height:1.7;color:{C["ink"]};background:{C["paper"]};border-radius:12px;padding:14px;border:1px solid {C["ink08"]};margin-bottom:10px;">' + ", ".join(parts) + "</div>", unsafe_allow_html=True)

    if p.get("allergens"):
        st.markdown(f'<div style="background:#fff8f0;border-left:3px solid {C["gold"]};border-radius:0 8px 8px 0;padding:10px 14px;margin-bottom:14px;"><div style="font-family:JetBrains Mono,monospace;font-size:9px;font-weight:700;letter-spacing:0.15em;color:{C["gold"]};text-transform:uppercase;margin-bottom:3px;">Contains Allergens</div><div style="font-family:Space Grotesk,sans-serif;font-size:13px;font-weight:600;color:{C["ink"]};">{", ".join(p["allergens"])}</div></div>', unsafe_allow_html=True)

    # Nutrition
    nu = p.get("nutrition", {})
    if nu and any(nu.values()):
        st.markdown(mlabel("Nutrition · per 100 mL"), unsafe_allow_html=True)
        rows = [
            ("Energy", f'{nu.get("energy_kj",0):.0f} kJ / {nu.get("energy_kcal",0):.0f} kcal', False),
            ("Fat", f'{nu.get("fat_g",0):.1f} g', False),
            ("of which saturates", f'{nu.get("saturated_fat_g",0):.1f} g', True),
            ("Carbohydrate", f'{nu.get("carbohydrate_g",0):.1f} g', False),
            ("of which sugars", f'{nu.get("sugars_g",0):.1f} g', True),
            ("Protein", f'{nu.get("protein_g",0):.1f} g', False),
            ("Salt", f'{nu.get("salt_g",0):.2f} g', False),
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
        st.markdown(mlabel("Packaging & Recycling"), unsafe_allow_html=True)
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
        pkg_items = [(v, k + (" bottle" if k == pkg.get("bottle_material") else ""), RECYCLING.get(k, ("♻️",""))[1])
                     for k, v in [(pkg.get("bottle_material",""), RECYCLING.get(pkg.get("bottle_material",""), ("♻️",""))[0]),
                                  (pkg.get("closure_type",""), RECYCLING.get(pkg.get("closure_type",""), ("♻️",""))[0]),
                                  (pkg.get("label_material",""), RECYCLING.get(pkg.get("label_material",""), ("♻️",""))[0]),
                                  (pkg.get("capsule_material",""), RECYCLING.get(pkg.get("capsule_material",""), ("♻️",""))[0])]
                     if k and k != "None"]
        # simpler approach
        pkg_rows = []
        for key, suffix in [("bottle_material", " bottle"), ("closure_type", ""), ("label_material", " label"), ("capsule_material", " capsule")]:
            val = pkg.get(key)
            if val and val != "None":
                icon, tip = RECYCLING.get(val, ("♻️", ""))
                pkg_rows.append((icon, val + suffix, tip))
        if pkg.get("recycled_content_pct"):
            pkg_rows.append(("🔄", f'{pkg["recycled_content_pct"]}% recycled glass content', ""))
        rows_html = "".join([
            f'<div style="display:flex;align-items:center;gap:12px;padding:10px 14px;background:{C["paper"] if i%2==0 else C["bg"]};">'
            f'<div style="font-size:20px;">{icon}</div><div>'
            f'<div style="font-family:Space Grotesk,sans-serif;font-size:13px;font-weight:600;color:{C["ink"]};">{mat}</div>'
            + (f'<div style="font-family:Space Grotesk,sans-serif;font-size:12px;color:{C["ink60"]};">{tip}</div>' if tip else "")
            + '</div></div>'
            for i, (icon, mat, tip) in enumerate(pkg_rows)])
        st.markdown(f'<div style="border-radius:12px;border:1px solid {C["ink08"]};overflow:hidden;margin-bottom:10px;">{rows_html}</div>', unsafe_allow_html=True)
        if pkg.get("recycling_instructions"):
            st.markdown(f'<div style="font-family:Space Grotesk,sans-serif;font-size:13px;color:{C["ink60"]};padding:10px 14px;background:{C["ink08"]};border-radius:10px;margin-bottom:14px;">{pkg["recycling_instructions"]}</div>', unsafe_allow_html=True)

    # Carbon
    sus = p.get("sustainability", {})
    if sus and sus.get("carbon_footprint_kg"):
        st.markdown(mlabel("Carbon Footprint"), unsafe_allow_html=True)
        st.markdown(f'<div style="display:flex;align-items:center;gap:12px;background:{C["green"]}10;border:1px solid {C["green"]}28;border-radius:12px;padding:14px;margin-bottom:14px;"><div style="font-size:28px;">🌱</div><div><div style="font-family:Space Grotesk,sans-serif;font-size:22px;font-weight:700;color:{C["green"]};">{sus["carbon_footprint_kg"]} kg CO₂e</div><div style="font-family:JetBrains Mono,monospace;font-size:9px;font-weight:700;letter-spacing:0.15em;color:{C["green"]}80;text-transform:uppercase;">per bottle · cradle to gate</div></div></div>', unsafe_allow_html=True)

    # Supply chain
    sc = p.get("supply_chain", {})
    sc_rows = [(k, v) for k, v in [("Vineyard", sc.get("vineyard_name")), ("Vineyard region", sc.get("vineyard_region")), ("Vineyard country", sc.get("vineyard_country")), ("Bottled by", sc.get("bottling_facility")), ("Bottling location", sc.get("bottling_location")), ("EU importer", sc.get("importer_name"))] if v]
    if sc_rows:
        st.markdown(mlabel("Provenance"), unsafe_allow_html=True)
        rows_html = "".join([f'<div style="display:flex;justify-content:space-between;padding:8px 14px;background:{C["paper"] if i%2==0 else C["bg"]};"><div style="font-family:Space Grotesk,sans-serif;font-size:13px;color:{C["ink60"]};">{k}</div><div style="font-family:Space Grotesk,sans-serif;font-size:13px;font-weight:600;color:{C["ink"]};">{v}</div></div>' for i, (k, v) in enumerate(sc_rows)])
        st.markdown(f'<div style="border-radius:12px;border:1px solid {C["ink08"]};overflow:hidden;margin-bottom:14px;">{rows_html}</div>', unsafe_allow_html=True)

    # Certifications
    certs = p.get("certifications", [])
    cert_docs = p.get("certificates", [])
    if certs or cert_docs:
        st.markdown(mlabel("Certifications"), unsafe_allow_html=True)
        if certs:
            chips = "".join([f'<span style="background:{C["green"]}18;color:{C["green"]};border:1px solid {C["green"]}30;border-radius:999px;padding:4px 12px;font-family:JetBrains Mono,monospace;font-size:10px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;">{c}</span>' for c in certs])
            st.markdown(f'<div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px;">{chips}</div>', unsafe_allow_html=True)
        for doc in cert_docs:
            if doc.get("data"):
                fname = doc.get("filename", "certificate.pdf")
                ext   = fname.rsplit(".", 1)[-1].lower() if "." in fname else "pdf"
                mime  = "application/vnd.openxmlformats-officedocument.wordprocessingml.document" if ext == "docx" else ("application/msword" if ext == "doc" else "application/pdf")
                st.download_button(f"📄 {doc['name']}" + (f" — {doc['issuer']}" if doc.get("issuer") else ""), data=base64.b64decode(doc["data"]), file_name=fname, mime=mime, key=f"dl_{doc['id']}")

    if p.get("storage_info"):
        st.markdown(f'<div style="font-family:Space Grotesk,sans-serif;font-size:13px;color:{C["ink60"]};padding:10px 14px;background:{C["ink08"]};border-radius:10px;margin-bottom:14px;"><strong>Storage:</strong> {p["storage_info"]}</div>', unsafe_allow_html=True)

    if p.get("producer_address"):
        st.markdown(f'<div style="font-family:Space Grotesk,sans-serif;font-size:12px;color:{C["ink60"]};margin-bottom:14px;">{p.get("producer_name","")} · {p["producer_address"]}</div>', unsafe_allow_html=True)

    st.markdown(f'<div style="margin-top:24px;padding:14px;border-top:1px solid {C["ink08"]};text-align:center;"><div style="font-family:JetBrains Mono,monospace;font-size:9px;font-weight:700;letter-spacing:0.15em;color:{C["ink60"]};text-transform:uppercase;">VineLabel · EU e-label Reg. 2021/2117</div></div></div>', unsafe_allow_html=True)


# ── Dashboard ─────────────────────────────────────────────────────────────────
def _product_card(p):
    pid = p["id"]
    exp_key = f"card_{pid}"
    is_expanded = st.session_state.get(exp_key, False)
    is_pub = p.get("status") == "published"

    scol = C["green"] if is_pub else C["gold"]
    slbl = (p.get("status") or "draft").upper()
    _price = f' · {p["price_currency"]} {p["price_rrp"]:.2f}' if p.get("price_rrp") and p.get("price_currency") else ""
    _thumb = (f'<img src="data:image/jpeg;base64,{p["product_image"]}" style="width:52px;height:52px;object-fit:cover;border-radius:8px;flex-shrink:0;" />'
              if p.get("product_image") else
              f'<div style="width:52px;height:52px;border-radius:8px;background:{C["wine"]}18;display:flex;align-items:center;justify-content:center;font-size:22px;flex-shrink:0;">🍷</div>')

    edit_sub = qr_sub = pub_sub = toggle_sub = False

    with st.form(f"pcard_{pid}", clear_on_submit=False):
        # Two-column: product info left, status badge + toggle right
        info_col, ctrl_col = st.columns([0.68, 0.32])

        with info_col:
            st.markdown(
                f'<div style="display:flex;align-items:flex-start;gap:12px;">'
                f'{_thumb}'
                f'<div style="flex:1;min-width:0;">'
                f'<div style="font-family:Fraunces,serif;font-size:20px;font-weight:600;color:{C["ink"]};line-height:1.2;letter-spacing:-0.01em;">{p["name"]} {p.get("vintage","")}</div>'
                f'<div style="font-family:DM Sans,sans-serif;font-size:13px;color:{C["ink2"]};margin-top:3px;">{p.get("variety","")} · {p.get("region","")}{_price}</div>'
                f'</div></div>',
                unsafe_allow_html=True
            )

        with ctrl_col:
            # Actions button left, DRAFT badge right — same row
            btn_col, badge_col = st.columns([0.52, 0.48])
            with btn_col:
                toggle_sub = st.form_submit_button(
                    "▴ Close" if is_expanded else "▾ Actions",
                    use_container_width=True,
                    type="secondary",
                )
            with badge_col:
                st.markdown(
                    f'<div style="text-align:right;padding-top:8px;">'
                    f'<span style="font-family:DM Sans,sans-serif;font-size:9px;font-weight:700;letter-spacing:0.12em;'
                    f'color:{scol};border:1px solid {scol}40;border-radius:999px;padding:3px 9px;white-space:nowrap;">{slbl}</span>'
                    f'</div>',
                    unsafe_allow_html=True
                )

        # Action buttons — shown when expanded
        if is_expanded:
            st.markdown(f'<div style="border-top:1px solid {C["paperEdge"]};margin:6px 0;"></div>', unsafe_allow_html=True)
            c1, c2, c3 = st.columns(3)
            with c1:
                edit_sub = st.form_submit_button("Edit", use_container_width=True)
            with c2:
                qr_sub = st.form_submit_button("QR Code", use_container_width=True)
            with c3:
                pub_sub = st.form_submit_button("Unpublish" if is_pub else "Publish", use_container_width=True, type="primary")

    # Handle submissions outside the form
    if edit_sub:
        st.session_state.update({"page": "edit", "edit_id": pid}); st.rerun()
    elif qr_sub:
        st.session_state.update({"page": "qr", "qr_id": pid}); st.rerun()
    elif pub_sub:
        all_p = load_products()
        for prod in all_p:
            if prod["id"] == pid:
                prod["status"] = "draft" if is_pub else "published"
        save_products(all_p); st.rerun()
    elif toggle_sub:
        st.session_state[exp_key] = not is_expanded; st.rerun()

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

    products  = load_products()
    published = sum(1 for p in products if p.get("status") == "published")
    drafts    = len(products) - published

    hero_b64 = load_hero()
    if hero_b64:
        st.markdown(
            f'<div style="margin:-1rem -1rem 0;position:relative;height:220px;overflow:hidden;border-radius:0 0 18px 18px;">'
            f'<img src="data:image/png;base64,{hero_b64}" '
            f'style="width:100%;height:100%;object-fit:cover;object-position:center 40%;" />'
            f'<div style="position:absolute;inset:0;background:linear-gradient(to bottom,rgba(26,26,46,0.18) 0%,rgba(26,26,46,0.62) 100%);border-radius:0 0 18px 18px;"></div>'
            f'<div style="position:absolute;bottom:20px;left:20px;right:20px;">'
            f'<div style="font-family:DM Sans,sans-serif;font-size:10px;font-weight:700;letter-spacing:0.28em;color:{C["gold"]};text-transform:uppercase;margin-bottom:10px;">Producer Dashboard</div>'
            f'<div style="font-family:Fraunces,serif;font-size:52px;font-weight:600;color:#fff;line-height:1;letter-spacing:-0.02em;">VineLabel</div>'
            f'<div style="font-family:DM Sans,sans-serif;font-size:14px;color:rgba(250,246,240,0.85);margin-top:10px;line-height:1.5;">EU digital wine labels, made simple.</div>'
            f'</div></div>'
            f'<div style="height:20px;"></div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            f'<div style="padding:24px 0 16px;">'
            f'<div style="font-family:DM Sans,sans-serif;font-size:10px;font-weight:700;letter-spacing:0.28em;color:{C["gold"]};text-transform:uppercase;margin-bottom:8px;">Producer Dashboard</div>'
            f'<div style="font-family:Fraunces,serif;font-size:38px;font-weight:600;color:{C["ink"]};line-height:1;letter-spacing:-0.02em;">VineLabel</div>'
            f'<div style="font-family:DM Sans,sans-serif;font-size:14px;color:{C["ink2"]};margin-top:6px;">EU digital wine labels, made simple.</div>'
            f'</div>',
            unsafe_allow_html=True
        )

    st.markdown(
        f'<div style="display:flex;gap:10px;margin-bottom:20px;">'
        f'<div style="flex:1;background:{C["paper"]};border:1px solid {C["paperEdge"]};border-radius:14px;padding:18px 14px;text-align:center;box-shadow:0 1px 0 rgba(255,255,255,0.6) inset,0 12px 28px -12px rgba(0,0,0,0.45);"><div style="font-family:Fraunces,serif;font-size:36px;font-weight:600;color:{C["wineDim"]};letter-spacing:-0.02em;line-height:1;">{len(products)}</div><div style="font-family:DM Sans,sans-serif;font-size:9.5px;font-weight:700;letter-spacing:0.22em;color:{C["ink2"]};text-transform:uppercase;margin-top:8px;">Products</div></div>'
        f'<div style="flex:1;background:{C["paper"]};border:1px solid {C["paperEdge"]};border-radius:14px;padding:18px 14px;text-align:center;box-shadow:0 1px 0 rgba(255,255,255,0.6) inset,0 12px 28px -12px rgba(0,0,0,0.45);"><div style="font-family:Fraunces,serif;font-size:36px;font-weight:600;color:{C["green"]};letter-spacing:-0.02em;line-height:1;">{published}</div><div style="font-family:DM Sans,sans-serif;font-size:9.5px;font-weight:700;letter-spacing:0.22em;color:{C["ink2"]};text-transform:uppercase;margin-top:8px;">Published</div></div>'
        f'<div style="flex:1;background:{C["paper"]};border:1px solid {C["paperEdge"]};border-radius:14px;padding:18px 14px;text-align:center;box-shadow:0 1px 0 rgba(255,255,255,0.6) inset,0 12px 28px -12px rgba(0,0,0,0.45);"><div style="font-family:Fraunces,serif;font-size:36px;font-weight:600;color:{C["gold"]};letter-spacing:-0.02em;line-height:1;">{drafts}</div><div style="font-family:DM Sans,sans-serif;font-size:9.5px;font-weight:700;letter-spacing:0.22em;color:{C["ink2"]};text-transform:uppercase;margin-top:8px;">Drafts</div></div>'
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
            f'<div style="font-family:Fraunces,serif;font-size:20px;font-weight:600;color:{C["ink"]};">No products yet</div>'
            f'<div style="font-family:DM Sans,sans-serif;font-size:14px;color:{C["ink2"]};margin-top:6px;">Add your first wine to generate an EU-compliant digital label.</div>'
            f'</div>',
            unsafe_allow_html=True
        )

    if st.button("+ New Product", type="primary", use_container_width=True):
        st.session_state.update({"page": "add", "edit_id": None}); st.rerun()

    st.markdown('<div style="height:8px;"></div>', unsafe_allow_html=True)
    settings = load_settings()
    current_url = st.session_state.get("base_url") or settings.get("base_url", "")
    with st.expander("⚙️ Settings"):
        st.markdown(f'<div style="font-family:DM Sans,sans-serif;font-size:13px;color:{C["ink2"]};margin-bottom:8px;">Paste your published app URL so QR codes link to the live label page.</div>', unsafe_allow_html=True)
        new_url = st.text_input("Published app URL", value=current_url, placeholder="https://vinelabel-app.streamlit.app")
        if st.button("Save", type="primary"):
            url_clean = (new_url or "").rstrip("/")
            st.session_state["base_url"] = url_clean
            s = load_settings()
            s["base_url"] = url_clean
            save_settings(s)
            st.success("URL saved.")
            st.rerun()


# ── Product form ──────────────────────────────────────────────────────────────
COMMON_INGREDIENTS = ["Grapes", "Concentrated grape must", "Sulfur dioxide (E220)", "Potassium metabisulphite (E224)", "Yeast", "Tartaric acid (E334)", "Bentonite", "Metatartaric acid (E353)"]
COMMON_ALLERGENS   = ["Sulphites", "Egg (albumin fining agent)", "Milk (casein fining agent)", "Fish (isinglass fining agent)"]
COMMON_CERTS       = ["Organic", "Biodynamic", "Vegan", "Vegetarian", "Sustainable"]
BOTTLE_MATERIALS   = ["Glass", "PET plastic", "Other"]
CLOSURE_TYPES      = ["Natural cork", "Screwcap", "Synthetic cork", "Crown cap", "Glass stopper"]
LABEL_MATERIALS    = ["Paper", "Plastic (PP)", "None"]
CAPSULE_MATERIALS  = ["Tin", "Aluminium", "PVC", "Wax", "None"]
PRODUCT_CATEGORIES = ["Wine", "Sparkling Wine", "Rosé", "Dessert Wine", "Fortified Wine", "De-alcoholized Wine", "Other"]
SPARKLING_DOSAGE   = ["Brut Nature (0–3 g/L)", "Extra Brut (0–6 g/L)", "Brut (0–12 g/L)", "Extra Dry (12–17 g/L)", "Dry (17–32 g/L)", "Semi-Sweet (32–50 g/L)", "Sweet (>50 g/L)"]


def show_product_form(existing=None):
    p = existing or {}
    st.markdown('<div class="edit-page-marker" style="display:none;"></div>', unsafe_allow_html=True)
    bc, tc = st.columns([0.12, 0.88])
    with bc:
        if st.button("←", type="secondary"):
            st.session_state["page"] = "dashboard"; st.rerun()
    with tc:
        st.markdown(f'<div style="font-family:Fraunces,serif;font-size:26px;font-weight:600;color:{C["ink"]};padding:6px 0;letter-spacing:-0.01em;">{"Edit Product" if existing else "New Product"}</div>', unsafe_allow_html=True)

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

    with st.form("product_form", clear_on_submit=False):
        # 1 — Identity
        st.markdown(mlabel("1 — Product Identity"), unsafe_allow_html=True)
        c1, c2 = st.columns([3, 1])
        with c1: name = st.text_input("Wine name *", value=p.get("name", ""), placeholder="e.g. Barossa Valley Shiraz")
        with c2: vintage = st.text_input("Vintage", value=str(p.get("vintage", "")), placeholder="2022")
        product_category = st.selectbox("Product category *", PRODUCT_CATEGORIES, index=PRODUCT_CATEGORIES.index(p.get("product_category", "Wine")) if p.get("product_category") in PRODUCT_CATEGORIES else 0, help="Required by EU Reg. 2021/2117 — must appear on the e-label")
        c3, c4 = st.columns(2)
        with c3: variety = st.text_input("Grape variety", value=p.get("variety", ""), placeholder="Shiraz, Grenache")
        with c4: region = st.text_input("Region / appellation", value=p.get("region", ""), placeholder="Barossa Valley")
        pdo_pgi = st.text_input("PDO / PGI designation", value=p.get("pdo_pgi", ""), placeholder="e.g. Barossa Valley GI · Protected Geographical Indication", help="Protected Designation of Origin or Geographical Indication — required if claimed on physical label")
        c5, c6 = st.columns(2)
        with c5: producer_name = st.text_input("Winery / producer *", value=p.get("producer_name", ""), placeholder="e.g. Penfolds")
        with c6: country = st.text_input("Country of origin", value=p.get("country", "Australia"))
        producer_address = st.text_input("Producer address", value=p.get("producer_address", ""), placeholder="Street, City, State, Postcode")
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
                default_idx = len(options) - 1  # pre-select "New"
            else:
                default_idx = 0
            coll_select = st.selectbox("Range / Collection", options, index=default_idx)
            if coll_select == NEW_OPT:
                collection = st.text_input(
                    "New collection name",
                    value=curr_collection if curr_collection not in existing_collections else "",
                    placeholder="e.g. Reserve Range"
                )
            elif coll_select == UNCATEGORISED:
                collection = ""
            else:
                collection = coll_select
        else:
            collection = st.text_input(
                "Range / Collection",
                value=curr_collection,
                placeholder="e.g. Reserve Range · Single Vineyard · Classic Series",
                help="Groups products together on the dashboard."
            )

        # 2 — Label basics
        st.markdown(mlabel("2 — Label Basics"), unsafe_allow_html=True)
        c7, c8, c9 = st.columns(3)
        with c7: abv = st.number_input("ABV %", min_value=0.0, max_value=100.0, value=float(p.get("abv", 13.5)), step=0.1, format="%.1f")
        with c8: net_quantity = st.text_input("Net quantity", value=p.get("net_quantity", "750 mL"))
        with c9: lot_number = st.text_input("Lot number", value=p.get("lot_number", ""), placeholder="L2022-001")
        _dosage_opts = ["— Not applicable —"] + SPARKLING_DOSAGE
        sparkling_dosage = st.selectbox("Sparkling wine dosage", _dosage_opts, index=_dosage_opts.index(p.get("sparkling_dosage", "— Not applicable —")) if p.get("sparkling_dosage") in _dosage_opts else 0, help="Mandatory for sparkling wines under EU Reg. 2021/2117. Leave as 'Not applicable' for still wines.")
        _bbd_raw = p.get("best_before_date")
        _bbd_val = None
        if _bbd_raw:
            try: _bbd_val = date.fromisoformat(_bbd_raw)
            except (ValueError, TypeError): pass
        best_before_date = st.date_input("Best before date", value=_bbd_val, min_value=date(2020, 1, 1), max_value=date(2040, 12, 31), format="DD/MM/YYYY", help="Only required for de-alcoholized wines under EU regulations. Leave blank for standard wines.")

        # 3 — Ingredients
        st.markdown(mlabel("3 — Ingredients"), unsafe_allow_html=True)
        existing_ings = p.get("ingredients", ["Grapes", "Sulfur dioxide (E220)", "Yeast"])
        selected_common = st.multiselect("Common wine ingredients", COMMON_INGREDIENTS, default=[i for i in existing_ings if i in COMMON_INGREDIENTS])
        custom_ings = st.text_area("Additional ingredients (one per line)", value="\n".join(i for i in existing_ings if i not in COMMON_INGREDIENTS), placeholder="Potassium sorbate (E202)\nAscorbic acid (E300)", height=70)

        # 4 — Allergens
        st.markdown(mlabel("4 — Allergens"), unsafe_allow_html=True)
        existing_allergens = p.get("allergens", ["Sulphites"])
        selected_allergens = st.multiselect("Allergen declarations", COMMON_ALLERGENS, default=[a for a in existing_allergens if a in COMMON_ALLERGENS])

        # 5 — Nutrition
        st.markdown(mlabel("5 — Nutrition (per 100 mL)"), unsafe_allow_html=True)
        st.markdown(f'<div style="font-family:Space Grotesk,sans-serif;font-size:12px;color:{C["ink60"]};margin-bottom:8px;">Dry wine ≈ 70 kcal / 293 kJ per 100 mL.</div>', unsafe_allow_html=True)
        auto_calc_energy = st.checkbox("Auto-calculate energy from ABV & carbohydrates (EU formula)", value=p.get("auto_calc_energy", False), help="Uses EU Reg. formula: Energy (kJ) = (ABV% × 0.789 × 29) + (carbs × 17) + (protein × 17) + (fat × 37). Values entered below will be overridden on save.")
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

        # 6 — Packaging & Recycling
        st.markdown(mlabel("6 — Packaging & Recycling"), unsafe_allow_html=True)
        st.markdown(f'<div style="font-family:Space Grotesk,sans-serif;font-size:12px;color:{C["ink60"]};margin-bottom:8px;">Required for DPP packaging compliance (PPWR 2025).</div>', unsafe_allow_html=True)
        pkg = p.get("packaging", {})
        pa1, pa2 = st.columns(2)
        with pa1:
            bottle_material = st.selectbox("Bottle material", BOTTLE_MATERIALS, index=BOTTLE_MATERIALS.index(pkg.get("bottle_material", "Glass")) if pkg.get("bottle_material") in BOTTLE_MATERIALS else 0)
            label_material  = st.selectbox("Label material",  LABEL_MATERIALS,  index=LABEL_MATERIALS.index(pkg.get("label_material", "Paper")) if pkg.get("label_material") in LABEL_MATERIALS else 0)
        with pa2:
            closure_type     = st.selectbox("Closure type",     CLOSURE_TYPES,     index=CLOSURE_TYPES.index(pkg.get("closure_type", "Natural cork")) if pkg.get("closure_type") in CLOSURE_TYPES else 0)
            capsule_material = st.selectbox("Capsule material", CAPSULE_MATERIALS, index=CAPSULE_MATERIALS.index(pkg.get("capsule_material", "Tin")) if pkg.get("capsule_material") in CAPSULE_MATERIALS else 0)
        recycled_pct = st.number_input("Recycled glass content %", min_value=0, max_value=100, value=int(pkg.get("recycled_content_pct") or 0), step=1)
        recycling_instructions = st.text_area("Recycling instructions", value=pkg.get("recycling_instructions", ""), placeholder="Rinse bottle before recycling at glass bank. Remove cork and recycle separately.", height=70)

        # 7 — Carbon & Sustainability
        st.markdown(mlabel("7 — Carbon & Sustainability"), unsafe_allow_html=True)
        st.markdown(f'<div style="font-family:Space Grotesk,sans-serif;font-size:12px;color:{C["ink60"]};margin-bottom:8px;">Optional now — required under ESPR 2026. Leave at 0 if not yet measured.</div>', unsafe_allow_html=True)
        sus = p.get("sustainability", {})
        s1, s2 = st.columns(2)
        with s1: carbon_footprint = st.number_input("Carbon footprint (kg CO₂e / bottle)", min_value=0.0, value=float(sus.get("carbon_footprint_kg") or 0.0), step=0.01, format="%.2f")
        with s2: water_usage = st.number_input("Water usage (L / bottle)", min_value=0.0, value=float(sus.get("water_usage_l") or 0.0), step=0.1, format="%.1f")
        renewable_energy = st.checkbox("Produced using renewable energy", value=sus.get("renewable_energy", False))

        # 8 — Supply Chain
        st.markdown(mlabel("8 — Supply Chain & Provenance"), unsafe_allow_html=True)
        sc = p.get("supply_chain", {})
        sc1, sc2 = st.columns(2)
        with sc1:
            vineyard_name     = st.text_input("Vineyard name",     value=sc.get("vineyard_name", ""),     placeholder="e.g. Block 42 Estate")
            vineyard_country  = st.text_input("Vineyard country",   value=sc.get("vineyard_country", "Australia"))
            bottling_facility = st.text_input("Bottling facility",  value=sc.get("bottling_facility", ""), placeholder="e.g. Penfolds Magill Estate")
        with sc2:
            vineyard_region   = st.text_input("Vineyard region",    value=sc.get("vineyard_region", ""),   placeholder="e.g. Barossa Valley, SA")
            bottling_location = st.text_input("Bottling location",  value=sc.get("bottling_location", ""), placeholder="e.g. Nuriootpa, SA")
            importer_name     = st.text_input("EU importer",        value=sc.get("importer_name", ""),     placeholder="Required for EU sales")
        importer_address = st.text_input("EU importer address", value=sc.get("importer_address", ""), placeholder="Street, City, Country")

        # 9 — Certifications
        st.markdown(mlabel("9 — Certifications"), unsafe_allow_html=True)
        selected_certs = st.multiselect("Certification badges", COMMON_CERTS, default=[c for c in COMMON_CERTS if c in p.get("certifications", [])])
        custom_certs   = st.text_input("Other certifications (comma-separated)", value=", ".join(c for c in p.get("certifications", []) if c not in COMMON_CERTS))

        # 10 — Optional
        st.markdown(mlabel("10 — Optional"), unsafe_allow_html=True)
        storage_info = st.text_input("Storage information", value=p.get("storage_info", ""), placeholder="Store in a cool, dark place. Serve at 16–18°C.")
        website      = st.text_input("Producer website", value=p.get("website", ""), placeholder="https://www.winery.com.au")
        _currencies  = ["AUD", "EUR", "USD", "GBP", "NZD", "CAD"]
        op1, op2     = st.columns([1, 3])
        with op1: price_currency = st.selectbox("Currency", _currencies, index=_currencies.index(p.get("price_currency", "AUD")) if p.get("price_currency") in _currencies else 0)
        with op2: price_rrp = st.number_input("RRP (recommended retail price)", min_value=0.0, value=float(p.get("price_rrp") or 0.0), step=0.50, format="%.2f")

        st.markdown('<div style="height:12px;"></div>', unsafe_allow_html=True)
        submitted = st.form_submit_button("Save Product", type="primary", use_container_width=True)

        if submitted:
            if not name.strip():
                st.error("Wine name is required.")
            elif not producer_name.strip():
                st.error("Producer / winery name is required.")
            else:
                custom_list = [l.strip() for l in custom_ings.splitlines() if l.strip()]
                all_ings    = selected_common + [i for i in custom_list if i not in selected_common]
                all_certs   = selected_certs + [c.strip() for c in custom_certs.split(",") if c.strip() and c.strip() not in selected_certs]
                if auto_calc_energy:
                    calc_kj   = round((abv * 0.789 * 29) + (carb_g * 17) + (protein_g * 17) + (fat_g * 37))
                    calc_kcal = round(calc_kj / 4.184)
                    energy_kj, energy_kcal = float(calc_kj), float(calc_kcal)
                product = {
                    "id": p.get("id", str(uuid.uuid4())[:8]),
                    "name": (name or "").strip(), "vintage": (vintage or "").strip(), "variety": (variety or "").strip(),
                    "product_category": product_category, "pdo_pgi": (pdo_pgi or "").strip(),
                    "region": (region or "").strip(), "producer_name": (producer_name or "").strip(),
                    "collection": (collection or "").strip(),
                    "country": (country or "").strip(), "producer_address": (producer_address or "").strip(),
                    "abv": round(abv, 1), "net_quantity": (net_quantity or "").strip(), "lot_number": (lot_number or "").strip(),
                    "sparkling_dosage": sparkling_dosage if sparkling_dosage != "— Not applicable —" else None,
                    "best_before_date": best_before_date.isoformat() if best_before_date else None,
                    "auto_calc_energy": auto_calc_energy,
                    "ingredients": all_ings, "allergens": selected_allergens,
                    "nutrition": {"energy_kj": energy_kj, "energy_kcal": energy_kcal, "fat_g": fat_g, "saturated_fat_g": sat_fat_g, "carbohydrate_g": carb_g, "sugars_g": sugars_g, "protein_g": protein_g, "salt_g": salt_g},
                    "packaging": {"bottle_material": bottle_material, "closure_type": closure_type, "label_material": label_material, "capsule_material": capsule_material, "recycled_content_pct": recycled_pct or None, "recycling_instructions": (recycling_instructions or "").strip() or None},
                    "sustainability": {"carbon_footprint_kg": carbon_footprint or None, "water_usage_l": water_usage or None, "renewable_energy": renewable_energy},
                    "supply_chain": {"vineyard_name": (vineyard_name or "").strip() or None, "vineyard_region": (vineyard_region or "").strip() or None, "vineyard_country": (vineyard_country or "").strip() or None, "bottling_facility": (bottling_facility or "").strip() or None, "bottling_location": (bottling_location or "").strip() or None, "importer_name": (importer_name or "").strip() or None, "importer_address": (importer_address or "").strip() or None},
                    "certifications": all_certs, "certificates": p.get("certificates", []),
                    "storage_info": (storage_info or "").strip(), "website": (website or "").strip(),
                    "price_rrp": price_rrp or None, "price_currency": price_currency,
                    "status": p.get("status", "draft"),
                    "created_at": p.get("created_at", datetime.now().isoformat()),
                    "updated_at": datetime.now().isoformat(),
                }
                upsert_product(product)
                st.session_state.update({"page": "edit", "edit_id": product["id"], "_saved": True})
                st.rerun()

    # Certificate upload (outside form)
    if p.get("id"):
        if st.session_state.pop("_saved", False):
            st.success("Product saved.")

        # Product image
        st.markdown(mlabel("Product Image"), unsafe_allow_html=True)
        st.markdown(f'<div style="font-family:Space Grotesk,sans-serif;font-size:12px;color:{C["ink60"]};margin-bottom:8px;">Upload a bottle or label photo — displayed on the consumer e-label page.</div>', unsafe_allow_html=True)
        cur_img = p.get("product_image")
        if cur_img:
            img_col, btn_col = st.columns([3, 1])
            with img_col:
                st.markdown(f'<img src="data:image/jpeg;base64,{cur_img}" style="width:100%;max-width:280px;border-radius:12px;border:1px solid {C["ink08"]};" />', unsafe_allow_html=True)
            with btn_col:
                if st.button("Remove image", key="rm_img", type="secondary"):
                    cur = get_product(p["id"])
                    cur.pop("product_image", None)
                    cur.pop("product_image_filename", None)
                    upsert_product(cur); st.rerun()
        img_file = st.file_uploader("Upload product image", type=["png", "jpg", "jpeg", "webp"], label_visibility="collapsed", key="img_upload")
        if img_file:
            cur = get_product(p["id"])
            cur["product_image"] = base64.b64encode(img_file.read()).decode()
            cur["product_image_filename"] = img_file.name
            upsert_product(cur); st.rerun()

        st.markdown(mlabel("Certificate Documents"), unsafe_allow_html=True)
        st.markdown(f'<div style="font-family:Space Grotesk,sans-serif;font-size:12px;color:{C["ink60"]};margin-bottom:8px;">Upload PDFs — organic certificates, lab reports, export documents. Downloadable on the public label.</div>', unsafe_allow_html=True)

        for cert in p.get("certificates", []):
            cc1, cc2 = st.columns([4, 1])
            with cc1:
                st.markdown(f'<div style="padding:8px 0;font-family:Space Grotesk,sans-serif;font-size:13px;">📄 <strong>{cert["name"]}</strong>' + (f' — {cert["issuer"]}' if cert.get("issuer") else "") + (f' · expires {cert["expiry"]}' if cert.get("expiry") else "") + '</div>', unsafe_allow_html=True)
            with cc2:
                if st.button("Remove", key=f"rm_{cert['id']}", type="secondary"):
                    cur = get_product(p["id"])
                    cur["certificates"] = [c for c in cur.get("certificates", []) if c["id"] != cert["id"]]
                    upsert_product(cur); st.rerun()

        with st.form("cert_upload", clear_on_submit=True):
            cf1, cf2, cf3 = st.columns(3)
            with cf1: cert_name   = st.text_input("Certificate name", placeholder="Organic Certificate")
            with cf2: cert_issuer = st.text_input("Issuer",           placeholder="ACO Certification")
            with cf3: cert_expiry = st.text_input("Expiry date",      placeholder="2026-12-31")
            cert_file  = st.file_uploader("Upload certificate (PDF or Word)", type=["pdf", "doc", "docx"], label_visibility="collapsed")
            upload_btn = st.form_submit_button("Attach Certificate", type="primary")
            if upload_btn and cert_file and cert_name.strip():
                entry = {"id": str(uuid.uuid4())[:8], "name": cert_name.strip(), "issuer": cert_issuer.strip(), "expiry": cert_expiry.strip(), "filename": cert_file.name, "data": base64.b64encode(cert_file.read()).decode()}
                cur = get_product(p["id"])
                cur.setdefault("certificates", []).append(entry)
                upsert_product(cur); st.rerun()


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
        st.session_state["page"] = "dashboard"; st.rerun(); return

    # Marker lets CSS give this page its own white container
    st.markdown('<div class="qr-page-marker" style="display:none;"></div>', unsafe_allow_html=True)

    # Header — dark ink now that we're on white
    bc, tc = st.columns([0.12, 0.88])
    with bc:
        if st.button("←", type="secondary"):
            st.session_state["page"] = "dashboard"; st.rerun()
    with tc:
        st.markdown(f'<div style="font-family:Fraunces,serif;font-size:26px;font-weight:600;color:{C["ink"]};padding:6px 0;letter-spacing:-0.01em;">QR Code</div>', unsafe_allow_html=True)

    st.markdown(f'<div style="border-bottom:1px solid {C["paperEdge"]};margin:4px 0 16px;"></div>', unsafe_allow_html=True)

    label_url = get_label_url(pid)

    # Pre-compute QR bytes so we can embed image + use download button
    qr_bytes = make_qr_image(label_url) if QR_AVAILABLE else None
    qr_html = ""
    if qr_bytes:
        b64 = base64.b64encode(qr_bytes).decode()
        qr_html = (
            f'<div style="text-align:center;padding:8px 0 16px;">'
            f'<img src="data:image/png;base64,{b64}" style="width:200px;height:200px;border-radius:10px;" />'
            f'</div>'
            f'<div style="background:{C["cream"]};border:1px solid {C["eu"]}40;border-radius:10px;padding:10px 14px;margin-bottom:16px;">'
            f'<span style="font-family:JetBrains Mono,monospace;font-size:9px;font-weight:700;letter-spacing:0.12em;color:{C["eu"]};text-transform:uppercase;">EU Print Requirement</span>'
            f'<div style="font-family:DM Sans,sans-serif;font-size:12px;color:{C["ink"]};margin-top:3px;">Minimum print size: <strong>13 × 13 mm at 300 DPI</strong> as required by EU Reg. 2021/2117.</div>'
            f'</div>'
        )
    elif QR_AVAILABLE:
        qr_html = f'<div style="font-family:DM Sans,sans-serif;font-size:13px;color:{C["red"]};margin:12px 0;">Could not generate QR code.</div>'

    # All content in a single flat HTML block (no inner card — the container IS the card)
    st.markdown(
        # Product info
        f'<div style="border-left:3px solid {C["wine2"]};padding-left:14px;margin-bottom:14px;">'
        f'<div style="font-family:Fraunces,serif;font-size:20px;font-weight:600;color:{C["ink"]};letter-spacing:-0.01em;">{p["name"]} {p.get("vintage","")}</div>'
        f'<div style="font-family:DM Sans,sans-serif;font-size:13px;color:{C["ink2"]};margin-top:2px;">{p.get("producer_name","")}</div>'
        f'{_compliance_badges_html(p)}'
        f'</div>'
        f'<div style="border-top:1px solid {C["paperEdge"]};margin:0 0 16px;"></div>'
        # QR code + EU notice
        f'{qr_html}'
        # Label URL
        f'<div style="border-top:1px solid {C["paperEdge"]};margin:0 0 14px;"></div>'
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
                st.session_state.update({"page": "preview", "preview_id": pid}); st.rerun()
    elif not QR_AVAILABLE:
        st.warning("Run `pip install qrcode[pil]` to enable QR codes.")

    st.markdown('<div style="height:8px;"></div>', unsafe_allow_html=True)
    if st.button("Edit Product", type="secondary", use_container_width=True):
        st.session_state.update({"page": "edit", "edit_id": pid}); st.rerun()


# ── Router ────────────────────────────────────────────────────────────────────
def main():
    inject_css()
    if "label" in st.query_params:
        show_public_label(st.query_params["label"])
        return
    page = st.session_state.get("page", "dashboard")
    if page == "preview":
        show_public_label(st.session_state.get("preview_id"))
        st.markdown('<div style="height:16px;"></div>', unsafe_allow_html=True)
        if st.button("← Back", type="secondary", use_container_width=True):
            st.session_state["page"] = "qr"; st.rerun()
    elif page == "add":
        show_product_form()
    elif page == "edit":
        pid = st.session_state.get("edit_id")
        show_product_form(existing=get_product(pid) if pid else None)
    elif page == "qr":
        show_qr_page(st.session_state.get("qr_id"))
    else:
        show_dashboard()

if __name__ == "__main__":
    main()
