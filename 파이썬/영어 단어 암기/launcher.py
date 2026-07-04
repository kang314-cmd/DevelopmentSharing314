"""영어 단어 암기 앱 실행기"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
APP_SCRIPT = APP_DIR / "vocabulary_app.py"
REQUIREMENTS = APP_DIR / "requirements.txt"


def _is_store_stub(path: str) -> bool:
    lowered = path.lower()
    return "windowsapps" in lowered or "microsoft\\windowsapps" in lowered


def _python_candidates() -> list[list[str]]:
    candidates: list[list[str]] = []

    if sys.executable and not _is_store_stub(sys.executable):
        candidates.append([sys.executable])

    if shutil.which("py"):
        candidates.append(["py", "-3"])

    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        programs = Path(local_app_data) / "Programs" / "Python"
        if programs.exists():
            for python_exe in sorted(programs.glob("Python*/python.exe"), reverse=True):
                candidates.append([str(python_exe)])

    for name in ("python3", "python"):
        path = shutil.which(name)
        if path and not _is_store_stub(path):
            candidates.append([path])

    unique: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()
    for cmd in candidates:
        key = tuple(cmd)
        if key not in seen:
            seen.add(key)
            unique.append(cmd)
    return unique


def _python_works(cmd: list[str]) -> bool:
    try:
        result = subprocess.run(
            cmd + ["-c", "import tkinter"],
            cwd=APP_DIR,
            capture_output=True,
            timeout=20,
            text=True,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def find_python() -> list[str] | None:
    for cmd in _python_candidates():
        if _python_works(cmd):
            return cmd
    return None


def ensure_dependencies(python_cmd: list[str]) -> None:
    if not REQUIREMENTS.exists():
        return
    subprocess.run(
        python_cmd + ["-m", "pip", "install", "-r", str(REQUIREMENTS), "-q"],
        cwd=APP_DIR,
        check=False,
    )


def main() -> int:
    os.chdir(APP_DIR)

    if not APP_SCRIPT.exists():
        print(f"앱 파일을 찾을 수 없습니다: {APP_SCRIPT}")
        input("Enter 키를 누르면 종료합니다...")
        return 1

    python_cmd = find_python()
    if not python_cmd:
        print("Python 3을 찾을 수 없습니다.")
        print("https://www.python.org/downloads/ 에서 Python 3를 설치해 주세요.")
        print("설치 시 'Add python.exe to PATH' 옵션을 체크하세요.")
        input("Enter 키를 누르면 종료합니다...")
        return 1

    ensure_dependencies(python_cmd)

    result = subprocess.run(
        python_cmd + [str(APP_SCRIPT)],
        cwd=APP_DIR,
    )
    if result.returncode != 0:
        print(f"\n앱 실행 중 오류가 발생했습니다. (종료 코드: {result.returncode})")
        input("Enter 키를 누르면 종료합니다...")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
