# Marriage Vendor Scraper

A powerful and user-friendly tool to scrape marriage vendor data (such as Halls, Caterers, Photographers) from **Justdial**. This application features a Streamlit-based UI for easy interaction, data visualization, and export capabilities.

## Features

-   **Multi-Source Scraping**: Scrape data from Justdial.
-   **User-Friendly Interface**: Built with [Streamlit](https://streamlit.io/) for a clean and intuitive web-based UI.
-   **Data Enrichment**: Enhance your data by cross-referencing sources (e.g., finding missing phone numbers via Google Maps).
-   **Smart Data Cleaning**: Built-in tools to extract phone numbers hidden in address fields and clean up "garbage" text.
-   **Database Storage**: Automatically saves all scraped data to a local SQLite database (`marriage_vendors.db`) to prevent duplicates.
-   **Dashboard & Export**: Visualize your data with charts and export everything to CSV or Excel.

## Prerequisites

-   **Python 3.8+** installed on your system.
-   **Google Chrome** installed (required for Playwright/Scraping).

## Installation

1.  **Clone the Repository**
    ```bash
    git clone <repository-url>
    cd marriage-vendor-scraper
    ```

2.  **Create a Virtual Environment** (Recommended)
    ```bash
    # Windows
    python -m venv venv
    .\venv\Scripts\activate

    # macOS/Linux
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Install Playwright Browsers**
    This tool uses Playwright for scraping. You need to install the browser binaries:
    ```bash
    playwright install chromium
    ```

5.  **Environment Configuration**
    Create a `.env` file in the root directory. While valid API keys are optional for the basic scraper, it's good practice to have the file:
    ```bash
    # .env
    # Add any required API keys here if future modules need them
    ```

## Usage

1.  **Run the Application**
    ```bash
    streamlit run app.py
    ```

2.  **Navigate the UI**
    The app will open in your default web browser (usually at `http://localhost:8501`).

    ### **Tab 1: Search**
    -   **State & District**: Enter the location you want to target (e.g., State: `Karnataka`, District: `Shimoga`).
    -   **Categories**: Select from a wide range of vendor types including `Catering`, `Photography`, `Halls`, `Makeover Artists`, `Decorators`, `Jewellery`, and more.
    -   **Data Source**: Choose between `Justdial` or `Google Maps`.
    -   **Search Vendors**: Click to start the scraping process. You will see real-time logs and progress.
    -   **Convert Scraped Data**: After scraping, a "Convert to CSV" section will appear. This uses our smart cleaning logic to:
        -   Extract phone numbers that might be mixed into the address field.
        -   Clean up formatting issues.
        -   Generate a pristine CSV file for download.

    ### **Tab 2: Dashboard**
    -   View statistics on total vendors collected.
    -   See a breakdown of vendors by category and district.
    -   **Export Data**: Download the entire database as a single CSV or Excel file.

## Troubleshooting

-   **Browser Error**: If you see errors related to the browser not launching, ensure you ran `playwright install chromium`.
-   **Timeout**: Scraping can be slow depending on your internet connection. If a search times out, try again or check your connection.
-   **Permission Denied**: On Windows, if you get permission errors writing files, try running the terminal as Administrator or check folder permissions.

## Project Structure

-   `app.py`: Main Streamlit application.
-   `scraper_agent.py`: Logic for scraping Justdial.
-   `maps_scraper.py`: Logic for scraping Google Maps.
-   `json_to_csv.py`: Module for cleaning JSON data and converting to CSV.
-   `database.py`: Handles SQLite database operations.
-   `requirements.txt`: Python dependencies.
