import json
import csv
import re
import os

def extract_phone_from_address(address):
    """
    Extracts phone number from address string and cleans the address.
    Returns (cleaned_address, phone_number)
    """
    if not address:
        return address, None

    # Regex patterns
    # Pattern to find phone numbers (approximate for Indian numbers: 10-12 digits, optional spaces)
    # Examples: 073386 66555 (6+5), 98442 82504 (6+5), 081832 22225 (6+5)
    # Allow 3-6 digits for the first part
    phone_pattern = r'\b(\d{3,6}\s?\d{5,8})\b'
    
    # Pattern to remove "Open . Closes .." garbage
    # Example: "Open \u00b7 Closes 5\u202fpm \u00b7 "
    garbage_pattern = r'Open.*Closes.*?[APap][Mm].*?(\u00b7|\.)\s*'

    phone_match = re.search(phone_pattern, address)
    phone = None
    
    clean_addr = address

    if phone_match:
        phone = phone_match.group(1)
        # Remove the phone number from the address
        clean_addr = clean_addr.replace(phone, '').strip()
    
    # Remove garbage prefix
    clean_addr = re.sub(garbage_pattern, '', clean_addr).strip()
    
    # Remove trailing/leading separators like '·' or ',' or '-'
    clean_addr = re.sub(r'^[\s\u00b7,\-]+|[\s\u00b7,\-]+$', '', clean_addr).strip()

    return clean_addr, phone

def convert_json_to_csv(json_file_path):
    """
    Converts a vendor JSON file to CSV with data cleaning.
    """
    if not os.path.exists(json_file_path):
        return None, "File not found."

    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        vendors = data.get("vendors", [])
        if not vendors:
            return None, "No vendors found in JSON."

        # Prepare CSV data
        csv_data = []
        for v in vendors:
            name = v.get("name")
            phone = v.get("phone", "Not Available")
            address = v.get("address", "")
            rating = v.get("rating", "N/A")
            snippet = v.get("snippet", "")
            
            # Logic: If phone is missing, try to find it in address
            if phone in ["Not Available", "N/A", ""] and address:
                cleaned_addr, extracted_phone = extract_phone_from_address(address)
                if extracted_phone:
                    phone = extracted_phone
                    address = cleaned_addr
                # Even if no phone extracted, we might want to clean garbage from address?
                # The user example implies garbage usually comes with the phone number logic,
                # but "Open . Closes.." might appear even if phone isn't there? 
                # Let's assume we clean address regardless if it looks like it has garbage.
                if "Open" in address and "Closes" in address:
                     address, _ = extract_phone_from_address(address) # Re-run to clean garbage if not already done

            csv_data.append({
                "name": name,
                "phone": phone,
                "address": address
            })
            
        # Generate CSV filename
        csv_file = json_file_path.replace('.json', '.csv')
        
        keys = ["name", "phone", "address"]
        
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(csv_data)
            
        return csv_file, "Success"

    except Exception as e:
        return None, str(e)

if __name__ == "__main__":
    # Test with the existing file if running standalone
    test_file = "vendors_Halls_Shimoga_Karnataka.json"
    if os.path.exists(test_file):
        print(f"Testing conversion on {test_file}...")
        csv_path, msg = convert_json_to_csv(test_file)
        print(f"Result: {csv_path} - {msg}")
