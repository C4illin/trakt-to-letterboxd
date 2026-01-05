import os
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService

from . import console
from .config import Config


def get_csv_path(filename: str) -> Path:
    """Get path for CSV file"""
    csv_path = Path("/csv") if Path("/csv").exists() else Path("./csv")
    return csv_path / filename


def dismiss_cookie_consent(driver: webdriver.Chrome) -> None:
    """Dismiss the Google Funding Choices cookie consent dialog if present"""
    try:
        consent_button = WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".fc-cta-consent"))
        )
        consent_button.click()
        time.sleep(1)
    except TimeoutException:
        pass
    except Exception as e:
        console.print(f"Could not dismiss cookie consent: {e}", style="dim")


def hide_ad_overlays(driver: webdriver.Chrome) -> None:
    """Hide ad overlays that might block button clicks"""
    try:
        driver.execute_script("""
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


def setup_driver(headless: bool = False) -> webdriver.Chrome:
    """Configure and return a Chrome/Chromium WebDriver"""
    options = ChromeOptions()
    
    if headless:
        options.add_argument("--headless=new")
    
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    prefs = {"profile.default_content_setting_values.notifications": 2}
    options.add_experimental_option("prefs", prefs)
    
    chromedriver_path = os.getenv("CHROMEDRIVER_PATH")
    chrome_bin = os.getenv("CHROME_BIN")
    
    if chrome_bin:
        options.binary_location = chrome_bin
    
    if chromedriver_path and Path(chromedriver_path).exists():
        service = ChromeService(executable_path=chromedriver_path)
    else:
        from webdriver_manager.chrome import ChromeDriverManager
        service = ChromeService(ChromeDriverManager().install())
    
    driver = webdriver.Chrome(service=service, options=options)
    driver.implicitly_wait(10)
    
    return driver


def login_to_letterboxd(driver: webdriver.Chrome, username: str, password: str) -> bool:
    """Login to Letterboxd"""
    console.print(f"Logging in to Letterboxd as {username}...", style="blue")
    
    try:
        driver.get("https://letterboxd.com/sign-in/")
        time.sleep(3)
        
        dismiss_cookie_consent(driver)
        
        username_field = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "field-username"))
        )
        username_field.clear()
        username_field.send_keys(username)
        
        password_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "field-password"))
        )
        password_field.clear()
        password_field.send_keys(password)
        
        try:
            submit_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']"))
            )
        except TimeoutException:
            console.print("Could not find submit button", style="red")
            return False
        
        submit_button.click()
        time.sleep(4)
        
        if "sign-in" in driver.current_url:
            console.print("Login failed - still on sign-in page", style="red")
            console.print("Check your credentials or if there's a captcha", style="yellow")
            return False
        
        console.print("Successfully logged in to Letterboxd", style="green")
        return True
        
    except TimeoutException as e:
        console.print(f"Login timeout - could not find login fields: {e}", style="red")
        return False
    except Exception as e:
        console.print(f"Login error: {e}", style="red")
        return False


def upload_csv_to_letterboxd(driver: webdriver.Chrome, csv_file_path: Path) -> bool:
    """Upload CSV file to Letterboxd import page"""
    console.print(f"Uploading {csv_file_path.name} to Letterboxd...", style="blue")
    
    try:
        if not csv_file_path.exists():
            console.print(f"CSV file not found: {csv_file_path}", style="red")
            return False
        
        with open(csv_file_path, 'r') as f:
            lines = f.readlines()
            if len(lines) <= 1:
                console.print("CSV file is empty (no data rows), skipping import", style="yellow")
                return True
        
        console.print(f"CSV contains {len(lines) - 1} row(s) to import", style="dim")
        
        driver.get("https://letterboxd.com/import/")
        time.sleep(3)
        
        dismiss_cookie_consent(driver)
        
        file_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']"))
        )
        
        absolute_path = str(csv_file_path.absolute())
        file_input.send_keys(absolute_path)
        
        console.print("File uploaded, waiting for processing...", style="blue")
        
        try:
            import_button = WebDriverWait(driver, 30).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "a.submit-matched-films"))
            )
        except TimeoutException:
            console.print("Could not find import button", style="yellow")
            console.print("The file may need manual review on Letterboxd", style="yellow")
            return False
        
        hide_ad_overlays(driver)
        
        driver.execute_script("arguments[0].click();", import_button)
        console.print("Import button clicked, waiting for completion...", style="blue")
        time.sleep(5)
        
        if "complete" in driver.page_source.lower() or "success" in driver.page_source.lower():
            console.print("Import completed successfully!", style="green")
            return True
        elif "error" in driver.page_source.lower():
            console.print("Import may have failed, check Letterboxd", style="yellow")
            return False
        else:
            console.print("Import submitted, check Letterboxd to verify", style="yellow")
            return True
            
    except TimeoutException as e:
        console.print(f"Timeout while uploading file: {e}", style="red")
        return False
    except Exception as e:
        console.print(f"Upload error: {e}", style="red")
        return False


def import_to_letterboxd(config: Config, headless: bool = False) -> bool:
    """Main import function to upload export.csv to Letterboxd"""
    console.print(f"Starting import for Letterboxd account: {config.letterboxd_username}", style="purple4")
    
    if not config.letterboxd_password:
        console.print("Letterboxd password not configured in config.yml", style="red")
        return False
    
    driver = None
    try:
        driver = setup_driver(headless=headless)
        
        if not login_to_letterboxd(driver, config.letterboxd_username, config.letterboxd_password):
            return False
        
        csv_path = get_csv_path("export.csv")
        if not upload_csv_to_letterboxd(driver, csv_path):
            return False
        
        console.print("Import process completed!", style="purple4")
        return True
        
    except Exception as e:
        console.print(f"Import failed: {e}", style="red")
        return False
        
    finally:
        if driver:
            time.sleep(2)
            driver.quit()


if __name__ == "__main__":
    from .config import load_config
    
    config = load_config()
    if config:
        import_to_letterboxd(config, headless=False)
