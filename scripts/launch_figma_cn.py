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
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
DETACHED_PROCESS = getattr(subprocess, "DETACHED_PROCESS", 0)
STARTF_USESHOWWINDOW = getattr(subprocess, "STARTF_USESHOWWINDOW", 1)
SW_HIDE = 0

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


def popen_hidden(args: list[str], env: dict[str, str] | None = None) -> subprocess.Popen:
    startupinfo = None
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = SW_HIDE
    return subprocess.Popen(
        args,
        env=env,
        close_fds=True,
        creationflags=CREATE_NO_WINDOW | DETACHED_PROCESS,
        startupinfo=startupinfo,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
    )


def message_box(text: str) -> None:
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, text, "Figma CN", 0x40)
    except Exception:
        log(text)


def bring_figma_to_front() -> bool:
    if os.name != "nt":
        return False

    try:
        import ctypes

        user32 = ctypes.windll.user32
        hwnds: list[int] = []

        def enum_window(hwnd, _):
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            title = buffer.value
            if "Figma" in title:
                hwnds.append(hwnd)
            return True

        enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(enum_window)
        user32.EnumWindows(enum_proc, 0)
        if not hwnds:
            log("No visible Figma window found to activate")
            return False

        hwnd = hwnds[0]
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        log("Activated Figma window")
        return True
    except Exception as exc:
        log(f"Could not activate Figma window: {exc}")
        return False


def reveal_figma_window() -> None:
    if bring_figma_to_front():
        return
    if start_stock_figma():
        time.sleep(3)
        bring_figma_to_front()


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
    popen_hidden([str(agent), "--from-desktop-app"])


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
    popen_hidden(args, env=env)


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


def inject_all(expression: str, scripted_ids: set[str]) -> tuple[int, int]:
    total = 0
    ready = 0
    for target in page_targets():
        target_id = target.get("id", "")
        ws_url = target.get("webSocketDebuggerUrl")
        if not ws_url:
            continue
        total += 1
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
            if probe_injected(ws_url):
                ready += 1
        except Exception as exc:
            log(f"Inject failed for {target.get('url')}: {exc}")
    return total, ready


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
        start_figma_agent()
        started_from_shortcut = start_stock_figma()
        if started_from_shortcut:
            time.sleep(6)
        if figma_running():
            log("Existing Figma detected without CDP; restarting it with debugging enabled")
            stop_figma()
            deadline = time.time() + 10
            while figma_running() and time.time() < deadline:
                time.sleep(0.5)
        elif not started_from_shortcut:
            time.sleep(1)
        if not cdp_ready():
            start_figma()
        if not wait_for_cdp(90):
            log(
                "Figma has not exposed /json/version yet; keeping launcher alive "
                "and continuing to retry in the background"
            )

    expression = INJECT_SCRIPT.read_text(encoding="utf-8")
    scripted_ids: set[str] = set()
    stable_ready_cycles = 0
    stay_attached = os.environ.get("FIGMA_CN_STAY_ATTACHED") == "1"

    while True:
        if not figma_running():
            log("Figma exited; launcher exiting")
            return 0
        if cdp_ready():
            total, ready = inject_all(expression, scripted_ids)
            if total > 0 and ready == total:
                stable_ready_cycles += 1
                if stable_ready_cycles >= 2 and not stay_attached:
                    reveal_figma_window()
                    log(f"Injection ready for {ready}/{total} targets; launcher exiting")
                    return 0
            else:
                stable_ready_cycles = 0
        else:
            scripted_ids.clear()
            stable_ready_cycles = 0
        time.sleep(2)


if __name__ == "__main__":
    raise SystemExit(main())
