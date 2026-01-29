# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Project Overview

macOS screenshot automation tool for capturing sequential screenshots with auto-scrolling. Primary use case: capturing entire PDFs or long documents by selecting a region, then automatically taking screenshots while scrolling.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the tool
python screenshot_tool.py
```

**Note**: Requires macOS Accessibility permissions for CGEventTap (System Preferences > Privacy & Security > Accessibility).

## Architecture

Single-file Python application (`screenshot_tool.py`) with these subsystems:

### Terminal UI
- `Colors` class provides ANSI color formatting for terminal output
- Clean, minimal interface with visual hierarchy

### Monitor Detection
- **macOS**: Uses `AppKit.NSScreen` to enumerate displays with coordinate system conversion (macOS uses bottom-left origin, pyautogui uses top-left)
- **Fallback**: tkinter for screen dimensions

### Selection Overlay
- **macOS primary** (`get_selection_macos_pynput`): PyObjC window with Quartz `CGEventTap` for mouse event interception. The event tap captures AND consumes mouse events only on the target monitor.
- **macOS alternative** (`get_selection_macos`): Pure PyObjC using `NSApplication` event loop
- **Non-macOS**: tkinter overlay with canvas drawing

### Screenshot Capture
- Uses `pyautogui.screenshot()` for region capture
- `pynput.keyboard.Listener` for Escape key detection in continuous mode
- Two scroll modes:
  - **Messages**: `smooth_scroll()` with pyautogui - 85% scroll with variance
  - **Page/PDF**: `smooth_scroll_pixels()` with Quartz `CGEventCreateScrollWheelEvent` using `kCGScrollEventUnitPixel` for pixel-precise 110% scroll

### OCR Text Extraction
- Uses Tesseract via subprocess for text recognition
- `clean_ocr_text()` filters noise from diagrams and UI elements
- `find_overlap_index()` detects overlapping lines between consecutive screenshots
- `append_text_deduplicated()` appends only non-overlapping text to output file

## Key Coordinate Systems

The code converts between three coordinate systems:
1. **NSScreen/AppKit**: Origin at bottom-left of primary display
2. **Quartz/CGEventTap**: Origin at top-left of primary display
3. **pyautogui**: Origin at top-left of primary display

The `quartz_to_view()` function handles CG to NSView conversion for drawing the selection rectangle.

## Output

- Screenshots: `./screenshots/screenshot_001.png`, etc. (PNG format)
- Extracted text: `./screenshots/extracted_text.txt` (deduplicated OCR output)

## Key Functions

| Function | Purpose |
|----------|---------|
| `smooth_scroll()` | Scroll using pyautogui wheel units (Messages mode) |
| `smooth_scroll_pixels()` | Pixel-precise scroll using Quartz (Page/PDF mode) |
| `get_selection_macos_pynput()` | Main selection overlay with CGEventTap |
| `SelectionBorderOverlay` | Red border shown during capture |
| `append_text_deduplicated()` | OCR text deduplication |
