import unittest
import tempfile
import time
from pathlib import Path
from unittest.mock import patch
from pptx import Presentation
from converter.gui import Application
from converter.models import ROOT


class GuiTests(unittest.TestCase):
    def test_main_settings_fit_normal_window_and_advanced_scrolls_into_view(self):
        app = Application(check_startup=False)
        try:
            app.geometry('940x820')
            app.update()
            canvas_bottom = app.body_canvas.winfo_rooty() + app.body_canvas.winfo_height()
            self.assertLessEqual(app.advanced_button.winfo_rooty() + app.advanced_button.winfo_height(), canvas_bottom)
            app.toggle_advanced()
            app.update()
            self.assertGreater(app.body_canvas.yview()[0], 0)
            self.assertGreaterEqual(app.advanced.winfo_rooty(), app.body_canvas.winfo_rooty() - 20)
        finally:
            app.destroy()

    def test_expanded_navigation_never_overlaps_actions_or_resizes_window(self):
        app = Application(check_startup=False)
        try:
            for width, height in ((940, 780), (1600, 940), (800, 640)):
                app.geometry(f'{width}x{height}')
                app.update()
                before = (app.winfo_width(), app.winfo_height())
                app.toggle_advanced()
                app.update()
                self.assertEqual((app.winfo_width(), app.winfo_height()), before)
                visible_bottom = min(app.advanced.winfo_rooty() + app.advanced.winfo_height(),
                                     app.body_canvas.winfo_rooty() + app.body_canvas.winfo_height())
                self.assertGreaterEqual(app.convert_button.winfo_rooty(), visible_bottom)
                self.assertLessEqual(app.open_button.winfo_rootx() + app.open_button.winfo_width(),
                                     app.winfo_rootx() + app.winfo_width())
                self.assertLessEqual(app.open_button.winfo_rooty() + app.open_button.winfo_height(),
                                     app.winfo_rooty() + app.winfo_height())
                app.toggle_advanced()
                app.update()
        finally:
            app.destroy()

    def test_window_starts_and_advanced_settings_toggle_without_worker(self):
        app = Application(check_startup=False)
        try:
            app.update()
            self.assertEqual(app.title(), 'HTML Presentation Converter')
            self.assertFalse(app.advanced.winfo_ismapped())
            app.toggle_advanced()
            app.update()
            self.assertTrue(app.advanced.winfo_ismapped())
            self.assertEqual(app.format_var.get(), 'pdf')
            self.assertEqual(app.resolution_var.get(), '1600 × 900')
        finally:
            app.destroy()

    def test_real_conversion_updates_window_and_finishes_pptx(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'tmp') as temporary:
            output = Path(temporary) / 'Интерфейс.pptx'
            app = Application(check_startup=False)
            errors = []
            ticks = []

            def tick():
                ticks.append(1)
                app.after(30, tick)

            try:
                app.format_var.set('pptx')
                app.delay_var.set('80')
                app.after(30, tick)
                with patch('converter.gui.filedialog.askopenfilename', return_value=str(ROOT / 'examples/02-javascript.html')), \
                     patch('converter.gui.filedialog.asksaveasfilename', return_value=str(output)), \
                     patch('converter.gui.messagebox.showerror', side_effect=lambda *args: errors.append(args)):
                    app.choose_button.invoke()
                    app.convert_button.invoke()
                    deadline = time.monotonic() + 40
                    while app.result is None and not errors and time.monotonic() < deadline:
                        app.update()
                        time.sleep(0.02)
                self.assertFalse(errors)
                self.assertEqual(app.result, output)
                self.assertEqual(len(Presentation(output).slides), 3)
                self.assertGreater(len(ticks), 10)
                self.assertEqual(float(app.progress['value']), 100)
            finally:
                app.stop.set()
                if app.worker:
                    app.worker.join(timeout=10)
                app.destroy()


if __name__ == '__main__':
    unittest.main()
