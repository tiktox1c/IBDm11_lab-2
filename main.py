"""Double-click run.bat for GUI; Python CLI is also available for reproducible tests."""
import argparse
import json
import sys
import threading
from pathlib import Path

from converter.bridge import check_environment, convert
from converter.models import Cancelled, ConversionError, Options


def main():
    parser = argparse.ArgumentParser(description='HTML Presentation Converter: локальный экспорт через Google Chrome')
    parser.add_argument('source', nargs='?', type=Path)
    parser.add_argument('output', nargs='?', type=Path)
    parser.add_argument('--check', action='store_true', help='Проверить Node.js и установленный Chrome')
    parser.add_argument('--slides', type=int, default=0, help='Количество слайдов (0 = автоматически)')
    parser.add_argument('--selector', default='', help='CSS-селектор слайдов')
    parser.add_argument('--capture-selector', default='', help='CSS-селектор области захвата')
    parser.add_argument('--next-key', default='ArrowRight')
    parser.add_argument('--delay', type=int, default=500, help='Задержка перехода в миллисекундах')
    parser.add_argument('--width', type=int, default=1600)
    parser.add_argument('--height', type=int, default=900)
    parser.add_argument('--aspect', choices=['auto', '16:9', '4:3'], default='auto')
    parser.add_argument('--allow-external', action='store_true')
    parser.add_argument('--chrome', default='', help='Необязательный путь к установленному Chrome')
    args = parser.parse_args()
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
    try:
        if args.check:
            print(json.dumps(check_environment(chrome_path=args.chrome), ensure_ascii=False))
        elif args.source and args.output:
            stop = threading.Event()

            def progress(event):
                if event['type'] in ('status', 'progress', 'export'):
                    print(event.get('message', ''), flush=True)
            try:
                result = convert(Options(args.source, args.output, width=args.width, height=args.height,
                                         count=args.slides, selector=args.selector,
                                         capture_selector=args.capture_selector, next_key=args.next_key,
                                         delay_ms=args.delay, allow_external=args.allow_external,
                                         chrome_path=args.chrome, aspect=args.aspect), progress, stop)
            except KeyboardInterrupt:
                stop.set()
                raise Cancelled('Конвертация отменена.')
            print(json.dumps(result, ensure_ascii=False))
        elif args.source or args.output:
            parser.error('Укажите исходный HTML и путь результата.')
        else:
            from converter.gui import Application
            Application().mainloop()
    except Cancelled as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except ConversionError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
