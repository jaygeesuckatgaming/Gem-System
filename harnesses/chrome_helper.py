"""
Helper to auto-accept Chrome consent dialogs
"""

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def accept_chrome_consent(driver):
    """Try to accept any Chrome consent/cookie dialogs"""
    try:
        # Google consent dialog
        accept_btn = WebDriverWait(driver, 2).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Accept')]"))
        )
        accept_btn.click()
        print("[AUTO] Accepted consent dialog")
        return True
    except:
        pass
    
    try:
        # Swedish "Godkänn" button
        accept_btn = WebDriverWait(driver, 2).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Godkänn')]"))
        )
        accept_btn.click()
        print("[AUTO] Accepted Swedish consent")
        return True
    except:
        pass
    
    try:
        # Cookie consent by class
        accept_btn = driver.find_element(By.CSS_SELECTOR, ".cookie-accept, .accept-cookies, button[aria-label*='accept']")
        accept_btn.click()
        print("[AUTO] Accepted cookie consent")
        return True
    except:
        pass
    
    return False
