from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from bs4 import BeautifulSoup
import time
import base64
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("scraper.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def fetch_case_details(e_code, c_type, reg_no, reg_year, captcha_solution=None):
    # Configure Chrome options
    options = webdriver.ChromeOptions()
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # Initialize WebDriver
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    # Hide WebDriver signature
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            })
        """
    })
    
    try:
        logger.info("Navigating to Warangal court website...")
        driver.get("https://warangal.dcourts.gov.in/case-status-search-by-case-number/")
        logger.info("Page loaded successfully")
        
        # Save initial state for debugging
        driver.save_screenshot("01_initial_page.png")
        with open("01_initial_page.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        logger.info("Saved initial page state")

        # Fill form using JavaScript with enhanced reliability
        logger.info("Setting form values...")
        
        # Set court complex value
        driver.execute_script(f"""
            document.getElementById('est_code').value = '{e_code}';
            var event = new Event('change', {{bubbles: true}});
            document.getElementById('est_code').dispatchEvent(event);
        """)
        logger.info(f"Set court complex: {e_code}")
        time.sleep(1)
        
        # Set case type value
        driver.execute_script(f"""
            document.getElementById('case_type').value = '{c_type}';
            var event = new Event('change', {{bubbles: true}});
            document.getElementById('case_type').dispatchEvent(event);
        """)
        logger.info(f"Set case type: {c_type}")
        time.sleep(1)
        
        # Set case number and year
        reg_no_field = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "reg_no"))
        )
        reg_no_field.clear()
        reg_no_field.send_keys(reg_no)
        
        reg_year_field = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "reg_year"))
        )
        reg_year_field.clear()
        reg_year_field.send_keys(reg_year)
        logger.info(f"Set case number: {reg_no}/{reg_year}")
        time.sleep(1)
        
        # Save form state after filling
        driver.save_screenshot("02_form_filled.png")
        with open("02_form_filled.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        logger.info("Saved form filled state")

        # CAPTCHA handling
        if captcha_solution:
            logger.info("Entering CAPTCHA...")
            captcha_field = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.ID, "siwp_captcha_value_0"))
            )
            captcha_field.clear()
            captcha_field.send_keys(captcha_solution)
        else:
            logger.info("CAPTCHA required...")
            try:
                # Wait for CAPTCHA image to be visible
                captcha_img = WebDriverWait(driver, 10).until(
                    EC.visibility_of_element_located((By.ID, "siwp_captcha_image_0"))
                )
                # Get CAPTCHA as base64
                captcha_base64 = captcha_img.screenshot_as_base64
                return {"status": "captcha_required", "captcha_image": captcha_base64}
            except Exception as e:
                logger.error(f"Error getting CAPTCHA: {str(e)}")
                driver.save_screenshot("03_captcha_error.png")
                return {"status": "error", "message": f"CAPTCHA element not found: {str(e)}"}

        # ROBUST FORM SUBMISSION
        logger.info("Submitting form...")
        try:
            # Try clicking the submit button using JavaScript
            submit_button = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.NAME, "submit"))
            )
            driver.execute_script("arguments[0].click();", submit_button)
            logger.info("Form submitted via JavaScript click")
        except Exception as submit_error:
            logger.error(f"Submit button click failed: {str(submit_error)}")
            # Fallback: Submit form directly
            form = driver.find_element(By.TAG_NAME, "form")
            driver.execute_script("arguments[0].submit();", form)
            logger.info("Form submitted via direct form submission")

        # Wait for results to load with flexible timeout
        logger.info("Waiting for results...")
        try:
            WebDriverWait(driver, 20).until(
                EC.or_(
                    EC.presence_of_element_located((By.CLASS_NAME, "resultsHolder")),
                    EC.presence_of_element_located((By.ID, "cnrResults"))
                )
            )
            logger.info("Results container detected")
        except:
            logger.warning("Results container not detected, proceeding anyway")
            time.sleep(5)  # Additional wait time
        
        # Save results page
        driver.save_screenshot("04_results_page.png")
        with open("04_results_page.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        logger.info("Saved results page")

        # Check for common errors
        page_text = driver.page_source
        if "Invalid Captcha" in page_text:
            logger.error("Invalid CAPTCHA detected")
            return {"status": "invalid_captcha"}
            
        if "No records found" in page_text:
            logger.warning("No records found")
            return {"status": "not_found"}
        
        # Parse results with flexible approach
        logger.info("Parsing results...")
        soup = BeautifulSoup(driver.page_source, "html.parser")
        results = []
        
        # Try multiple ways to find results container
        results_holder = soup.find("div", class_="resultsHolder")
        if not results_holder:
            results_holder = soup.find("div", id="cnrResults")
        
        if results_holder:
            # Find all case sections
            case_sections = results_holder.find_all("div", class_="distTableContent")
            
            if not case_sections:
                # Try alternative class names
                case_sections = results_holder.find_all("div", class_="case-result")
            
            for section in case_sections:
                # Get court name
                caption = section.find("caption") or section.find("h3")
                court_name = caption.get_text(strip=True) if caption else "Unknown Court"
                
                # Find all case rows
                tbody = section.find("tbody")
                if not tbody:
                    # Try without tbody
                    rows = section.find_all("tr")
                else:
                    rows = tbody.find_all("tr")
                
                for row in rows:
                    cells = row.find_all("td")
                    if len(cells) < 3:
                        continue
                    
                    # Extract case details
                    case_no = cells[1].get_text(strip=True)
                    parties = cells[2].get_text(" ", strip=True)
                    
                    # Add to results
                    results.append({
                        "court": court_name,
                        "case_no": case_no,
                        "parties": parties,
                        "filing_date": "N/A",
                        "next_hearing": "N/A",
                        "orders": []
                    })
        
        if not results:
            logger.warning("No cases found in results")
            return {"status": "not_found"}
            
        logger.info(f"Found {len(results)} cases")
        return {"status": "success", "results": results}

    except Exception as e:
        logger.error(f"Error occurred: {str(e)}", exc_info=True)
        # Save error screenshot
        driver.save_screenshot("05_error_screenshot.png")
        logger.info("Saved error screenshot")
        return {"status": "error", "message": str(e)}
    finally:
        driver.quit()