import tempfile
import threading
import unittest
from pathlib import Path

from pypdf import PdfReader
from converter.models import Options, Cancelled, ConversionError, ROOT
from converter.bridge import convert, check_environment


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT / 'tmp')
        self.work = Path(self.tmp.name)
        self.existing = set((ROOT / 'tmp').glob('conversion-*'))

    def tearDown(self):
        self.tmp.cleanup()

    def test_real_node_pipeline_exports_pdf_and_reports_progress(self):
        events = []
        output = self.work / 'результат.pdf'
        result = convert(Options(ROOT / 'examples/02-javascript.html', output,
                                 width=1000, height=600, delay_ms=50), events.append)
        self.assertEqual(result['count'], 3)
        self.assertEqual(len(PdfReader(output).pages), 3)
        self.assertEqual([e['current'] for e in events if e['type'] == 'progress'], [1, 2, 3])
        self.assertEqual(set((ROOT / 'tmp').glob('conversion-*')), self.existing)

    def test_environment_really_launches_chrome(self):
        self.assertTrue(check_environment()['version'])

    def test_cancellation_during_capture_cleans_work_and_preserves_output(self):
        output = self.work / 'existing.pdf'
        output.write_bytes(b'keep')
        stop = threading.Event()

        def progress(event):
            if event['type'] == 'progress':
                stop.set()

        with self.assertRaises(Cancelled):
            convert(Options(ROOT / 'examples/02-javascript.html', output,
                            delay_ms=500), progress, stop)
        self.assertEqual(output.read_bytes(), b'keep')
        self.assertEqual(set((ROOT / 'tmp').glob('conversion-*')), self.existing)

    def test_missing_resource_does_not_produce_output(self):
        source = self.work / 'bad.html'
        source.write_text('<div class="slide" style="width:800px;height:450px">Hello<img src="missing.png"></div>')
        output = self.work / 'bad.pdf'
        with self.assertRaisesRegex(ConversionError, 'ресурс|изображение'):
            convert(Options(source, output, delay_ms=50))
        self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
