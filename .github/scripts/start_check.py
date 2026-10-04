"""Start the app with a temporary data folder and a spare port, check
that it answers, and stop it. The last step of the GitHub check, written
so it also runs on a development machine: uv run python .github/scripts/start_check.py
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

from openconsult.settings.paths import default_data_folder

WAIT_S = 60


def free_port() -> int:
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    return port


def wait_for_answer(address: str, proc: subprocess.Popen) -> str:
    deadline = time.monotonic() + WAIT_S
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise SystemExit(f"the app stopped by itself with code {proc.returncode}")
        try:
            with urllib.request.urlopen(f"{address}/login", timeout=2) as answer:
                if answer.status == 200:
                    return answer.read().decode("utf-8")
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.5)
    raise SystemExit(f"the app did not answer within {WAIT_S} seconds")


def main() -> int:
    port = free_port()
    folder = tempfile.mkdtemp(prefix="openconsult-check-")
    address = f"http://127.0.0.1:{port}"
    command = [sys.executable, "-u", "-m", "openconsult", "--data-folder", folder, "--port", str(port)]
    with open(f"{folder}.out", "w+", encoding="utf-8") as output:
        proc = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT)
        try:
            body = wait_for_answer(address, proc)
            if "OpenConsult" not in body:
                raise SystemExit("the app answered, but not with its own page")
            print(f"The app answered at {address}")
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            output.seek(0)
            print("The app said:", output.read().strip(), sep="\n")
            shutil.rmtree(folder, ignore_errors=True)
    os.remove(f"{folder}.out")
    print(f"Stopped. The default data folder on this system would be: {default_data_folder()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
