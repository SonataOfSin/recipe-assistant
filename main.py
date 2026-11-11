import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def available_port(preferred: int) -> int:
    for port in range(preferred, preferred + 100):
        with socket.socket() as sock:
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError(f"No available port found near {preferred}.")


def wait_for_api(process: subprocess.Popen, url: str, timeout: float = 60) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("The API process exited before it became healthy.")
        try:
            with urllib.request.urlopen(f"{url}/health", timeout=1) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError):
            time.sleep(0.25)
    raise TimeoutError("The API did not become healthy within 60 seconds.")


def wait_for_ui(process: subprocess.Popen, url: str, timeout: float = 60) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("The Streamlit process exited before it became healthy.")
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError):
            time.sleep(0.25)
    raise TimeoutError("Streamlit did not become healthy within 60 seconds.")


def stop_process(process: subprocess.Popen) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)


def main() -> None:
    api_port = available_port(8000)
    ui_port = available_port(8501)
    api_url = f"http://127.0.0.1:{api_port}"
    api = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.api:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(api_port),
        ],
        cwd=ROOT,
    )
    ui = None
    try:
        wait_for_api(api, api_url)
        environment = dict(os.environ)
        environment["API_BASE_URL"] = api_url
        ui = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                "app/streamlit_app.py",
                "--server.address=127.0.0.1",
                f"--server.port={ui_port}",
                "--server.headless=true",
            ],
            cwd=ROOT,
            env=environment,
        )
        ui_url = f"http://127.0.0.1:{ui_port}"
        wait_for_ui(ui, ui_url)
        print(f"Recipe Assistant is ready: {ui_url}", flush=True)
        print(f"API documentation: {api_url}/docs", flush=True)
        while api.poll() is None and ui.poll() is None:
            time.sleep(0.5)
        if api.poll() is not None:
            raise RuntimeError("The API process stopped unexpectedly.")
        raise RuntimeError("The Streamlit process stopped unexpectedly.")
    except KeyboardInterrupt:
        print("\nStopping Recipe Assistant...", flush=True)
    finally:
        if ui is not None:
            stop_process(ui)
        stop_process(api)


if __name__ == "__main__":
    main()
