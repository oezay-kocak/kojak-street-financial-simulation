"""Build and install a wheel into a temporary target, then run outside checkout.

Uses the invoking interpreter's dependencies, but imports all project code from
the installed wheel. CI additionally installs dependencies in a fresh runner.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="kojak-wheel-") as directory:
        temp = Path(directory)
        subprocess.run([sys.executable, "-m", "pip", "wheel", str(root), "--no-deps", "--no-build-isolation", "--no-cache-dir", "--wheel-dir", str(temp / "wheels")], check=True)
        wheel = next((temp / "wheels").glob("*.whl"))
        target = temp / "installed"
        subprocess.run([sys.executable, "-m", "pip", "install", str(wheel), "--no-deps", "--no-cache-dir", "--target", str(target)], check=True)
        env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        env.update(QT_QPA_PLATFORM="offscreen", KOJAKSTREET_DATA_DIR=str(temp / "data"))
        script = """
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import daten, speicher, kojakstreet
for module in (daten, speicher, kojakstreet):
    assert Path(module.__file__).is_relative_to(sys.argv[1]), module.__file__
from kojakstreet.ui_qt.app import main
assert main(['--smoke-test']) == 0
print('Installed wheel: root modules, Qt entrypoint, runtime and shutdown OK')
"""
        subprocess.run([sys.executable, "-I", "-c", script, str(target)], cwd=temp, env=env, check=True)


if __name__ == "__main__":
    main()
