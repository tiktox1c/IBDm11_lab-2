"""Copy dev-only Reveal resources into the example's permitted source directory."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
if __name__ == '__main__':
    source = ROOT / 'node_modules' / 'reveal.js' / 'dist'
    if not source.is_dir():
        raise SystemExit('Install dev dependencies: npm install --ignore-scripts')
    shutil.copytree(source, ROOT / 'examples' / 'assets' / 'reveal' / 'dist', dirs_exist_ok=True)
    print('Reveal example ready (local resources).')
