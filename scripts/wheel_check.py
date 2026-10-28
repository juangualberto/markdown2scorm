"""Install the built wheel in an isolated venv and export the real manuscript."""
from hashlib import sha256
from pathlib import Path
import subprocess
import tempfile
import venv


def main():
    root = Path(__file__).resolve().parents[1]
    wheel = root / 'dist/markdown2scorm-1.0.0-py3-none-any.whl'
    with tempfile.TemporaryDirectory(prefix='scorm-wheel-') as folder:
        env = Path(folder) / 'venv'
        venv.create(env, with_pip=True)
        commands = [
            [str(env / 'bin/pip'), 'install', str(wheel)],
            [str(env / 'bin/python'), '-m', 'markdown2scorm', '--help'],
            [str(env / 'bin/markdown2scorm'), str(root / 'test/manuscrito/01-Introduccion-al-analisis-forense.md'),
             '--assets-dir', str(root / 'test/figuras'), '--template', 'fpd-medu',
             '--output', str(Path(folder) / 'wheel-real.zip'), '--validate'],
        ]
        with (root / 'dist/wheel-install.log').open('w') as log:
            for command in commands:
                subprocess.run(command, cwd=folder, stdout=log, stderr=subprocess.STDOUT, check=True)
            log.write('\nPASS: wheel instalado en entorno limpio, CLI desde otro directorio y conversión real validados.\n')
            log.write('Wheel SHA-256: ' + sha256(wheel.read_bytes()).hexdigest() + '\n')


if __name__ == '__main__':
    main()
