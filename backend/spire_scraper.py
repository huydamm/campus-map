"""
spire_scraper.py
Logs into UMass SPIRE and scrapes course schedule data
to extract building names, days, and times for Spring 2026.
Saves results to spire_schedule.json
"""
import os
import json
import time
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

load_dotenv()

SPIRE_USERNAME = os.getenv("SPIRE_USERNAME")
SPIRE_PASSWORD = os.getenv("SPIRE_PASSWORD")
SPIRE_URL = "https://www.spire.umass.edu"

# Subjects to scrape - covers most popular buildings
SUBJECTS = [
    "Accounting",
    "Biology",
    "Chemistry",
    "Computer Science",
    "Economics",
    "English",
    "History",
    "Mathematics",
    "Physics",
    "Psychological & Brain Sciences",
    "Sociology",
    "Statistics",
    "Electrical & Computer Engin",
    "Mechanical & Industrial Engrg",
    "Public Health",
    "Management",
    "Finance",
    "Political Science",
    "Communication",
    "Education",
]


def setup_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)


def login(driver):
    print("Logging into SPIRE via Microsoft SSO...")
    driver.get(f"{SPIRE_URL}/psp/heproda/?cmd=login")
    wait = WebDriverWait(driver, 20)

    # Enter email
    email_field = wait.until(EC.presence_of_element_located((By.ID, "i0116")))
    email_field.clear()
    email_field.send_keys(SPIRE_USERNAME)
    driver.find_element(By.ID, "idSIButton9").click()
    time.sleep(2)

    # Enter password
    password_field = wait.until(EC.presence_of_element_located((By.ID, "i0118")))
    password_field.clear()
    password_field.send_keys(SPIRE_PASSWORD)
    driver.find_element(By.ID, "idSIButton9").click()
    time.sleep(3)
# Screenshot the MFA page so we can see the number
    driver.save_screenshot('/mnt/c/Users/Asus/Downloads/mfa_screen.png')
    print("MFA screenshot saved - check Downloads folder!")
    time.sleep(30)  # 30 seconds to approve

    # Handle "Stay signed in?" prompt if it appears
    try:
        stay_signed_in = driver.find_element(By.ID, "idSIButton9")
        stay_signed_in.click()
        time.sleep(2)
    except:
        pass

    print("Logged in!")


def navigate_to_class_search(driver):
    wait = WebDriverWait(driver, 20)
    driver.get(f"{SPIRE_URL}/psc/heproda/EMPLOYEE/SA/c/COMMUNITY_ACCESS.CLASS_SEARCH.GBL")
    time.sleep(3)
    driver.save_screenshot('/mnt/c/Users/Asus/Downloads/class_search.png')
    print("Navigated to class search.")


def search_subject(driver, subject):
    wait = WebDriverWait(driver, 20)
    results = []

    try:
        # Select term - Spring 2026
        term_select = wait.until(EC.presence_of_element_located(
            (By.ID, "UM_DERIVED_SA_UM_TERM_DESCR")
        ))
        Select(term_select).select_by_visible_text("2026 Spring")
        time.sleep(1)

        # Select subject
        subj_select = wait.until(EC.presence_of_element_located(
            (By.ID, "CLASS_SRCH_WRK2_SUBJECT$108$")
        ))
        try:
            Select(subj_select).select_by_visible_text(subject)
        except:
            for option in Select(subj_select).options:
                if subject.lower() in option.text.lower():
                    option.click()
                    break
        time.sleep(1)

        # Select Career = Undergraduate (2nd required criteria)
        career_select = driver.find_element(By.ID, "CLASS_SRCH_WRK2_ACAD_CAREER")
        Select(career_select).select_by_visible_text("Undergraduate")
        time.sleep(1)

        # Uncheck "Open Classes Only"
        try:
            open_only = driver.find_element(By.ID, "CLASS_SRCH_WRK2_SSR_OPEN_ONLY")
            if open_only.is_selected():
                open_only.click()
        except:
            pass

        # Click Search
        search_btn = wait.until(EC.element_to_be_clickable(
            (By.ID, "CLASS_SRCH_WRK2_SSR_PB_CLASS_SRCH")
        ))
        search_btn.click()
        time.sleep(6)

        # Screenshot to verify
        driver.save_screenshot(f'/mnt/c/Users/Asus/Downloads/results_{subject}.png')

        # Parse results
        soup = BeautifulSoup(driver.page_source, "html.parser")
        results = parse_results(soup, subject)
        print(f"  {subject}: found {len(results)} sections")

    except Exception as e:
        print(f"  {subject}: error - {e}")

    return results


def parse_results(soup, subject):
    sections = []
    
    # Find all rows in the Days & Times / Room tables
    tables = soup.find_all("table")
    
    for table in tables:
        headers = [th.get_text(strip=True) for th in table.find_all("th")]
        if "Days & Times" not in headers or "Room" not in headers:
            continue
        
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 2:
                continue
            
            try:
                days_time = cells[0].get_text(strip=True)
                room = cells[1].get_text(strip=True)
                
                if not days_time or days_time == "TBA" or not room or room == "TBA":
                    continue
                if "On-Line" in room or "On-line" in room:
                    continue
                
                sections.append({
                    "subject": subject,
                    "building": room,
                    "days_time": days_time,
                })
            except:
                continue
    
    return sections


def main():
    print(f"Starting SPIRE scraper for {len(SUBJECTS)} subjects...")
    driver = setup_driver()
    all_sections = []

    try:
        login(driver)
        navigate_to_class_search(driver)
        driver.save_screenshot('/mnt/c/Users/Asus/Downloads/after_nav.png')
        print("Page title:", driver.title)
        print("URL:", driver.current_url)
# Print all form element IDs
        from selenium.webdriver.common.by import By
        for el in driver.find_elements(By.TAG_NAME, 'select') + driver.find_elements(By.TAG_NAME, 'input'):
            eid = el.get_attribute('id')
            ename = el.get_attribute('name')
            if eid or ename:
                print(f'Element id={eid} name={ename}')

        for subject in SUBJECTS:
            print(f"Scraping {subject}...")
            sections = search_subject(driver, subject)
            all_sections.extend(sections)

            # Go back to search for next subject
            try:
                new_search = driver.find_element(By.ID, "CLASS_SRCH_WRK2_SSR_PB_NEW_SEARCH")
                new_search.click()
                time.sleep(2)
            except:
                navigate_to_class_search(driver)
                time.sleep(2)

    finally:
        driver.quit()

    # Save results
    with open("spire_schedule.json", "w") as f:
        json.dump(all_sections, f, indent=2)

    print(f"\nDone! Scraped {len(all_sections)} sections.")
    print("Saved to spire_schedule.json")

    # Summary by building
    buildings = {}
    for s in all_sections:
        b = s["building"]
        buildings[b] = buildings.get(b, 0) + 1

    print("\nTop buildings by section count:")
    for b, count in sorted(buildings.items(), key=lambda x: -x[1])[:20]:
        print(f"  {b}: {count} sections")


if __name__ == "__main__":
    main()
