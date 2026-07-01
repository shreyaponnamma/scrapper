import os
import sys
import re
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
import pandas as pd

# Add the project root to sys.path to allow imports from scripts.*
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from scripts.utils.config import INSTRUMENT_MERGE

# Default config
TARGETS = ["ICEYE","Elektro"]
ADDITIONAL_SOURCES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "additional_sources.txt")

def read_start_url():
    """Reads starting URL from additional_sources.txt or falls back to default."""
    default_url = "https://space.skyrocket.de/doc_chr/lau2026.htm"
    if os.path.exists(ADDITIONAL_SOURCES_FILE):
        try:
            with open(ADDITIONAL_SOURCES_FILE, "r") as f:
                content = f.read().strip()
                if content.startswith("http"):
                    print(f"Read launch page URL from additional_sources.txt: {content}")
                    return content
        except Exception as e:
            print(f"Warning: Could not read additional_sources.txt: {e}")
    print(f"Using default launch page URL: {default_url}")
    return default_url

def is_valid_launched_cospar(cospar_str):
    """Validates that a string matches a launched COSPAR ID format and isn't planned/TBD."""
    if not cospar_str:
        return False
    cospar_str = cospar_str.strip()
    if any(w in cospar_str.lower() for w in ["tbd", "planned", "t.b.d.", "lost", "fail", "launch"]):
        return False
    # Standard format: YYYY-NNNAAA (e.g. 2019-038D, 2024-043E, 2025-135BJ, or 2025-052-AV)
    # We require 4 digits, a hyphen, and at least 3 digits/characters representing launch sequence
    return bool(re.search(r'\d{4}-\d{3}', cospar_str))

def is_table_planned(table_element):
    """Checks if a table falls under a section labeled 'Planned'."""
    curr = table_element.previous_sibling
    while curr:
        if curr.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p']:
            text = curr.get_text().lower()
            if 'planned' in text:
                return True
            if 'launched' in text or 'active' in text:
                return False
        curr = curr.previous_sibling
    return False

def scrape_skyrocket():
    start_url = read_start_url()
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    print(f"Fetching launch chronicle: {start_url}...")
    try:
        r = requests.get(start_url, headers=headers, timeout=15)
        r.raise_for_status()
    except Exception as e:
        print(f"Error fetching launch page: {e}")
        return

    soup = BeautifulSoup(r.text, 'html.parser')
    
    # Find all links on page
    links = soup.find_all('a', href=True)
    print(f"Found {len(links)} total links on launch chronicle.")

    scraped_satellites = []

    for target in TARGETS:
        print(f"\nProcessing target satellite series: '{target}'")
        target_lower = target.lower()
        first_match_link = None
        
        for link in links:
            text = link.get_text().strip()
            # Simple substring check (e.g., 'ICEYE X63' contains 'ICEYE')
            if target_lower in text.lower():
                first_match_link = link
                print(f"Found first match: '{text}' -> {link['href']}")
                break
                
        if not first_match_link:
            print(f"No match found on chronicle for target '{target}'. skipping.")
            continue
            
        # Resolve detail URL
        detail_url = urljoin(start_url, first_match_link['href'])
        print(f"Navigating to satellite details page: {detail_url}")
        
        try:
            r_detail = requests.get(detail_url, headers=headers, timeout=15)
            r_detail.raise_for_status()
        except Exception as e:
            print(f"Error fetching details page {detail_url}: {e}")
            continue
            
        detail_soup = BeautifulSoup(r_detail.text, 'html.parser')
        
        # Find tables on page
        tables = detail_soup.find_all('table')
        print(f"Found {len(tables)} tables on details page.")
        
        for idx, table in enumerate(tables):
            # Check if this table is planned
            if is_table_planned(table):
                print(f"Table {idx+1} is in a 'Planned' section. Skipping.")
                continue
                
            # Find columns for "Satellite" and "COSPAR"
            # Look at first row or headers
            rows = table.find_all('tr')
            if not rows:
                continue
                
            first_row_cells = rows[0].find_all(['th', 'td'])
            headers_text = [c.get_text().strip().lower() for c in first_row_cells]
            
            sat_col_idx = -1
            cospar_col_idx = -1
            
            for col_idx, h in enumerate(headers_text):
                if 'satellite' in h:
                    sat_col_idx = col_idx
                elif 'cospar' in h or 'designator' in h:
                    cospar_col_idx = col_idx
                    
            if sat_col_idx == -1 or cospar_col_idx == -1:
                # Let's check headers in the second row as well (some tables have span headers)
                if len(rows) > 1:
                    second_row_cells = rows[1].find_all(['th', 'td'])
                    second_headers = [c.get_text().strip().lower() for c in second_row_cells]
                    for col_idx, h in enumerate(second_headers):
                        if 'satellite' in h and sat_col_idx == -1:
                            sat_col_idx = col_idx
                        elif ('cospar' in h or 'designator' in h) and cospar_col_idx == -1:
                            cospar_col_idx = col_idx
                            
            if sat_col_idx == -1 or cospar_col_idx == -1:
                # Table does not contain the required headers
                continue
                
            print(f"Table {idx+1}: Identified columns -> Satellite index: {sat_col_idx}, COSPAR index: {cospar_col_idx}")
            
            # Now parse data rows
            for row in rows[1:]:
                cells = row.find_all(['td', 'th'])
                if len(cells) <= max(sat_col_idx, cospar_col_idx):
                    continue
                    
                sat_name = cells[sat_col_idx].get_text().strip()
                cospar_id = cells[cospar_col_idx].get_text().strip()
                
                # Clean up name/cospar
                sat_name = re.sub(r'\s+', ' ', sat_name).strip()
                cospar_id = re.sub(r'\s+', ' ', cospar_id).strip()
                
                # Check if it's a valid launched COSPAR
                if not is_valid_launched_cospar(cospar_id):
                    # Skip planned / invalid
                    continue
                    
                scraped_satellites.append({
                    "name": sat_name,
                    "cospar": cospar_id
                })
                
    print(f"\nScrape completed. Found {len(scraped_satellites)} launched satellites.")
    for sat in scraped_satellites:
        print(f" - {sat['name']} (COSPAR: {sat['cospar']})")
        
    if not scraped_satellites:
        print("No satellites to merge. Exiting.")
        return
        
    merge_data(scraped_satellites)

def merge_data(scraped_sats):
    print(f"\nLoading database from: {INSTRUMENT_MERGE}")
    if not os.path.exists(INSTRUMENT_MERGE):
        print(f"Error: Database file does not exist at {INSTRUMENT_MERGE}")
        return
        
    df = pd.read_excel(INSTRUMENT_MERGE)
    print(f"Existing database has {len(df)} rows.")
    
    # Extract lowercased existing fields for fast checking
    excel_names = df['Sat_Full_Name'].dropna().astype(str).str.strip().str.lower().tolist()
    excel_acronyms = df['Sat_Acronym'].dropna().astype(str).str.strip().str.lower().tolist()
    excel_cospars = df['International Designator'].dropna().astype(str).str.strip().str.lower().tolist()
    
    new_rows = []
    
    for sat in scraped_sats:
        name = sat['name']
        cospar = sat['cospar']
        
        name_lower = name.lower()
        cospar_lower = cospar.lower()
        
        name_exists = (name_lower in excel_names) or (name_lower in excel_acronyms)
        cospar_exists = (cospar_lower in excel_cospars)
        
        if name_exists or cospar_exists:
            print(f"Satellite '{name}' (COSPAR: {cospar}) already exists in database. Skipping.")
        else:
            print(f"Satellite '{name}' (COSPAR: {cospar}) does not exist. Appending to updates.")
            # Build new row matching the schema
            new_row = {col: None for col in df.columns}
            new_row['Merge_Source'] = 'Skyrocket'
            new_row['Sat_Full_Name'] = name
            new_row['International Designator'] = cospar
            new_rows.append(new_row)
            
    if not new_rows:
        print("All scraped satellites already exist in the database. No updates written.")
        return
        
    # Append to df
    df_new = pd.DataFrame(new_rows)
    df_updated = pd.concat([df, df_new], ignore_index=True)
    
    print(f"Saving updated database with {len(df_updated)} rows...")
    df_updated.to_excel(INSTRUMENT_MERGE, index=False)
    print("Done! Database successfully updated.")

if __name__ == "__main__":
    scrape_skyrocket()
