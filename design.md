# Design System Specification: Neomorphic Hybrid Fintech & Web3 Dashboard

## 1. Overview & Visual Philosophy
This design system defines a high-craft, soft-tactile, modern neo-surface aesthetic tailored for next-generation fintech, crypto, launchpad, and analytics platforms. 

The aesthetic synthesizes:
- **Soft Neomorphic Surface Elevation**: Sculpted, pillowy cards with layered drop-shadows and subtle inner borders rather than stark outlines.
- **Deep Contrast Asymmetry**: An ultra-dark, grounding sidebar paired with an airy, bright neutral canvas and pastel-tinted focal cards.
- **Micro-tactile Pill Elements**: Squircle containers, rounded pill badges, tactile toggles, and compact icon buttons with inset/embossed tactile cues.
- **Friendly Modern Geometry**: Generously rounded corners (`border-radius: 20px - 32px`), clean geometric typography, and playful iconography/emojis.

---

## 2. Color Palette & Semantic Tokens

### 2.1 Base Neutrals & Canvas
| Token Name | Hex Value | Usage / Description |
| :--- | :--- | :--- |
| `color-canvas-bg` | `#F0F2F6` | Main viewport soft-tinted canvas background |
| `color-surface-card` | `#FFFFFF` | Primary content cards, panels, and elevated tables |
| `color-surface-subtle`| `#F7F9FC` | Secondary surfaces, input backgrounds, table rows |
| `color-surface-inset` | `#E8EDF2` | Inset search bars, sunken pill toggles, calendar grids |
| `color-border-subtle` | `rgba(0, 0, 0, 0.05)` | Micro-divider lines and card perimeter definition |
| `color-border-card` | `rgba(255, 255, 255, 0.8)` | Top-edge highlight rim for tactile elevation |

### 2.2 Deep Contrast Sidebar
| Token Name | Hex Value | Usage / Description |
| :--- | :--- | :--- |
| `color-sidebar-bg` | `#111216` | Pitch black / deep charcoal persistent navigation frame |
| `color-sidebar-active`| `#1E2026` | Elevated active item container with rounded pill highlight |
| `color-sidebar-text` | `#8E929D` | Inactive icon and text label fill |
| `color-sidebar-text-active` | `#FFFFFF` | Active navigation label and icon stroke |
| `color-sidebar-accent`| `#38B6FF` / `#60A5FA` | Primary wallet connect button or primary CTA |

### 2.3 Pastel Card Accents & Category Tints
Used for hero metric tiles, IDO cards, and category indicators. All card tints maintain accessible dark contrast for typography (`#121417` or `#1E293B`).

| Palette Name | Surface Tint (`bg`) | Text / Stroke Accent | Context / Semantic |
| :--- | :--- | :--- | :--- |
| **Soft Lilac / Purple** | `#E1D9FF` | `#5B3CEB` | Gaming, NFTs, Primary Highlight |
| **Soft Pistachio / Lime** | `#E2F4A6` | `#3F6E00` | Retail, Growth, Positive Yield |
| **Sky Blue / Ice** | `#D4EBFD` | `#1D79E8` | Development, AI, Transfers |
| **Warm Peach / Coral** | `#FFE0D6` | `#C83A14` | Alerts, High Risk, Insurance |

### 2.4 Semantic & Status Tokens
| Token Name | Hex Value | Description |
| :--- | :--- | :--- |
| `color-status-success` | `#22C55E` | Transaction success, positive yield, live status dot |
| `color-status-warning` | `#F59E0B` | In-progress, pending, processing transactions |
| `color-status-danger` | `#EF4444` | Failed transactions, negative delta, urgent alerts |
| `color-text-primary` | `#121417` | Headings, large currency values, primary card labels |
| `color-text-secondary` | `#667085` | Subtitles, helper text, timestamps, labels |
| `color-text-muted` | `#98A2B3` | Disabled states, card serials, breadcrumb hints |

---

## 3. Typography & Hierarchy

The typographic voice is modern geometric sans-serif (e.g., **Plus Jakarta Sans**, **Inter**, or **Cabinet Grotesk**). Numbers and metrics use tabular numerals (`tnum`) for accounting accuracy.

### 3.1 Type Scale
- **Display / Page Title**: `28px - 32px` | Bold / Extrabold (800) | `line-height: 1.2` | Tracking: `-0.02em`
- **Metric / Hero Numerals**: `24px - 30px` | Semibold / Bold (700) | `line-height: 1.15` | Tabular figures
- **Section Heading (H2)**: `18px - 20px` | Bold (700) | `line-height: 1.3`
- **Card Subtitle / Category**: `11px - 12px` | Uppercase Semibold (600) | Tracking: `+0.05em` | Opacity: `0.7`
- **Body Regular**: `14px` | Regular / Medium (400 / 500) | `line-height: 1.5`
- **Caption / Meta Info**: `12px` | Medium (500) | `line-height: 1.4`
- **Badge / Micro-label**: `10px - 11px` | Semibold (600) | Uppercase or Sentence case

---

## 4. Elevation, Radii & Depth System

A defining feature is the dual elevation approach: **Crisp Geometric Outer Shell** with **Floating Neomorphic Inset Layers**.

### 4.1 Border Radii
- **Main App Container**: `36px` to `44px` (pill-like desktop canvas frame with dark bezel)
- **Primary Cards & Modals**: `24px` to `28px`
- **Nested Inner Cards & Metric Tiles**: `18px` to `22px`
- **Buttons & Search Insets**: `14px` to `16px`
- **Pills, Badges & Toggles**: `9999px` (Full pill radius)

### 4.2 Shadows & Neomorphic Layering
```css
/* Primary Floating White Card */
--shadow-card-elevated: 
  0 12px 28px -6px rgba(18, 24, 40, 0.06),
  0 4px 10px -2px rgba(18, 24, 40, 0.03),
  inset 0 1px 0 rgba(255, 255, 255, 0.85);

/* Soft Inset / Sunken Element (Search bar, toggle wells) */
--shadow-inset-soft:
  inset 0 2px 4px rgba(0, 0, 0, 0.04),
  inset 0 -1px 2px rgba(255, 255, 255, 0.9);

/* Neomorphic Floating Action / Tactile Pill Button */
--shadow-button-tactile:
  0 6px 16px -2px rgba(0, 0, 0, 0.06),
  0 2px 4px rgba(0, 0, 0, 0.03),
  inset 0 1px 1px rgba(255, 255, 255, 0.6);

/* Dark Sidebar Card / Floating Card Element */
--shadow-dark-card:
  0 16px 32px rgba(0, 0, 0, 0.35),
  inset 0 1px 1px rgba(255, 255, 255, 0.1);
```

---

## 5. Component Patterns & Rules

### 5.1 App Navigation Frame (Sidebar)
1. **Bezel & Alignment**:
   - Fixed width (`220px - 260px`), pure dark matte background (`#111216`).
   - Unified left-aligned brand mark (bold lower-case monogram or geometric logo) with `24px` internal padding.
2. **Nav Items**:
   - Height: `44px`, corner radius `12px - 14px`.
   - Inactive: transparent background, `#8E929D` muted icon + label.
   - Active: `#1E2026` background, white label, high-contrast icon.
3. **Sidebar Footer**:
   - Ancillary link list (About, Team, Docs) at `12px` font size.
   - Distinct, full-width Action Button (e.g., `#38B6FF` "Connect Wallet" pill button) flanked by circular social icons (Discord, Twitter, Telegram).

### 5.2 Top Bar & Global Header
- **Contextual Welcome / Search Area**:
  - Left: User greeting avatar + status (`Greetings! Start your day with...`) or page breadcrumb title.
  - Center: Generous pill search input (`bg: #E8EDF2` or `#FFFFFF`, height `48px`, rounded `9999px`, magnifying glass icon).
  - Right: Quick CTA buttons (`+ Apply`, `Connect Wallet`, or `My Account` pill dropdown).

### 5.3 Pastel Metric & IDO Launchpad Cards
1. **Composition**:
   - Aspect ratio approximately `4:3` or horizontal rectangular card.
   - Top row: Uppercase category tags (`GAMING`, `NFT`, `RETAIL`) + project title + floating square squircle icon badge.
   - Social links bar: Compact monochrome link icons (`Twitter`, `Discord`, `Web`).
   - Metric highlight: Large bold numerical value (`$524,202`) with right-aligned countdown timer (`03d 08h 16m`).
   - Progress bar: Thin 4px pill-shaped progress track with smooth contrasting fill.
   - Footer strip: Split meta details (`Total raise: $850,000` | `Price: $1.30`).
2. **Color Rule**:
   - Do not use more than 3 distinct pastel colors across the primary horizontal row. Alternate Lilac, Pistachio, Sky Blue, and White.

### 5.4 Realistic Virtual Payment Cards
1. **Design**:
   - Classic credit card aspect ratio (`1.586:1`).
   - Left card: Deep obsidian matte (`#16171B`), subtle dot-matrix world map embossing, white embossed balance, masked number `**** 1810`, Visa/Mastercard badge.
   - Right card: Crisp alabaster card (`#FFFFFF`), light gray topography/world map watermark, dark charcoal balance, tactile switch toggle for card freeze/lock.
2. **Action Shortcuts Below Cards**:
   - Row of rounded squircle action pills: `Transfer` (tinted blue pill), `Utility`, `Taxes`, `Transport` with dark circle icon containers.

### 5.5 Donut & Circular Analytics Panel
1. **Structure**:
   - Split card widget containing custom segmented donut chart (`stroke-width: 22px - 26px`, rounded cap terminals).
   - Prominent central inner value (`Total $14,810.0`).
   - Micro category legend below with colored dots.
   - Transaction list underneath with soft brand circle icons (Spotify, Apple, Bitcoin, Binance), timestamps, and right-aligned debit/credit amounts.

### 5.6 Tabular Voting & Project Leaderboard
1. **Rows & Hover**:
   - Flat rows with subtle `#F7F9FC` hover states.
   - Rank indicator: `#1`, `#2`, `#3` in bold muted gray.
   - Logo squircle: `40px x 40px` rounded `12px` icon with branded colored background.
   - Name & sub-tags: Bold title with category below.
   - Star Vote button: Tactile pill button with star icon and live vote count (`⭐ 1,204`) + upvote caret.

### 5.7 Integrated Mini Calendar Widget
1. **Format**:
   - Compact 7-column calendar grid embedded within cards.
   - Month switcher header with chevrons (`December 2022 < >`).
   - Active selected date highlighted with dark pill container (`#111216`, text white).
   - Event indicator dots: Mint green, coral red, and amber dots placed below active dates to represent scheduled IDO launches or recurring debits.

---

## 6. Interaction & Micro-Motion Guidelines

1. **Card Hover**:
   - Soft translateY elevation (`transform: translateY(-2px)`), shadow softens and spreads (`transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1)`).
2. **Active Pill Toggles**:
   - Spring-physics slide for segmented tab controls (e.g., `All | Active | Upcoming`).
3. **Number Counters**:
   - Rolling odometer style or smooth fade-in for dynamic monetary metrics.
4. **Tooltips**:
   - High-contrast mini-pills (`#111216`, text white, `border-radius: 8px`, `font-size: 11px`).

---

## 7. Do's and Don'ts

### DO:
- Keep the canvas background tinted off-white/pale silver (`#F0F2F6`) so elevated white cards pop with soft drop shadows.
- Maintain consistent squircle and pill border radii across all nested elements.
- Use pastel backgrounds exclusively with dark, readable typography for guaranteed AA contrast.
- Anchor the layout with a dark, commanding sidebar or dark virtual card for visual balance.

### DON'T:
- Do NOT use harsh 1px black borders or harsh neon drop-shadows.
- Do NOT clutter cards with multiple saturated accent colors simultaneously.
- Do NOT use square or sharp 90-degree corners anywhere in this UI language.
- Do NOT use pure `#FFFFFF` background for the entire page canvas; the tactile elevation requires a soft background contrast.
