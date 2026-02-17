import streamlit as st
import subprocess
import json
import os
import database
from dotenv import load_dotenv
import sys
import pandas as pd
import io

# Load environment variables
load_dotenv()

def main():
    st.set_page_config(page_title="Marriage Vendor Scraper", layout="wide")
    
    st.title("Marriage Vendor Scraper")
    st.markdown("Search for wedding and event vendors by location and category.")
    
    with st.sidebar:
        st.header("Settings")
        # Try to get key from env first
        env_api_key = os.getenv("GEMINI_API_KEY")
        gemini_api_key = st.text_input("Gemini API Key", type="password", value=env_api_key if env_api_key else "", help="Enter your Google Gemini API Key to enable AI features.")
    
    if gemini_api_key:
        import google.generativeai as genai
        genai.configure(api_key=gemini_api_key)

    def generate_summary(text):
        if not gemini_api_key:
            return "API Key missing."
        try:
            model = genai.GenerativeModel('gemini-pro')
            prompt = f"Give a 1-sentence 'vibe check' or pro/con summary for this wedding vendor based on these details: {text}"
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"Error: {e}"

    # Create tabs
    tab1, tab2, tab3, tab4 = st.tabs(["Search", "Dashboard", "Logs", "AI Planner"])
    
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
                            
                            if os.path.exists(json_file):
                                with open(json_file, "r") as f:
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

    with tab3:
        st.header("Scraper Logs")
        database.init_logs_db()
        logs_df = database.get_logs_df() if hasattr(database, 'get_logs_df') else pd.DataFrame()
        if not logs_df.empty:
            st.dataframe(logs_df)
        else:
            st.info("No logs available yet. Run a search to generate logs.")

    with tab4:
        st.header("AI Wedding Planner")
        st.markdown("Ask questions about your wedding planning, and I'll use the scraped vendor data to help you!")
        
        if "messages" not in st.session_state:
            st.session_state.messages = []

        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        if prompt := st.chat_input("Ex: Which caterer in Bangalore has the best rating?"):
            st.chat_message("user").markdown(prompt)
            st.session_state.messages.append({"role": "user", "content": prompt})

            if not gemini_api_key:
                response = "Please enter your Gemini API Key in the sidebar settings to use the AI Planner."
            else:
                with st.spinner("Thinking..."):
                    try:
                        df = database.get_all_vendors_df() if hasattr(database, 'get_all_vendors_df') else pd.DataFrame()
                        if df.empty:
                            context = "No vendor data available yet."
                        else:
                            context = df.to_csv(index=False)
                        
                        model = genai.GenerativeModel('gemini-pro')
                        full_prompt = f"""
                        You are an expert Wedding Planner. Use the following vendor data to answer the user's question.
                        If the answer is not in the data, say so, but provide general advice.
                        
                        Vendor Data (CSV):
                        {context}
                        
                        User Question: {prompt}
                        """
                        
                        ai_response = model.generate_content(full_prompt)
                        response = ai_response.text
                    except Exception as e:
                        response = f"I encountered an error: {str(e)}"

            with st.chat_message("assistant"):
                st.markdown(response)
            st.session_state.messages.append({"role": "assistant", "content": response})

if __name__ == "__main__":
    main()
