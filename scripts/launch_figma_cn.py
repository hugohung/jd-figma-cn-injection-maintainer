import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PORT = int(os.environ.get("FIGMA_CN_PORT", "9233"))
LOCK_PORT = int(os.environ.get("FIGMA_CN_LOCK_PORT", "39233"))
CDP = f"http://127.0.0.1:{PORT}"
INJECT_SCRIPT = ROOT / "figmacn_inject.js"
LOG_FILE = ROOT / "figma-cn-launcher.log"

sys.path.insert(0, str(ROOT / "pydeps"))

try:
    import websocket
except Exception as exc:  # pragma: no cover
    websocket = None
    WEBSOCKET_IMPORT_ERROR = exc
else:
    WEBSOCKET_IMPORT_ERROR = None


def log(message: str) -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with LOG_FILE.open("a", encoding="utf-8") as file:
        file.write(f"[{stamp}] {message}\n")


def message_box(text: str) -> None:
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, text, "Figma CN", 0x40)
    except Exception:
        log(text)


def url_json(url: str, timeout: float = 2.0):
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def tcp_port_open() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=1.0):
            return True
    except OSError:
        return False


def cdp_ready() -> bool:
    if not tcp_port_open():
        return False
    try:
        url_json(f"{CDP}/json/version", timeout=4.0)
        return True
    except Exception as exc:
        log(f"CDP socket is open, but /json/version is not ready yet: {exc}")
        return False


def find_figma_exe() -> Path | None:
    app_root = Path(os.environ.get("LOCALAPPDATA", "")) / "Figma"
    candidates = [app_root / "Figma.exe"]
    if app_root.exists():
        candidates.extend(sorted(app_root.glob("app-*/Figma.exe"), reverse=True))
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def find_figma_agent_exe() -> Path | None:
    agent = Path(os.environ.get("LOCALAPPDATA", "")) / "FigmaAgent" / "figma_agent.exe"
    if agent.exists():
        return agent
    return None


def find_stock_figma_shortcut() -> Path | None:
    desktop = Path(os.environ.get("USERPROFILE", "")) / "Desktop" / "Figma.lnk"
    if desktop.exists():
        return desktop

    programs = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Figma.lnk"
    if programs.exists():
        return programs

    return None


def figma_agent_running() -> bool:
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq figma_agent.exe"],
            capture_output=True,
            text=True,
            timeout=3,
            encoding="mbcs",
            errors="ignore",
        )
        return "figma_agent.exe" in result.stdout
    except Exception:
        return True


def start_figma_agent() -> None:
    agent = find_figma_agent_exe()
    if not agent or figma_agent_running():
        return
    log("Starting figma_agent.exe from desktop app context")
    subprocess.Popen([str(agent), "--from-desktop-app"], close_fds=True)


def start_stock_figma() -> bool:
    shortcut = find_stock_figma_shortcut()
    if not shortcut:
        return False
    log(f"Starting Figma from stock shortcut: {shortcut}")
    os.startfile(str(shortcut))
    return True


def start_figma() -> None:
    exe = find_figma_exe()
    if not exe:
        raise RuntimeError("Figma.exe was not found")

    env = os.environ.copy()
    env["FIGMA_TEST"] = "1"
    args = [
        str(exe),
        f"--remote-debugging-port={PORT}",
        "--remote-allow-origins=*",
    ]
    log("Starting Figma with debugging enabled")
    subprocess.Popen(args, env=env, close_fds=True)


def figma_running() -> bool:
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq Figma.exe"],
            capture_output=True,
            text=True,
            timeout=3,
            encoding="mbcs",
            errors="ignore",
        )
        return "Figma.exe" in result.stdout
    except Exception:
        return True


def stop_figma() -> None:
    for image_name in ("Figma.exe", "figma_agent.exe"):
        subprocess.run(
            ["taskkill", "/F", "/T", "/IM", image_name],
            capture_output=True,
            text=True,
            encoding="mbcs",
            errors="ignore",
        )


def wait_for_cdp(seconds: int = 25) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        if cdp_ready():
            return True
        time.sleep(0.5)
    return False


def evaluate(ws_url: str, expression: str) -> dict:
    if websocket is None:
        raise RuntimeError(f"Missing websocket-client: {WEBSOCKET_IMPORT_ERROR}")

    ws = websocket.create_connection(ws_url, timeout=10)
    try:
        ws.send(
            json.dumps(
                {
                    "id": 1,
                    "method": "Runtime.evaluate",
                    "params": {
                        "expression": expression,
                        "awaitPromise": True,
                        "returnByValue": True,
                    },
                }
            )
        )
        while True:
            message = json.loads(ws.recv())
            if message.get("id") == 1:
                return message
    finally:
        ws.close()


def send_cdp_command(ws_url: str, method: str, params: dict | None = None) -> dict:
    if websocket is None:
        raise RuntimeError(f"Missing websocket-client: {WEBSOCKET_IMPORT_ERROR}")

    ws = websocket.create_connection(ws_url, timeout=10)
    try:
        payload = {"id": 1, "method": method}
        if params is not None:
            payload["params"] = params
        ws.send(json.dumps(payload))
        while True:
            message = json.loads(ws.recv())
            if message.get("id") == 1:
                return message
    finally:
        ws.close()


def probe_injected(ws_url: str) -> bool:
    result = evaluate(ws_url, "Boolean(window.__codexFigmaCNInjected)")
    return bool(result.get("result", {}).get("result", {}).get("value"))


def page_targets() -> list[dict]:
    try:
        targets = url_json(f"{CDP}/json/list", timeout=3.0)
    except Exception as exc:
        log(f"Cannot read targets: {exc}")
        return []
    return [target for target in targets if target.get("type") == "page" and target.get("webSocketDebuggerUrl")]


def inject_all(expression: str, scripted_ids: set[str]) -> None:
    for target in page_targets():
        target_id = target.get("id", "")
        ws_url = target.get("webSocketDebuggerUrl")
        if not ws_url:
            continue
        try:
            if target_id not in scripted_ids:
                result = send_cdp_command(
                    ws_url,
                    "Page.addScriptToEvaluateOnNewDocument",
                    {"source": expression},
                )
                scripted_ids.add(target_id)
                log(
                    "Registered init script "
                    + json.dumps(
                        {
                            "title": target.get("title"),
                            "url": target.get("url"),
                            "result": result.get("result", {}),
                        },
                        ensure_ascii=False,
                    )
                )
            if not probe_injected(ws_url):
                result = evaluate(ws_url, expression)
                value = result.get("result", {}).get("result", {}).get("value", {})
                log(
                    "Injected "
                    + json.dumps(
                        {
                            "title": target.get("title"),
                            "url": target.get("url"),
                            "result": value,
                        },
                        ensure_ascii=False,
                    )
                )
        except Exception as exc:
            log(f"Inject failed for {target.get('url')}: {exc}")


def main() -> int:
    log("Launcher started")

    lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        lock_socket.bind(("127.0.0.1", LOCK_PORT))
        lock_socket.listen(1)
    except OSError:
        log("Another launcher instance is already running")
        return 0

    if not INJECT_SCRIPT.exists():
        message_box("Missing figmacn_inject.js. Run build_injector.py first.")
        return 1

    if websocket is None:
        message_box("Missing websocket-client. Install it in scripts/pydeps.")
        return 1

    if not cdp_ready():
        was_running = figma_running()
        start_figma_agent()
        started_from_shortcut = start_stock_figma()
        if was_running:
            log("Existing Figma detected without CDP; restarting it with debugging enabled")
            stop_figma()
            deadline = time.time() + 10
            while figma_running() and time.time() < deadline:
                time.sleep(0.5)
        elif not started_from_shortcut:
            time.sleep(1)
        if not started_from_shortcut:
            start_figma()
        if not wait_for_cdp(90):
            log(
                "Figma has not exposed /json/version yet; keeping launcher alive "
                "and continuing to retry in the background"
            )
            message_box(
                "Figma is still starting and the debugging endpoint has not answered yet.\n\n"
                "Leave this window open. The launcher will keep retrying in the background."
            )

    expression = INJECT_SCRIPT.read_text(encoding="utf-8")
    scripted_ids: set[str] = set()

    while True:
        if not figma_running():
            log("Figma exited; launcher exiting")
            return 0
        if cdp_ready():
            inject_all(expression, scripted_ids)
        else:
            scripted_ids.clear()
        time.sleep(2)


if __name__ == "__main__":
    raise SystemExit(main())
