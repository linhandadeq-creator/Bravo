# UI Guidelines — Minimal Scientific Research Interface

The interface should read like a precise scientific instrument: quiet, dense,
and legible. It borrows Apple's restraint, research software's information
density, and modern SaaS clarity.

## Do

- White background (`#ffffff`), black / dark-grey text.
- Hairline borders (`1px`, light grey) as the primary structural device.
- Small, consistent radii — around `8px`.
- A single restrained accent color used sparingly for focus and primary actions.
- Tabular numerals for data columns.
- Generous but disciplined whitespace; sections divided by thin rules.
- A fixed left sidebar, ~`220px` wide, headed by **Neoantigen Platform**.

## Don't

- No gradients, glows, or shadows used decoratively.
- No 3D, particles, or complex animation.
- No "medical tech big-screen" dashboards.
- No large marketing cards or hero sections.
- No marketing-website tone.

## Tokens

Defined as CSS variables in `frontend/app/globals.css` and surfaced through
Tailwind (`background`, `foreground`, `border`, `muted`, `accent`, ...).

| Token          | Light value         |
| -------------- | ------------------- |
| `background`   | `0 0% 100%` (white) |
| `foreground`   | `0 0% 9%`           |
| `border`       | `0 0% 89%`          |
| `muted`        | `0 0% 96%`          |
| `accent`       | `210 100% 42%`      |
| `radius`       | `0.5rem` (~8px)     |
