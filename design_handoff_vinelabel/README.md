# Handoff: VineLabel — Landing + Dashboard + New Product + QR

## Overview

Four screens of **VineLabel**, a SaaS that helps Australian wineries create the **EU Digital Product Passport (DPP)** required for every bottle of wine sold in the European Union since December 2023.

- **Landing** (`VineLabel Landing.html`) — public marketing hero.
- **Dashboard** (`VineLabel Dashboard.html`) — first screen after sign-in. Lists products grouped by category.
- **New Product** (`VineLabel New Product.html`) — full-page wizard to create / edit a DPP record.
- **QR** (`VineLabel QR.html`) — once a product is saved, this is the publish / print view: shows the generated QR code, compliance scores, EU print requirement, and the consumer label URL.

All four share one brand system (color, type, gradient veil, nav, hero photo) so a winemaker moves between them without a visual jolt. They use the **same `.stage` / `.nav` / paper-card** chrome described below.

## About the Design Files

The HTML files in this bundle are **design references** — working prototypes that show the intended look, type, color, copy, and interactions. **They are not production code to deploy as-is.**

Recreate them inside the target codebase, using its existing framework, component library, design system, and patterns (React / Next.js / Vue / Astro / SwiftUI / etc.). If there isn't a frontend codebase yet, choose a framework that fits the team and implement the designs there.

The `<style>` blocks inside each HTML file are pragmatic single-file stylesheets; re-express them using the codebase's preferred styling approach (Tailwind, CSS Modules, vanilla-extract, styled-components, SCSS tokens, etc.).

## Fidelity

**High-fidelity (hifi).** Final colors, type sizes, spacing, copy, and accent details are all locked. Reproduce them pixel-accurately. The wood-grain background photograph in `assets/wine-bg.jpg` is part of the design — not a placeholder.

## Files

- `VineLabel Landing.html`
- `VineLabel Dashboard.html`
- `VineLabel New Product.html`
- `VineLabel QR.html`
- `assets/wine-bg.jpg` — shared hero background photograph (1600 × 1067, watermark removed).

Navigation between screens is already wired:
- Landing **Sign in** + **Start free →** → Dashboard
- Dashboard **product thumbnail** → QR
- Dashboard **+ New Product** → New Product
- New Product **← back / breadcrumb Products** → Dashboard
- QR **← back / breadcrumb Products** → Dashboard
- QR **Edit Product** → New Product

---

# Shared design system (read this first)

## Background "stage"

All four screens use the same `.stage` element: full-viewport container with `assets/wine-bg.jpg` as a `background-size: cover; background-position: center right` image, layered with two `pointer-events: none` overlays for legibility:

**`.stage::before`** — left-darkening veil. Same on every screen:
```
linear-gradient(95deg,
  rgba(12,8,6,0.92)  0%,
  rgba(12,8,6,0.78) 28%,
  rgba(12,8,6,0.25) 55%,
  rgba(12,8,6,0.05) 80%),
radial-gradient(ellipse at 18% 50%, rgba(0,0,0,0.55) 0%, transparent 60%);
```

**`.stage::after`** — edge vignette:
```
radial-gradient(ellipse at center, transparent 55%, rgba(0,0,0,0.55) 100%);
```

Page bg color (behind the photo, in case it fails to load): `#0c0907` / `#1a0f08`.

Screens that pin a card to the viewport (**New Product**, **QR**) add `height: 100vh; overflow: hidden` to `.stage` so only the card's inner content scrolls. The landing and dashboard let the page scroll normally.

On **≤ 1000–1100 px** the gradient flips to vertical so the bottle no longer dictates the layout:
```
linear-gradient(180deg, rgba(12,8,6,0.92) 0%, rgba(12,8,6,0.88) 40%, rgba(12,8,6,0.92) 100%);
```
…and any viewport-locked card unlocks to natural height.

## Nav

Same `.nav` shell on every screen: padding `22px 56px`, flex row space-between.

**Left** — logo block (`.logo`, flex, gap 14 px):
- `.logo-mark` — 44 × 44 px square, radius 8 px, `background: #7a1d24`, Gloock-serif "V" 22 px, shadow `inset 0 0 0 1px rgba(255,255,255,0.08), 0 4px 14px rgba(0,0,0,0.4)`.
- `.logo-name` — "VineLabel" in Gloock serif 22 px, color `#f3ead9`.
- `.logo-sub` — "EU DPP STUDIO" in Inter 10.5 px, uppercase, `letter-spacing: 0.28em`, color `#b7a786`.

**Right** — varies per screen:
- Landing: **Sign in** (ghost button) + **Start free →** (solid wine button).
- Dashboard / New Product / QR: text links (**Products** · **Compliance** · **Help**) + `.user` pill.

**Buttons** (`.btn` base): Inter 14 px / weight 500, padding `11px 18px`, radius 8 px, transition `transform .15s, background .15s, border-color .15s`.

Variants:
- `.btn-ghost` (on dark) — text `#f3ead9`, border `rgba(243,234,217,0.22)`, background `rgba(243,234,217,0.04)`. Hover background `rgba(243,234,217,0.1)`.
- `.btn-solid` (on dark) — background `#7a1d24`, color `#f3ead9`. Hover `#9c2731` + `translateY(-1px)`. Shadow `0 6px 18px rgba(122,29,36,0.45), inset 0 1px 0 rgba(255,255,255,0.08)`.
- `.btn-lg` — Inter 15.5 px, padding `14px 22px`, radius 10 px.

**User pill (`.user`)** — pill shape, border `rgba(243,234,217,0.22)`, background `rgba(243,234,217,0.04)`, hover `0.1`. 32 × 32 px circular `.avatar` (gold `#c89a5a`, Gloock initial in `#15110d`) + Inter 13 px winery name + 10 px caret "▾".

**Nav link** (`.nav-link`) — Inter 14 px, color `rgba(243,234,217,0.7)`, hover `#f3ead9`. Active variant `.is-active` is `#f3ead9` with a 1 px `#c89a5a` underline (`border-bottom`).

## Cards (paper surfaces on dark)

Every paper surface on top of the wood uses the same recipe:
- Background `#f6efe0` (paper-card).
- Radius `14px` (small/medium cards) or `18px` (form / QR card).
- Shadow `0 12px 30px rgba(0,0,0,0.35), 0 2px 6px rgba(0,0,0,0.2)`.
- Text color `#15110d` (ink) for headings, `#2a221a` (ink-soft) for body, `#6e5a3d` (muted-dark) for labels/meta.

## Sticky-chrome card pattern (used by New Product + QR)

Both heavyweight detail screens share one structural recipe. Build it once as a layout component (e.g. `<DetailCard>`):

```
.card                 // standard paper-card, display:flex; flex-direction:column; flex:1 1 auto; min-height:0
├── .card-head        // padding 22px 28px; border-bottom; flex 0 0 auto. Holds back-btn + title + eyebrow + status chip
├── .card-scroll      // flex 1 1 auto; overflow-y:auto; min-height:0. Custom wine scrollbar.
└── .card-footer      // padding 18px 28px; border-top; background rgba(0,0,0,0.025); flex 0 0 auto. Actions row.
```

Custom scrollbar:
- `scrollbar-color: rgba(122,29,36,0.4) transparent` (Firefox).
- Webkit: 10 px wide, transparent track, thumb `rgba(122,29,36,0.35)` (hover `0.55`), `border-radius: 999px; border: 2px solid var(--paper-card)`.

**`.card-head`**:
- `.back-btn` — 40 × 40 px square, radius 10 px, border `var(--line)`, transparent bg, 18 px arrow. Hover `rgba(0,0,0,0.04)`.
- `.head-title` — Gloock serif 32 px / 1.05, flex 1.
- `.head-eye` — Caveat 22 px, color `#7a1d24`. Two-three word reassuring eyebrow (e.g. "a fresh label", "ready to print").
- `.save-chip` — inline-flex, padding `6px 12px`, radius 999 px, background `rgba(0,0,0,0.04)`, Inter 12 px / muted-dark. Leading 7 × 7 px olive dot with halo `box-shadow: 0 0 0 3px rgba(79,107,58,0.18)`. Default label: "Draft saved" (New Product) / "Published" (QR).

On `< 640 px` the eyebrow and save-chip disappear; the title and back arrow stay.

## Color tokens

| Token | Value | Use |
|---|---|---|
| `--ink` | `#15110d` | Deepest brand black |
| `--ink-soft` | `#2a221a` | Body text on paper |
| `--paper` | `#f3ead9` | Warm off-white, primary text on dark |
| `--paper-card` | `#f6efe0` | Card background on dark |
| `--paper-soft` | `#faf3e2` | Inner info card background (QR) |
| `--paper-input` | `#ede2c8` | Form input background |
| `--paper-deep` | `#ece1c8` | Recessed paper, thumbnail background |
| `--wine` | `#7a1d24` | Primary brand — buttons, logo mark, stat #1, section headers |
| `--wine-bright` | `#9c2731` | Wine hover |
| `--gold` | `#c89a5a` | Accent — eyebrows, dots, avatar, hand-script, active underline |
| `--olive` | `#4f6b3a` | Published / success / passing compliance score |
| `--amber` | `#b87527` | Warning / partial compliance score |
| `--muted` | `#b7a786` | Secondary text on dark |
| `--muted-dark` | `#6e5a3d` | Secondary text on paper |
| `--line` | `rgba(40,28,18,0.12)` | Dividers on paper |
| `--line-strong` | `rgba(40,28,18,0.22)` | Strong dividers / help icon border / secondary button border |

Text-on-photo opacities used: `0.82` (lede), `0.92` (bullets), `0.7` (nav-link rest), `0.55` (breadcrumbs).

## Typography

| Family | Source | Weights used |
|---|---|---|
| **Gloock** (serif) | Google Fonts | 400 (headlines, logo, product names, panel/form titles), 700 (stamp, stat numbers) |
| **Caveat** (handwritten) | Google Fonts | 500, 600, 700 |
| **Inter** (UI sans) | Google Fonts | 400, 500, 600, 700 |
| **ui-monospace** (system) | Local | URL display on QR page |

Type scale (px):
- Landing display headline `clamp(44, 5.6vw, 78)` / 1.02
- Panel title (dashboard) 36 / 1.1
- Detail-card head title (New Product / QR) 32 / 1.05
- Product name on QR strip 26 / 1.1 (Gloock)
- Stat number (dashboard) 56 / 1.0 (Gloock)
- Product name (dashboard row) 22 / 1.1 (Gloock)
- Group-name 18 / Inter 700
- Lede 18 / 1.6
- Form control text 15 / Inter 400
- Field label 13 / Inter 500
- Stat label 11 (Inter 600, tracked 0.32em)
- Section number 11 (Inter 700, tracked 0.28em, wine)
- Score chip 11 (Inter 600, tracked 0.18em)
- Info-card key 11 (Inter 600, tracked 0.28em, muted-dark)
- Pill 11.5 (Inter, tracked 0.18em)
- Caveat: landing eyebrow 28, panel/head eye 22, mood-strip 20, note 26, note arrow 44
- Logo name 22 / Logo subtitle 10.5 (Inter, tracked 0.28em)
- Button base 14, large 15.5, primary footer 15, Actions/Step 13
- Stamp big 32 (Gloock) / small caps 12.5 + 13.5
- Step rail items 13 / step number 12 (700)
- URL text 13 (monospace)

## Spacing & radius

- Page-edge gutter: 56 px desktop / 24 px mobile.
- Card radius: 18 px (form / QR card) / 14 px (cards, stats, new-product button) / 12 px (info card, footer button) / 10 px (form inputs, product row, back btn, large button) / 8 px (buttons, logo mark, copy button).
- Card internal padding: 16–36 px (QR section uses generous 36 px top / 32 px bottom).

## Shadows

- **Logo mark** — `inset 0 0 0 1px rgba(255,255,255,0.08), 0 4px 14px rgba(0,0,0,0.4)`
- **Primary button (landing)** — `0 6px 18px rgba(122,29,36,0.45), inset 0 1px 0 rgba(255,255,255,0.08)`
- **New Product CTA (dashboard)** — `0 10px 24px rgba(122,29,36,0.45), inset 0 1px 0 rgba(255,255,255,0.1)`
- **Card-footer primary button** — `0 8px 20px rgba(122,29,36,0.45), inset 0 1px 0 rgba(255,255,255,0.1)`
- **Cards** — `0 12px 30px rgba(0,0,0,0.35), 0 2px 6px rgba(0,0,0,0.2)`
- **QR frame** — `0 10px 24px rgba(0,0,0,0.16), inset 0 0 0 1px rgba(255,255,255,0.4)`
- **Stamp (landing)** — `0 0 0 1.5px rgba(255,255,255,0.5) inset, 0 0 36px rgba(0,0,0,0.6)`
- **Note text shadow (landing)** — `0 2px 12px rgba(0,0,0,0.7)`

---

# Screen 1 — Landing / Hero

## Purpose

Convince an Australian winemaker that exporting to Europe is easier with VineLabel, and convert them to start a free account.

## Layout

`.stage` → `.nav` + `.hero` (grid `minmax(0, 1fr) minmax(0, 1.05fr)`, 40 px gap, 40 px top / 56 px sides / 80 px bottom padding, `min-height: calc(100vh - 88px)`, items center-aligned) + `.mood-strip` (bottom rule, 18 px / 56 px / 28 px padding).

Copy column ≤ 620 px. Right column shows the bottle from the background image plus two decorative overlays.

**Responsive (≤ 1000 px):** single-column grid; wax stamp moves to bottom-right and shrinks; "every bottle gets one" callout hidden. At ≤ 560 px Sign-in button + logo subtitle disappear.

## Components

### Copy column
- **Pill** — "EU Digital Product Passport · Built for Australia". Inline-flex, gap 10 px, padding `6px 12px 6px 8px`, radius 999 px, background `rgba(243,234,217,0.06)`, border `rgba(243,234,217,0.14)`. Inter 11.5 px uppercase tracked 0.18em, color `#b7a786`. 7 × 7 px gold dot with halo `box-shadow: 0 0 0 3px rgba(200,154,90,0.18)`. 24 px bottom margin.
- **Eyebrow** — "a smoother way to ship into Europe". Caveat 28 px, color `#c89a5a`, preceded by a 38 × 1 px gold rule (`opacity: 0.7`). 14 px bottom margin.
- **Title** — "Compliance," in Gloock weight 400, `clamp(44px, 5.6vw, 78px)`, line-height 1.02, `text-wrap: balance`. Accent "without the complexity." in Caveat weight 700, `0.78em` relative, `display: block`, `white-space: nowrap`, color `#c89a5a`. 22 px bottom margin.
- **Lede** — Inter 18 px / 1.6, color `rgba(243,234,217,0.82)`, max-width 52 ch, bottom margin 26 px:
  > Since **December 2023**, every bottle sold in Europe needs a **QR code** linked to its compliance details — ingredients, nutrition, allergens, and sustainability info. VineLabel makes it easy: fill in your details once, and we generate the QR code and consumer page for every bottle.
- **Pros list** — 3 rows, gap 12 px, bottom margin 32 px. Each row uses a 24 × 24 px gold check chip + Inter 16 px / 1.45 text.
  1. **All EU-required fields,** checked as you type — no guessing what's missing.
  2. **One simple dashboard** for every wine. No more spreadsheets at midnight.
  3. **Built with Australian wineries** shipping to Europe.
- **CTA** — single primary button **Start free — 2 labels included.**

### Right column
- **Wax stamp (`.stamp`)** — 148 × 148 px circle, `top: 6%; right: 4%`, rotated `-14°`. 3 px white border, inner dashed ring at `inset: 7px`. Three stacked all-white lines: **COMPLIANT** (Inter 12.5 px / 700, uppercase tracked 0.32em), **EU DPP** (Gloock 700, 32 px, NBSP between EU and DPP), **READY** (Inter 13.5 px / 700, uppercase tracked 0.24em).
- **Hand-script note (`.note`)** — "every bottle gets one ↓" pointing at the QR label on the photo. Prototype: `position: absolute; top: 28%; left: 52%; transform: translateX(-50%) rotate(-3deg); width: 220px; text-align: center;`. Caveat 26 px, white, text-shadow `0 2px 12px rgba(0,0,0,0.7)`. Arrow on its own line at 44 px. Hide on ≤ 1000 px.

### Mood strip
Bottom rule. Flex row, 18 px gap, 18 px top / 28 px bottom padding. Left/right `.hr` flex-grow at 1 px height. Center: "pour a glass · take your time" in Caveat 20 px / color `#c89a5a`.

---

# Screen 2 — Products Dashboard

## Purpose

Landing screen after sign-in. Shows the winery's product summary at a glance and lets them open / edit / create products.

## Layout

`.stage` → `.nav` → `.page` (grid `minmax(0, 760px) minmax(0, 1fr)`, gap 40 px, padding `12px 56px 80px`, `min-height: calc(100vh - 88px)`). Left grid item: products panel. Right grid item: empty `.right-spacer` so the bottle shows.

**Responsive:** ≤ 1100 px → single column; ≤ 640 px → stats become single column, product rows wrap.

## Components

### Panel header
- Title (`.panel-title`) — Gloock 36 px, color `#f3ead9`.
- Eyebrow (`.panel-eye`) — Caveat 22 px, color `#c89a5a`. Prototype copy: "welcome back, Sarah".

### Stat cards
Three cards in a `1fr 1fr 1fr` grid, 14 px gap. Each card uses standard recipe with padding `22px 18px 18px`. `.stat-num` — Gloock 56 px / 1.0.
- Default `#7a1d24` (wine), `.is-published` → `#4f6b3a` (olive), `.is-drafts` → `#2a221a` (ink-soft).
- `.stat-label` — Inter 11 px / 600, uppercase tracked 0.32em, color `#6e5a3d`.

Prototype values: **2 Products** / **0 Published** / **2 Drafts**.

### Category group (`.group`, native `<details>`)
Standard card. `summary.group-summary` — flex row, gap 12 px, padding `16px 20px`, Inter 16 px / 600, color `#7a1d24`. Leading 24 × 24 px circular `.chev` (background `rgba(122,29,36,0.08)`, color wine, 12 px "▶") rotates to 90° when `[open]`. Body has `.group-head` (Inter 18 px / 700 name + Inter 11 px tracked-meta separated by 3 × 3 px dots) above the product rows.

### Product row (`.product`)
Flex row, gap 16 px, padding `12px 14px`, radius 10 px, border `var(--line)`, background `#fbf5e6`, margin-bottom 10 px. `::before` — 3 px rounded wine-red accent bar on the left edge. 54 × 54 px `.thumb` (radius 10 px, background `#ece1c8`) holds SVG product image. `.product-name` — Gloock 22 px. `.product-meta` — Inter 13 px / muted-dark, format `{varietal} · {region}`. Actions: `.actions-btn` (pill button) + `.badge` (pill — neutral `draft` or olive `.is-published`).

**The product thumbnail is a link to the QR page.** Each product opens directly into its publish view; clicking the Actions menu is for edit/duplicate/delete.

### + New Product button (`.new-btn`)
Full-width block, padding 18 px, radius 14 px, background `#7a1d24`, color `#f3ead9`, Inter 16 px / 600. 22 × 22 px circular `.plus` chip with 16 px "+". Hover `#9c2731`, lift. Links to New Product screen.

### Settings (`.settings`, native `<details>`)
Same card recipe. Summary uses neutral chev + gold "✦" icon + Inter 15 px / 600. Body rows: flex space-between, padding `10px 0`, dashed border-bottom. Prototype rows: Winery / Default importer / Label language / Plan.

---

# Screen 3 — New Product

## Purpose

Full-page wizard to create a new EU DPP entry (or edit an existing one). Form lives on the left over the dark veil; bottle background shows on the right. Uses the **sticky-chrome card pattern** described above.

## Layout

- `.stage` locked to `height: 100vh; overflow: hidden`.
- `.page` — grid `minmax(0, 780px) minmax(0, 1fr)`, gap 40 px, padding `12px 56px 24px`, `height: calc(100vh - 88px)`.
- Left `.left-col` — flex column: breadcrumb at top, then `.card` (which here is named `.form-card`) filling the rest.

**Responsive (≤ 1100 px):** `.stage` unlocks; grid collapses; `.card-scroll` becomes natural-height (no inner scroll); page scrolls normally.

## Components

### Breadcrumb (`.crumbs`)
Flex row, gap 10 px, font 13 px, color `rgba(243,234,217,0.55)`. Links at `0.85` opacity. Prototype: `Products / New product`.

### Card head
Standard `.card-head` (see shared pattern). Title "New Product", eyebrow "a fresh label", chip "Draft saved".

### Step rail (`.steps`)
Flex row, no gap, padding `18px 28px 4px`, background `linear-gradient(180deg, rgba(122,29,36,0.04), transparent)`, dashed border-bottom. Overflow-x auto on narrow viewports.

Each `.step`: flex row gap 10 px, padding `8px 14px`, font 13 px / muted-dark. 2 px transparent border-bottom (`margin-bottom: -1px`). 22 × 22 px circular `.n` numeral chip (Inter 12 px / 700).
- `.is-active` — text `#7a1d24` / 600, border-bottom wine, chip wine / paper.
- `.is-done` — chip `rgba(79,107,58,0.15)` / olive, content "✓".

Prototype rail: 1 Product identity (active) · 2 Composition · 3 Nutrition · 4 Sustainability · 5 Importer & QR.

### Section (`.section`, native `<fieldset>`)
Padding `26px 28px 30px`, border-bottom between sections. `.section-head` has `.section-num` (Inter 11 px / 700, uppercase tracked 0.28em, wine, `white-space: nowrap`) formatted `N — Section name`.

### Field grid (`.grid`)
Default `1fr 1fr` gap `14px 16px`. Variants: `.grid.thirds`, child `.full` (spans all columns).

### Field (`.field`)
Flex column, gap 6 px. Each label wraps its text in `.label-text` (inline-flex baseline) so the required `*` hugs the field name; the `space-between` only triggers when a `.help` button is present.
- `.req` — color wine, 2 px left margin.
- `.help` — 18 × 18 px circular button with `?`, hover `rgba(0,0,0,0.04)`. Should open a popover with regulatory context in production.

### Control
Width 100 %, padding `12px 14px`, radius 10 px, border `var(--line)`, background `#ede2c8` (paper-input), Inter 15 px, color ink-soft. Focus: border wine, box-shadow `0 0 0 3px rgba(122,29,36,0.15)`. `select.control` adds inline-SVG caret + right padding 38 px. `textarea.control` — resize vertical, min-height 92 px, line-height 1.5.

### Tag input (`.tags`)
Flex wrap, gap 8 px, padding `10px 12px`, radius 10 px, border, background paper-input. `.tag` — pill, background `rgba(122,29,36,0.1)`, color wine, font 13 px / 500, trailing `.x` at 12 px / 0.7 opacity. `.tag-input-blank` — placeholder.

### Checkbox grid (`.checks`)
`1fr 1fr` or `.checks.three` for thirds. Native checkboxes at 16 × 16 px with `accent-color: var(--wine)`.

### Card footer
Standard `.card-footer` shell. `.footer-meta` (Inter 13 px / muted-dark, `Step N of M · saved Xm ago`) + `.footer-actions` (Save & close / Preview label / **Continue → {next}**).

## Form data shape (starting point)

```ts
type NewProduct = {
  identity: {
    wineName: string;          // required
    vintage?: string;
    category: 'Wine' | 'Sparkling wine' | 'Fortified wine' |
              'Dealcoholised wine' | 'Aromatised wine'; // required
    grapeVariety?: string;
    region?: string;
    pdoPgi?: string;
    producer: string;          // required
    countryOfOrigin?: string;  // default 'Australia'
    producerAddress?: string;
    range?: string;
  };
  composition: {
    abvPercent: number;        // required
    netVolumeMl: number;       // required
    ingredients: string[];     // required, order matters
    allergens: ('sulphites'|'egg'|'milk'|'fish'|'tree-nuts'|'none')[]; // required
  };
  nutrition_per_100ml: {       // required for nutrition table
    energyKj: number; energyKcal: number;
    fatG?: number; saturatesG?: number;
    carbsG?: number; sugarsG?: number;
    proteinG?: number; saltG?: number;
    labReferencePdfUrl?: string;
  };
  sustainability: {
    bottleMaterial: 'glass-recyclable' | 'glass-recycled-content' |
                    'lightweight-glass' | 'pet' | 'aluminium';
    closure: 'natural-cork' | 'agglo-cork' | 'screw-cap' |
             'glass-stopper' | 'crown-cap';
    recyclingInstructions: string[];
    certifications: string[];
    story?: string;            // ≤ 220 chars
  };
  // step 5 (Importer & QR) not yet designed
};
```

---

# Screen 4 — QR / Publish View

## Purpose

Once a product is saved (draft or published), this is the screen the winemaker reaches to **get the QR code onto the bottle**. It shows:

- which product they're looking at (thumbnail + name + producer);
- compliance scores so they know what's still incomplete;
- the QR code itself, on a print-ready white card;
- the EU print-size requirement;
- the consumer-facing label URL the QR resolves to;
- actions to download the QR, preview the consumer label, or edit the product.

It uses the **same sticky-chrome card pattern** as New Product, but the body is content rather than form fields.

## Layout

Identical shell to New Product: `.stage` locked `height: 100vh; overflow: hidden`, `.page` grid `minmax(0, 780px) minmax(0, 1fr)`, gap 40 px, padding `12px 56px 24px`, `height: calc(100vh - 88px)`.

**Responsive:** ≤ 1100 px unlocks the card; ≤ 640 px the QR shrinks (`--qr-size: 200px`), the footer goes single-column, info cards reduce padding.

## Components

### Breadcrumb
`Products / {Product name} / QR Code`. Same style as New Product.

### Card head
Standard `.card-head`. Title "QR Code", eyebrow "ready to print", chip "Published" (olive dot signals product is live).

### Product summary strip (`.product-strip`)
- Flex row, gap 18 px, padding `20px 28px`, border-bottom. Wine-red 3 px accent bar pseudo-element on the left edge (matches dashboard product row).
- **`.product-thumb`** — 76 × 76 px, radius 12 px, background `#2a1212`, holds SVG product image.
- **`.product-name`** — Gloock 26 px / 1.1.
- **`.product-sub`** — Inter 14 px / muted-dark. Producer / winery name.
- **`.scores`** — flex wrap, gap 8 px. Each `.score` is a pill:
  - Inline-flex, padding `6px 12px`, radius 999 px, border `var(--line)`, Inter 11 px / 600 uppercase tracked 0.18em, background `rgba(0,0,0,0.02)`, color muted-dark.
  - 16 × 16 px circular `.glyph` chip inside (Inter 11 px / 700 letter or symbol).
  - Variants:
    - `.is-ok` — color `#4f6b3a` (olive), border `rgba(79,107,58,0.4)`, background `rgba(79,107,58,0.08)`, glyph chip `rgba(79,107,58,0.18)`. Use for ≥ 95 % completion. Default glyph: `✓`.
    - `.is-warn` — color `#b87527` (amber), border `rgba(184,117,39,0.45)`, background `rgba(184,117,39,0.08)`, glyph chip `rgba(184,117,39,0.18)`. Use for partial completion (< 95 %). Default glyph: `!`.
  - Each chip text format: `{scope} {percent}%`.

Prototype values:
  - **EU E-Label 100%** (`.is-ok`)
  - **Packaging 60%** (`.is-warn`)
  - **DPP Carbon 66%** (`.is-warn`)

Wire each chip to navigate to the relevant section of the New Product form (anchor scroll on the matching step), so users can fix incomplete scores.

### QR section (`.qr-section`)
Padding `36px 28px 32px`, centered grid, border-bottom.

**`.qr-frame`** — Print-style white card holding the QR:
- Background `#ffffff`, padding 22 px, radius 18 px, border `var(--line)`, shadow `0 10px 24px rgba(0,0,0,0.16), inset 0 0 0 1px rgba(255,255,255,0.4)`.

**`.qr`** — the QR code itself. SVG, `--qr-size: 260px` (desktop) / `200px` (mobile). Cells fill `var(--ink)`. **In production, render a real QR** (e.g. `qrcode` npm or server-side library) encoding the product's consumer URL. The prototype draws a deterministic decorative bitmap with proper finder squares + an alignment square purely so the page renders without a network call; **swap it out**.

QR generation tips:
- Use error-correction level **Q** (25 %) or **H** (30 %) — there will sometimes be a small logo overlay in future iterations.
- Render at least at the displayed pixel size × 4 (≥ 1024 px) for downloadable PNG so it stays sharp when scaled up for label print.

### Info block (`.info-block`)
Two stacked `.info-card`s, each background `#faf3e2` (paper-soft), radius 12 px, border, padding `14px 18px`, margin-bottom 14 px.

- `.k` — Inter 11 px / 600, uppercase tracked 0.28em, color muted-dark. 4 px bottom margin.
- `.v` — Inter 14 px / 1.55, color ink-soft. `<strong>` brightens to ink / weight 600.

Two cards in prototype:
1. **EU print requirement** — "Minimum print size: **13 × 13 mm at 300 DPI** as required by EU Reg. 2021/2117."
2. **Label URL** (`.info-card.url`) — `.v` uses `ui-monospace` 13 px in wine red. Layout: `.url-row` flex space-between with a `.copy-btn` (pill, Inter 12 px / 600, padding `7px 12px`, radius 8 px, border, transparent). Clicking copies via `navigator.clipboard.writeText`, swaps label to "Copied!" for 1.2 s, then restores.

### Card footer (`.card-footer`)
Two-column grid (`1fr 1fr`, gap 12 px) plus a centered Edit Product link spanning both columns underneath.

Buttons at this scale are taller than elsewhere: Inter 15 px / 600, padding `14px 20px`, radius 12 px. Both have leading SVG icons (24 × 24, stroke 2.2):
- **Download QR** — `.btn-primary` (wine, white text, lift on hover). Icon: down-arrow into tray.
- **Preview Label** — `.btn-secondary` (ink text, border `var(--line-strong)`, transparent). Icon: eye.
- **Edit Product** — `.edit-link`, full-width centered, padding 12 px, font 14 px / ink-soft, dashed top border, radius 8 px, hover `rgba(0,0,0,0.03)`. Routes to New Product (edit mode).

## QR page data shape

```ts
type ProductQRView = {
  product: {
    id: string;
    name: string;             // "Madeli Test"
    producer: string;         // "Penfolds"
    thumbnailUrl: string | null;
    status: 'draft' | 'published';
  };
  scores: Array<{
    scope: 'EU E-Label' | 'Packaging' | 'DPP Carbon' | string;
    percent: number;          // 0–100
    href?: string;            // deep-link into edit form for that scope
  }>;
  consumerUrl: string;        // "https://vinelabel.eu/l/6dfcf646"
  qrSvg: string;              // rendered QR svg from server, or use client-side library
  printSpec: {
    minWidthMm: number;       // 13
    minHeightMm: number;      // 13
    minDpi: number;           // 300
    regulation: string;       // "EU Reg. 2021/2117"
  };
};
```

`scores[i].percent` ≥ 95 → `.is-ok`; else `.is-warn`. Round to nearest whole.

## Interactions & Behavior

### Landing
Buttons hover-lift `-1px` + color shift to `#9c2731` (150 ms ease). Both Sign-in and Start-free link to the dashboard (swap with real auth flow). No client state.

### Dashboard
- `<details>` drive Red wine + Settings expand/collapse. Replace with the codebase's accordion / disclosure primitive.
- **Product thumbnail** → opens that product's QR view directly.
- **Actions button** is a placeholder for a per-product menu — Open, Edit fields, Duplicate, Delete, Publish.
- **+ New Product** routes to New Product.
- Badge state: `draft` (neutral pill) or `published` (olive pill, `.is-published`).
- No drag / sort yet; render in API order grouped by category.
- Empty state (zero products) not yet designed.

### New Product
- Sticky header + footer; only `.card-scroll` overflows.
- Wire each `.step` to its `<fieldset>` (anchor scroll inside `.card-scroll`, update `.is-active` / `.is-done`). When step changes, update footer's "Continue →" label + meta.
- Help `?` opens a small popover with regulatory context.
- Tag inputs: implement as real chip-input components.
- Draft autosave on field blur; update the meta line from server response.
- "Preview label" opens the consumer page (separate screen, not yet designed).
- "Save & close" returns to Dashboard with the product persisted as a draft.
- Validation: required fields enforced on Continue; invalid fields get a `border-color: var(--wine)` plus a hint message below in the same red.

### QR
- The QR SVG is rendered server-side (or via a QR npm) from `product.consumerUrl`. Re-render only when the URL changes.
- **Copy URL**: `navigator.clipboard.writeText(consumerUrl)` with the optimistic "Copied!" pulse.
- **Download QR**: trigger a download of a high-resolution PNG (≥ 1024 px on the short edge) **and** an SVG, ideally as a small zip — wineries put the QR onto printed labels and need vector. The prototype's button is a stub (`alert`).
- **Preview Label**: opens the consumer page (the URL the QR resolves to) in a new tab.
- **Edit Product**: routes to New Product (edit mode) for this product.
- **Score chips** are click targets; each navigates into the New Product form at the corresponding step's anchor.
- **Status chip** at top reflects `product.status`: olive dot + "Published" for `published`; if `draft`, use a neutral chip — "Draft" with a muted-dark dot — and surface a "Publish" CTA next to the action buttons.

## State Management

### Landing
Static. No state.

### Dashboard
```
{
  user: { name, initial, winery, plan },
  groups: [
    { id, label, products: [ { id, name, varietal, region, status, thumbnailUrl } ] }
  ]
}
```
Stats cards derive from `groups` — don't ship them separately.

### New Product
Form holds the `NewProduct` object. Track `currentStep`, `completedSteps[]`, `lastSavedAt`. Each step is its own slice; autosave per slice.

### QR
Receives `ProductQRView` keyed by product id. Read-only screen with three side-effects (copy, download, navigate to edit / preview).

## Assets

- **`assets/wine-bg.jpg`** — primary hero photograph. 1600 × 1067, JPEG. Used by **all four** screens — serve responsively (`<picture>` + `srcset`, AVIF/WebP) in production.
- Product thumbnails (grape cluster, wine glass) are inline SVG placeholders — replace with uploaded product photography.
- QR is rendered SVG. The prototype's decorative SVG must be replaced with a real QR (encode `product.consumerUrl`).
- All other "imagery" is CSS — stamp, pill, check icons, accent rules, dropdown caret SVG inline, scrollbar styling, score-chip glyphs, footer-button icons.

## Accessibility Notes

- Text-on-photo: the dark gradient veils carry the contrast. Verify ≥ 4.5:1, especially the lede on landing (`rgba(243,234,217,0.82)`), nav links (`0.7`), breadcrumbs (`0.55`).
- `.right-spacer` / `.right` asides are decorative (`aria-hidden="true"` in the prototype).
- Wax stamp on landing: `role="img"` with `aria-label="EU DPP Ready"`.
- `<details>` / `<fieldset>` / `<label>` for / native form controls used throughout — preserve keyboard / screen-reader behavior.
- Step rail should be `role="tablist"` with `role="tab"` items in the target framework.
- QR SVG should carry an `aria-label` summarising what the QR encodes (e.g. "QR code for the consumer label, opens vinelabel.eu/l/6dfcf646"). Provide the URL as a focusable, copyable element below the QR for users who can't scan.
- The compliance score chips should be focusable buttons / links (not bare spans) so keyboard users can jump into the corresponding edit step.
- Custom focus rings should follow the rest of the codebase; the prototype shows a wine-tinted focus ring on `.control` and defers to the browser default elsewhere — match that pattern across the app.

## Implementation Notes for Claude Code

1. **Map tokens into the existing theme system first.** All four screens share one token set; don't fork them per screen.
2. **Hero photograph is shared** — single first-class asset used by every layout. Serve responsively.
3. **Type pairing carries the brand voice**: Gloock for editorial seriousness + product names + stat numerals + form / QR headlines; Caveat for the handwritten "wine farm" warmth (eyebrows, mood strip, head-eye); Inter for utility / UI; system mono for the consumer URL on the QR page. Do not substitute.
4. **Build the sticky-chrome card pattern once** as a `<DetailCard>` (or equivalent) and reuse it in New Product and QR. It owns the `.card` / `.card-head` / `.card-scroll` / `.card-footer` layout and the custom scrollbar. The two screens only differ in what they put inside the head and footer slots and what content fills the scroll area.
5. **Stat numerals on the dashboard** must use Gloock at the prototype's pixel size — that scale is the moment of brand on the dashboard.
6. **`<details>` collapsibles** in the dashboard prototype map to your accordion / disclosure primitive. Preserve the chev-rotate-on-open and the wine-red color on the "Red wine" summary text.
7. **Product row's left accent bar** (3 px wine-red strip) is the brand decoration distinguishing a product card from a generic row. Also used at 3 × {strip-height} on the QR product summary strip. Keep it. Add status-dependent variants later (olive bar for published, gold for in-review).
8. **The "EU DPP READY" wax stamp** on landing is built entirely in CSS. Recreate as `<EuDppStamp />`; reusable elsewhere.
9. **New Product form**: build as a wizard, not one giant page. Each step is its own component / route, sharing the `<DetailCard>` chrome via a layout component.
10. **Help icons** ("?") deserve a real `<Popover>` with WCAG-compliant trigger (Enter/Space to open, Esc to close). The prototype's `cursor: help` is not enough.
11. **QR generation must be real.** Use a maintained QR library (`qrcode` for Node / `qrcode.react` for client) and render at least at 4× the displayed size when producing downloadable PNG. Encode `product.consumerUrl`. Use error-correction Q or H. Don't ship the prototype's decorative SVG.
12. **Download QR** should bundle both PNG (≥ 1024 px) and SVG into a zip; wineries need both raster and vector for label print at multiple scales. Filename pattern: `{producerSlug}-{productSlug}-qr.{ext}`.
13. **Score-chip thresholds** are placeholders. Confirm with product the actual cut-offs (e.g. < 60 % red / 60–94 % amber / ≥ 95 % olive) and add a `.is-bad` variant if needed.
14. **The hand-script note** on landing points at the QR on the photo. If you change the photo or its aspect, re-position the note at the target viewport to land on the QR; brand-critical detail.
15. **Below the fold doesn't exist yet** on landing or dashboard. The **consumer-facing label page** (what the QR scans to) and the **empty state** for a winery with zero products are also not yet designed — flag for the next pass.
16. **Copy is final** on the marketing surfaces. Don't paraphrase the lede or bullets on landing without product confirmation — wording was tuned to feel calm and avoid jargon.
