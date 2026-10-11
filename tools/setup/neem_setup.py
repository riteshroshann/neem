"""Neem for Windows: sets Neem up on this computer and opens it in your browser.

Run it once to install and again any time to start Neem. It installs uv and Bun if they are
missing, each from its official installer, downloads Neem's code from GitHub, installs the
Python and web dependencies, then starts the physics API and the site and opens the site.
Close the window to stop Neem.

Built into web/public/download/neem-setup.exe with PyInstaller:

    uv run --no-project --with pyinstaller pyinstaller --onefile --name neem-setup
        --distpath web/public/download tools/setup/neem_setup.py

NEEM_HOME moves the install (default %LOCALAPPDATA%\\Neem); NEEM_SOURCE points at another zip of
the code, a URL or a local file; NEEM_NO_BROWSER=1 skips opening the browser.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import webbrowser
import zipfile
from pathlib import Path

REPO_ZIP = "https://github.com/riteshroshann/neem/archive/refs/heads/main.zip"
HOME = Path(
    os.environ.get("NEEM_HOME") or Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Neem"
)
APP = HOME / "app"
INSTALLERS = {
    "uv": ("https://astral.sh/uv/install.ps1", Path.home() / ".local" / "bin" / "uv.exe"),
    "bun": ("https://bun.sh/install.ps1", Path.home() / ".bun" / "bin" / "bun.exe"),
}


def say(line: str = "") -> None:
    print(f"  {line}", flush=True)


def find(tool: str) -> str | None:
    """The tool on PATH, or where its official installer puts it."""
    found = shutil.which(tool)
    if found:
        return found
    where = INSTALLERS[tool][1]
    return str(where) if where.exists() else None


def ensure(tool: str) -> str:
    path = find(tool)
    if path:
        say(f"{tool}: found")
        return path
    url = INSTALLERS[tool][0]
    say(f"{tool}: installing from {url}")
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", f"irm {url} | iex"],
        check=True,
    )
    path = find(tool)
    if not path:
        raise RuntimeError(f"{tool} did not install; install it by hand and run this again")
    return path


def fetch_code() -> None:
    """Neem's code into APP, from GitHub or NEEM_SOURCE; kept if it is already there."""
    if (APP / "pyproject.toml").exists():
        say(f"code: {APP}")
        return
    source = os.environ.get("NEEM_SOURCE") or REPO_ZIP
    HOME.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=HOME) as tmp:
        archive = Path(tmp) / "neem.zip"
        if source.startswith("http"):
            say(f"code: downloading {source}")
            urllib.request.urlretrieve(source, archive)
        else:
            shutil.copy(source, archive)
        with zipfile.ZipFile(archive) as z:
            z.extractall(tmp)
        # a GitHub archive holds one folder, neem-main; a local one may hold the files directly
        roots = [p for p in Path(tmp).iterdir() if p.is_dir() and p.name != "__MACOSX"]
        if len(roots) == 1 and not (Path(tmp) / "pyproject.toml").exists():
            shutil.move(str(roots[0]), str(APP))
        else:
            archive.unlink()
            shutil.copytree(tmp, APP)
    say(f"code: {APP}")


def taken(port: int) -> bool:
    """Something answers on the port, over IPv4 or IPv6 (dev servers often take only one)."""
    for family, host in ((socket.AF_INET, "127.0.0.1"), (socket.AF_INET6, "::1")):
        with socket.socket(family) as s:
            s.settimeout(0.5)
            if s.connect_ex((host, port)) == 0:
                return True
    return False


def free_port(start: int) -> int:
    for port in range(start, start + 50):
        if not taken(port):
            return port
    raise RuntimeError(f"no free port from {start}")


def wait_for(url: str, seconds: int) -> bool:
    end = time.time() + seconds
    while time.time() < end:
        try:
            with urllib.request.urlopen(url, timeout=2):
                return True
        except OSError:
            time.sleep(1)
    return False


def main() -> None:
    print("\n  Neem: heat twins for Delhi schoolyards\n")
    uv = ensure("uv")
    bun = ensure("bun")
    fetch_code()
    say("Python packages (the first run takes a few minutes)")
    subprocess.run([uv, "sync"], cwd=APP, check=True)
    say("web packages")
    subprocess.run([bun, "install"], cwd=APP / "web", check=True)

    running = []
    if free_port(8000) == 8000:
        running.append(subprocess.Popen([uv, "run", "neem-api"], cwd=APP))
        say("physics API: http://127.0.0.1:8000")
    else:
        say("physics API: port 8000 is busy, so the planner previews without verifying")
    port = free_port(4321)
    running.append(subprocess.Popen([bun, "run", "dev", "--port", str(port)], cwd=APP / "web"))
    site = f"http://localhost:{port}/"
    if wait_for(site, 180):
        say(f"Neem is running at {site}")
        if not os.environ.get("NEEM_NO_BROWSER"):
            webbrowser.open(site)
    say("Close this window to stop Neem.\n")
    try:
        running[-1].wait()
    finally:
        for proc in running:
            proc.terminate()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as err:  # the window must stay open long enough to read what went wrong
        say(f"Setup stopped: {err}")
        say("Neem's docs have the manual steps: https://neem-lemon.vercel.app/docs#run")
        with contextlib.suppress(EOFError):  # no console to wait on when run from a script
            input("\n  Press Enter to close.")
        sys.exit(1)
