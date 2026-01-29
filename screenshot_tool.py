#!/usr/bin/env python3
"""
Screenshot Automation Tool

Automates sequential screenshots with auto-scrolling for capturing
entire PDFs or long documents.

Usage:
    python screenshot_tool.py

Flow:
    1. Select which monitor to use
    2. Fullscreen overlay appears on that monitor
    3. Click and drag to select capture area
    4. Enter number of screenshots OR press Enter for continuous mode
    5. Script captures, scrolls, and repeats
    6. In continuous mode, press Escape to stop
"""

import platform
import time
from pathlib import Path

import pyautogui
from pynput import keyboard


# ============================================================================
# Terminal Colors
# ============================================================================

class Colors:
    """ANSI color codes for terminal output."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Colors
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    CYAN = "\033[36m"
    GRAY = "\033[90m"

    @staticmethod
    def success(text):
        return f"{Colors.GREEN}{text}{Colors.RESET}"

    @staticmethod
    def info(text):
        return f"{Colors.CYAN}{text}{Colors.RESET}"

    @staticmethod
    def warn(text):
        return f"{Colors.YELLOW}{text}{Colors.RESET}"

    @staticmethod
    def error(text):
        return f"{Colors.RED}{text}{Colors.RESET}"

    @staticmethod
    def bold(text):
        return f"{Colors.BOLD}{text}{Colors.RESET}"

    @staticmethod
    def dim(text):
        return f"{Colors.DIM}{text}{Colors.RESET}"

    @staticmethod
    def header(text):
        return f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.RESET}"


class MonitorInfo:
    """Simple class to hold monitor information."""
    def __init__(self, x, y, width, height, is_primary=False, name="", screen_index=0):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.is_primary = is_primary
        self.name = name
        self.screen_index = screen_index  # Index in NSScreen.screens()


def get_monitors_macos():
    """Get monitor information using macOS NSScreen APIs."""
    try:
        from AppKit import NSScreen

        monitors = []
        screens = NSScreen.screens()

        if not screens:
            return None

        # Find the total height for coordinate conversion
        # macOS uses bottom-left origin, pyautogui uses top-left
        all_frames = [s.frame() for s in screens]
        min_y = min(f.origin.y for f in all_frames)
        max_y = max(f.origin.y + f.size.height for f in all_frames)
        total_height = max_y - min_y

        for i, screen in enumerate(screens):
            frame = screen.frame()

            x = int(frame.origin.x)
            # Convert y from bottom-left to top-left coordinate system
            y = int(total_height - frame.origin.y - frame.size.height)
            width = int(frame.size.width)
            height = int(frame.size.height)

            is_primary = (i == 0)

            monitors.append(MonitorInfo(
                x=x,
                y=y,
                width=width,
                height=height,
                is_primary=is_primary,
                name=f"Display {i + 1}",
                screen_index=i
            ))

        return monitors

    except ImportError:
        return None


def get_monitors_fallback():
    """Fallback monitor detection."""
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    width = root.winfo_screenwidth()
    height = root.winfo_screenheight()
    root.destroy()
    return [MonitorInfo(0, 0, width, height, is_primary=True, name="Primary", screen_index=0)]


def select_monitor():
    """
    Display available monitors and let user select one.
    Returns the selected monitor object or None if cancelled.
    """
    if platform.system() == "Darwin":
        monitors = get_monitors_macos()
    else:
        monitors = None

    if not monitors:
        monitors = get_monitors_fallback()

    if len(monitors) == 1:
        m = monitors[0]
        print(f"\n{Colors.info('→')} Single monitor: {Colors.bold(f'{m.width}×{m.height}')}")
        return m

    print(f"\n{Colors.info('?')} Available monitors:")
    print(Colors.dim("   " + "─" * 50))
    for i, m in enumerate(monitors, 1):
        primary = Colors.dim(" (primary)") if m.is_primary else ""
        print(f"   {Colors.bold(str(i))}. {m.name}: {m.width}×{m.height} at ({m.x}, {m.y}){primary}")
    print(Colors.dim("   " + "─" * 50))

    while True:
        try:
            choice = input(f"\n   Select monitor {Colors.dim(f'[1-{len(monitors)}]')}: ").strip()
            if not choice:
                print(Colors.warn("Cancelled."))
                return None
            idx = int(choice) - 1
            if 0 <= idx < len(monitors):
                selected = monitors[idx]
                print(f"   {Colors.success('✓')} Selected: {Colors.bold(f'{selected.width}×{selected.height}')}")
                return selected
            else:
                print(Colors.warn(f"   Please enter a number between 1 and {len(monitors)}"))
        except ValueError:
            print(Colors.warn("   Invalid input. Enter a number or press Enter to cancel."))


# ============================================================================
# Native macOS Selection Overlay using PyObjC
# ============================================================================

# Import PyObjC components at module level to avoid class redefinition issues
import objc
from AppKit import (
    NSApplication, NSWindow, NSView, NSColor, NSScreen,
    NSBezierPath, NSFont, NSFontAttributeName, NSForegroundColorAttributeName,
    NSMutableDictionary, NSRunLoop, NSDate, NSDefaultRunLoopMode,
    NSApplicationActivationPolicyAccessory,
)


class KeyableWindow(NSWindow):
    """Custom window that can become key window even when borderless."""

    def canBecomeKeyWindow(self):
        return True

    def canBecomeMainWindow(self):
        return True


class SelectionView(NSView):
    """Custom view that handles mouse events and draws selection rectangle."""

    # Class-level storage for result (set before each use)
    _result_dict = None

    def initWithFrame_(self, frame):
        self = objc.super(SelectionView, self).initWithFrame_(frame)
        if self is not None:
            self.start_point = None
            self.current_point = None
        return self

    def acceptsFirstResponder(self):
        return True

    def canBecomeKeyView(self):
        return True

    def acceptsFirstMouse_(self, event):
        # Accept mouse clicks even when window isn't active
        return True

    def drawRect_(self, rect):
        # Fill with semi-transparent gray
        NSColor.colorWithCalibratedRed_green_blue_alpha_(0.5, 0.5, 0.5, 0.3).set()
        NSBezierPath.fillRect_(self.bounds())

        # Draw instructions using NSAttributedString for stability
        from AppKit import NSAttributedString
        instruction_text = "Click and drag to select area (Escape to cancel)"
        attrs = {
            NSFontAttributeName: NSFont.systemFontOfSize_(24),
            NSForegroundColorAttributeName: NSColor.whiteColor()
        }
        attr_string = NSAttributedString.alloc().initWithString_attributes_(instruction_text, attrs)

        text_size = attr_string.size()
        text_x = (self.bounds().size.width - text_size.width) / 2
        text_y = self.bounds().size.height - 100

        attr_string.drawAtPoint_((text_x, text_y))

        # Draw selection rectangle
        if self.start_point and self.current_point:
            x1, y1 = self.start_point
            x2, y2 = self.current_point

            rect_x = min(x1, x2)
            rect_y = min(y1, y2)
            rect_w = abs(x2 - x1)
            rect_h = abs(y2 - y1)

            selection_rect = ((rect_x, rect_y), (rect_w, rect_h))

            # Clear the selection area (make it transparent)
            NSColor.colorWithCalibratedRed_green_blue_alpha_(1.0, 1.0, 1.0, 0.1).set()
            NSBezierPath.fillRect_(selection_rect)

            # Draw red border
            NSColor.redColor().set()
            path = NSBezierPath.bezierPathWithRect_(selection_rect)
            path.setLineWidth_(3)
            path.stroke()

    def mouseDown_(self, event):
        loc = self.convertPoint_fromView_(event.locationInWindow(), None)
        self.start_point = (loc.x, loc.y)
        self.current_point = (loc.x, loc.y)
        self.setNeedsDisplay_(True)

    def mouseDragged_(self, event):
        loc = self.convertPoint_fromView_(event.locationInWindow(), None)
        self.current_point = (loc.x, loc.y)
        self.setNeedsDisplay_(True)

    def mouseUp_(self, event):
        loc = self.convertPoint_fromView_(event.locationInWindow(), None)
        self.current_point = (loc.x, loc.y)

        if self.start_point and self.current_point:
            x1, y1 = self.start_point
            x2, y2 = self.current_point

            rect_x = min(x1, x2)
            rect_y = min(y1, y2)
            rect_w = abs(x2 - x1)
            rect_h = abs(y2 - y1)

            if rect_w >= 10 and rect_h >= 10:
                # Convert from view coordinates to screen coordinates
                frame = self.window().frame()
                screen_x = frame.origin.x + rect_x
                screen_y_bottom = frame.origin.y + rect_y

                # Convert to top-left origin for pyautogui
                screens = NSScreen.screens()
                all_frames = [s.frame() for s in screens]
                max_y = max(f.origin.y + f.size.height for f in all_frames)

                screen_y = max_y - screen_y_bottom - rect_h

                if SelectionView._result_dict is not None:
                    SelectionView._result_dict["selection"] = (
                        int(screen_x), int(screen_y), int(rect_w), int(rect_h)
                    )

        if SelectionView._result_dict is not None:
            SelectionView._result_dict["done"] = True

    def keyDown_(self, event):
        # Escape key = keyCode 53
        if event.keyCode() == 53:
            if SelectionView._result_dict is not None:
                SelectionView._result_dict["cancelled"] = True
                SelectionView._result_dict["done"] = True


def get_selection_macos(monitor):
    """
    Show a native macOS overlay on the specified monitor and let user select an area.
    Returns (x, y, width, height) in screen coordinates or None if cancelled.
    """
    # Result storage
    result = {"selection": None, "cancelled": False, "done": False}
    SelectionView._result_dict = result

    # Get the target screen
    screens = NSScreen.screens()
    if monitor.screen_index >= len(screens):
        print(f"Screen index {monitor.screen_index} not found")
        return None

    target_screen = screens[monitor.screen_index]
    screen_frame = target_screen.frame()

    # Set up application (accessory mode = no dock icon)
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

    # Create borderless window that can become key (for mouse/keyboard events)
    window = KeyableWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        screen_frame,
        0,  # Borderless
        2,  # Buffered
        False
    )

    window.setBackgroundColor_(NSColor.clearColor())
    window.setOpaque_(False)
    window.setHasShadow_(False)
    window.setLevel_(25)  # Status window level
    window.setIgnoresMouseEvents_(False)  # Ensure window receives mouse events
    window.setAcceptsMouseMovedEvents_(True)  # Track mouse movement

    # Collection behavior for overlay
    window.setCollectionBehavior_(
        1 << 8    # FullScreenAuxiliary - allows window to appear over fullscreen apps
    )

    # Explicitly set the frame to ensure correct positioning
    window.setFrame_display_(screen_frame, True)

    # Create content view - frame is relative to window, so origin should be (0,0)
    content_frame = ((0, 0), (screen_frame.size.width, screen_frame.size.height))
    content_view = SelectionView.alloc().initWithFrame_(content_frame)
    window.setContentView_(content_view)

    # Show window on the specific screen
    window.makeKeyAndOrderFront_(None)
    window.makeFirstResponder_(content_view)

    app.activateIgnoringOtherApps_(True)

    # Run event loop until selection is made or cancelled
    # Use NSApplication event handling instead of NSRunLoop for proper mouse event processing
    NSEventMaskAny = 0xFFFFFFFF  # All event types
    while not result["done"]:
        event = app.nextEventMatchingMask_untilDate_inMode_dequeue_(
            NSEventMaskAny,
            NSDate.dateWithTimeIntervalSinceNow_(0.1),
            NSDefaultRunLoopMode,
            True
        )
        if event is not None:
            app.sendEvent_(event)
            app.updateWindows()

    # Clean up
    window.orderOut_(None)

    if result["cancelled"]:
        return None

    return result["selection"]


# ============================================================================
# macOS Selection using PyObjC window + pynput mouse events
# ============================================================================

def get_selection_macos_pynput(monitor):
    """
    Use PyObjC for window display with CGEventTap to capture AND consume mouse events.
    This blocks clicks from reaching apps behind the overlay.
    """
    from Quartz import (
        CGEventTapCreate, CGEventTapEnable, CFMachPortCreateRunLoopSource,
        CFRunLoopAddSource, CFRunLoopGetCurrent, CFRunLoopRunInMode,
        kCGSessionEventTap, kCGHeadInsertEventTap, kCGEventTapOptionDefault,
        CGEventMaskBit, kCGEventLeftMouseDown, kCGEventLeftMouseUp,
        kCGEventLeftMouseDragged, kCGEventKeyDown, CGEventGetLocation,
        CGEventGetIntegerValueField, kCGKeyboardEventKeycode,
        kCFRunLoopDefaultMode, CGDisplayBounds, CGMainDisplayID,
    )

    # State
    state = {
        "start_x": None,
        "start_y": None,
        "current_x": None,
        "current_y": None,
        "selecting": False,
        "done": False,
        "cancelled": False,
    }

    # Get target screen for window positioning (NSScreen)
    screens = NSScreen.screens()
    if monitor.screen_index >= len(screens):
        print(f"Screen index {monitor.screen_index} not found")
        return None

    target_screen = screens[monitor.screen_index]
    screen_frame = target_screen.frame()

    # Get bounds in Quartz/CG coordinates using display ID from NSScreen
    # CGDisplayBounds gives us the exact coordinates CGEventTap uses
    display_id = target_screen.deviceDescription().get('NSScreenNumber')
    if display_id:
        bounds = CGDisplayBounds(display_id)
        mon_left = int(bounds.origin.x)
        mon_top = int(bounds.origin.y)
        mon_right = mon_left + int(bounds.size.width)
        mon_bottom = mon_top + int(bounds.size.height)
    else:
        # Fallback: use main display bounds conversion
        main_bounds = CGDisplayBounds(CGMainDisplayID())
        mon_left = int(screen_frame.origin.x)
        mon_top = int(main_bounds.size.height - screen_frame.origin.y - screen_frame.size.height)
        mon_right = mon_left + int(screen_frame.size.width)
        mon_bottom = mon_top + int(screen_frame.size.height)

    def is_in_monitor(x, y):
        return mon_left <= x < mon_right and mon_top <= y < mon_bottom

    def quartz_to_view(x, y):
        """Convert Quartz/CG coords to NSView coords (bottom-left origin)."""
        vx = x - mon_left
        # CG y increases downward, NSView y increases upward
        vy = (mon_bottom - mon_top) - (y - mon_top)
        return vx, vy

    # Set up application
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

    # Create overlay window
    window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        screen_frame, 0, 2, False
    )
    window.setBackgroundColor_(NSColor.clearColor())
    window.setOpaque_(False)
    window.setHasShadow_(False)
    window.setLevel_(25)
    window.setIgnoresMouseEvents_(True)
    window.setFrame_display_(screen_frame, True)

    # View for drawing
    class OverlayView(NSView):
        def drawRect_(self, rect):
            NSColor.colorWithCalibratedRed_green_blue_alpha_(0.5, 0.5, 0.5, 0.3).set()
            NSBezierPath.fillRect_(self.bounds())

            from AppKit import NSAttributedString
            text = "Click and drag to select area (Escape to cancel)"
            attrs = {
                NSFontAttributeName: NSFont.systemFontOfSize_(24),
                NSForegroundColorAttributeName: NSColor.whiteColor()
            }
            attr_str = NSAttributedString.alloc().initWithString_attributes_(text, attrs)
            text_size = attr_str.size()
            text_x = (self.bounds().size.width - text_size.width) / 2
            text_y = self.bounds().size.height - 100
            attr_str.drawAtPoint_((text_x, text_y))

            if state["selecting"] and state["start_x"] is not None:
                vx1, vy1 = quartz_to_view(state["start_x"], state["start_y"])
                vx2, vy2 = quartz_to_view(state["current_x"], state["current_y"])

                rect_x = min(vx1, vx2)
                rect_y = min(vy1, vy2)
                rect_w = abs(vx2 - vx1)
                rect_h = abs(vy2 - vy1)

                if rect_w > 0 and rect_h > 0:
                    selection_rect = ((rect_x, rect_y), (rect_w, rect_h))
                    NSColor.colorWithCalibratedRed_green_blue_alpha_(1, 1, 1, 0.1).set()
                    NSBezierPath.fillRect_(selection_rect)
                    NSColor.redColor().set()
                    path = NSBezierPath.bezierPathWithRect_(selection_rect)
                    path.setLineWidth_(3)
                    path.stroke()

    content_frame = ((0, 0), (screen_frame.size.width, screen_frame.size.height))
    overlay_view = OverlayView.alloc().initWithFrame_(content_frame)
    window.setContentView_(overlay_view)

    # CGEventTap callback - captures events, only consumes on target monitor
    def event_callback(proxy, event_type, event, refcon):
        loc = CGEventGetLocation(event)
        x, y = int(loc.x), int(loc.y)

        # Handle Escape key - only consume Escape, let other keys through
        if event_type == kCGEventKeyDown:
            keycode = CGEventGetIntegerValueField(event, kCGKeyboardEventKeycode)
            if keycode == 53:  # Escape
                state["cancelled"] = True
                state["done"] = True
                return None  # Consume Escape
            return event  # Let other keys through

        # Only handle mouse events in our target monitor
        if not is_in_monitor(x, y):
            return event  # Pass through - don't interfere with other monitors

        if event_type == kCGEventLeftMouseDown:
            state["selecting"] = True
            state["start_x"] = x
            state["start_y"] = y
            state["current_x"] = x
            state["current_y"] = y
            return None  # Consume on our monitor

        elif event_type == kCGEventLeftMouseDragged:
            if state["selecting"]:
                state["current_x"] = x
                state["current_y"] = y
                return None  # Consume while selecting
            return event  # Pass through if not selecting

        elif event_type == kCGEventLeftMouseUp:
            if state["selecting"]:
                state["current_x"] = x
                state["current_y"] = y
                state["selecting"] = False
                state["done"] = True
                return None  # Consume
            return event  # Pass through if not selecting

        return event

    # Create event tap
    event_mask = (
        CGEventMaskBit(kCGEventLeftMouseDown) |
        CGEventMaskBit(kCGEventLeftMouseUp) |
        CGEventMaskBit(kCGEventLeftMouseDragged) |
        CGEventMaskBit(kCGEventKeyDown)
    )

    tap = CGEventTapCreate(
        kCGSessionEventTap,
        kCGHeadInsertEventTap,
        kCGEventTapOptionDefault,  # Can modify/consume events
        event_mask,
        event_callback,
        None
    )

    if tap is None:
        print("Failed to create event tap. Check Accessibility permissions.")
        return None

    # Add to run loop
    run_loop_source = CFMachPortCreateRunLoopSource(None, tap, 0)
    CFRunLoopAddSource(CFRunLoopGetCurrent(), run_loop_source, kCFRunLoopDefaultMode)
    CGEventTapEnable(tap, True)

    # Show window
    window.makeKeyAndOrderFront_(None)
    app.activateIgnoringOtherApps_(True)

    # Event loop - process both CGEventTap and window updates
    while not state["done"]:
        # Process CGEventTap events
        CFRunLoopRunInMode(kCFRunLoopDefaultMode, 0.016, False)  # ~60fps
        # Update window
        overlay_view.setNeedsDisplay_(True)
        NSRunLoop.currentRunLoop().runMode_beforeDate_(
            NSDefaultRunLoopMode,
            NSDate.dateWithTimeIntervalSinceNow_(0.001)
        )

    # Clean up - fully release the overlay window
    CGEventTapEnable(tap, False)
    window.orderOut_(None)
    window.setContentView_(None)  # Release the view
    overlay_view = None
    window = None
    # Give window server time to process
    time.sleep(0.1)

    if state["cancelled"]:
        return None

    # Calculate final selection
    if state["start_x"] is not None and state["current_x"] is not None:
        x1, y1 = state["start_x"], state["start_y"]
        x2, y2 = state["current_x"], state["current_y"]

        rect_x = min(x1, x2)
        rect_y = min(y1, y2)
        rect_w = abs(x2 - x1)
        rect_h = abs(y2 - y1)

        if rect_w >= 10 and rect_h >= 10:
            return (int(rect_x), int(rect_y), int(rect_w), int(rect_h))

    return None


# ============================================================================
# Fallback tkinter Selection Overlay
# ============================================================================

def get_selection_tkinter(monitor):
    """Fallback selection using tkinter (for non-macOS)."""
    import tkinter as tk

    result = {"selection": None}

    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-alpha", 0.3)
    root.attributes("-topmost", True)
    root.configure(bg="gray")

    x_str = f"+{monitor.x}" if monitor.x >= 0 else str(monitor.x)
    y_str = f"+{monitor.y}" if monitor.y >= 0 else str(monitor.y)
    root.geometry(f"{monitor.width}x{monitor.height}{x_str}{y_str}")

    canvas = tk.Canvas(root, cursor="cross", bg="gray", highlightthickness=0)
    canvas.pack(fill=tk.BOTH, expand=True)

    state = {"start_x": None, "start_y": None, "rect_id": None}

    def on_press(event):
        state["start_x"] = event.x
        state["start_y"] = event.y
        state["rect_id"] = canvas.create_rectangle(
            event.x, event.y, event.x, event.y, outline="red", width=3
        )

    def on_drag(event):
        if state["rect_id"]:
            canvas.coords(state["rect_id"], state["start_x"], state["start_y"], event.x, event.y)

    def on_release(event):
        x1 = min(state["start_x"], event.x)
        y1 = min(state["start_y"], event.y)
        x2 = max(state["start_x"], event.x)
        y2 = max(state["start_y"], event.y)
        w, h = x2 - x1, y2 - y1
        if w >= 10 and h >= 10:
            result["selection"] = (monitor.x + x1, monitor.y + y1, w, h)
        root.quit()

    def on_escape(event):
        root.quit()

    canvas.bind("<ButtonPress-1>", on_press)
    canvas.bind("<B1-Motion>", on_drag)
    canvas.bind("<ButtonRelease-1>", on_release)
    root.bind("<Escape>", on_escape)

    label = tk.Label(root, text="Click and drag to select (Escape to cancel)",
                     font=("Helvetica", 24), fg="white", bg="gray")
    label.place(relx=0.5, rely=0.1, anchor=tk.CENTER)

    root.lift()
    root.focus_force()
    root.mainloop()
    root.destroy()

    return result["selection"]


def get_selection(monitor):
    """Get area selection from user on the specified monitor."""
    if platform.system() == "Darwin":
        return get_selection_macos_pynput(monitor)
    else:
        return get_selection_tkinter(monitor)


# ============================================================================
# Selection Border Overlay (visible during capture)
# ============================================================================

class SelectionBorderOverlay:
    """
    A transparent overlay that shows just a red border around the selection area.
    Stays visible during screenshot capture so user can see what's being captured.
    """

    def __init__(self, selection):
        """
        Create border overlay for the given selection.
        selection: (x, y, width, height) in screen coordinates (top-left origin)
        """
        self.window = None
        self.selection = selection

        if platform.system() != "Darwin":
            return

        x, y, width, height = selection

        # Convert from top-left origin (pyautogui) to bottom-left origin (NSWindow)
        screens = NSScreen.screens()
        all_frames = [s.frame() for s in screens]
        max_y = max(f.origin.y + f.size.height for f in all_frames)

        # NSWindow origin is bottom-left
        ns_x = x
        ns_y = max_y - y - height

        # Create a borderless, transparent window
        frame = ((ns_x, ns_y), (width, height))

        self.window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            frame, 0, 2, False
        )
        self.window.setBackgroundColor_(NSColor.clearColor())
        self.window.setOpaque_(False)
        self.window.setHasShadow_(False)
        self.window.setLevel_(25)  # Above normal windows
        self.window.setIgnoresMouseEvents_(True)  # Click-through

        # Create a view that draws just the border
        class BorderView(NSView):
            def drawRect_(self, rect):
                # Draw red border
                NSColor.redColor().set()
                path = NSBezierPath.bezierPathWithRect_(self.bounds())
                path.setLineWidth_(3)
                path.stroke()

        content_view = BorderView.alloc().initWithFrame_(((0, 0), (width, height)))
        self.window.setContentView_(content_view)

    def show(self):
        """Show the border overlay."""
        if self.window:
            self.window.orderFront_(None)

    def hide(self):
        """Hide the border overlay (can be shown again)."""
        if self.window:
            self.window.orderOut_(None)

    def destroy(self):
        """Fully release the border overlay."""
        if self.window:
            self.window.orderOut_(None)
            self.window.setContentView_(None)
            self.window = None


# ============================================================================
# Screenshot Capture
# ============================================================================

class EscapeListener:
    """Listens for Escape key press in a background thread."""

    def __init__(self):
        self.stopped = False
        self.listener = None

    def on_press(self, key):
        if key == keyboard.Key.esc:
            self.stopped = True
            return False

    def start(self):
        self.stopped = False
        self.listener = keyboard.Listener(on_press=self.on_press)
        self.listener.start()

    def stop(self):
        if self.listener:
            self.listener.stop()


def capture_screenshot(region, output_path):
    """Capture a screenshot of the specified region and save as PNG (lossless)."""
    x, y, width, height = region
    screenshot = pyautogui.screenshot(region=(x, y, width, height))
    screenshot.save(output_path, "PNG")


def smooth_scroll(amount, steps=10, delay=0.02):
    """
    Perform a smooth scroll by breaking it into smaller increments.

    Args:
        amount: Total scroll amount (negative = down, positive = up)
        steps: Number of scroll increments
        delay: Delay between each step in seconds
    """
    step_amount = amount // steps
    remainder = amount % steps

    for i in range(steps):
        # Add remainder to first step to ensure total is exact
        scroll_step = step_amount + (remainder if i == 0 else 0)
        pyautogui.scroll(scroll_step)
        time.sleep(delay)


def smooth_scroll_pixels(pixels, steps=15, delay=0.015):
    """
    Perform smooth pixel-precise scrolling on macOS using Quartz.

    Args:
        pixels: Total pixels to scroll (negative = down, positive = up)
        steps: Number of scroll increments
        delay: Delay between each step in seconds
    """
    if platform.system() != "Darwin":
        # Fallback to regular scroll for non-macOS (rough approximation)
        smooth_scroll(pixels // 10, steps, delay)
        return

    from Quartz import (
        CGEventCreateScrollWheelEvent,
        CGEventPost,
        kCGHIDEventTap,
        kCGScrollEventUnitPixel,
    )

    step_pixels = pixels // steps
    remainder = pixels % steps

    for i in range(steps):
        scroll_step = step_pixels + (remainder if i == 0 else 0)
        # Create pixel-precise scroll event
        # Args: source, units, wheelCount, wheel1 (vertical)
        event = CGEventCreateScrollWheelEvent(
            None,
            kCGScrollEventUnitPixel,
            1,  # number of wheels
            scroll_step
        )
        CGEventPost(kCGHIDEventTap, event)
        time.sleep(delay)


# ============================================================================
# OCR using macOS Vision Framework
# ============================================================================

def clean_ocr_text(text):
    """
    Clean up OCR output by removing garbled characters, image noise, and normalizing whitespace.
    """
    import re

    # Remove Unicode replacement characters and other common OCR artifacts
    text = text.replace('\ufffd', '')

    # Remove other common garbled characters
    text = re.sub(r'[￿¥£¢€•]', '', text)

    # Remove sequences of special characters that are likely noise
    text = re.sub(r'[*#@$%&]+', ' ', text)

    # Normalize multiple spaces/newlines
    text = re.sub(r' +', ' ', text)
    text = re.sub(r'\n\s*\n', '\n\n', text)

    # Filter out noise lines (from embedded images, diagrams, etc.)
    lines = text.split('\n')
    cleaned_lines = []

    for line in lines:
        line = line.strip()

        # Skip empty lines (but preserve paragraph breaks)
        if not line:
            if cleaned_lines and cleaned_lines[-1] != '':
                cleaned_lines.append('')
            continue

        # Skip very short lines (likely noise from icons/graphics)
        if len(line) < 4:
            continue

        # Skip lines that are mostly symbols/punctuation
        alnum_count = sum(1 for c in line if c.isalnum() or c.isspace())
        if alnum_count < len(line) * 0.6:
            continue

        # Skip lines that look like diagram labels (short, no sentence structure)
        words = line.split()
        if len(words) <= 3:
            # Check if it looks like a real short message vs diagram noise
            # Real messages usually have common words or punctuation
            has_common_pattern = bool(re.search(r'[.!?,:]|^(Hi|I |OK|Yes|No|Sure|Thanks)', line, re.IGNORECASE))
            has_timestamp = bool(re.search(r'\d{1,2}:\d{2}|AM|PM|Monday|Tuesday|Wednesday|Thursday|Friday', line))
            has_name_pattern = bool(re.search(r'\[TECH\]|@|\w+,\s+\w+', line))

            # If short line has none of these patterns, likely noise
            if not (has_common_pattern or has_timestamp or has_name_pattern):
                # Check if it's mostly gibberish (random caps, no real words)
                real_words = sum(1 for w in words if len(w) > 2 and w.isalpha() and not w.isupper())
                if real_words < len(words) * 0.5:
                    continue

        # Skip lines that look like workflow diagram text
        diagram_patterns = [
            r'^Entity\s+O',  # Entity Originator
            r'Orgnator',     # Garbled "Originator"
            r'Originator',   # Clean version
            r'EDM\s*Ana',    # EDM Analyst
            r'CDM\s*Ana',    # Garbled EDM Analyst
            r'Analyst\s*\(?Review',  # Analyst (Review) or Analyst Review
            r'^Completion$',
            r'Compation',    # Garbled "Completion"
            r'^Review\)$',
            r'——',           # Long dashes from diagrams
            r'^\w{2}\d{4,}$',  # IDs like DI4937, KB53473
            r'^ouster',
            r'^rosters$',
            r'EnttyOrg',     # Garbled "Entity Org"
        ]
        if any(re.search(p, line, re.IGNORECASE) for p in diagram_patterns):
            continue

        cleaned_lines.append(line)

    # Remove trailing empty lines
    while cleaned_lines and cleaned_lines[-1] == '':
        cleaned_lines.pop()

    return '\n'.join(cleaned_lines).strip()


def ocr_image(image_path):
    """
    Extract text from image using Tesseract OCR.
    Returns extracted text as a string, or None if OCR fails.
    """
    import subprocess

    try:
        # Run tesseract OCR
        result = subprocess.run(
            ['tesseract', str(image_path), 'stdout', '-l', 'eng', '--psm', '6'],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            print(f"  [OCR] Tesseract error: {result.stderr}")
            return None

        text = result.stdout.strip()
        if text:
            return clean_ocr_text(text)
        return None

    except FileNotFoundError:
        print("  [OCR] Tesseract not installed. Install with: brew install tesseract")
        return None
    except subprocess.TimeoutExpired:
        print("  [OCR] Tesseract timed out")
        return None
    except Exception as e:
        print(f"  [OCR] Error during text recognition: {e}")
        return None


def find_overlap_index(existing_lines, new_lines, max_overlap=15):
    """
    Find where new_lines overlap with the end of existing_lines.
    Returns the index in new_lines where non-overlapping content starts.

    Algorithm: Look for the longest matching sequence where the end of
    existing_lines matches the beginning of new_lines.
    """
    if not existing_lines or not new_lines:
        return 0

    # Limit how far back we look in existing text
    check_lines = existing_lines[-max_overlap:]

    # Try to find overlap starting from longest possible
    for overlap_size in range(min(len(check_lines), len(new_lines)), 0, -1):
        # Check if last 'overlap_size' lines of existing match first 'overlap_size' of new
        existing_suffix = check_lines[-overlap_size:]
        new_prefix = new_lines[:overlap_size]

        # Normalize whitespace for comparison
        existing_normalized = [line.strip() for line in existing_suffix]
        new_normalized = [line.strip() for line in new_prefix]

        if existing_normalized == new_normalized:
            return overlap_size

    return 0


def append_text_deduplicated(txt_path, new_text, overlap_lines=15):
    """
    Append new OCR text to file, skipping overlapping content from previous screenshots.

    Args:
        txt_path: Path to the text file
        new_text: Newly extracted OCR text
        overlap_lines: Maximum number of lines to check for overlap
    """
    if not new_text or not new_text.strip():
        return

    new_lines = new_text.strip().split("\n")

    # If file doesn't exist or is empty, write everything
    if not txt_path.exists() or txt_path.stat().st_size == 0:
        with open(txt_path, "a", encoding="utf-8") as f:
            f.write(new_text.strip() + "\n")
        return

    # Read last N lines from existing file
    try:
        with open(txt_path, "r", encoding="utf-8") as f:
            existing_lines = f.read().strip().split("\n")
    except Exception:
        existing_lines = []

    # Find where overlap ends
    overlap_idx = find_overlap_index(existing_lines, new_lines, overlap_lines)

    # Append non-overlapping portion
    if overlap_idx < len(new_lines):
        non_overlapping = new_lines[overlap_idx:]
        with open(txt_path, "a", encoding="utf-8") as f:
            f.write("\n".join(non_overlapping) + "\n")


def main():
    """Main entry point."""
    print(Colors.header("\n  Screenshot Automation Tool"))
    print(Colors.dim("  " + "─" * 36))

    # Select monitor
    monitor = select_monitor()
    if monitor is None:
        return

    print(f"\n{Colors.info('→')} A selection overlay will appear on the selected monitor.")
    print(f"{Colors.info('→')} Click and drag to select the capture area.")
    print(f"{Colors.dim('  Press Escape to cancel.')}\n")

    time.sleep(0.5)

    # Get selection
    selection = get_selection(monitor)

    if selection is None:
        print(Colors.warn("Selection cancelled or invalid. Exiting."))
        return

    x, y, width, height = selection
    print(f"\n{Colors.success('✓')} Selected area: {Colors.bold(f'{width}×{height}')} at ({x}, {y})")

    # Get number of screenshots
    user_input = input(
        f"\n{Colors.info('?')} Number of screenshots {Colors.dim('(Enter for continuous)')}: "
    ).strip()

    continuous_mode = False
    num_screenshots = None

    if user_input == "":
        continuous_mode = True
        print(f"\n{Colors.warn('⚡')} {Colors.bold('CONTINUOUS MODE')}")
        print(Colors.dim("   Press Escape at any time to stop capturing."))
    else:
        try:
            num_screenshots = int(user_input)
            if num_screenshots < 1:
                print(Colors.error("Must take at least 1 screenshot. Exiting."))
                return
        except ValueError:
            print(Colors.error("Invalid number. Exiting."))
            return

    # Get scroll mode
    print(f"\n{Colors.info('?')} Scroll mode:")
    print(f"   {Colors.bold('1.')} Messages {Colors.dim('(85% scroll with overlap - for chats)')}")
    print(f"   {Colors.bold('2.')} Page/PDF {Colors.dim('(110% scroll - for documents)')}")
    scroll_mode = input(f"   Select {Colors.dim('[1/2, default: 1]')}: ").strip()
    page_mode = (scroll_mode == "2")

    # Create output directory
    output_dir = Path(__file__).parent / "screenshots"
    output_dir.mkdir(exist_ok=True)

    # Clear previous screenshots and OCR text
    for old_file in output_dir.glob("screenshot_*.png"):
        old_file.unlink()
    for old_file in output_dir.glob("screenshot_*.jpg"):
        old_file.unlink()
    txt_file = output_dir / "extracted_text.txt"
    if txt_file.exists():
        txt_file.unlink()
    print(Colors.dim(f"   Cleared previous files from {output_dir}"))

    # Initialize OCR text file
    txt_path = output_dir / "extracted_text.txt"
    from datetime import datetime
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(f"# OCR Extracted Text\n")
        f.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# Selection: x={x}, y={y}, width={width}, height={height}\n")
        f.write(f"# {'=' * 50}\n\n")

    import random

    print(f"\n{Colors.header('Starting capture in 3 seconds...')}")
    if continuous_mode:
        print(f"   Mode:   {Colors.warn('Continuous')} {Colors.dim('(press Escape to stop)')}")
    else:
        print(f"   Mode:   {Colors.info(f'{num_screenshots} screenshots')}")
    if page_mode:
        print(f"   Scroll: {Colors.info(f'{int(height * 1.1)}px')} {Colors.dim('(110% of selection)')}")
    else:
        print(f"   Scroll: {Colors.info(f'~{int(height * 0.85)}px')} {Colors.dim('(85% with overlap)')}")
    time.sleep(3)

    # Click middle-right of selection to ensure focus
    click_x = x + width - 50  # 50px from right edge
    click_y = y + height // 2
    pyautogui.click(click_x, click_y)
    time.sleep(0.3)

    # Show red border overlay during capture
    border_overlay = SelectionBorderOverlay(selection)
    border_overlay.show()

    # Set up escape listener
    escape_listener = None
    if continuous_mode:
        escape_listener = EscapeListener()
        escape_listener.start()

    # Capture loop
    i = 0
    while True:
        if not continuous_mode and i >= num_screenshots:
            break
        if continuous_mode and escape_listener.stopped:
            print(f"\n\n{Colors.warn('⏹')}  Escape pressed - stopping capture.")
            break

        filename = output_dir / f"screenshot_{i + 1:03d}.png"
        # Hide border so it's not captured in screenshot
        border_overlay.hide()
        time.sleep(0.15)  # Give window server time to fully hide the overlay
        capture_screenshot(selection, filename)
        border_overlay.show()  # Show border again
        print(f"   {Colors.success('✓')} {filename.name}", end="")

        # Run OCR on the captured screenshot
        ocr_text = ocr_image(filename)
        if ocr_text:
            append_text_deduplicated(txt_path, ocr_text)
            word_count = len(ocr_text.split())
            print(f" {Colors.dim('│')} OCR: {Colors.info(f'{word_count} words')}", end="")

        if continuous_mode:
            print(f" {Colors.dim('(Esc to stop)')}", end="")
        print()

        i += 1

        # Scroll down based on selected mode
        if page_mode:
            # Scroll 110% of height to minimize overlap while OCR dedup handles remainder
            # Use pixel-precise scrolling for exact page movement
            scroll_amount = int(height * 1.1)
            smooth_scroll_pixels(-scroll_amount, steps=15, delay=0.015)
        else:
            # Messages mode - 85% with small variance for overlap
            base_scroll = int(height * 0.85)
            scroll_amount = base_scroll + random.randint(-int(height * 0.02), int(height * 0.02))
            smooth_scroll(-scroll_amount, steps=15, delay=0.015)  # Smooth scroll over ~225ms
        time.sleep(0.3)  # Wait for scroll to settle

    if escape_listener:
        escape_listener.stop()

    # Fully release the border overlay
    border_overlay.destroy()

    print(f"\n{Colors.success('✓')} {Colors.bold('Done!')} {i} screenshots saved")
    print(f"   {Colors.dim('Screenshots:')} {output_dir}")
    if txt_path.exists() and txt_path.stat().st_size > 0:
        print(f"   {Colors.dim('OCR text:   ')} {txt_path}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nCancelled by user.")
        exit(0)
