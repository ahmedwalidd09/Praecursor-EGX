# Design

## Aesthetic direction
Silver-and-charcoal research instrument: an editorial landing page leads into a quiet, table-first market workspace. The user's black/white/silver/grey palette supersedes the earlier green palette.

## Dials
- Design variance: 7/10 landing, 4/10 dashboard
- Motion: 4/10 (short entrances and meaningful press/task feedback)
- Density: 3/10 landing, 7/10 dashboard

## Typography
Manrope for headings and interface text; Fira Code for numbers and small labels. Google Fonts use display=swap. Segoe UI/Consolas fallbacks keep the laptop dashboard usable offline. Body line height 1.6; descriptive paragraphs capped at 62ch.

## Tokens
Background #0b0b0b; surface #141414; raised #1c1c1c; text #f3f3f3; muted #aaaaaa; divider #343434; control outline #777777; silver #d5d5d5. Grayscale only. Status meanings use words and symbols, never color alone. Flat surfaces, 5px control radii, 9px dialog radius. Silver gradients belong only to the decorative vector instrument; no gradient headings or neon glow.

## Layout and interaction
1440px maximum width; 48px desktop, 28px tablet and 20px mobile gutters. Landing uses an asymmetric two-column hero, a silver vector monogram, a real saved-session strip, and numbered editorial rows. No fabricated charts or testimonials. Four dashboard metric columns collapse to two. Data tables scroll within their focusable region; the page itself does not overflow.

Buttons have at least 44px targets, visible keyboard focus, a short scale press and a 550ms fading ripple. Actions show aria-busy, distinct task labels, disabled duplicate submissions, and live completion/error feedback. A refresh toast confirms the saved view was reloaded. The native details dialog has an accessible title, Escape/backdrop dismissal and restored focus. Entrances use transform/opacity with cubic-bezier(.16,1,.3,1). Reduced motion removes transitions, ripples, rotations and smooth scrolling. Polling pauses when the document is hidden and resumes after browser back/forward restoration.

Routes: `/` landing, `/dashboard` workspace, `/dashboard#evidence` validation. The existing desktop shortcut opens `/`. Saved HTML inlines the shared theme and scripts and hides live controls/navigation. The existing access gate remains enforced.

## Data contracts
Show real saved records only. Old scans explicitly marked historical. Setup scores are not probabilities. Target touches and executable trades remain separate. Missing models, loading, empty tables, and errors have explicit messages. Scan and model evaluation are separate actions.

## Components
Shared header, primary/secondary buttons, landing instrument, session strip, numbered approach rows, dashboard notice, metrics, searchable/filterable table, stock details dialog, model evidence, task progress, live feedback toast. Theme and behavior are shared between the local app and static export through reporting/pages.py.

## Last updated
2026-11-05: local desktop research dashboard.
2026-11-08: UI/UX Pro Max redesign; monochrome palette, landing page, responsive layout and press/task feedback. The skill's generic marketing recommendations were not persisted; this document records the product-specific decisions.
