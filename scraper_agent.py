import argparse
import json
import time
import random
import sys
from playwright.sync_api import sync_playwright

def scrape_justdial(category, location):
    data = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            # Arguments to hide automation
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-http2", 
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-infobars",
                "--window-position=0,0",
                "--ignore-certificate-errors",
                "--ignore-certificate-errors-spki-list",
                "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
            ]
        )
        context = browser.new_context(
            viewport={"width": 1366, "height": 768}
        )
        
        # Additional stealth scripts
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        context.add_init_script("window.navigator.chrome = { runtime: {} };")
        context.add_init_script("Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]})")
        
        page = context.new_page()
        
        # 1. Navigate
        print(f"Navigating to Justdial...")
        page.goto("https://www.justdial.com/", timeout=60000)
        
        try:
            # 2. Search
            search_query = f"Wedding {category} in {location}"
            print(f"Searching for: {search_query}")
            
            # Priority 1: Use Search Box (Most reliable if selectors work)
            search_successful = False
            try:
                print("Waiting for search box...")
                # Try generic input if specific ones fail
                page.wait_for_selector("input.search-input, input#srchbx, input[role='combobox'], input[type='text']", timeout=10000)
                input_box = page.query_selector("input.search-input") or \
                            page.query_selector("input#srchbx") or \
                            page.query_selector("input[role='combobox']")
                if input_box:
                    input_box.fill(search_query)
                    time.sleep(1)
                    page.keyboard.press("Enter")
                    print("Used search box. Submitted query.")
                    
                    # Verify if search actually worked by waiting for result element
                    try:
                        print("Verifying search results...")
                        page.wait_for_selector(".resultbox_title_anchor, .store-name, .cntanr", timeout=10000)
                        search_successful = True
                        print("Search results verified.")
                    except:
                        print("Search verification failed (no results found). Triggering fallback.")
                        search_successful = False
                else:
                    print("Search box not found.")
            except Exception as e:
                print(f"Search box interaction failed: {e}")

            # Priority 2: Direct URL (Fallback)
            if not search_successful:
                print("Trying direct URL navigation as fallback...")
                # Map categories to Justdial slugs
                slug_map = {
                    "Catering": "Caterers",
                    "Photography": "Photographers",
                    "Halls": "Banquet-Halls",
                    "Shamiyana": "Tent-House",
                    "Transport": "Travel-Agents",
                    "Pandits": "Pandits",
                    "Textiles": "Fabric-Retailers",
                    "Bakery": "Bakeries",
                    "Makeover Artists": "Beauty-Parlours",
                    "Music Systems": "Sound-Systems-On-Hire",
                    "Florists": "Florists",
                    "Decorators": "Wedding-Decorators",
                    "Jewellery": "Jewellery-Showrooms"
                }
                city = location.split(",")[0].strip()
                cat_slug = slug_map.get(category, category)
                if category in ["Pandits", "Textiles", "Transport", "Shamiyana", "Bakery", "Makeover Artists", "Music Systems", "Florists", "Decorators", "Jewellery"]:
                     query_slug = cat_slug
                else:
                     query_slug = f"Wedding-{cat_slug}"
                
                # Construct URL carefully
                url = f"https://www.justdial.com/{city}/{query_slug}"
                print(f"Navigating directly to URL: {url}")
                try:
                    page.goto(url, timeout=60000)
                    page.wait_for_load_state("domcontentloaded")
                except Exception as e:
                    print(f"Direct navigation failed: {e}")

            # 3. Wait for results
            print("Waiting for results to load...")
            try:
                # Wait explicitly for result containers
                # Removed generic 'h2' from wait to ensure we don't proceed on homepage
                page.wait_for_selector("div.result-box, li.cntanr, div.store-details, .resultbox_title_anchor", timeout=20000)
            except Exception as w_err:
                print(f"Warning: Wait for results timed out or page structure changed ({w_err})")
            
            # 4. Infinite Scroll and Extraction Loop
            data = []
            target_count = 300 # Increased default target
            
            BLACKLIST_NAMES = [
                "Wedding Requisites", "Beauty & Spa", "Repairs & Services", "Daily Needs", 
                "Bills & Recharge", "Travel Bookings", "Trending Searches", "Explore Top Tourist Places", 
                "Popular Searches", "Cool Day Essentials", "Follow us on", "One-Stop for All Local Businesses",
                "JD Mart", "Advertise", "Free Listing", "Login / Sign Up", "Recent Activity", "Seasonal"
            ]

            # Helper for phone extraction
            def extract_phone_number(card_element):
                try:
                    # Strategy 1: Look for explicit call/contact elements
                    phone_el = card_element.query_selector(".callcontent, .contact-info, .mobilessv, .mobilesv, .phone, a[href^='tel:']")
                    if phone_el:
                        text = phone_el.inner_text().strip()
                        # If text is obfuscated or empty, try to get aria-label or title
                        if not text:
                            text = phone_el.get_attribute("title") or phone_el.get_attribute("aria-label") or ""
                        if text: return text
                    
                    # Strategy 2: Regex on the whole card text
                    # Mobile: (+91) 6-9xxxxxxxxx
                    # Landline: 0xxxxx-xxxxxx (Std code 3-5 digits, number 6-8 digits)
                    card_text = card_element.inner_text()
                    
                    # Try finding mobile match
                    mob_match = re.search(r"(\+91[\-\s]?)?[6-9]\d{9}", card_text)
                    if mob_match: return mob_match.group(0)
                    
                    # Try finding landline match (e.g. 08182 222222)
                    land_match = re.search(r"\b0\d{2,4}[\-\s]?\d{6,8}\b", card_text)
                    if land_match: return land_match.group(0)
                        
                    return "Not Available"
                except:
                    return "Not Available"

            print(f"Starting extraction loop. Target: {target_count} items...")
            
            processed_hashes = set()
            scroll_attempts = 0
            max_scroll_attempts = 30 # Increased safety break
            current_batch_results = [] # Initialize here
            
            while len(data) < target_count and scroll_attempts < max_scroll_attempts:
                # Scroll Logic: Super Smooth Scroll
                print(f"Scrolling smoothly... (Current count: {len(data)})")
                
                # Get current scroll position and height
                current_height = page.evaluate("document.body.scrollHeight")
                viewport_height = page.viewport_size['height']
                
                # Scroll down in smaller chunks for longer - VERY SLOWLY
                scroll_occurred = False
                for _ in range(0, 40): # Fewer steps, slower
                    page.mouse.wheel(0, 200) # Small step
                    time.sleep(random.uniform(0.4, 0.7)) # Slow read speed
                    
                    new_height = page.evaluate("document.body.scrollHeight")
                    if new_height > current_height:
                        current_height = new_height
                        scroll_occurred = True
                        
                    # Check if we hit bottom
                    scroll_y = page.evaluate("window.scrollY")
                    if scroll_y + viewport_height >= current_height:
                         # We hit bottom, try to jiggle
                         print("  (Hit apparent bottom, jiggling...)")
                         page.mouse.wheel(0, -200)
                         time.sleep(1)
                         page.mouse.wheel(0, 200)
                         time.sleep(1)
                         
                         # Check for Footer
                         footer = page.query_selector("footer, .footer, #footer")
                         if footer and footer.is_visible():
                             print("  (Footer detected. Stopping scroll.)")
                             max_scroll_attempts = 0 # Force stop outer loop
                             break
                             
                         new_height_2 = page.evaluate("document.body.scrollHeight")
                         if new_height_2 > current_height:
                             current_height = new_height_2
                             continue 
                         break

                print("Finished scroll step.")
                
                # 3. Wait for load (Use explicit wait requested by user + random buffer)
                time.sleep(3 + random.uniform(0, 2)) 
                
                # 4. Check for "Show More" / "Load More" button
                try:
                     # Try multiple selectors for load more buttons
                     show_more = page.query_selector("button:has-text('Show More'), .load-more-btn, #loadMore, a:has-text('Load more')")
                     if show_more: 
                         print("Clicked 'Show More' button.")
                         show_more.click()
                         time.sleep(2)
                except: pass
                
                # Start from top strategy to avoid broad matches

                
                # Check for "Show More"
                try:
                     show_more = page.query_selector("button:has-text('Show More')")
                     if show_more: show_more.click()
                except: pass
                
                # Start from top strategy to avoid broad matches
                strategies = [
                    ("li.cntanr", "Classic List Item"),
                    ("div.result-box", "Result Box Div"),
                    ("div.store-details", "Store Details Div"),
                    (".resultbox_title_anchor", "Title Anchor Class"),
                    ("h2.store-name", "Store Name H2")
                    # Removed generic "h2" strategy
                ]
                
                current_batch_results = []
                strategy_name = ""
                for selector, name in strategies:
                    found = page.query_selector_all(selector)
                    if found:
                        current_batch_results = found
                        strategy_name = name
                        break
                
                print(f"  - Found {len(current_batch_results)} items in DOM (Strategy: {strategy_name})")
                
                new_items_found = False
                for card in current_batch_results:
                    if len(data) >= target_count: break
                    
                    try:
                        # Identify name first 
                        name = "Unknown"
                        is_title_strategy = strategy_name in ["Title Anchor Class", "Store Name H2"]
                        
                        container = card
                        if is_title_strategy:
                             name = card.inner_text().strip()
                             # Traverse up
                             try:
                                 container = card.query_selector("xpath=./ancestor::li[contains(@class, 'cntanr')]") or \
                                             card.query_selector("xpath=./ancestor::div[contains(@class, 'result-box')]") or \
                                             card.query_selector("xpath=./ancestor::div[contains(@class, 'store-details')]")
                             except:
                                 container = None
                                 
                             if not container:
                                 container = card # Fallback to card itself
                        else:
                            name_el = card.query_selector(".resultbox_title_anchor, .store-name, h2")
                            if name_el: name = name_el.inner_text().strip()
                        
                        # Debug raw name
                        # print(f"DEBUG: Raw extracted name: '{name}'")

                        # Clean name
                        name = name.split('\n')[0].strip()
                        
                        if name == "Unknown":
                            print(f"DEBUG: Skipped {name} (Name is Unknown)")
                            continue 
                            
                        if any(b.lower() in name.lower() for b in BLACKLIST_NAMES):
                            # print(f"DEBUG: Skipped {name} (Blacklisted)")
                            continue
                        
                        # Use a simple hash for deduplication
                        item_hash = f"{name}-{location}"
                        if item_hash in processed_hashes:
                            # print(f"DEBUG: Skipped {name} (Duplicate)")
                            continue
                        
                        # Extract details
                        phone = "Not Available"
                        address = location
                        rating = "N/A"
                        
                        if container:
                            phone = extract_phone_number(container)
                            
                            address_el = container.query_selector(".address-info, .cont_sw_addr, span.cont_fl_addr, .full-address")
                            if address_el: address = address_el.inner_text().replace("Map", "").strip()
                            
                            rating_el = container.query_selector(".green-box, .rating, .star_m")
                            if rating_el: rating = rating_el.inner_text().strip()

                        snippet = f"{category} vendor in {location}"

                        data.append({
                            "name": name,
                            "phone": phone,
                            "address": address,
                            "rating": rating,
                            "snippet": snippet
                        })
                        processed_hashes.add(item_hash)
                        new_items_found = True
                        print(f"    + Added: {name} | Phone: {phone}")
                        
                    except Exception as e:
                        print(f"DEBUG: Error extracting {name}: {e}")
                        continue
                
                if not new_items_found:
                     print("  - No new items found in this scroll.")
                     scroll_attempts += 1
                else:
                     scroll_attempts = 0 # Reset
                     
                print(f"  - Total extracted: {len(data)}")

            if len(data) == 0:
                print("No data extracted. Check 'last_scrape.html'.")
                # Save page content for debugging
                with open("last_scrape.html", "w", encoding="utf-8") as f:
                    f.write(page.content())

        except Exception as e:
            print(f"Scraping error: {e}", file=sys.stderr)
            # Take screenshot and save HTML on error
            page.screenshot(path="debug_error.png")
            with open("last_scrape_error.html", "w", encoding="utf-8") as f:
                 f.write(page.content())
            sys.exit(1) # Ensure app.py knows it failed

        browser.close()
        
    return data



if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--category", required=True)
    parser.add_argument("--location", required=True)
    args = parser.parse_args()
    
    print(f"Starting scraper for {args.category} in {args.location}")
    
    vendors = scrape_justdial(args.category, args.location)
    
    output = {
        "category": args.category,
        "location": args.location,
        "vendors": vendors
    }
    # Save to JSON
    sanitized_category = args.category.replace(' ', '_')
    sanitized_location = args.location.replace(' ', '_').replace(',', '').replace('/', '_')
    filename = f"vendors_{sanitized_category}_{sanitized_location}.json"
    
    with open(filename, "w", encoding="utf-8") as f:
        json.dump({"category": args.category, "location": args.location, "vendors": vendors}, f, indent=2)
        
    print(f"Successfully scraped {len(vendors)} vendors. Saved to {filename}")
