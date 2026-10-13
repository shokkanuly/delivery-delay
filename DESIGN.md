# Design System: SitePulse

> The single source of truth for generating and reviewing SitePulse screens:
> the Streamlit dashboard, the HTML console, and any new screen prompted in
> Google Stitch. Token values live in
> [`static/design/tokens.css`](static/design/tokens.css), and
> `tests/test_design_system.py` enforces the rules marked **(enforced)**.

## 1. Visual Theme & Atmosphere

A site office at 07:00. The logistics manager has ten minutes before the first
truck is due, and needs to know which delivery will slip and which crane is free.
The interface feels like a **well-kept dispatch board: calm, dense, legible**.
Neutral Zinc surfaces carry the data, a single Signal Orange marks what needs
action, and every number wears a small badge saying what backs it. The mood is
clinical and trustworthy, closer to an aircraft checklist than a marketing page.

- **Density 7 of 10, "Cockpit Balanced":** many numbers per screen, grouped by
  1px borders and whitespace, not by stacked cards.
- **Variance 3 of 10, "Predictable Symmetric":** the same metric sits in the same
  place every morning. Asymmetry is used only to show priority (the lead engine
  and the target market get the wider column).
- **Motion 3 of 10, "Static Restrained":** views arrive with a short cascade and
  loading values shimmer. Nothing else moves, and numbers never count up, because
  a moving number reads as an unstable one.
- **Two themes, one system:** the HTML console uses the light theme; the Streamlit
  dashboard uses the dark theme. Both use the same token names, accent, type and
  badges.

## 2. Color Palette & Roles

**Neutrals: one Zinc ramp, never mixed with warm or cool greys (enforced)**
- **Canvas Zinc** (#FAFAFA, dark: Zinc-950 #09090B): page background.
- **Pure Surface** (#FFFFFF, dark: Charcoal #18181B): panels, inputs, table bodies.
- **Quiet Surface** (Zinc-100 #F4F4F5, dark: Zinc-800 #27272A): table headers, hover rows, skeletons.
- **Whisper Border** (Zinc-200 #E4E4E7, dark: Zinc-800 #27272A): 1px structural lines.
- **Firm Border** (Zinc-300 #D4D4D8, dark: Zinc-700 #3F3F46): hover and focus borders.
- **Charcoal Ink** (#18181B, dark: Zinc-50 #FAFAFA): primary text and key numbers.
- **Steel Body** (Zinc-600 #52525B, dark: Zinc-400 #A1A1AA): body copy and descriptions.
- **Muted Steel** (Zinc-500 #71717A in both themes): metadata and provenance lines.
- **Navigation Rail** (#18181B, dark: #111113): the left rail, dark in both themes.

**The single accent**
- **Signal Orange** (#E0643C, 73% saturation, same in both themes): primary
  actions, the active nav item, focus rings, "act on this". It is construction
  safety orange, tuned down from neon. No other colour asks for attention.

**Status colours: meaning only, never decoration**
- **Cleared Green** (#2F855A, dark #4FB387): green risk band, Sanity Check badge.
- **Caution Amber** (#B7791F, dark #D69E2E): yellow risk band, Estimate badge.
- **Critical Red** (#C53030, dark #E26D6D): red risk band, errors.
- **Ledger Blue** (#2B6CB0, dark #63A4E0): Correctness Invariant badge, neutral highlights.

Tints are always `color-mix(in srgb, <token> N%, transparent)`, never a new hex.
Shadows are tinted Zinc-950 (`rgba(9,9,11,…)`), never pure black. Markup
contains no raw hex apart from white text on dark or accent fills **(enforced)**.

## 3. Typography Rules

- **Display & UI:** **Geist** (weights 400–700). Headlines are weight 600,
  tracked tight (−0.02em), scaling `clamp(1.5rem, 4vw, 2.1rem)`. Hierarchy comes
  from weight and colour, not from size.
- **Body:** Geist at 14px with relaxed leading (1.55) in Steel Body. Prose
  blocks are capped at about 65 characters.
- **Mono:** **Geist Mono** for every KPI value, access key, timestamp and badge
  label, so digits line up in columns.
- **Banned (enforced):** Inter; every serif font in either UI, including the
  retired Instrument Serif and Georgia.

## 4. Component Stylings

- **Buttons:** flat with gently rounded corners (8px). Primary buttons are a
  Signal Orange fill with white text; secondary buttons are Pure Surface outlined
  in Whisper Border, turning Firm Border on hover. Pressing a button moves it
  down 1px. No outer glow, no gradient, no custom cursor.
- **Panels:** Pure Surface, a 1px Whisper Border, softly rounded corners (10px).
  Elevation is reserved for modals (a large Zinc-tinted shadow) and hovered site
  cards (a small one). Dense views separate groups with borders and whitespace,
  never a card inside a card.
- **KPI tile:** in reading order: an uppercase mono label in Muted Steel, then the
  value in mono Charcoal Ink, then one sub-line, then a dashed-top provenance line,
  plus exactly one claim badge in the corner.
- **Claim badges (the only five allowed, enforced):** small uppercase mono pills
  with a 1px border in their own colour.
  - **Correctness Invariant** (Ledger Blue): a tested property of the code, such as
    "0 double-bookings". Never used on a money figure.
  - **Estimate** (Caution Amber): statistical or assumption-based, not yet
    measured on a real site, such as "$103k losses avoided".
  - **Synthetic Data** (Muted Steel, dashed border): a result on the demo dataset,
    such as "260 bookings".
  - **Sanity Check** (Cleared Green): a guard-rail number that keeps an estimate
    honest, such as "2.9% of logistics budget".
  - **Operating Input** (Steel Body on Quiet Surface): a value the user typed.
- **Risk bands:** green, amber and red always map to the status colours, and the
  band name is always printed next to the colour.
- **Inputs:** label above in Muted Steel; helper or error text below; Pure Surface
  fill; a focus ring in Signal Orange. No floating labels. At least 44px tall on
  mobile.
- **Loading:** values still loading show a shimmering Quiet Surface skeleton the
  width of the number (`.sp-skeleton`). No circular spinners on numbers.
- **Empty and error states:** inline, where the data would have been, saying the
  next step ("Start the API to compute site economics"). Errors use Critical Red
  text on a 12% red tint.

## 5. Layout Principles

- **Frame:** a 240px Navigation Rail on the left and a content column with 32px
  gutters, capped at 1400px. Use CSS Grid for every row, no flexbox percentage
  maths, and `100dvh`, never `100vh` **(enforced)**. Elements never overlap.
- **The header acts as the hero:** a left-aligned greeting headline, one line of
  context, then one primary action (Score Delivery) beside a single utility
  action (Refresh). No centred hero, no "learn more", no scroll prompts.
- **Rows:** a feature row is never three equal cards. The lead item gets the
  wider track: engines use `1.3fr 1fr 1fr` (Delay Risk leads), pricing
  `1fr 1.3fr 1fr` (the standard tier), and market `1fr 1.3fr 1fr` (the beachhead).
  A row of four equal KPI tiles is allowed, because it is a scan-and-compare pattern
  rather than a feature showcase. Forms may use equal columns.
- **Mobile (< 768px):**
  - Every grid collapses to one column.
  - The rail becomes a wrapped row of 44px nav targets; the weather widget and
    user card hide.
  - The top bar wraps and the search box goes full width.
  - Gutters shrink to 16px, and the page never scrolls horizontally.
  - Wide data tables scroll inside their own box.

## 6. Motion & Interaction

- **Easing:** `cubic-bezier(0.22, 1, 0.36, 1)`, the CSS stand-in for a spring
  (stiffness 100, damping 20): quick start, soft settle, no overshoot. Never
  linear. Micro-interactions take 160ms; reveals take 420ms.
- **Cascade reveal:** when a view mounts, the children of a KPI, engine or pricing
  row rise 6px and fade in, 60ms apart (`.sp-cascade`).
- **The only perpetual loops:** the live-status dot pulse and the skeleton
  shimmer while data loads.
- **Performance:** animate `transform` and `opacity` only.
- **Accessibility:** under `prefers-reduced-motion: reduce`, every animation and
  transition is cut to near zero **(enforced)**.
- **Streamlit exception:** the dashboard does not cascade, because every widget
  interaction re-runs the script and would replay the entrance as flicker.

## 7. Anti-Patterns (Banned)

- Emojis anywhere in UI copy. Use geometric glyphs (↯ ◈ ◎ ▣ ⌕) or nothing **(enforced)**.
- Inter, and any serif font in the product **(enforced)**.
- Pure black (#000000) and black shadows; raw hex in markup **(enforced)**.
- A second accent colour; purple or neon; glows; gradient text; custom cursors.
- Three equal feature cards in a row; centred hero headers; overlapping elements.
- `100vh` (it jumps on iOS Safari): use `100dvh` **(enforced)**.
- Money figures without a claim badge, and "guarantee" or "proven" wording on
  estimates **(enforced for retired claims)**.
- Fake precision: "83%" of 7 interviews, "221.8%" ROI, "$621,000" to the dollar,
  "99.99%" anything.
- AI copywriting clichés: "AI engine automatically…", "seamless", "elevate",
  "unleash", "next-gen", "revolutionary".
- Filler UI text: "Scroll to explore", bouncing chevrons, scroll arrows.
- Generic placeholder names ("John Doe", "Acme"). Demo sites are labelled "Site A",
  "Site B" and so on, and are marked as fictional.
- A partner's or prospect's brand in the product name, logo or window title.
  The product is **SitePulse**; the marks are `static/design/mark.svg`,
  `logo.svg` and `icon.png` **(enforced)**.
