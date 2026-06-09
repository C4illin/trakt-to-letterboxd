import asyncio
import os
import re
import subprocess
from pathlib import Path

import zendriver as zd

from . import console
from .config import Config


def get_csv_path(filename: str) -> Path:
    """Get path for CSV file"""
    csv_path = Path("/csv") if Path("/csv").exists() else Path("./csv")
    return csv_path / filename


async def dismiss_cookie_consent(page) -> None:
    try:
        btn = await page.select(".fc-cta-consent", timeout=10)
        await btn.click()
        await asyncio.sleep(1)
    except Exception as e:
        console.print(f"Could not dismiss cookie consent: {e}", style="dim")


async def hide_ad_overlays(page) -> None:
    try:
        await page.evaluate("""
            var bottomRail = document.getElementById('pw-oop-bottom_rail');
            if (bottomRail) bottomRail.style.display = 'none';
            
            var ads = document.querySelectorAll('[id^="pw-oop-"], .pw-tag, .pw-corner-ad-video');
            ads.forEach(function(ad) {
                ad.style.display = 'none';
            });
            
            var playwireAds = document.querySelectorAll('[alt*="Playwire"]');
            playwireAds.forEach(function(ad) {
                if (ad.parentElement) ad.parentElement.style.display = 'none';
            });
        """)
    except Exception as e:
        console.print(f"Could not hide ad overlays: {e}", style="dim")


async def setup_browser(headless: bool) -> tuple:
    """Start a browser (and Xvfb in Docker) and return (browser, xvfb)"""
    chrome_bin = os.getenv("CHROME_BIN")
    in_docker = os.getenv("IN_DOCKER", "false").lower() == "true"

    xvfb = None
    if in_docker:
        xvfb = subprocess.Popen(["Xvfb", ":99", "-screen", "0", "1920x1080x24"])
        os.environ["DISPLAY"] = ":99"
        headless = False

    browser = await zd.start(
        headless=headless,
        browser_executable_path=chrome_bin or None,
        browser_args=["--disable-dev-shm-usage"],
    )
    return browser, xvfb


async def login_to_letterboxd(browser, username: str, password: str) -> bool:
    """Login to Letterboxd"""
    console.print(f"Logging in to Letterboxd as {username}...", style="blue")
    try:
        page = await browser.get("https://letterboxd.com/sign-in/")
        await asyncio.sleep(3)
        await dismiss_cookie_consent(page)

        username_field = await page.select("#field-username")
        await username_field.clear_input()
        await username_field.send_keys(username)

        password_field = await page.select("#field-password")
        await password_field.clear_input()
        await password_field.send_keys(password)

        submit = await page.select("button[type='submit']")
        await submit.click()
        await asyncio.sleep(4)

        await page
        if "sign-in" in page.url:
            console.print("Login failed - still on sign-in page", style="red")
            console.print("Check your credentials or if there's a captcha", style="yellow")
            return False

        console.print("Successfully logged in to Letterboxd", style="green")
        return True
    except Exception as e:
        console.print(f"Login error: {e}", style="red")
        return False


async def import_progress_text(page) -> str:
    """Read the Letterboxd import-summary status line.

    Reports matching progress ("100 films matched from 417 in your file."),
    readiness ("Matching complete...") and the final result ("Saved 417 films.").
    """
    return await page.evaluate(
        "(document.querySelector('.js-import-progress') || {}).innerText || ''"
    ) or ""


async def submit_button_disabled(page) -> bool:
    """Whether the import submit button is still disabled (matching in progress)."""
    return await page.evaluate(
        "(function(){var b=document.querySelector('a.submit-matched-films');"
        "return b ? b.classList.contains('import-button-disabled') : true;})()"
    )


async def upload_csv_to_letterboxd(browser, csv_file_path: Path) -> bool:
    """Upload CSV file to Letterboxd import page"""
    console.print(f"Uploading {csv_file_path.name} to Letterboxd...", style="blue")
    try:
        if not csv_file_path.exists():
            console.print(f"CSV file not found: {csv_file_path}", style="red")
            return False

        with open(csv_file_path) as f:
            lines = f.readlines()
        if len(lines) <= 1:
            console.print("CSV file is empty (no data rows), skipping import", style="yellow")
            return True

        console.print(f"CSV contains {len(lines) - 1} row(s) to import", style="dim")

        page = await browser.get("https://letterboxd.com/import/")
        await asyncio.sleep(3)
        await dismiss_cookie_consent(page)

        file_input = await page.select("input[type='file']")
        await file_input.send_file(str(csv_file_path.absolute()))

        console.print("File uploaded, waiting for processing...", style="blue")

        expected_rows = len(lines) - 1
        await page.select("a.submit-matched-films", timeout=120)

        # Letterboxd matches every film against its database before the import
        # can run, showing "N films matched from M" with a spinner and keeping
        # the submit button disabled (class "import-button-disabled") until it
        # finishes. With hundreds of films this takes a while; clicking too
        # early does nothing and the import never lands, so wait for the button
        # to become enabled before clicking it.
        console.print("Waiting for Letterboxd to finish matching films...", style="blue")
        match_status = ""
        for _ in range(120):  # up to ~10 minutes (120 * 5s)
            match_status = await import_progress_text(page)
            if await submit_button_disabled(page) is False:
                break
            await asyncio.sleep(5)
        else:
            console.print(
                f"Matching did not finish within timeout (last status: "
                f"{match_status.strip()!r})",
                style="red",
            )
            return False

        console.print(f"Matching complete: {match_status.strip()}", style="green")
        await hide_ad_overlays(page)
        # Re-select the button now that matching is done, then submit.
        import_button = await page.select("a.submit-matched-films")
        await import_button.click()

        console.print("Import button clicked, waiting for completion...", style="blue")

        # On success the status line reads e.g. "Saved 417 films." We only
        # report success once we see that confirmed count; anything else
        # (timeout, missing element) is treated as a failure so the caller does
        # not advance merged.csv for an import that never landed.
        saved_re = re.compile(r"saved\s+(\d+)\s+films?", re.IGNORECASE)
        status = ""
        for _ in range(60):  # up to ~5 minutes (60 * 5s)
            await asyncio.sleep(5)
            status = await import_progress_text(page)
            match = saved_re.search(status)
            if match:
                saved = int(match.group(1))
                console.print(f"Import completed: {status.strip()}", style="green")
                if saved < expected_rows:
                    console.print(
                        f"Only {saved} of {expected_rows} rows were saved "
                        "(some films may not have matched on Letterboxd)",
                        style="yellow",
                    )
                return True

        console.print(
            f"Import did not confirm completion within timeout "
            f"(last status: {status.strip()!r})",
            style="red",
        )
        return False
    except Exception as e:
        console.print(f"Upload error: {e}", style="red")
        return False


async def _run_async(config: Config, headless: bool) -> bool:
    browser, xvfb = await setup_browser(headless)
    try:
        if not await login_to_letterboxd(browser, config.letterboxd_username, config.letterboxd_password):
            return False

        csv_path = get_csv_path("export.csv")
        if not await upload_csv_to_letterboxd(browser, csv_path):
            return False

        console.print("Import process completed!", style="purple4")
        return True
    finally:
        await browser.stop()
        if xvfb:
            xvfb.terminate()


def import_to_letterboxd(config: Config, headless: bool = False) -> bool:
    """Main import function to upload export.csv to Letterboxd"""
    console.print(f"Starting import for Letterboxd account: {config.letterboxd_username}", style="purple4")
    if not config.letterboxd_password:
        console.print("Letterboxd password not configured in config.yml", style="red")
        return False
    try:
        return asyncio.run(_run_async(config, headless))
    except Exception as e:
        console.print(f"Import failed: {e}", style="red")
        return False


if __name__ == "__main__":
    from .config import load_config

    config = load_config()
    if config:
        import_to_letterboxd(config, headless=False)
