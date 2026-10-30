"""Render only this application's own windows for visual layout review on Windows."""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import ImageGrab
from converter.gui import Application


def main():
    output = ROOT / 'test-results' / 'interface'
    output.mkdir(parents=True, exist_ok=True)
    app = Application(check_startup=False)
    try:
        for name, geometry, expanded in (
                ('normal', '940x820', False),
                ('advanced', '940x820', True),
                ('wide', '1700x940', False),
                ('small', '800x640', True)):
            app.geometry(geometry)
            app.update()
            if bool(app.advanced.winfo_ismapped()) != expanded:
                app.toggle_advanced()
            app.update()
            time.sleep(.2)
            app.update()
            ImageGrab.grab(window=app.winfo_id()).save(output / (name + '.png'))
            print(name, 'window', app.winfo_width(), app.winfo_height(),
                  'form', app.shell.winfo_width(), 'scroll', app.body_canvas.yview())
    finally:
        app.destroy()


if __name__ == '__main__':
    main()
