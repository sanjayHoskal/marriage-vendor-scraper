import schedule
import time
import subprocess
import os
import json
import sqlite3
import database
from datetime import datetime
from dotenv import load_dotenv
import sys

# Load environment variables
load_dotenv()

# Configuration
# Ideally these could be loaded from a config file or arguments
CATEGORIES = [
    "Catering", "Photography", "Shamiyana", "Halls",
    "Transport", "Pandits", "Textiles"
]
LOCATIONS = ["Bangalore, Karnataka"]

def job():
    print(f"\n[{datetime.now()}] Starting scheduled scraping job for {LOCATIONS}...")
    
    # Initialize DB (idempotent)
    database.init_db()
    database.init_logs_db()

    for location in LOCATIONS:
        for category in CATEGORIES:
            print(f"[{datetime.now()}] Scraping {category} in {location}...")
            
            try:
                # Construct command to run Python scraper
                cmd = [
                    sys.executable, "scraper_agent.py",
                    "--category", category,
                    "--location", location
                ]
                
                # Run command
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode == 0:
                    sanitized_category = category.replace(' ', '_')
                    sanitized_location = location.replace(' ', '_').replace(',', '').replace('/', '_')
                    json_file = f"vendors_{sanitized_category}_{sanitized_location}.json"
                    
                    if os.path.exists(json_file):
                        try:
                            with open(json_file, "r") as f:
                                data = json.load(f)
                                
                            new_count = 0
                            for vendor in data.get("vendors", []):
                                added = database.add_vendor(
                                    vendor.get("name"),
                                    vendor.get("phone"),
                                    vendor.get("address"),
                                    category,
                                    location
                                )
                                if added:
                                    new_count += 1
                                    
                            print(f"[{datetime.now()}] Success: Added {new_count} new vendors for {category}.")
                            database.log_scraper_run(category, location, "Success", f"Added {new_count} new vendors")
                        except json.JSONDecodeError:
                             print(f"[{datetime.now()}] Error: JSON decode failed for {json_file}")
                             database.log_scraper_run(category, location, "Failed", "JSON decode failed")
                    else:
                        print(f"[{datetime.now()}] Warning: Output file '{json_file}' not found.")
                        database.log_scraper_run(category, location, "Warning", "Output file not found")
                else:
                    print(f"[{datetime.now()}] Error running skill for {category}: {result.stderr}")
                    database.log_scraper_run(category, location, "Failed", result.stderr[:200]) # Limit msg length
                    
            except FileNotFoundError:
                print(f"[{datetime.now()}] Error: 'openclaw' command not found. Ensure it is installed and in PATH.")
                database.log_scraper_run(category, location, "Error", "openclaw command not found")
            except Exception as e:
                print(f"[{datetime.now()}] Exception occurred: {e}")
                database.log_scraper_run(category, location, "Exception", str(e))
                
    # Send email summary
    summary_msg = f"Daily scraping job complete for {locations}. Check database logs for details."
    send_email("Daily Scraper Report", summary_msg)
    
    print(f"[{datetime.now()}] Scheduled job completed.")

def send_email(subject, body):
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    sender_email = os.environ.get("GMAIL_USER")
    sender_password = os.environ.get("GMAIL_APP_PASSWORD")
    
    if not sender_email or not sender_password:
        print("Email credentials not found (GMAIL_USER, GMAIL_APP_PASSWORD). Skipping email.")
        return
        
    receiver_email = sender_email # Send to self
    
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        text = msg.as_string()
        server.sendmail(sender_email, receiver_email, text)
        server.quit()
        print("Email notification sent successfully.")
    except Exception as e:
        print(f"Failed to send email: {e}")

# Schedule the job every day at 08:00
schedule.every().day.at("08:00").do(job)

print("Scheduler started. Job scheduled for 08:00 AM daily.")
print("To enable email alerts, set GMAIL_USER and GMAIL_APP_PASSWORD environment variables.")
print("Press Ctrl+C to exit.")

while True:
    try:
        schedule.run_pending()
        time.sleep(60) # Check every minute
    except KeyboardInterrupt:
        print("Scheduler stopped by user.")
        break
