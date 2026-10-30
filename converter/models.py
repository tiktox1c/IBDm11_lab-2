from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_SLIDES = 500


class ConversionError(Exception):
    """A user-facing conversion failure."""


class Cancelled(ConversionError):
    pass


@dataclass
class Options:
    source: Path
    output: Path
    width: int = 1600
    height: int = 900
    count: int = 0
    selector: str = ''
    capture_selector: str = ''
    next_key: str = 'ArrowRight'
    delay_ms: int = 500
    timeout_ms: int = 20000
    allow_external: bool = False
    chrome_path: str = ''
    aspect: str = 'auto'

    def validate(self):
        self.source = Path(self.source).resolve()
        self.output = Path(self.output).resolve()
        if not self.source.is_file() or self.source.suffix.lower() not in ('.html', '.htm'):
            raise ConversionError('Выберите существующий HTML-файл (.html или .htm).')
        if self.output.suffix.lower() not in ('.pdf', '.pptx'):
            raise ConversionError('Формат результата должен быть PDF или PPTX.')
        if self.output == self.source:
            raise ConversionError('Нельзя перезаписать исходную презентацию.')
        if not self.output.parent.is_dir():
            raise ConversionError('Папка результата не существует.')
        if not 320 <= self.width <= 3840 or not 240 <= self.height <= 2160:
            raise ConversionError('Разрешение должно быть в пределах 320–3840 × 240–2160.')
        if not 0 <= self.count <= MAX_SLIDES:
            raise ConversionError(f'Количество слайдов: 0 (авто) или от 1 до {MAX_SLIDES}.')
        if not 0 <= self.delay_ms <= 10000 or not 1000 <= self.timeout_ms <= 60000:
            raise ConversionError('Недопустимая задержка или таймаут.')
        if not self.next_key.strip() or len(self.next_key) > 60:
            raise ConversionError('Укажите клавишу следующего слайда, например ArrowRight или Space.')
        if self.aspect not in ('auto', '16:9', '4:3'):
            raise ConversionError('Пропорции: автоматически, 16:9 или 4:3.')
        return self

    def renderer_config(self, work: Path):
        return dict(source=str(self.source), work=str(work), width=self.width,
                    height=self.height, count=self.count, selector=self.selector.strip(),
                    captureSelector=self.capture_selector.strip(), nextKey=self.next_key,
                    delayMs=self.delay_ms, timeoutMs=self.timeout_ms,
                    allowExternal=self.allow_external, chromePath=self.chrome_path)
