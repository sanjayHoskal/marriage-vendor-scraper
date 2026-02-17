---
name: wedding-vendor-scraper
description: Scrape wedding vendor information from Justdial and Indiamart with human emulation.
requirements:
  bins: [openclaw]
---

# Wedding Vendor Scraper

Using the OpenClaw browser tool, navigate to Justdial or Indiamart and extract vendor details.

## Inputs
- `category`: The type of vendor (e.g., Catering, Photography).
- `location`: The city and state (e.g., Bangalore, Karnataka).

## Steps

1.  Use the `browser_tool` to open `https://www.justdial.com/`.
2.  Search for `Wedding {category} in {location}` using the search bar.
3.  Wait for the results page to load completely.
4.  **Emulate Human Behavior:** Wait randomly between 2 to 5 seconds.
5.  Scroll down to load more results. Wait 2-5 seconds between each scroll action to mimic human reading speed.
6.  Extract the **Business Name**, **Phone Number** (if visible), **Address**, **Rating** (e.g. "4.5"), and **Snippet** (short description or tags) for at least 5 businesses from the results.
7.  Format the data as a JSON object:
    ```json
    {
      "category": "{category}",
      "location": "{location}",
      "vendors": [
        {
          "name": "Vendor Name",
          "phone": "Phone Number",
          "address": "Address",
          "rating": "4.5",
          "snippet": "Wedding photographers, candid photography..."
        }
      ]
    }
    ```
8.  Save this JSON to a file named `vendors_{category}.json` in the current directory.
