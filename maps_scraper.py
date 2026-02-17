import argparse
import json
import time
import random
import re
import sys
from playwright.sync_api import sync_playwright

def scrape_google_maps(category, location, target_count=50):
    data = []
    
    with sync_playwright() as p:
        # Launch browser (Headful is safer for Maps)
        browser = p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-infobars",
                "--window-position=0,0",
                "--ignore-certificate-errors",
                "--ignore-certificate-errors-spki-list",
                "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ]
        )
        context = browser.new_context(viewport={"width": 1366, "height": 768})
        
        # Stealth scripts
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        page = context.new_page()
        
        try:
            # 1. Navigate and Search
            search_query = f"{category} in {location}"
            print(f"Navigating to Google Maps for: {search_query}")
            
            page.goto(f"https://www.google.com/maps/search/{search_query}", timeout=60000)
            
            # 2. Wait for Feed
            print("Waiting for results feed...")
            try:
                # The feed is usually a div with role='feed'
                page.wait_for_selector("div[role='feed']", timeout=15000)
                print("Feed found.")
            except:
                print("Feed not found immediately. Checking if valid results exist...")
                if "maps/search" not in page.url:
                    print(f"Redirected unexpectedly to: {page.url}")
            
            # 3. Infinite Scroll Logic (Target: div[role='feed'])
            feed_selector = "div[role='feed']"
            
            print(f"Starting scroll loop. Target: {target_count} items...")
            
            previous_count = 0
            scroll_attempts = 0
            max_scroll_attempts = 30
            
            while len(data) < target_count and scroll_attempts < max_scroll_attempts:
                # Count items currently in DOM
                items = page.locator(f"{feed_selector} > div > div[role='article']").all()
                count = len(items)
                
                print(f"  - Currently loaded: {count}")
                
                if count >= target_count:
                    print("Reached target count in DOM.")
                    break
                
                if count == previous_count:
                    scroll_attempts += 1
                    print(f"  - No new items loaded. Attempt {scroll_attempts}/{max_scroll_attempts}")
                else:
                    previous_count = count
                    scroll_attempts = 0
                
                # Scroll the FEED, not the window
                # We hover over the feed and wheel
                try:
                    page.hover(feed_selector)
                    page.mouse.wheel(0, 2000)
                    time.sleep(2)
                    
                    # Explicitly scroll to the last element found to trigger loading
                    if items:
                        items[-1].scroll_into_view_if_needed()
                        
                    # End key fallback
                    page.keyboard.press("End")
                    time.sleep(1)
                except Exception as e:
                    print(f"Scroll error: {e}")
                
                # Check for "You've reached the end of the list" text
                if page.get_by_text("You've reached the end of the list").is_visible():
                    print("Reached end of list.")
                    break
                
                time.sleep(random.uniform(2, 4))
            
            # 4. Extract Data
            print("Extracting data from loaded items...")
            
            # Re-fetch items to get fresh handles
            items = page.locator(f"{feed_selector} > div > div[role='article']").all()
            print(f"Found {len(items)} items to process.")
            
            for item in items:
                try:
                    # Google Maps structure is messy and changes. We use Aria Labels and relative locators.
                    
                    # Name is usually the Aria Label of the distinct div or inside a specific class
                    # Method 1: Get aria-label of the article itself or first link
                    name = item.get_attribute("aria-label")
                    if not name:
                        # Method 2: Look for fontHeadlineSmall
                        name_el = item.locator(".fontHeadlineSmall").first
                        if name_el.count() > 0:
                            name = name_el.inner_text()
                    
                    if not name: name = "Unknown Vendor"
                    
                    # Content Text (Address, etc) is often in fontBodyMedium
                    text_content = item.inner_text()
                    
                    # Rating
                    rating = "N/A"
                    rating_el = item.locator("span[role='img']").first
                    if rating_el.count() > 0:
                        rating_aria = rating_el.get_attribute("aria-label")
                        if rating_aria and "stars" in rating_aria:
                             rating = rating_aria.split("stars")[0].strip()
                    
                    # Phone - Hard to get without clicking. 
                    # Sometimes visible in text if we are lucky, or we try to click 'Details'
                    # For now, let's extract address/open status from text
                    lines = text_content.split('\n')
                    # Address is usually the line after rating or category
                    address = location # Default
                    for line in lines:
                        if location.split(',')[0] in line or "Road" in line or "St" in line:
                            address = line
                            break
                            
                    # Phone extraction from text regex
                    phone = "Not Available"
                    phone_match = re.search(r"(\+91[\-\s]?)?[6-9]\d{4}[\-\s]?\d{5}", text_content)
                    if phone_match:
                        phone = phone_match.group(0)

                    snippet = f"{name} - {category} in {location}"
                    
                    data.append({
                        "name": name,
                        "phone": phone,
                        "address": address,
                        "rating": rating,
                        "snippet": snippet
                    })
                    print(f"    + Extracted: {name}")
                    
                except Exception as e:
                    # print(f"Error parsing item: {e}")
                    continue
            
            # Save debug screenshot
            page.screenshot(path="maps_debug.png")
            
        except Exception as e:
            print(f"Scraper error: {e}", file=sys.stderr)
            page.screenshot(path="maps_error.png")
            
        browser.close()
        
    return data

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--category", required=True)
    parser.add_argument("--location", required=True)
    args = parser.parse_args()
    
    print(f"Starting Google Maps scraper for {args.category} in {args.location}")
    
    results = scrape_google_maps(args.category, args.location)
    
    # Save to JSON
    sanitized_category = args.category.replace(' ', '_')
    sanitized_location = args.location.replace(' ', '_').replace(',', '').replace('/', '_')
    filename = f"vendors_{sanitized_category}_{sanitized_location}.json"
    
    with open(filename, "w", encoding="utf-8") as f:
        json.dump({"category": args.category, "location": args.location, "vendors": results}, f, indent=2)
        
    print(f"Successfully scraped {len(results)} vendors. Saved to {filename}")
