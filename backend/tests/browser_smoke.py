"""Optional explicit Chromium check against both running servers; cleans its data."""

import json
import re
import sys
import os
import shutil
import tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.db import connect

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
root = os.getenv("MCLAB_BASE_URL", "http://127.0.0.1:5173")
screenshots = Path(tempfile.mkdtemp(prefix="mclab-browser-"))


def run():
    created = []
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=os.getenv("CHROMIUM_PATH") or shutil.which("chromium"),
            headless=True,
            args=["--no-sandbox"],
        )
        context = browser.new_context(viewport={"width": 1360, "height": 1050})
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        try:
            page.goto(root)
            expect(page.get_by_role("heading", name="Set up a session")).to_be_visible()
            page.screenshot(path=str(screenshots / "setup.png"), full_page=True)
            page.get_by_role("button", name="Easy", exact=True).click()
            page.get_by_label("Category", exact=True).select_option("logic")
            page.get_by_label("Group label", exact=True).fill("PLAYWRIGHT-VERIFICATION")
            page.get_by_role("button", name="Start session", exact=False).click()
            page.wait_for_url(re.compile(r".*/session/.*"))
            sid = page.url.rsplit("/", 1)[-1]
            created.append(sid)
            page.get_by_role("button", name="Begin first trial", exact=False).click()
            expect(
                page.get_by_role("button", name="Submit answer", exact=False)
            ).to_be_disabled()
            page.keyboard.press("1")
            slider = page.get_by_label("How confident are you?", exact=True)
            expect(slider).to_be_visible()
            expect(
                page.get_by_role("button", name="Submit answer", exact=False)
            ).to_be_disabled()
            page.screenshot(path=str(screenshots / "trial.png"), full_page=True)
            slider.focus()
            page.keyboard.press("ArrowRight")
            page.keyboard.press("Enter")
            expect(page.get_by_role("progressbar")).to_have_attribute(
                "aria-valuenow", "1"
            )
            page.keyboard.press("2")
            slider = page.get_by_label("How confident are you?", exact=True)
            slider.focus()
            page.keyboard.press("ArrowRight")
            page.keyboard.press("Enter")
            page.wait_for_url(re.compile(r".*/report/.*"))
            expect(
                page.get_by_role("heading", name="Calibration report", exact=True)
            ).to_be_visible()
            expect(
                page.get_by_text("Confidence meets accuracy", exact=True)
            ).to_be_visible()
            expect(page.locator(".recharts-responsive-container")).to_have_count(2)
            page.screenshot(path=str(screenshots / "report.png"), full_page=True)
            page.set_viewport_size({"width": 768, "height": 1024})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.screenshot(path=str(screenshots / "report-tablet.png"), full_page=True)
            print(
                "PASS: setup, instructions, keyboard option selection, untouched slider guard, slider/Enter submission, report charts, and tablet width"
            )

            # Test visual display deadlines and all-timeout completion with a virtual clock.
            s = context.request.post(
                root + "/api/sessions",
                data={
                    "group": "PLAYWRIGHT-VERIFICATION",
                    "condition": {
                        "difficulty": "easy",
                        "categories": "perceptual",
                        "time_limit": "20",
                    },
                },
            ).json()
            created.append(s["session_id"])
            timed = context.new_page()
            timed.on("pageerror", lambda error: errors.append(str(error)))
            timed.clock.install()
            timed.goto(root + "/session/" + s["session_id"])
            timed.get_by_role("button", name="Begin first trial", exact=False).click()
            for i in range(2):
                expect(
                    timed.get_by_text(
                        "Watch closely. The display will disappear.", exact=True
                    )
                ).to_be_visible()
                expect(timed.get_by_role("img")).to_be_visible()
                timed.clock.fast_forward(2100)
                expect(
                    timed.get_by_role("button", name="Submit answer", exact=False)
                ).to_be_visible()
                expect(timed.get_by_role("img")).to_have_count(0)
                timed.clock.fast_forward(20100)
                if i == 0:
                    expect(timed.get_by_role("progressbar")).to_have_attribute(
                        "aria-valuenow", "1"
                    )
            timed.wait_for_url(re.compile(r".*/report/.*"))
            report = context.request.get(
                root + "/api/reports/" + s["session_id"]
            ).json()
            assert (
                report["metrics"]["timed_out_count"] == 2
                and report["metrics"]["n"] == 0
            )
            assert report["metrics"]["accuracy"] is None
            print(
                "PASS: timed circle/dot display hides before options, both trials expire, and report excludes all timeouts"
            )

            # Study and filler phases keep answer controls hidden; filler input is not submitted.
            s = context.request.post(
                root + "/api/sessions",
                data={
                    "group": "PLAYWRIGHT-VERIFICATION",
                    "condition": {
                        "difficulty": "easy",
                        "categories": "memory",
                        "feedback": "delayed",
                        "interface": "buttons",
                    },
                },
            ).json()
            created.append(s["session_id"])
            memory = context.new_page()
            memory.on("pageerror", lambda error: errors.append(str(error)))
            memory.clock.install()
            memory.goto(root + "/session/" + s["session_id"])
            memory.get_by_role("button", name="Begin first trial", exact=False).click()
            expect(
                memory.get_by_text("MEMORIZE THESE WORDS", exact=True)
            ).to_be_visible()
            expect(
                memory.get_by_role("button", name="Submit answer", exact=False)
            ).to_have_count(0)
            memory.clock.fast_forward(6100)
            expect(
                memory.get_by_text("A SHORT DISTRACTION", exact=True)
            ).to_be_visible()
            memory.get_by_label("Your countdown", exact=True).fill("UNRECORDED-FILLER")
            memory.clock.fast_forward(10100)
            expect(
                memory.get_by_role("button", name="Submit answer", exact=False)
            ).to_be_visible()
            memory.keyboard.press("1")
            memory.get_by_role("button", name="80", exact=True).click()
            memory.get_by_role("button", name="Submit answer", exact=False).click()
            expect(
                memory.get_by_role("heading", name="Response saved", exact=True)
            ).to_be_visible()
            memory.clock.fast_forward(5100)
            expect(memory.get_by_text("Correct answer:", exact=False)).to_be_visible()
            memory.clock.fast_forward(2100)
            expect(
                memory.get_by_text("MEMORIZE THESE WORDS", exact=True)
            ).to_be_visible()
            trial = context.request.get(
                root + "/api/sessions/" + s["session_id"]
            ).json()["trials"][0]
            assert trial["latency_ms"] < 2000
            assert "UNRECORDED-FILLER" not in json.dumps(trial)
            print(
                "PASS: memory study → unrecorded filler → options, browser latency excludes study/filler, delayed feedback waits then advances"
            )

            page.goto(root + "/sessions")
            expect(
                page.get_by_role("heading", name="Sessions", exact=True)
            ).to_be_visible()
            page.goto(root + "/dashboard")
            expect(
                page.get_by_role("heading", name="Instructor dashboard", exact=True)
            ).to_be_visible()
            expect(
                page.get_by_text("Pooled calibration curves", exact=True)
            ).to_be_visible()
            page.screenshot(path=str(screenshots / "dashboard.png"), full_page=True)
            assert not errors, errors
            print("PASS: sessions and dashboard render; no JavaScript page errors")
        finally:
            for sid in created:
                response = context.request.get(root + "/api/sessions/" + sid)
                if response.ok:
                    participant = response.json()["participant_id"]
                    context.request.delete(root + "/api/sessions/" + sid)
                    db = connect()
                    if not db.sessions.find_one({"participant_id": participant}):
                        db.participants.delete_one({"participant_id": participant})
            browser.close()


if __name__ == "__main__":
    run()
