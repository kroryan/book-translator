"""
Book Translator Desktop Application
====================================
This file wraps the Flask application to run as a desktop app.
Includes system tray support to keep the server running in background.
"""

import sys
import os
import subprocess

# Determine if we're running as a packaged .exe
if getattr(sys, 'frozen', False):
    # Running as packaged .exe (PyInstaller)
    BUNDLE_DIR = sys._MEIPASS
    APP_DIR = os.path.dirname(sys.executable)
else:
    # Running as a normal Python script
    BUNDLE_DIR = os.path.dirname(os.path.abspath(__file__))
    APP_DIR = BUNDLE_DIR

# Change to the application directory
os.chdir(APP_DIR)

# Create necessary folders if they don't exist
for folder in ['uploads', 'translations', 'logs']:
    folder_path = os.path.join(APP_DIR, folder)
    os.makedirs(folder_path, exist_ok=True)

# Configure paths for translator.py
os.environ['BOOK_TRANSLATOR_APP_DIR'] = APP_DIR
os.environ['BOOK_TRANSLATOR_BUNDLE_DIR'] = BUNDLE_DIR

# Add directories to path
sys.path.insert(0, APP_DIR)
sys.path.insert(0, BUNDLE_DIR)

# Import the Flask application
from translator import app, VERBOSE_DEBUG, Colors

# Import pystray for system tray
try:
    import pystray
    from PIL import Image, ImageDraw
    HAS_PYSTRAY = True
except ImportError:
    HAS_PYSTRAY = False
    print("pystray not installed, tray mode disabled")

import webbrowser
import threading
import time

# Global variables
flask_thread = None
tray_icon = None
server_port = 5001
APP_URL = f'http://localhost:{server_port}'


def check_ollama():
    """Check if Ollama is running"""
    import requests
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        return response.status_code == 200
    except:
        return False


def print_banner():
    """Display startup banner"""
    print(f"\n{Colors.CYAN}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.GREEN}  📚 BOOK TRANSLATOR - Desktop Edition{Colors.RESET}")
    print(f"{Colors.CYAN}{'='*60}{Colors.RESET}")
    print(f"  Version: 1.2.0 (Tray Mode)")
    print(f"  Server: {APP_URL}")
    print(f"  Working Directory: {os.getcwd()}")
    print(f"{Colors.CYAN}{'='*60}{Colors.RESET}\n")


def create_app_icon():
    """Create a proper icon for the application"""
    # Create a 256x256 image with transparency
    size = 256
    image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    
    # Draw a book shape
    # Book cover (blue)
    draw.rounded_rectangle([20, 20, 236, 236], radius=20, fill=(41, 128, 185, 255))
    
    # Inner cover highlight
    draw.rounded_rectangle([30, 30, 226, 226], radius=15, fill=(52, 152, 219, 255))
    
    # Pages (white/cream)
    draw.rounded_rectangle([50, 40, 220, 216], radius=10, fill=(253, 253, 253, 255))
    
    # Book spine (darker blue)
    draw.rounded_rectangle([20, 20, 60, 236], radius=10, fill=(31, 97, 141, 255))
    
    # Text lines on pages
    line_color = (189, 195, 199, 255)
    y_positions = [70, 100, 130, 160, 190]
    for y in y_positions:
        width = 140 if y != 190 else 100
        draw.rounded_rectangle([75, y, 75 + width, y + 12], radius=3, fill=line_color)
    
    # Translation arrow symbol (green)
    draw.polygon([
        (160, 85), (200, 128), (160, 171),
        (160, 145), (120, 145), (120, 111), (160, 111)
    ], fill=(46, 204, 113, 255))
    
    return image


def create_tray_icon_image():
    """Create a smaller icon for the system tray"""
    icon = create_app_icon()
    return icon.resize((64, 64), Image.Resampling.LANCZOS)


def save_app_icon():
    """Save the application icon as ICO file"""
    icon_path = os.path.join(APP_DIR, 'app_icon.ico')
    try:
        icon = create_app_icon()
        # Save with multiple sizes for ICO
        icon.save(icon_path, format='ICO', sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
        print(f"{Colors.GREEN}✓ Application icon saved: {icon_path}{Colors.RESET}")
        return icon_path
    except Exception as e:
        print(f"{Colors.YELLOW}⚠ Could not save icon: {e}{Colors.RESET}")
        return None


def start_flask_server():
    """Start Flask server in a separate thread"""
    print(f"{Colors.GREEN}🚀 Starting Flask server on port {server_port}...{Colors.RESET}")
    app.run(host='127.0.0.1', port=server_port, debug=False, use_reloader=False, threaded=True)


def open_app_window(icon=None, item=None):
    """Open the translator in the default browser"""
    print(f"{Colors.CYAN}🌐 Opening application in browser...{Colors.RESET}")
    try:
        webbrowser.open(APP_URL)
        print(f"{Colors.GREEN}✓ Browser opened successfully{Colors.RESET}")
    except Exception as e:
        print(f"{Colors.RED}✗ Could not open browser: {e}{Colors.RESET}")


def quit_app(icon=None, item=None):
    """Completely quit the application"""
    print(f"\n{Colors.YELLOW}👋 Shutting down Book Translator...{Colors.RESET}")
    if tray_icon:
        tray_icon.stop()
    os._exit(0)


def create_tray_menu():
    """Create the system tray menu"""
    return pystray.Menu(
        pystray.MenuItem("📖 Open Book Translator", open_app_window, default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(f"🌐 Server: localhost:{server_port}", lambda: None, enabled=False),
        pystray.MenuItem("✅ Server Running", lambda: None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("❌ Quit Completely", quit_app)
    )


def run_with_tray():
    """Run the app with system tray support"""
    global flask_thread, tray_icon
    
    print(f"{Colors.GREEN}🚀 Starting in System Tray mode...{Colors.RESET}")
    print(f"{Colors.CYAN}   The server runs in background.{Colors.RESET}")
    print(f"{Colors.CYAN}   Close browser tab anytime - reopen from tray icon.{Colors.RESET}")
    print(f"{Colors.YELLOW}   To fully quit: right-click tray icon → Quit Completely{Colors.RESET}\n")
    
    # Save the application icon
    save_app_icon()
    
    # Start Flask server in background thread
    flask_thread = threading.Thread(target=start_flask_server, daemon=True)
    flask_thread.start()
    
    # Give server time to start
    print(f"{Colors.YELLOW}⏳ Starting server...{Colors.RESET}")
    time.sleep(3)
    
    # Open browser window automatically
    print(f"{Colors.GREEN}✓ Server started!{Colors.RESET}")
    open_app_window()
    
    # Create and run system tray icon
    icon_image = create_tray_icon_image()
    tray_icon = pystray.Icon(
        "BookTranslator",
        icon_image,
        "Book Translator - Click to Open",
        menu=create_tray_menu()
    )
    
    print(f"\n{Colors.GREEN}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.GREEN}✓ Book Translator is running!{Colors.RESET}")
    print(f"{Colors.GREEN}{'='*60}{Colors.RESET}")
    print(f"  🌐 URL: {APP_URL}")
    print(f"  📌 System tray icon active")
    print(f"  💡 Close browser anytime - server keeps running")
    print(f"  🔄 Click tray icon to reopen")
    print(f"{Colors.GREEN}{'='*60}{Colors.RESET}\n")
    
    # Run the tray icon (this blocks but keeps the app alive)
    tray_icon.run()


def run_simple():
    """Run without tray (fallback)"""
    print(f"{Colors.GREEN}🚀 Starting Flask server...{Colors.RESET}")
    print(f"{Colors.CYAN}   URL: {APP_URL}{Colors.RESET}")
    print(f"\n{Colors.RED}   Press Ctrl+C to close{Colors.RESET}\n")
    
    def open_browser():
        time.sleep(1.5)
        webbrowser.open(APP_URL)
    
    threading.Thread(target=open_browser, daemon=True).start()
    app.run(host='127.0.0.1', port=server_port, debug=False, use_reloader=False)


def main():
    """Main entry point"""
    print_banner()
    
    # Check Ollama
    print(f"{Colors.YELLOW}🔍 Checking Ollama...{Colors.RESET}")
    if check_ollama():
        print(f"{Colors.GREEN}   ✓ Ollama is running{Colors.RESET}")
    else:
        print(f"{Colors.RED}   ⚠️  Ollama not detected at localhost:11434{Colors.RESET}")
        print(f"{Colors.YELLOW}   Please start Ollama before translating{Colors.RESET}")
    
    print()
    
    if HAS_PYSTRAY:
        run_with_tray()
    else:
        run_simple()


if __name__ == '__main__':
    main()
