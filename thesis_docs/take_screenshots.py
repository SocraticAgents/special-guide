"""
Thesis screenshots of the V1 interface, taken with headless Chrome (DevTools protocol).

Needs the app running in demo mode on a throw-away database (never the pilot database):
    SOCRATIC_AGENT_DEMO=1 SOCRATIC_AGENT_DB=/tmp/demo_ui.db TEACHER_PASSCODE=demo-teacher \\
        .venv/bin/streamlit run app.py --server.port 8599 --server.headless true
then, from code/:
    .venv/bin/python thesis_docs/take_screenshots.py
PNGs are written to thesis_docs/screenshots/. The demo account and passcode are test values.
"""
from __future__ import annotations

import base64
import json
import subprocess
import tempfile
import time
from pathlib import Path

import requests
from websockets.sync.client import connect

APP = "http://localhost:8599"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
OUT = Path(__file__).parent / "screenshots"
W, H = 1280, 900


class Page:
    def __init__(self, ws_url: str):
        self.ws = connect(ws_url, max_size=50_000_000)  # noqa: kept open for the whole run
        self.n = 0

    def cmd(self, method: str, **params):
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self.n:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    def js(self, expr: str):
        res = self.cmd("Runtime.evaluate", expression=expr, awaitPromise=True, returnByValue=True)
        if "exceptionDetails" in res:
            raise RuntimeError(f"JS error in: {expr[:80]} -> {res['exceptionDetails']}")
        return res.get("result", {}).get("value")

    def wait_for(self, expr: str, timeout: float = 30):
        end = time.time() + timeout
        while time.time() < end:
            if self.js(f"!!({expr})"):
                return
            time.sleep(0.4)
        self.shot("_debug_timeout")
        print(self.js("document.querySelector('[data-testid=stMain]').innerText.slice(0, 600)"))
        raise TimeoutError(expr)

    def settle(self, seconds: float = 1.5):
        """Wait until Streamlit stops running the script, then a little longer for rendering."""
        time.sleep(0.6)
        self.wait_for("!document.querySelector('[data-testid=\"stStatusWidget\"] button')", 60)
        time.sleep(seconds)

    def click(self, selector_js: str):
        self.js(f"({selector_js}).click()")
        self.settle()

    def type_into(self, selector_js: str, text: str, commit: str = "Tab"):
        """Type into a field, then commit with Tab (inside forms) or Enter (stand-alone password field,
        where Tab only moves focus to the show/hide button and Streamlit never sees a blur)."""
        self.js(f"({selector_js}).focus()")
        self.cmd("Input.insertText", text=text)
        code = {"Tab": 9, "Enter": 13}[commit]
        for kind in ("keyDown", "keyUp"):
            self.cmd("Input.dispatchKeyEvent", type=kind, key=commit, code=commit, windowsVirtualKeyCode=code,
                     **({"text": "\r"} if commit == "Enter" and kind == "keyDown" else {}))
        time.sleep(0.3)

    def shot(self, name: str):
        data = self.cmd("Page.captureScreenshot", format="png")["data"]
        (OUT / f"{name}.png").write_bytes(base64.b64decode(data))
        print("saved", name)


def by_text(tag: str, text: str, root: str = "document") -> str:
    return (f"[...{root}.querySelectorAll('{tag}')].find(e => e.innerText.trim() === {json.dumps(text)})")


def scroll_main_to(page: Page, selector_js: str, block: str = "start"):
    page.js(f"({selector_js}).scrollIntoView({{block: '{block}'}})")
    time.sleep(0.8)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    profile = tempfile.mkdtemp()
    chrome = subprocess.Popen([CHROME, "--headless=new", "--remote-debugging-port=9333", f"--user-data-dir={profile}",
                               "--hide-scrollbars", "--no-first-run", f"--window-size={W},{H}", "about:blank"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                targets = requests.get("http://127.0.0.1:9333/json", timeout=1).json()
                break
            except requests.RequestException:
                time.sleep(0.2)
        page = Page(next(t for t in targets if t["type"] == "page")["webSocketDebuggerUrl"])
        page.cmd("Emulation.setDeviceMetricsOverride", width=W, height=H, deviceScaleFactor=2, mobile=False)
        page.cmd("Emulation.setEmulatedMedia", features=[{"name": "prefers-color-scheme", "value": "light"}])
        page.cmd("Page.enable")
        page.cmd("Page.navigate", url=APP)
        page.wait_for("document.querySelector('[data-testid=\"stTabs\"]')")
        page.settle()

        page.shot("ui_00a_sign_in")
        # Sign up a demo account (test values).
        page.click(by_text("[role=tab]", "Sign up"))
        inputs = "[...document.querySelectorAll('[data-testid=\"stForm\"]')][1].querySelectorAll('input')"
        for i, value in enumerate(["Demo Student", "demo01", "demo-pass-1", "demo-pass-1"]):
            page.type_into(f"{inputs}[{i}]", value)
        page.click("[...document.querySelectorAll('[data-testid=\"stForm\"]')][1].querySelector('[data-testid=stCheckbox] input')")
        page.shot("ui_00b_sign_up")
        page.click(by_text("button", "Create account"))
        page.wait_for("document.querySelector('.st-key-start_loops button')")

        page.settle()
        page.shot("ui_00c_topics")
        # Loops topic, then replay the scripted walkthrough.
        page.click("document.querySelector('.st-key-start_loops button')")
        page.wait_for(by_text("button", "Play scripted walkthrough"))
        page.shot("ui_01_chat_opening")
        page.click(by_text("button", "Play scripted walkthrough"))
        page.wait_for("document.body.innerText.includes('Session summary')", 90)
        page.settle(2.5)

        alerts = "[...document.querySelectorAll('[data-testid=\"stAlert\"]')]"
        scroll_main_to(page, f"{alerts}.find(a => a.innerText.includes('LO5 mastered'))", "center")
        page.shot("ui_02_feedback_mastered")
        scroll_main_to(page, f"{alerts}.find(a => a.innerText.includes('LO6 is parked'))", "center")
        page.shot("ui_03_feedback_parked")
        scroll_main_to(page, by_text("h4", "🌟 Session summary"), "start")
        page.shot("ui_04_session_summary")

        # My Progress.
        page.click("[...document.querySelectorAll('a')].find(a => a.href.includes('My_Progress'))")
        page.wait_for("document.body.innerText.includes('Your next step')")
        page.settle()
        page.shot("ui_05_my_progress_top")
        scroll_main_to(page, by_text("h3", "🏅 Milestones"), "start")
        page.shot("ui_06_my_progress_milestones")

        # Teacher dashboard (test passcode).
        page.click("[...document.querySelectorAll('a')].find(a => a.href.includes('Teacher_Dashboard'))")
        page.wait_for("document.querySelector('input[type=password]')")
        page.settle()
        page.shot("ui_10_dashboard_passcode")
        page.type_into("document.querySelector('input[type=password]')", "demo-teacher", commit="Enter")
        page.settle()
        page.click(by_text("button", "Enter"))
        page.wait_for("document.body.innerText.includes('Objectives and rule enforcement')")
        page.settle(2)
        scroll_main_to(page, "[...document.querySelectorAll('h3')].find(h => h.innerText.includes('Objectives and rule enforcement'))")
        page.shot("ui_07_dashboard_outcomes")
        scroll_main_to(page, "[...document.querySelectorAll('p,strong')].find(e => e.innerText.startsWith('Objective records'))", "start")
        page.shot("ui_08_dashboard_objective_records")
        scroll_main_to(page, "[...document.querySelectorAll('p,strong')].find(e => e.innerText.startsWith('SOLO estimate over the session'))", "start")
        page.shot("ui_09_dashboard_solo_trajectory")
    finally:
        chrome.terminate()


if __name__ == "__main__":
    main()
