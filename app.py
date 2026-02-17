import streamlit as st
import subprocess
import json
import os
import database
from dotenv import load_dotenv
import sys
import pandas as pd
import io
import json_to_csv

# Load environment variables
load_dotenv()

def main():
    st.set_page_config(page_title="Marriage Vendor Scraper", layout="wide")
    
    # Initialize session state for scraped files
    if 'scraped_files' not in st.session_state:
        st.session_state['scraped_files'] = []

    st.title("Marriage Vendor Scraper")
    st.markdown("Search for wedding and event vendors by location and category.")
    
    # Sidebar only for Settings if needed (currently empty as API Key is removed)
    # Keeping it just in case or removing if empty.
    # Let's keep it minimal or remove "Settings" header if nothing is there.
    
    # Create tabs - Only Search and Dashboard
    tab1, tab2 = st.tabs(["Search", "Dashboard"])
    
    with tab1:
        # Inputs for State and District
        col1, col2 = st.columns(2)
        with col1:
            state = st.text_input("State", placeholder="Enter State (e.g. Karnataka)")
        with col2:
            district = st.text_input("District", placeholder="Enter District (e.g. Bangalore)")

        st.markdown("### Select Categories")
        
        # Checkboxes for categories
        cat_col1, cat_col2, cat_col3, cat_col4 = st.columns(4)

        categories = [
            "Catering", "Photography", "Shamiyana", "Halls",
            "Transport", "Pandits", "Textiles", "Other"
        ]
        
        selected_categories = []

        # Distribute checkboxes across columns
        for i, category in enumerate(categories):
            col = [cat_col1, cat_col2, cat_col3, cat_col4][i % 4]
            with col:
                if st.checkbox(category):
                    selected_categories.append(category)

        st.markdown("---")
        
        # Add Source Selection
        source = st.radio("Select Data Source", ["Justdial", "Google Maps"], horizontal=True)

        if st.button("Search Vendors", type="primary"):
            # Clear previous scraped files
            st.session_state['scraped_files'] = []
            
            if not state or not district:
                st.error("Please provide both State and District.")
            elif not selected_categories:
                st.error("Please select at least one category.")
            else:
                st.info(f"Searching in **{district}, {state}** for: {', '.join(selected_categories)}")
                
                # Initialize DB
                database.init_db()
                database.init_logs_db()

                for category in selected_categories:
                    st.write(f"Initiating scraper for: {category}...")
                    
                    location = f"{district}, {state}"
                    
                    # Construct command to run Python scraper
                    script_name = "scraper_agent.py" if source == "Justdial" else "maps_scraper.py"
                    cmd = [
                        sys.executable, script_name,
                        "--category", category,
                        "--location", location
                    ]
                    
                    try:
                        # Run the command and capture output
                        result = subprocess.run(cmd, capture_output=True, text=True)
                        
                        if result.returncode == 0:
                            st.success(f"Successfully scraped data for {category}!")
                            
                            with st.expander("View Scraper Debug Logs", expanded=False):
                                st.code(result.stdout)
                                if result.stderr:
                                    st.write("STDERR:")
                                    st.code(result.stderr)
                            
                            # Load and display the JSON if created
                            sanitized_category = category.replace(' ', '_')
                            sanitized_location = location.replace(' ', '_').replace(',', '').replace('/', '_')
                            json_file = f"vendors_{sanitized_category}_{sanitized_location}.json"
                            
                            # Track this file for conversion
                            if json_file not in st.session_state['scraped_files']:
                                st.session_state['scraped_files'].append(json_file)
                            
                            if os.path.exists(json_file):
                                with open(json_file, "r", encoding="utf-8") as f:
                                    data = json.load(f)
                                    
                                    # Save to Database
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
                                            
                                    msg = f"Added {new_count} new vendors"
                                    st.info(f"{msg} to the database.")
                                    database.log_scraper_run(category, location, "Success", msg)
                                    
                                    st.subheader(f"Results for {category}")
                                    for idx, vendor in enumerate(data.get("vendors", [])):
                                        v_name = vendor.get("name", "Unknown")
                                        v_phone = vendor.get("phone", "")
                                        v_rating = vendor.get("rating", "N/A")
                                        
                                        with st.expander(f"{v_name} (Rating: {v_rating})"):
                                            st.write(f"**Phone:** {v_phone}")
                                            st.write(f"**Address:** {vendor.get('address', '')}")
                        else:
                            st.error(f"Error running scraper for {category}")
                            st.code(result.stderr)
                            database.log_scraper_run(category, location, "Failed", result.stderr[:200] if result.stderr else "Unknown Error")
                            
                    except Exception as e:
                        st.error(f"An error occurred: {str(e)}")
                        database.log_scraper_run(category, location, "Exception", str(e))
        
        # Display Conversion Tools if files are available
        if st.session_state['scraped_files']:
            st.markdown("### Convert Scraped Data")
            for json_file in st.session_state['scraped_files']:
                if os.path.exists(json_file):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.text(f"File: {json_file}")
                    with col2:
                        if st.button(f"Convert to CSV", key=f"btn_{json_file}"):
                            csv_file, msg = json_to_csv.convert_json_to_csv(json_file)
                            if csv_file:
                                st.success(f"Converted!")
                                try:
                                    with open(csv_file, "r", encoding='utf-8') as f:
                                        csv_data = f.read()
                                    st.download_button(
                                        label="Download CSV",
                                        data=csv_data,
                                        file_name=os.path.basename(csv_file),
                                        mime='text/csv',
                                        key=f"dl_{json_file}"
                                    )
                                except Exception as e:
                                    st.error(f"Error reading CSV: {e}")
                            else:
                                st.error(f"Error: {msg}")

        st.markdown("---")
        st.markdown("### Data Enrichment")
        if st.button("Enrich Missing Phones (G-Maps)"):
             if not state or not district or not selected_categories:
                 st.error("Please fill State, District and Categories first.")
             else:
                 location = f"{district}, {state}"
                 for category in selected_categories:
                     st.info(f"Enriching {category} via Google Maps...")
                     cmd = [sys.executable, "enrich_agent.py", "--category", category, "--location", location]
                     proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                     
                     # Stream output
                     with st.expander(f"Enrichment Logs - {category}", expanded=True):
                         container = st.empty()
                         output = ""
                         for line in proc.stdout:
                             output += line
                             container.code(output)
                         proc.wait()
                     
                     st.success(f"Enrichment completed for {category}.")
                
    with tab2:
        st.header("Dashboard")
        
        # Initialize DB ensures tables exist if running for first time
        database.init_db()
        
        total = database.get_total_vendors()
        st.metric("Total Vendors Found", total)
        
        st.subheader("Vendors by Category")
        counts = database.get_vendor_counts_by_category()
        
        if counts:
            st.bar_chart(counts)
        else:
            st.info("No vendor data available yet. Use the Search tab to find vendors.")
            
        st.subheader("Top 5 Districts")
        top_districts = database.get_top_districts(5) if hasattr(database, 'get_top_districts') else None
        if top_districts:
            st.bar_chart(top_districts)
        
        st.subheader("Export Data")
        df = database.get_all_vendors_df() if hasattr(database, 'get_all_vendors_df') else pd.DataFrame()
        
        if not df.empty:
            col1, col2 = st.columns(2)
            with col1:
                st.download_button(
                    label="Download as CSV",
                    data=df.to_csv(index=False).encode('utf-8'),
                    file_name='vendors.csv',
                    mime='text/csv',
                )
            with col2:
                buffer = io.BytesIO()
                try:
                    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                        df.to_excel(writer, index=False, sheet_name='Vendors')
                        
                    st.download_button(
                        label="Download as Excel",
                        data=buffer,
                        file_name='vendors.xlsx',
                        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                    )
                except ModuleNotFoundError:
                    st.warning("xlsxwriter not found. Please run `pip install xlsxwriter` to enable Excel export.")
                except Exception as e:
                    st.error(f"Error creating Excel file: {e}")
        else:
            st.info("No data to export.")

if __name__ == "__main__":
    main()
