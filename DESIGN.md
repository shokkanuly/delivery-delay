# Design System: SitePulse

Tokens live in [`static/design/tokens.css`](static/design/tokens.css). The HTML
console links the file and uses the light theme; the Streamlit dashboard inlines
it with the dark theme. `tests/test_design_system.py` guards the rules below.
Change a colour in the token file, never in markup.

## 1. Visual Theme & Atmosphere

A site office at 07:00: the manager has ten minutes before the first truck is due
and needs to know which delivery will slip and which crane is free. The interface
is **calm, dense and legible**, like a well-kept dispatch board. It is not a
marketing page. Neutral surfaces carry the data, one orange accent marks what needs
action, and every number says what backs it.

- **Density 7, "Cockpit Balanced":** many numbers per screen, grouped by border and
  whitespace rather than stacked cards.
- **Variance 3, "Predictable":** consistent grids, so the same metric sits in the
  same place every morning. This is an operational tool, so there is no hero
  section and no asymmetric showpiece layout.
- **Motion 2, "Static Restrained":** the only perpetual motion is the live-status
  dot. Numbers never animate in, because a moving number reads as an unstable one.

## 2. Color Palette & Roles

One Zinc neutral ramp, one accent, four status colours. Status colours carry
meaning (risk bands, claim badges) and are never used as decoration.

| Token | Light | Dark | Role |
|---|---|---|---|
| `--sp-bg` | Canvas Zinc `#FAFAFA` | Zinc-950 `#09090B` | Page background |
| `--sp-surface` | Pure Surface `#FFFFFF` | Charcoal `#18181B` | Panels, inputs |
| `--sp-surface-2` | Zinc-100 `#F4F4F5` | Zinc-800 `#27272A` | Table headers, hover rows |
| `--sp-border` | Zinc-200 `#E4E4E7` | Zinc-800 `#27272A` | 1px structure lines |
| `--sp-border-strong` | Zinc-300 `#D4D4D8` | Zinc-700 `#3F3F46` | Hover and focus borders |
| `--sp-text` | Charcoal Ink `#18181B` | Zinc-50 `#FAFAFA` | Primary text, key numbers |
| `--sp-text-2` | Zinc-600 `#52525B` | Zinc-400 `#A1A1AA` | Body copy, descriptions |
| `--sp-text-3` | Zinc-500 `#71717A` | Zinc-500 `#71717A` | Metadata, provenance lines |
| `--sp-chrome` | Charcoal `#18181B` | `#111113` | Navigation rail (dark in both themes) |
| **`--sp-accent`** | **Signal Orange `#E0643C`** | **`#E0643C`** | The one accent: primary actions, active nav, "act on this" |
| `--sp-ok` | `#2F855A` | `#4FB387` | Green risk band; sanity-check badge |
| `--sp-warn` | `#B7791F` | `#D69E2E` | Yellow risk band; estimate badge |
| `--sp-risk` | `#C53030` | `#E26D6D` | Red risk band; errors |
| `--sp-info` | `#2B6CB0` | `#63A4E0` | Correctness-invariant badge; neutral highlights |

Signal Orange is construction-safety orange with saturation held at 73%. It is
the only colour that asks for attention. Tints use
`color-mix(in srgb, var(--token) N%, transparent)`, never new hex values.

## 3. Typography Rules

- **Sans (UI and display):** `Geist`, weights 400–700. Headlines use weight 600
  with −0.02em tracking at 2.1rem. Hierarchy comes from weight and colour, not size.
- **Mono (numbers, keys, badges):** `Geist Mono`. KPI values, access keys,
  timestamps and badge labels use it, so digits align in columns.
- **Body:** 14px base, 1.55 line-height, prose blocks capped at about 65ch.
- **Banned:** Inter; every serif (including the retired Instrument Serif) in either UI.

## 4. The Claim-Badge Vocabulary

Every number shown to a customer or juror carries exactly one badge that says
what backs it. These five are the only badges allowed:

| Badge | Class | Meaning | Example |
|---|---|---|---|
| **Correctness Invariant** | `sp-badge sp-badge--invariant` (legacy: `badge-guarantee`) | A tested property of the code. Not a measure of business impact. | "0 double-bookings" |
| **Estimate** | `sp-badge sp-badge--estimate` (legacy: `badge-estimate`) | Statistical or assumption-based; not yet measured on a real site. | "$103k losses avoided" |
| **Synthetic Data** | `sp-badge sp-badge--synthetic` | A count or result on the demo dataset. | "260 bookings" |
| **Sanity Check** | `sp-badge sp-badge--check` | A guard-rail number that keeps an estimate honest. | "2.9% of logistics budget" |
| **Operating Input** | `sp-badge sp-badge--input` | A value the user typed in. | "Machinery run cost" |

Never put "Correctness Invariant" on a money figure, and never call an estimate
"proven".

## 5. Component Stylings

- **Buttons:** flat. Primary buttons use an accent fill with `--sp-on-accent` text;
  secondary buttons are outlined in `--sp-border-strong`. On press they move 1px
  down (`transform: translateY(1px)`). No glows, no gradients.
- **Panels:** `--sp-surface` with a 1px `--sp-border` and radius `--sp-radius`
  (10px). Use elevation only for modals. Inside dense views, separate groups with
  borders or whitespace, not nested cards.
- **KPI tile:** label (uppercase mono, `--sp-text-3`), then value (mono,
  `--sp-text`), then one sub-line, then a provenance line (`.metric-provenance`),
  plus exactly one claim badge.
- **Inputs:** label above, helper or error text below, `--sp-surface` fill, a focus
  ring in `--sp-accent`. No floating labels.
- **Risk bands:** green, yellow and red always map to `--sp-ok`, `--sp-warn` and
  `--sp-risk`, and the band name is always printed next to the colour.
- **Loading:** skeleton blocks sized like the content. No spinners on numbers.
- **Empty and error states:** say what to do next ("Start the API to compute site
  economics"), inline, where the data would have been.

## 6. Layout Principles

- Navigation rail on the left (240px, `--sp-chrome`) and a content column capped
  at 1400px.
- Use CSS Grid for KPI rows. A row of four equal KPI tiles is allowed here, because
  it is a scan pattern for comparison, not a marketing feature row.
- Below 768px every grid collapses to one column. Tap targets are at least 44px.
  Nothing scrolls horizontally except data tables inside their own container.

## 7. Motion & Interaction

- Transitions are 120–180ms on `opacity` and `transform` only.
- There is one perpetual loop: the live-status dot pulse.
- Numbers update in place; they never count up.

## 8. Brand Marks

- `static/design/mark.svg`: the pulse line turning into a rising arrow in Signal
  Orange, on a Charcoal tile. Used for the favicon and the navigation rail.
- `static/design/logo.svg`: the mark plus the "SitePulse" wordmark, for dark
  backgrounds.
- `static/design/icon.png`: a 128px raster of the mark, for surfaces that cannot
  take SVG (the Streamlit page icon).
- The product is **SitePulse**. Never put a partner's or prospect's brand into the
  product name, logo or window title.

## 9. Anti-Patterns (Banned)

- Emojis in UI copy. Use geometric glyphs (↯ ◈ ◎ ▣) or nothing.
- Inter, and any serif font.
- Pure black `#000000`, and raw hex values in markup: use tokens.
- Purple or neon accents, glows, and gradient text.
- More than one accent colour.
- Money figures without a claim badge. "Guarantee" language on estimates.
- Fake precision: `83%` of 7 people, `221.8%` ROI, `$621,000` to the dollar.
- AI copywriting clichés: "AI engine automatically…", "seamless", "next-gen".
- Invented people on screen presented as real customers.
