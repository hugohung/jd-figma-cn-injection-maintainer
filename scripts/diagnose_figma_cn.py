import argparse
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PORT = int(os.environ.get("FIGMA_CN_PORT", "9233"))
CDP = f"http://127.0.0.1:{PORT}"

sys.path.insert(0, str(ROOT / "pydeps"))

try:
    import websocket
except Exception:
    websocket = None


def url_json(url: str, timeout: float = 2.0):
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def tcp_port_open() -> bool:
    import socket

    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=1.0):
            return True
    except OSError:
        return False


def tasklist_running() -> bool:
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
        return False


def check_injection(target: dict) -> dict:
    if websocket is None:
        return {"error": "websocket-client missing"}

    ws_url = target.get("webSocketDebuggerUrl")
    if not ws_url:
        return {"error": "missing webSocketDebuggerUrl"}

    expression = """(() => {
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      let chineseTextNodes = 0;
      while (walker.nextNode()) {
        const text = (walker.currentNode.textContent || '').trim();
        if (/[\\u4e00-\\u9fff]/.test(text)) chineseTextNodes++;
      }
      return {
        title: document.title,
        url: location.href,
        injected: Boolean(window.__codexFigmaCNInjected),
        chineseTextNodes
      };
    })();"""

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
                return message.get("result", {}).get("result", {}).get("value", {})
    finally:
        ws.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-injection", action="store_true")
    args = parser.parse_args()

    report: dict = {
        "figma_running": tasklist_running(),
        "cdp_url": CDP,
        "cdp_socket_open": tcp_port_open(),
        "cdp_ready": False,
        "targets": [],
    }

    try:
        report["version"] = url_json(f"{CDP}/json/version", timeout=2.0)
        report["cdp_ready"] = True
        report["targets"] = url_json(f"{CDP}/json/list", timeout=2.0)
    except Exception as exc:
        report["cdp_error"] = str(exc)

    if args.check_injection and report.get("cdp_ready"):
        checked = []
        for target in report["targets"]:
            if target.get("type") == "page" and "figma.com" in target.get("url", ""):
                checked.append(check_injection(target))
        report["injection"] = checked

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
