import sqlite3

DB_NAME = "marriage_vendors.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Create table with unique constraint on name and phone (or location) to avoid duplicates
    # We include category and location in uniqueness constraint to allow same vendor in multiple categories/locations if applicable
    c.execute('''CREATE TABLE IF NOT EXISTS vendors
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT NULL,
                  phone TEXT,
                  address TEXT,
                  category TEXT,
                  location TEXT,
                  rating TEXT,
                  summary TEXT,
                  UNIQUE(name, phone, category, location))''')
    
    # Simple migration for existing tables that might miss columns
    # In production, use a proper migration tool like Alembic
    try:
        c.execute("ALTER TABLE vendors ADD COLUMN rating TEXT")
    except sqlite3.OperationalError:
        pass # Column likely exists
        
    try:
        c.execute("ALTER TABLE vendors ADD COLUMN summary TEXT")
    except sqlite3.OperationalError:
        pass
        
    conn.commit()
    conn.close()


def init_logs_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS scraper_logs
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                  category TEXT,
                  location TEXT,
                  status TEXT,
                  message TEXT)''')
    conn.commit()
    conn.close()

def log_scraper_run(category, location, status, message):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO scraper_logs (category, location, status, message) VALUES (?, ?, ?, ?)",
              (category, location, status, message))
    conn.commit()
    conn.close()

def add_vendor(name, phone, address, category, location, rating=None):
    """
    Add a vendor to the database. Returns True if added, False if duplicate.
    """
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO vendors (name, phone, address, category, location, rating) VALUES (?, ?, ?, ?, ?, ?)",
                  (name, phone, address, category, location, rating))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def update_vendor_summary(vendor_id, summary):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE vendors SET summary = ? WHERE id = ?", (summary, vendor_id))
    conn.commit()
    conn.close()

def get_vendor_by_name_phone(name, phone):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, summary FROM vendors WHERE name = ? AND phone = ?", (name, phone))
    row = c.fetchone()
    conn.close()
    return row

def get_vendors(category=None, location=None):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Return all columns including id, rating, summary
    query = "SELECT id, name, phone, address, category, location, rating, summary FROM vendors WHERE 1=1"
    params = []
    if category:
        query += " AND category = ?"
        params.append(category)
    if location:
        query += " AND location = ?"
        params.append(location)
    

    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    return rows

def get_total_vendors():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM vendors")
    count = c.fetchone()[0]
    conn.close()
    return count

def get_vendor_counts_by_category():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT category, COUNT(*) FROM vendors GROUP BY category")
    rows = c.fetchall()
    conn.close()
    # Return as a dictionary: {category: count}
    return {row[0]: row[1] for row in rows}

def get_top_districts(limit=5):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT location, COUNT(*) FROM vendors GROUP BY location ORDER BY COUNT(*) DESC LIMIT ?", (limit,))
    c.execute("SELECT location, COUNT(*) FROM vendors GROUP BY location ORDER BY COUNT(*) DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return {row[0]: row[1] for row in rows}

def get_all_vendors_df():
    import pandas as pd
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM vendors", conn)
    conn.close()
    return df

# Logging functions
def init_logs_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS scraper_logs
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  timestamp TEXT,
                  category TEXT,
                  location TEXT,
                  status TEXT,
                  message TEXT)''')
    conn.commit()
    conn.close()

def log_scraper_run(category, location, status, message):
    from datetime import datetime
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO scraper_logs (timestamp, category, location, status, message) VALUES (?, ?, ?, ?, ?)",
              (timestamp, category, location, status, message))
    conn.commit()
    conn.close()

def get_logs(limit=50):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT timestamp, category, location, status, message FROM scraper_logs ORDER BY id DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_logs_df():
    import pandas as pd
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM scraper_logs ORDER BY id DESC", conn)
    conn.close()
    return df

if __name__ == "__main__":
    init_db()
    init_logs_db()
