# Lock Screen Feature

## Overview
A lock screen feature has been implemented for KlipperScreen to prevent unauthorized access to the printer interface.

## Features
- **PIN-based authentication**: 4-digit PIN code protection
- **Numeric keypad**: Easy-to-use numeric keypad for PIN entry
- **Visual feedback**: Masked PIN display with dots (●)
- **Error handling**: Clear error message for incorrect PIN attempts
- **Theme support**: Lock icon available in all themes
- **Two access modes**:
  - Panel mode: Access via Settings > More > Lock Screen
  - Overlay mode: Programmatic locking via `screen.show_lock_screen()`

## Usage

### Accessing the Lock Screen
1. Navigate to the main menu
2. Go to Settings > More
3. Select "Lock Screen"
4. Enter the PIN when prompted

### Default PIN
The default PIN is: **1234**

### Unlocking
1. Enter your 4-digit PIN using the numeric keypad
2. Press "Enter" to submit
3. If correct, the screen will unlock
4. If incorrect, an error message will appear and you can try again

### Clearing Entry
Press the "Clear" button to reset your PIN entry at any time.

## Implementation Details

### Files Created/Modified
- `panels/lock_screen.py` - Lock screen panel implementation
- `styles/*/images/lock.svg` - Lock icon for all themes
- `screen.py` - Lock screen overlay methods
- `styles/base.css` - Lock screen styling
- `ks_includes/defaults.conf` - Menu configuration

### Panel Structure
The lock screen panel (`panels/lock_screen.py`) includes:
- Lock icon display
- Title: "Screen Locked"
- PIN display (masked with dots)
- Info/error message display
- 4x3 numeric keypad (1-9, Clear, 0, Enter)

### CSS Classes
- `.lock-screen` - Main container
- `.lock-screen-title` - Title text
- `.lock-screen-pin` - PIN display
- `.lock-screen-info` - Info message
- `.lock-screen-error` - Error message
- `.lock-screen-button` - Keypad buttons

### Programmatic Usage
To lock the screen programmatically:
```python
screen.show_lock_screen()
```

To unlock the screen programmatically:
```python
screen.close_lock_screen()
```

## Customization

### Changing the Default PIN
To change the default PIN, modify the `default_pin` parameter in `panels/lock_screen.py`:
```python
def __init__(self, screen, title, default_pin="1234"):
```

### Styling
Modify the lock screen CSS in `styles/base.css` to customize:
- Colors
- Font sizes
- Button appearance
- Layout spacing

## Future Enhancements
Potential improvements for future versions:
- Configurable PIN via settings interface
- Auto-lock after inactivity timeout
- Multiple user PINs with different access levels
- PIN change functionality
- Forgot PIN recovery mechanism
- Lock screen timeout (auto-unlock after X hours)
- Integration with screensaver for automatic locking

## Technical Notes

### Lock Screen vs Screensaver
- **Screensaver**: Activated automatically after inactivity, blanks screen
- **Lock Screen**: Requires PIN to access, maintains display

### Security Considerations
- PIN is stored in plain text (suitable for physical access protection)
- For enhanced security, consider implementing encrypted storage
- Current implementation protects against casual unauthorized access

## Troubleshooting

### Lock icon not showing
- Ensure lock.svg exists in: `styles/[theme]/images/lock.svg`
- Check that the theme is properly loaded

### Cannot unlock with correct PIN
- Verify the default PIN hasn't been changed
- Check console logs for errors
- Ensure the panel is properly initialized

### Keypad not responding
- Check GTK event handling
- Verify button connections in the code
- Review console for click event errors
