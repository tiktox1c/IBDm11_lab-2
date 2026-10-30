"""Supervise a real Node.js worker, exchanging JSONL without blocking Tkinter."""
import json
import os
import queue
import shutil
import subprocess
import tempfile
import threading
import time
from collections import deque
from pathlib import Path

from .export import check_cancel, export_slides
from .models import ROOT, Cancelled, ConversionError, Options

CREATE_NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def node_path():
    local = ROOT / '.runtime' / ('node.exe' if os.name == 'nt' else 'node')
    candidate = str(local) if local.is_file() else shutil.which('node')
    if not candidate:
        raise ConversionError('Не найден Node.js. Установите Node.js LTS 22+ с https://nodejs.org/ и перезапустите программу.')
    return candidate


def _stop_process(process):
    if process.poll() is not None:
        return
    try:
        process.stdin.write('cancel\n')
        process.stdin.flush()
        process.wait(timeout=4)
        return
    except (OSError, subprocess.TimeoutExpired, ValueError):
        pass
    # Kill only the worker started by this application, including its Chrome descendants.
    if os.name == 'nt':
        subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       creationflags=CREATE_NO_WINDOW, timeout=10)
    else:
        process.kill()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()


def run_worker(argument, emit, stop, idle_timeout=70):
    environment = os.environ.copy()
    scratch = ROOT / 'tmp'
    scratch.mkdir(exist_ok=True)
    environment.update(TEMP=str(scratch), TMP=str(scratch), TMPDIR=str(scratch),
                       PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD='1')
    try:
        arguments = argument if isinstance(argument, list) else [str(argument)]
        process = subprocess.Popen([node_path(), str(ROOT / 'renderer' / 'cli.mjs'), *arguments],
                                   cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace',
                                   bufsize=1, env=environment, creationflags=CREATE_NO_WINDOW)
    except OSError as exc:
        raise ConversionError(f'Не удалось запустить Node.js: {exc}') from exc
    events = queue.Queue()
    errors = deque(maxlen=20)

    def stdout_reader():
        try:
            for line in process.stdout:
                events.put(line)
        finally:
            events.put(None)

    def stderr_reader():
        for line in process.stderr:
            errors.append(line.rstrip()[:2000])

    readers = [threading.Thread(target=stdout_reader, daemon=True),
               threading.Thread(target=stderr_reader, daemon=True)]
    for reader in readers:
        reader.start()
    result = None
    last_message = time.monotonic()
    try:
        while True:
            check_cancel(stop)
            if time.monotonic() - last_message > idle_timeout:
                raise ConversionError('Node.js не отвечает. Превышен таймаут обработки слайда.')
            try:
                line = events.get(timeout=0.1)
            except queue.Empty:
                continue
            if line is None:
                break
            last_message = time.monotonic()
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ConversionError('Повреждён JSON-ответ Node.js. Проверьте установку зависимостей.') from exc
            if not isinstance(event, dict):
                raise ConversionError('Некорректный ответ Node.js.')
            if event.get('type') == 'error':
                raise ConversionError(event.get('message', 'Ошибка захвата слайдов.'))
            if event.get('type') == 'result':
                result = event
            emit(event)
        check_cancel(stop)
        try:
            code = process.wait(timeout=5)
        except subprocess.TimeoutExpired as exc:
            raise ConversionError('Node.js не завершил работу.') from exc
        if code or result is None:
            detail = '\n'.join(errors)[-4000:]
            raise ConversionError(f'Ошибка Node.js (код {code}). {detail or "Нет результата захвата."}')
        return result
    finally:
        _stop_process(process)
        for stream in (process.stdin, process.stdout, process.stderr):
            stream.close()
        for reader in readers:
            reader.join(timeout=1)


def check_environment(stop=None, chrome_path=''):
    return run_worker(['--check', json.dumps({'chromePath': chrome_path})],
                      lambda _: None, stop or threading.Event(), idle_timeout=35)


def convert(options: Options, emit=lambda _: None, stop=None):
    stop = stop or threading.Event()
    options.validate()
    check_cancel(stop)
    (ROOT / 'tmp').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='conversion-', dir=ROOT / 'tmp') as temporary:
        work = Path(temporary)
        config_file = work / 'config.json'
        config_file.write_text(json.dumps(options.renderer_config(work), ensure_ascii=False), encoding='utf-8')
        result = run_worker(config_file, emit, stop, idle_timeout=options.timeout_ms / 1000 * 3 + options.delay_ms / 500 + 30)
        slides = result.get('slides', [])
        if not 1 <= len(slides) <= 500:
            raise ConversionError('Браузер вернул недопустимое количество слайдов.')
        images = []
        for index, slide in enumerate(slides):
            image = Path(slide['file']).resolve()
            if not image.is_relative_to(work.resolve()) or slide['index'] != index:
                raise ConversionError('Некорректный путь или порядок изображений в ответе Node.js.')
            images.append(image)
        check_cancel(stop)
        emit({'type': 'status', 'message': 'Проверка изображений и сборка результата'})
        canvas = None
        if options.aspect != 'auto':
            a, b = map(int, options.aspect.split(':'))
            canvas = (options.width, round(options.width * b / a))
        export_slides(images, options.output, stop,
                      lambda n, total, text: emit({'type': 'export', 'current': n, 'total': total, 'message': text}),
                      canvas_size=canvas)
        return {'output': str(options.output), 'count': len(images), 'mode': result['mode'],
                'width': canvas[0] if canvas else result['width'],
                'height': canvas[1] if canvas else result['height'], 'chrome': result['chrome']}
