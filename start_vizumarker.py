#!/usr/bin/env python3
"""Convenience launcher for the VizuMarker backend with auto-auth bypass and browser opening."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path
from shutil import which

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_HOST = os.environ.get("VIZUMARKER_HOST", "127.0.0.1")
DEFAULT_PORT = os.environ.get("VIZUMARKER_PORT", "8000")


def _best_python_command() -> list[str]:
    """Prefer the local virtualenv, fall back to poetry, then system python."""
    venv_python = PROJECT_ROOT / "venv" / "bin" / "python"
    if venv_python.exists():
        return [str(venv_python), "-m", "uvicorn"]

    poetry_exe = which("poetry")
    if poetry_exe:
        return [poetry_exe, "run", "uvicorn"]

    return [sys.executable, "-m", "uvicorn"]


def _wait_for_server(host: str, port: str, proc: subprocess.Popen, timeout: float = 15.0) -> bool:
    """Poll the health endpoint until the backend responds, process exits, or timeout."""
    deadline = time.time() + timeout
    url = f"http://{host}:{port}/health"
    while time.time() < deadline:
        if proc.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(url, timeout=1.0) as response:
                if response.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False


def main() -> int:
    host = DEFAULT_HOST
    port = DEFAULT_PORT

    env = os.environ.copy()
    env.setdefault("DISABLE_AUTH", "1")

    cmd = _best_python_command() + ["ld35_service.main:app", "--host", host, "--port", port]

    print("Starte VizuMarker Backend …")
    print("Befehl:", " ".join(cmd))

    try:
        proc = subprocess.Popen(cmd, cwd=PROJECT_ROOT, env=env)
    except FileNotFoundError as exc:
        print("Fehler: Konnte uvicorn nicht starten.")
        print("Stelle sicher, dass die Abhängigkeiten installiert sind (z.B. via 'poetry install').")
        print(f"Details: {exc}")
        return 1

    try:
        server_ready = _wait_for_server(host, port, proc)
        proc_exit_code = proc.poll()

        if server_ready and proc_exit_code is None:
            app_url = f"http://{host}:{port}/app/"
            docs_url = f"http://{host}:{port}/docs"
            print(f"VizuMarker UI läuft unter {app_url}")
            print(f"API-Dokumentation: {docs_url}")
            webbrowser.open(app_url)
            print("Dieses Fenster offen lassen, um den Server weiter laufen zu lassen. Beenden mit Strg+C.")
        else:
            if proc_exit_code is not None and proc_exit_code != 0:
                print("Fehler: Der Server wurde vorzeitig beendet. Siehe Logausgabe oben.")
            else:
                print("Warnung: Der Server antwortet nicht rechtzeitig. Überprüfe die Logs im Fenster.")

            if proc_exit_code is not None:
                return proc_exit_code

        proc.wait()
        return proc.returncode or 0
    except KeyboardInterrupt:
        print("\nBeende VizuMarker …")
        proc.send_signal(signal.SIGINT)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
