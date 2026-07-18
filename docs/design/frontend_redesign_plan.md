# Design Plan — Decision Intelligence Platform

## Read

This is a **presentation-grade financial intelligence terminal** for treasury professionals. The audience is senior: they read Bloomberg, they trust density over whitespace, they expect data to be the hero. The single job of this UI is to signal precision and authority while making complex optimization output legible at a glance.

The current UI is a clean, functional SaaS prototype — capable but generic. It reads like a React dashboard template. The redesign needs a deliberate visual identity that feels like it was built for this specific instrument.

---

## Color

A **deep instrument-panel palette** — like the interior of a flight deck or a high-end trading terminal at night. Not Bloomberg orange-on-black (too derivative), not purple-gradient fintech (too generic). The signature is **electric cyan on deep navy**, with semantic colors kept strictly separate from the accent.

| Token | Hex | Role |
|---|---|---|
| `--void` | `#070C14` | Page/app background — near-black with strong blue cast |
| `--surface` | `#0C1522` | Panel background — dark navy |
| `--surface-raised` | `#101D2C` | Elevated cards, hover states |
| `--rim` | `#1A2D42` | Borders, dividers — thin, structural |
| `--muted` | `#3D5A78` | Disabled, secondary labels |
| `--body` | `#7A9BB8` | Body/prose text — steel blue-white, not pure white (deliberate) |
| `--ink` | `#C4D9EE` | High-emphasis text, headings |
| `--accent` | `#00C8F0` | Electric cyan — primary interactive, data highlights, the signature |
| `--positive` | `#00C896` | Teal-green — good, within bounds, improvement |
| `--warning` | `#F0A020` | Warm amber — approaching limit, caution |
| `--critical` | `#F04860` | Red-pink — breach, drag, alert |

**The aesthetic risk:** body text is `#7A9BB8` — a steel blue-white, not near-white. This makes the UI feel self-luminous, like instruments lit from within. High-emphasis values and accent color pop harder because the baseline is already slightly dimmed. It's unusual in web UI and immediately signals "this was designed for this."

---

## Typography

Two roles, paired deliberately:

- **Data / values / identifiers:** `"SF Mono", "Cascadia Code", "Fira Code", ui-monospace, monospace` — every number, percentage, fund name, status code. Monospace enforces Bloomberg-style information density and makes columns align without effort.
- **Labels / prose / UI text:** `"Inter", ui-sans-serif, system-ui, sans-serif` — clean and neutral, recedes behind the data.

### Type scale

| Use | Size | Weight | Case |
|---|---|---|---|
| Large metric value | 28–32px mono | 700 | — |
| Section heading | 13px sans | 600 | — |
| Eyebrow / column header | 10px sans | 700 | UPPERCASE + tracked |
| Body / message | 13px sans | 400 | — |
| Caption / sub-label | 11px sans | 500 | — |
| Data cell | 12px mono | 500 | — |

No display font. Personality comes entirely from palette and density, not a decorative typeface. The mono data values are the typographic hero.

---

## Layout

**A command-and-control layout:** ultra-slim topbar (48px), narrow instrument sidebar (268px) that is its own dark panel rather than part of the page background, and a main content area that is a strict grid of panels — no loose elements. Panels are defined by `1px` borders using `--rim` and a one-step background lift (`--surface-raised`), never by box-shadow. Depth comes from layering, not blur.

Panels have a **4px left accent stripe** (`border-left: 4px solid var(--accent)`) on active/highlighted sections — a Bloomberg-specific motif repurposed as a structural element, not decoration.

Status pills are replaced by **inline status strips** — a single line of colored text with a colored dot, never a pill with a border-radius. This reads as terminal-native, not SaaS-native.

The chat input becomes a **command bar** — full-width, monospaced, with a blinking cursor and a prompt character (`›`). This is the most Bloomberg-unlike element, so it's where the futuristic identity is clearest.

---

## What changes from the current UI

| Current | Redesign |
|---|---|
| White panels, light grey background | Near-black void + navy panels |
| Blue `#2563eb` primary | Electric cyan `#00C8F0` accent |
| Inter for all text | Mono for all data, sans for labels |
| Rounded pills, soft shadows | Thin borders, no shadows, accent stripes |
| Status pills (rounded, colored bg) | Dot + text status indicators |
| Chat input with grey border | Full-width command bar with `›` prompt |
| Colorful holding cards | Dark instrument cards with colored left stripes |
| Canvas gauge in warm tones | Cyan arc gauge with glowing endpoint |
| Assessment items as soft cards | Left-bordered terminal-style entries |

---

## Single-theme decision

This design **commits to dark only**. A light-mode version of a terminal instrument panel is a category error — it would lose the entire aesthetic. The design includes `prefers-color-scheme: dark` and `data-theme="dark"` support, and the light-mode fallback renders as a well-considered deep-slate rather than inverting to white.

---

## Implementation scope

- Full `styles.css` rewrite
- Minor `index.html` structural tweaks (topbar markup, command bar prompt character, status dot pattern)
- `app.js` canvas gauge redrawn in cyan
- No content changes — visual layer only
