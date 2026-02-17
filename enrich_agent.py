import json
import sqlite3
import re
import time
import random
import sys
import argparse
from playwright.sync_api import sync_playwright

DB_NAME = "marriage_vendors.db"

def get_db_connection():
    return sqlite3.connect(DB_NAME)

def update_db_details(name, phone, address, category, location):
    conn = get_db_connection()
    c = conn.cursor()
    
    # Update phone if found/needed
    if phone:
        c.execute("UPDATE vendors SET phone = ? WHERE name = ? AND location = ? AND (phone IS NULL OR phone = '' OR phone = 'Not Available')", 
                  (phone, name, location))
    
    # Update address if found/needed (and not just default location)
    if address and address != location:
         c.execute("UPDATE vendors SET address = ? WHERE name = ? AND location = ?", 
                  (address, name, location))
                  
    if c.rowcount > 0:
        print(f"Updated DB for {name}")
    conn.commit()
    conn.close()

def enrich_data(category, location):
    sanitized_category = category.replace(' ', '_')
    sanitized_location = location.replace(' ', '_').replace(',', '').replace('/', '_')
    json_file = f"vendors_{sanitized_category}_{sanitized_location}.json"
    
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"File {json_file} not found. Please run the scraper first for this location.")
        return

    vendors = data.get("vendors", [])
    print(f"Loaded {len(vendors)} vendors from {json_file}. Checking for missing phones...")
    
    vendors_to_enrich = [v for v in vendors if v.get("phone") in ["Not Available", "", None]]
    
    if not vendors_to_enrich:
        print("No vendors need enrichment.")
        return

    print(f"Enriching {len(vendors_to_enrich)} vendors via Google Maps...")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = browser.new_page()
        
        updated_count = 0
        
        for vendor in vendors_to_enrich:
            name = vendor["name"]
            search_query = f"{name} {location}"
            print(f"Searching: {search_query}")
            
            try:
                page.goto(f"https://www.google.com/maps/search/{search_query}", timeout=30000)
                time.sleep(3) # Wait for load
                
                # Check if it opened a single result or a list
                # If we are lucky, it opens the details directly
                
                # Try to find phone number on the page
                # Look for buttons with data-item-id starting with "phone:" 
                # or aria-label containing "Phone:"
                
                phone = None
                
                # Method 1: Look for the phone number text directly in the panel
                # Often formatted like: 080 1234 5678 or +91 ...
                
                # We can grab the whole text content of the visible Sidebar
                sidebar = page.locator("div[role='main']").first
                if sidebar.count() > 0:
                    text = sidebar.inner_text()
                    # Regex for phone
                    mob_match = re.search(r"(\+91[\-\s]?)?[6-9]\d{9}", text)
                    if mob_match: 
                        phone = mob_match.group(0)
                    else:
                        land_match = re.search(r"\b0\d{2,4}[\-\s]?\d{6,8}\b", text)
                        if land_match: phone = land_match.group(0)

                    # Extract Address 
                    # Look for button with data-item-id="address" or check text
                    # Often the address is the text inside a specific button or section
                    # A robust way is to look for the "location" icon or known address patterns
                    # But simpler: just get the full text and looks for lines that look like address (contain pin code)
                    # OR: Look for button with aria-label="Address: ..."
                    
                    address_btn = page.locator("button[data-item-id='address']").first
                    if address_btn.count() > 0:
                        address = address_btn.get_attribute("aria-label")
                        if address: address = address.replace("Address: ", "").strip()
                    else:
                        # Fallback: look for lines with 6 digit pincode
                        lines = text.split('\n')
                        for line in lines:
                             if re.search(r"\b\d{6}\b", line):
                                 address = line
                                 break

                if phone or address:
                    log_msg = []
                    if phone: 
                        vendor["phone"] = phone
                        log_msg.append(f"Phone: {phone}")
                    if address:
                        vendor["address"] = address
                        log_msg.append(f"Addr: {address}")
                        
                    print(f"  Found {', '.join(log_msg)}")
                    update_db_details(name, phone, address, category, location)
                    updated_count += 1
                else:
                    print(f"  No phone found.")
                
            except Exception as e:
                print(f"Error enriching {name}: {e}")
            
            time.sleep(random.uniform(2, 4))
            
        browser.close()
        
    # Save updated JSON
    with open(json_file, "w") as f:
        json.dump(data, f, indent=2)
    
    print(f"Enrichment complete. Updated {updated_count} vendors.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--category", required=True)
    parser.add_argument("--location", required=True)
    args = parser.parse_args()
    
    enrich_data(args.category, args.location)
