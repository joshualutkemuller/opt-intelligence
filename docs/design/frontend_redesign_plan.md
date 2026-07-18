# Frontend Redesign Plan

## Purpose

This document is the build handoff for redesigning the Decision Intelligence
demo UI into a presentation-grade financial intelligence terminal.

The audience is senior treasury, liquidity, and markets stakeholders. They are
comfortable with dense screens, market terminals, and institutional analytics.
The UI should therefore signal precision, governed decisioning, and analytical
authority rather than generic SaaS friendliness.

The redesign is visual and interaction-focused. It should not change optimizer
math, workflow API contracts, governance behavior, or demo data.

---

## Design Thesis

Build a dark, dense, command-and-control workspace.

The current React demo is functional, but visually reads like a polished SaaS
dashboard. The redesign should feel closer to a purpose-built treasury
operations terminal: structured panels, instrument-like metrics, crisp status
signals, and data-first typography.

The design should be:

- **Dense:** more Bloomberg-style information density, less spacious marketing
  dashboard layout.
- **Precise:** thin borders, aligned data, consistent mono numerics, no soft
  shadows.
- **Governed:** approval, validation, trace, and workflow progress should feel
  like first-class control surfaces, not secondary diagnostics.
- **Demo-ready:** a nontechnical stakeholder should immediately understand what
  is running, what changed, what requires review, and what the recommendation
  is.

---

## Product Surface

Primary app:

- `frontend/app/src/main.tsx`
- `frontend/prototype/styles.css`

The React app imports the shared prototype stylesheet. Treat
`frontend/prototype/styles.css` as the main redesign surface unless the
component structure must change.

Primary startup:

```bash
make demo-ui
```

Primary local URLs:

- API: `http://127.0.0.1:8000`
- UI: `http://127.0.0.1:5173` or next available Vite port

---

## Visual Identity

### Palette

Use a deep instrument-panel palette. The signature color is electric cyan on
deep navy. Semantic colors must stay separate from the accent.

| Token | Hex | Role |
|---|---:|---|
| `--void` | `#070C14` | App background |
| `--surface` | `#0C1522` | Standard panel background |
| `--surface-raised` | `#101D2C` | Elevated panels and hover states |
| `--surface-hot` | `#12243A` | Selected / active region |
| `--rim` | `#1A2D42` | Borders and dividers |
| `--rim-strong` | `#294866` | Active borders |
| `--muted` | `#3D5A78` | Disabled text and secondary labels |
| `--body` | `#7A9BB8` | Body text |
| `--ink` | `#C4D9EE` | Headings and high-emphasis text |
| `--accent` | `#00C8F0` | Primary interactive and data highlight |
| `--accent-dim` | `#087A96` | Secondary cyan data line |
| `--positive` | `#00C896` | Passing, improvement, approved |
| `--warning` | `#F0A020` | Review, pending, caution |
| `--critical` | `#F04860` | Rejected, blocked, violation |

Avoid:

- Purple-blue gradients.
- Beige, cream, tan, or espresso palettes.
- Rounded pastel status chips.
- Large shadows or glassmorphism.
- Pure black / pure white as dominant colors.

### Typography

Use two typography roles:

- **Data, IDs, metrics, tables:** `"SF Mono", "Cascadia Code", "Fira Code",
  ui-monospace, monospace`
- **Labels, prose, commands:** `Inter, ui-sans-serif, system-ui, sans-serif`

Recommended type scale:

| Use | Size | Weight | Font |
|---|---:|---:|---|
| Large metric value | `28-32px` | `700` | Mono |
| Section heading | `13px` | `700` | Sans |
| Eyebrow / column header | `10px` | `700` | Sans, uppercase |
| Body / chat message | `13px` | `400` | Sans |
| Caption / sub-label | `11px` | `500` | Sans |
| Data cell | `12px` | `500` | Mono |
| Command input | `14px` | `500` | Mono |

Rules:

- Do not use viewport-scaled font sizes.
- Use `letter-spacing: 0` except uppercase eyebrows, which may use modest
  positive tracking.
- Every percentage, currency amount, request ID, approval ID, workflow ID, and
  solver name should render in monospace.

---

## Layout System

### App Shell

Target structure:

- Top bar: `48px` high, compact, utility-focused.
- Left instrument sidebar: `268px` wide on desktop.
- Main workspace: strict grid of panels.
- Right/secondary content should remain within the grid, not float as loose
  cards.

Panels:

- Background: `--surface` or `--surface-raised`.
- Border: `1px solid var(--rim)`.
- Radius: `4px` maximum for panels, `2px` for small controls.
- Shadow: none.
- Active panels may use a `4px` left border in `--accent`.

The layout should read like a terminal dashboard composed of instruments, not a
marketing page made of cards.

### Desktop Grid

Recommended desktop grid:

```text
┌────────────────────────────────────────────────────────────────────┐
│ Topbar: product, API status, export, reset                         │
├──────────────┬────────────────────────────┬────────────────────────┤
│ Sidebar      │ Main chat / command center │ Results / workflow     │
│ workflow     │ plan / input controls      │ timeline / governance  │
│ selector     │                            │                        │
├──────────────┴────────────────────────────┴────────────────────────┤
│ Analytics grid: metrics, allocations, validation, explanation       │
└────────────────────────────────────────────────────────────────────┘
```

Suggested CSS grid:

```css
.app-main {
  display: grid;
  grid-template-columns: 268px minmax(360px, 1fr) minmax(420px, 1.25fr);
  gap: 10px;
}
```

Mobile:

- Collapse to one column.
- Sidebar sections stack above the command/chat surface.
- Command bar remains sticky at the bottom only if it does not cover content.
- Timeline and tables should scroll horizontally only when a compact table is
  truly necessary.

---

## Interaction Model

### Chat As Command Bar

The chat input should become a command bar:

- Full width within its panel.
- Monospace text.
- Prompt glyph prefix: `›`.
- Cyan focus line.
- No large rounded input field.

The chat should support two visible modes:

- **Guided collection:** assistant asks field-by-field questions.
- **Workflow command:** user can type `run the full liquidity stress funding
  workflow` and immediately see the workflow timeline populate.

### Status Indicators

Replace pill-heavy visual language with terminal-native status strips:

```text
● OPTIMAL
● PENDING APPROVAL
● REVIEW REQUIRED
● BLOCKED
```

Rules:

- Dot uses semantic color.
- Label is uppercase mono or small sans.
- Avoid filled rounded pills except where legacy layout requires a small badge
  during transition.

### Buttons

Buttons should feel like terminal controls:

- Height: `32-36px`.
- Radius: `2px`.
- Primary: cyan border/text with dark fill; hover uses `--surface-hot`.
- Destructive/reject: critical border/text.
- Secondary: rim border and body text.

Avoid oversized CTA buttons.

---

## Component Redesign Map

### 1. Top Bar

Current role:

- Product title, reset/export actions, server status.

Redesign:

- Compact terminal header.
- Left: `DECISION INTELLIGENCE` plus environment/status text.
- Center: optional active workflow ID / portfolio ID.
- Right: reset, export JSON, export package, API status.

Acceptance:

- Topbar is exactly `48px` high on desktop.
- Actions do not wrap at `1280px`.
- API status uses dot + text, not a pill.

### 2. Workflow Selector

Current role:

- Preset selector, workflow selector, editable inputs.

Redesign:

- Sidebar instrument.
- Workflow and preset selectors should look like compact terminal fields.
- Domain tags become small text markers separated by slashes, not chips.
- Input labels are uppercase; values are mono.

Acceptance:

- Selected workflow is the strongest visual item in the sidebar.
- Editable inputs remain usable without opening dev tools.
- Presenter review status is visible before run.

### 3. Guided Chat

Current role:

- Primary conversational interface.

Redesign:

- Header becomes `COMMAND CHANNEL`.
- Messages are terminal rows with role labels in a narrow column.
- User messages use accent text sparingly.
- Assistant messages are readable body text, not chat bubbles.
- Input is the command bar.

Acceptance:

- A nontechnical user can type:

```text
run the full liquidity stress funding workflow
```

and see the sequential workflow panel update.

### 4. Agent Plan

Current role:

- Shows plan summary and steps.

Redesign:

- Render as an execution checklist.
- Use left rail or small step index.
- Completed/pending/blocked states use dot + text.
- Missing fields should appear as compact field rows.

Acceptance:

- The plan panel makes it obvious whether the system is collecting inputs or
  ready to run.

### 5. Workflow Timeline

Current role:

- Shows sequential workflow progress, dependency effects, and trace.

Redesign:

- This should become the visual centerpiece after a workflow run.
- Treat each workflow step as a terminal event block, not a soft card.
- Dependency effects should render as audit deltas:

```text
financing_001 -> money_market_001
daily_liquidity_req 40.0% -> 43.5%
```

Acceptance:

- Step order is obvious.
- Dependency propagation is obvious.
- Governance status inside each step is discoverable.
- Timeline remains readable with 3-5 steps.

### 6. Governance Review

Current role:

- Shows approval state and allows approve/reject/rerun.

Redesign:

- Make governance feel like a control gate.
- Highlight tier, escalation reason, approval ID, approver, and action withheld.
- Approve/reject controls are visually serious and separated from ordinary demo
  controls.

Acceptance:

- Pending approvals cannot be mistaken for a successful execution.
- Approved/rejected rerun behavior is explained in one line.

### 7. Workflow Comparison

Current role:

- Shows objective impact and optional risk/return points.

Redesign:

- Use compact horizontal bars with mono values.
- Best step indicator should be a cyan left rail or small marker, not a badge.
- Risk/return plot should use cyan and semantic accents on dark gridlines.

Acceptance:

- The chart is legible on a projector.
- Values are still readable without hovering.

### 8. Explanation Panels

Current role:

- Structured explanation and validation details.

Redesign:

- Make the recommendation the first line.
- Then show drivers, risks, validation warnings, and next actions as terminal
  entries.
- Avoid long paragraphs in dense side panels.

Acceptance:

- A stakeholder can read the first 10 seconds of the panel and understand the
  recommendation and risk posture.

### 9. Tables

Current role:

- Allocations and sensitivities.

Redesign:

- Dense table treatment.
- Sticky-ish headers if simple.
- Mono values aligned right.
- Thin row separators.
- No alternating pastel row backgrounds.

Acceptance:

- Allocation fractions align visually.
- Tables fit without horizontal scrolling at `1440px`.

---

## CSS Implementation Plan

### Current Implementation Status

Initial implementation has started in `frontend/prototype/styles.css`.

Completed in the first pass:

- Added dark terminal color tokens and mapped legacy color variables onto them.
- Converted the app shell, panels, sidebar, and topbar toward the dense terminal
  layout.
- Restyled status pills into dot + text status strips without changing markup.
- Restyled chat into a command-channel treatment with terminal rows and a prompt
  prefix.
- Restyled workflow timeline, dependency effects, governance review, workflow
  comparison, tables, and pre-trade panels toward the instrument-panel visual
  system.
- Kept React behavior and API contracts unchanged.

Completed in the QA hardening pass:

- Replaced transitional React `.status-pill` markup with a reusable
  `StatusStrip` component.
- Added responsive hardening for topbar wrapping, sidebar/main-stage overflow,
  panel headers, metric values, and workflow step labels.
- Confirmed the live local UI and API respond successfully when started with
  `make demo-ui`.

Still pending:

- Browser screenshot QA across desktop and mobile viewports in an environment
  with an exposed browser target.
- Any chart-specific canvas/SVG refinement after visual review.

### Phase 1: Tokens And Reset

Files:

- `frontend/prototype/styles.css`

Tasks:

- Replace root color tokens with the terminal palette.
- Normalize panel radius to `4px`.
- Remove broad box-shadow usage.
- Add common data text utilities:

```css
.mono,
.metric-value,
.data-cell {
  font-family: "SF Mono", "Cascadia Code", "Fira Code", ui-monospace, monospace;
}
```

Acceptance:

- App is dark-only.
- No remaining large light surfaces.
- No purple/cream/gradient-dominant theme.

### Phase 2: Shell And Panels

Files:

- `frontend/prototype/styles.css`
- `frontend/app/src/main.tsx` only if class hooks are missing.

Tasks:

- Implement compact topbar.
- Implement desktop grid.
- Convert panels to bordered instruments.
- Add active left accent stripe for primary panels.

Acceptance:

- Desktop layout is stable at `1440x900`.
- Mobile layout is usable at `390x844`.
- No text overlap.

### Phase 3: Command Channel

Files:

- `frontend/prototype/styles.css`
- `frontend/app/src/main.tsx` if command prompt markup is needed.

Tasks:

- Convert chat message display from conversational cards to terminal rows.
- Convert input to command bar.
- Add prompt glyph.
- Make pending state visible without a spinner-heavy look.

Acceptance:

- The command `run the full liquidity stress funding workflow` is visually
  obvious as a command.
- Assistant output remains readable.

### Phase 4: Workflow And Governance Instruments

Files:

- `frontend/prototype/styles.css`

Tasks:

- Redesign timeline, dependency list, trace list, governance review panel, and
  validation strip.
- Replace pills with status strips where possible.
- Make approval controls prominent but compact.

Acceptance:

- Pending governance status visually dominates over ordinary success metrics.
- Workflow trace reads like an audit event stream.

### Phase 5: Charts And Tables

Files:

- `frontend/prototype/styles.css`
- `frontend/app/src/main.tsx` only if chart labels need markup tweaks.

Tasks:

- Restyle workflow comparison bars.
- Restyle allocation and sensitivity tables.
- Ensure numeric columns are mono and right-aligned.

Acceptance:

- Charts and tables remain readable on projector and laptop.
- No hover-only critical values.

---

## Markup Change Guidelines

Prefer CSS-only changes first. Touch `frontend/app/src/main.tsx` only when:

- A missing class hook prevents styling.
- A status pill needs a dot + text structure.
- The command bar needs a real prompt prefix element.
- A dense table needs a semantic column wrapper.

Do not:

- Rebuild the app in a new framework.
- Replace the deterministic API flow.
- Introduce a component library.
- Add marketing/landing-page sections.
- Add decorative SVG/gradient illustration.

---

## Demo Script To Preserve

The redesigned UI must still support this stakeholder script:

1. Start the app with `make demo-ui`.
2. Confirm API status is connected.
3. In the command channel, type:

```text
run the full liquidity stress funding workflow
```

4. Show the sequential workflow timeline:
   - financing
   - collateral
   - money market
5. Point out dependency propagation into money-market liquidity constraints.
6. Show validation/readiness.
7. Show governance status if using a high-materiality preset.
8. Ask Ollama to explain the workflow in plain English if local Ollama is
   available.
9. Export the demo package.

---

## Quality Gates

Run before considering the redesign complete:

```bash
npm run build
```

From repo root:

```bash
./.venv/bin/python -m pytest -q
git diff --check
```

Manual viewport checks:

- `1440x900`: no overlap, dashboard fits naturally.
- `1280x800`: topbar actions do not wrap awkwardly.
- `390x844`: command/chat, workflow selector, and timeline are usable.

Manual workflow checks:

- Chat-guided single optimizer still works.
- Chat-driven multi-domain workflow still works.
- Manual workflow selector still works.
- Governance approve/reject/rerun still works.
- Export JSON still works.
- Export package still works.
- Ollama panel still degrades gracefully when local Ollama is unavailable.

---

## Non-Goals

This redesign does not include:

- Authentication.
- Multi-user collaboration.
- Production deployment.
- New optimizers.
- New workflow math.
- Durable approval storage.
- Real-time streaming workflow events.

Those belong in platform or orchestration workstreams, not this visual redesign.

---

## Open Decisions

1. **Exact terminal density:** decide whether the main grid should show all
   panels at once on `1440x900`, or allow one lower analytics row below the
   fold.
2. **Status migration depth:** decide whether to fully remove existing pill
   markup or style the existing `.status-pill` class to behave like a status
   strip during transition.
3. **Command bar placement:** decide whether the command bar stays inside the
   chat panel or becomes sticky across the bottom of the full app.
4. **Chart rendering:** decide whether the workflow comparison remains pure CSS
   bars or moves to a small canvas/SVG chart for better axis control.

Recommendation for first implementation: keep markup mostly intact, restyle
`.status-pill` as a transition status strip, keep the command bar inside the chat
panel, and use CSS bars before introducing a charting dependency.

---

## Completion Definition

The redesign is complete when the app looks and behaves like a purpose-built
financial terminal while preserving the existing demo capabilities.

Success criteria:

- The first screen is the working demo workspace, not a landing page.
- The visual hierarchy prioritizes workflow state, recommendation, validation,
  and governance.
- Data and IDs use monospace consistently.
- The UI remains dense but readable.
- A stakeholder can run the full workflow demo without knowing terminal
  commands beyond `make demo-ui`.
- The code remains a thin frontend over the existing deterministic Python API.
