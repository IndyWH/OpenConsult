# DESIGN_SPEC.md — the shared design system and page layouts

> **RECONSTRUCTION, 2026-07-28.** The original of this document (approved
> 2026-07-24) was lost — it existed only in Downloads and a deleted chat.
> This version is rebuilt from `app/static/theme.css` (which implemented
> it), the two approved mockups (`live_mockup.html`, `review_mockup.html`
> — still the visual source of truth), and HANDOVER's design-pass
> section. Where this document and the code disagree, the code and the
> mockups win. The 7b addendum at the end is new, not part of the lost
> original.

## Intent

Heidi-inspired, warm, calm, light. A clinical tool that does not look
cold. **Light theme only, by owner decision** — dark mode was dropped in
the 2026-07-24 pass, including the old `select, option { background:
Canvas }` workaround. Do not reintroduce `color-scheme: light dark`
piecemeal.

## Tokens (`app/static/theme.css` `:root`)

| Token | Value | Meaning |
|---|---|---|
| `--paper` | `#FAF6F1` | warm cream canvas |
| `--panel` | `#FFFFFF` | cards / panes |
| `--ink` | `#29231F` | warm near-black text |
| `--ink-soft` | `#6E645C` | secondary text |
| `--ink-faint` | `#A39A91` | metadata |
| `--line` | `#E9E1D8` | hairline borders |
| `--plum` | `#4E2A3A` | the single brand accent |
| `--plum-hover` | `#3E2130` | its hover state |
| `--red` | `#C2402F` | **urgency ONLY** |
| `--amber` | `#B07C1E` | low-confidence flags, awaiting states |
| `--green` | `#2E7D4F` | mic level, linked, approved |
| `--radius` | `10px` | pane corner radius |
| `--serif` | Source Serif 4, Georgia | display type |
| `--sans` | Inter, system-ui | everything else |

## The colour rules — semantic scarcity

- **Plum is the one brand accent**, reserved for the primary action and
  the active tab (plus the Doctor label in transcripts and the letter
  pane heading). Everything else stays in the ink/line neutrals.
- **Red means urgency and nothing else.** Not errors of convenience, not
  emphasis. (Fault states like a dead mic or a failed status borrow the
  red family because they are safety-relevant; nothing decorative may.)
- **Amber** marks low-confidence audio and awaiting states.
- **Green** marks finished or healthy states: mic live, linked from the
  queue, approved. **Lesson from consultation 448:** green reads as
  *spent* in this app. Never put green on a control the doctor is meant
  to press again.

## Type and shape

- Serif display (`--serif`) for the brand, page titles, patient names
  and SOAP section headings. Sans (`--sans`, 15px base, 1.55 line
  height) for everything else.
- Pane labels are small uppercase letter-spaced sans (`.72rem`,
  `.09em`), colour `--ink-faint`.
- Pills everywhere the element is tappable or a badge: buttons, chips,
  tabs (`border-radius: 999px`). Panes are `--radius` (10px) with
  1px `--line` borders. Shadows only on floating elements (menus,
  dialogs).

## Components (all in `theme.css`, shared by every page)

App chrome injected by `nav.js`: brand, pill tabs (Today / Consultation
/ Consultations), identity block, footer disclaimer on every page
("Research/educational prototype — not a medical device…"). Chips
(`.chip`, with `.linked` and `.status` variants coloured by state).
Buttons: default outlined, `.primary` plum, `.small`, `.danger`, the
round `.plus`. Panes with `.pane-head` / `.pane-body`. Tables with
uppercase headers. The urgency banner (`.urgent` / `.urgency`, 1.5px red
border, pale red fill, `.acked` flips to neutral with green icon).
Likelihood tags (`.lk` high/moderate/low). Citation chips (`.cchip`) and
low-confidence flags (`.flag`). Diarised transcript turns (`.turn`, plum
Doctor label, green Patient label, amber dotted underline on low
confidence, `.hl` highlight when a citation chip is clicked).

## Page layouts

**Live page** (owner's priority order, top to bottom):

1. Urgent-actions banner — always first.
2. Questions to ask | Signs to check, as a two-column duo.
3. Differential diagnosis, with the corpus-grounded guidelines summary
   inside an open `<details>` beneath it.
4. Live transcript **last** — the doctor listens to the patient, not
   the screen.

The session header carries the server-sourced patient banner, the
linked-from-queue chip, and the live cluster: timer with blinking
record dot, the mic pill, Stop. **The mic cluster is a safety feature,
not chrome**: the level meter runs off the SAME `getUserMedia` stream
the transcriber consumes, so the meter cannot disagree with what the
server hears; sustained silence turns the pill red (floor 1e-4 RMS,
hysteresis at 5e-4); the device picker re-acquires with
`deviceId: {exact}` and is disabled while recording.

**Review page** (top to bottom):

1. Header: patient, date/duration/language/status chips, then
   Regenerate · Copy as text · Approve (Approve gated), and after
   approval the plum "+" opening the referral menu.
2. Urgency banner, acknowledge-gated, if an urgent action was left
   unresolved.
3. Draft SOAP note — the document the doctor is here to sign — with
   citation chips, ⚠ flags, and the grounding footer ("N/M claims
   cited").
4. Letter panes (draft-tagged, own edit/approve).
5. Diarised transcript last, as reference material.

## Interface rules

The three standing rules (HANDOVER, "THE THREE STANDING RULES") bind
every page this system styles: never swallow an action; a control that
can act must not look as if it cannot; a control the doctor must reach
must be where they are looking. Any new control designed under this
spec inherits them.

## 7b addendum — the face panel (NEW, 2026-07-28, not in the original)

The kindalive face renders in a small **bedside-device panel**: a
standard `.pane` in the existing system, sized modestly (it is a
presence, not a display the doctor watches), kindalive's mood accent
recoloured to this palette (plum/ink neutrals — never red, which stays
urgency-only). Face on/off is a runtime toggle, default off; when off
the panel is absent entirely, not blanked — off is the control arm of
the CARE study and must remain first-class. Exact placement against the
live page's priority order is an owner decision at the styling pass.
