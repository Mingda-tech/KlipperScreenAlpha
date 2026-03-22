# Lock Screen Interface Mockup

```
┌─────────────────────────────────────────────────────────────┐
│                    KlipperScreen                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│                         🔒                                  │
│                                                             │
│                   Screen Locked                             │
│                                                             │
│                      ● ● ● ●                               │
│                                                             │
│                 Enter PIN to unlock                         │
│                                                             │
│                                                             │
│                   ┌───┬───┬───┐                           │
│                   │ 1 │ 2 │ 3 │                           │
│                   ├───┼───┼───┤                           │
│                   │ 4 │ 5 │ 6 │                           │
│                   ├───┼───┼───┤                           │
│                   │ 7 │ 8 │ 9 │                           │
│                   ├───┼───┼───┤                           │
│                   │CLR│ 0 │ENT│                           │
│                   └───┴───┴───┘                           │
│                                                             │
│                                                             │
└─────────────────────────────────────────────────────────────┘

Legend:
- 🔒 Lock icon (lock.svg)
- ● Masked PIN dots (shows for each digit entered)
- CLR = Clear button (resets PIN entry)
- ENT = Enter button (submit PIN for validation)
- 0-9 = Numeric keypad buttons

Flow:
1. User taps numbers to enter PIN
2. Each digit shows as a dot (●)
3. Tap CLR to reset
4. Tap ENT to submit
5. If correct (1234): Screen unlocks
6. If incorrect: "Incorrect PIN" error shown in red
```

## Menu Navigation Path

```
Main Menu
  └─ Settings (More)
       └─ Lock Screen  <-- Tap here to lock
            └─ [Lock Screen Interface Shown]
                 └─ Enter PIN: 1234
                      └─ [Screen Unlocked - Returns to previous screen]
```

## Component Structure

```
Lock Screen Panel (lock_screen.py)
├─ Lock Icon (SVG)
├─ Title Label: "Screen Locked"
├─ PIN Display: "● ● ● ●" (masked)
├─ Info Label: "Enter PIN to unlock"
└─ Numeric Keypad (Grid)
    ├─ Row 1: [1] [2] [3]
    ├─ Row 2: [4] [5] [6]
    ├─ Row 3: [7] [8] [9]
    └─ Row 4: [Clear] [0] [Enter]
```

## CSS Styling Classes

```css
.lock-screen           /* Main container - uses theme background */
.lock-screen-title     /* Title text - 1.8x font size, bold */
.lock-screen-pin       /* PIN display - 2.5x font size, spaced */
.lock-screen-info      /* Info text - 1.2x font size */
.lock-screen-error     /* Error state - red color */
.lock-screen-button    /* Keypad buttons - 1.5x font size */
.lock-screen-button:hover /* Hover effect - color3 */
```

## File Structure

```
KlipperScreenAlpha/
├── panels/
│   └── lock_screen.py           [NEW] Lock screen panel
├── styles/
│   ├── base.css                 [MODIFIED] Added lock screen styles
│   ├── colorized/images/
│   │   └── lock.svg            [NEW] Lock icon
│   ├── material-light/images/
│   │   └── lock.svg            [NEW] Lock icon
│   ├── material-dark/images/
│   │   └── lock.svg            [NEW] Lock icon
│   ├── material-darker/images/
│   │   └── lock.svg            [NEW] Lock icon
│   └── z-bolt/images/
│       └── lock.svg            [NEW] Lock icon
├── ks_includes/
│   └── defaults.conf            [MODIFIED] Added menu entry
├── screen.py                    [MODIFIED] Added lock methods
└── LOCK_SCREEN.md              [NEW] Documentation
```
