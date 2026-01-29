<div align="center">

# scrollshot

**Automated Sequential Screenshot Capture with Auto-Scrolling**

[![Version](https://img.shields.io/badge/Version-1.0.0-red?logo=github&logoColor=white)](https://github.com/Zer0Wav3s/scrollshot/releases)
[![macOS](https://img.shields.io/badge/macOS-Quartz-blue?logo=apple&logoColor=white)](https://developer.apple.com/documentation/coregraphics)
[![Python](https://img.shields.io/badge/Python-3.8+-green?logo=python&logoColor=white)](https://www.python.org)
[![Tesseract](https://img.shields.io/badge/Tesseract-OCR-orange?logo=tesseract&logoColor=white)](https://github.com/tesseract-ocr/tesseract)

</div>

> **Disclaimer**: This is an experimental project provided as-is. The author assumes no responsibility for how this tool is used. By using this software, you agree that you are solely responsible for ensuring your use complies with applicable laws and terms of service. Use at your own risk.

---

A macOS command-line tool for capturing sequential screenshots with automatic scrolling. Designed for capturing entire PDFs, long documents, or chat histories.

## Features

- **Region Selection**: Visual overlay to select any screen area
- **Auto-Scrolling**: Automatically scrolls and captures in sequence
- **Two Scroll Modes**:
  - **Messages**: 85% scroll with overlap (ideal for chats)
  - **Page/PDF**: 110% pixel-precise scroll (ideal for documents)
- **OCR Extraction**: Extracts text from screenshots with automatic deduplication
- **Multi-Monitor Support**: Works across multiple displays
- **Continuous Mode**: Keep capturing until you press Escape

## Requirements

- macOS (uses native Quartz APIs for pixel-precise scrolling)
- Python 3.8+
- Accessibility permissions enabled

## Installation

```bash
# Clone the repository
git clone https://github.com/Zer0Wav3s/scrollshot.git
cd scrollshot

# Install dependencies
pip install -r requirements.txt

# Install Tesseract for OCR (optional)
brew install tesseract
```

### Enable Accessibility Permissions

The tool requires Accessibility permissions to capture mouse events:

1. Open **System Preferences** (or System Settings on macOS Ventura+)
2. Go to **Privacy & Security** > **Accessibility**
3. Add your terminal application (Terminal, iTerm2, etc.)

## Usage

```bash
python screenshot_tool.py
```

### Workflow

1. **Select Monitor** - Choose which display to capture from
2. **Draw Selection** - Click and drag to define the capture area
3. **Set Count** - Enter number of screenshots or press Enter for continuous mode
4. **Choose Mode** - Select Messages (overlap) or Page/PDF (exact scroll)
5. **Capture** - Tool auto-scrolls and captures; press Escape to stop

### Output

Screenshots and extracted text are saved to `./screenshots/`:

```
screenshots/
  screenshot_001.png
  screenshot_002.png
  screenshot_003.png
  extracted_text.txt
```

## Scroll Modes

| Mode | Scroll Amount | Best For |
|------|---------------|----------|
| Messages | 85% of selection height | Chat apps, social media feeds |
| Page/PDF | 110% of selection height | PDFs, documents, web pages |

The Messages mode intentionally overlaps to ensure no content is missed. The Page/PDF mode scrolls slightly more than the selection height to minimize duplicate content while OCR deduplication handles any remaining overlap.

## How It Works

1. **Selection Overlay**: Creates a transparent overlay window using PyObjC
2. **Mouse Capture**: Uses Quartz `CGEventTap` to intercept mouse events on the target monitor only
3. **Pixel-Precise Scrolling**: Uses `CGEventCreateScrollWheelEvent` with `kCGScrollEventUnitPixel` for exact scroll distances
4. **OCR**: Runs Tesseract on each screenshot and deduplicates overlapping text

## Troubleshooting

### "Failed to create event tap"
Enable Accessibility permissions for your terminal app (see Installation).

### Scrolling too fast or too slow
The tool uses pixel-precise scrolling on macOS. If scrolling seems off, try adjusting your selection area or switching scroll modes.

### OCR not working
Install Tesseract: `brew install tesseract`

## License

MIT

---

This software is provided "as is", without warranty of any kind. See [LICENSE](LICENSE) for details.
