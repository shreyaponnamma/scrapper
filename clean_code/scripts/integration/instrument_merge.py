"""
Instrument-Level Merge Script
-----------------------------
This script performs a condensed version of the satellite data merge, focusing on 
instrument-level metadata rather than specific instrument modes or technical specs.

It collapses multiple entries for the same instrument within the OSCAR dataset and 
matches them against CEOS instruments using satellite names and launch years, 
supported by LLM verification where necessary.
"""

import pandas as pd
import numpy as np
import re
import difflib
import requests
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dateutil import parser

# Import constants from config
from scripts.utils.config import (
    CEOS_PROCESSED,
    OSCAR_PROCESSED,
    INSTRUMENT_MERGE,
    OLLAMA_URL,
    OLLAMA_MODEL
)

# Columns to keep (excluding specific mode technical specs)
CORE_COLUMNS = [
    'Sat_Full_Name', 
    'Sat_Acronym', 
    'Sat_Agency', 
    'Sat_Status', 
    'Sat_Launch', 
    'Sat_EOL', 
    'Sat_Altitude', 
    'NORAD Catalog #', 
    'International Designator', 
    'Inst_Full_Name', 
    'Inst_Acronym'
]

# --- HELPERS ---

def normalize_name(name):
    """
    Normalizes satellite and instrument names for comparison.
    
    Args:
        name (str): The name to normalize.
        
    Returns:
        str: Normalized alphanumeric string.
    """
    if not isinstance(name, str) or pd.isna(name): return ""
    name = re.sub(r'\(.*?\)', '', name)
    name = re.sub(r'\bMission\b', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\bInstrument\b', '', name, flags=re.IGNORECASE)
    return re.sub(r'[^a-z0-9]', '', name.lower())

def parse_date(date_str):
    """Parses a date string into a datetime object."""
    if pd.isna(date_str) or not str(date_str).strip() or str(date_str).lower() == 'n/a': return None
    try:
        return parser.parse(str(date_str), fuzzy=True)
    except:
        return None

def ask_llm_verification(o_row, c_row):
    """
    Queries local LLM (Ollama) to verify satellite identity.
    
    Args:
        o_row (dict): OSCAR satellite data.
        c_row (dict): CEOS satellite data.
        
    Returns:
        bool: True if they are the same satellite.
    """
    prompt = f"""Compare these two satellites and say if they are the SAME physical spacecraft.
OSCAR: {o_row['Sat_Acronym']} ({o_row['Sat_Agency']}) Launched: {o_row['Sat_Launch']}
CEOS: {c_row['Sat_Full_Name']} ({c_row['Sat_Agency']}) Launched: {c_row['Sat_Launch']}

Rules:
1. 'Sentinel-1A' and 'Sentinel-1B' are DIFFERENT.
2. Reply 'YES' or 'NO'.

Output:"""
    try:
        data = {"model": OLLAMA_MODEL, "messages": [{"role": "user", "content": prompt}], "stream": False, "options": {"temperature": 0}}
        res = requests.post(OLLAMA_URL, json=data, timeout=15)
        response_text = res.json()['message']['content'].strip().upper()
        return "YES" in response_text
    except:
        return False

def merge_core_fields(oscar_part, ceos_part):
    """
    Merges matching records focusing only on core metadata fields.
    
    Args:
        oscar_part (dict): OSCAR data.
        ceos_part (dict): CEOS data.
        
    Returns:
        dict: Merged dictionary containing core metadata.
    """
    new_row = ceos_part.copy()
    
    for key in CORE_COLUMNS:
        o_val = oscar_part.get(key)
        c_val = ceos_part.get(key)
        
        if (pd.isna(c_val) or str(c_val).lower() in ['n/a', 'nan', '']) and not (pd.isna(o_val) or str(o_val).lower() in ['n/a', 'nan', '']):
            new_row[key] = o_val
            continue
            
        if key == 'Sat_Agency' and pd.notna(o_val) and pd.notna(c_val):
            ag_o = [s.strip() for s in str(o_val).split('/') if s.strip()]
            ag_c = [s.strip() for s in str(c_val).split('/') if s.strip()]
            combined = list(dict.fromkeys(ag_o + ag_c))
            new_row[key] = " / ".join(combined)
        elif key in ['Sat_Launch', 'Sat_EOL'] and pd.notna(o_val) and pd.notna(c_val):
            if len(str(o_val)) >= len(str(c_val)): new_row[key] = o_val
        elif key == 'Sat_Altitude' and pd.notna(o_val):
            new_row[key] = o_val
            
    new_row['Merge_Source'] = "OSCAR+CEOS"
    return new_row

def main():
    """
    Executes the instrument-level merge pipeline.
    1. Loads processed datasets.
    2. Collapses OSCAR modes to the instrument level.
    3. Identifies satellite matches using name and launch year filters.
    4. Verifies matches via LLM.
    5. Merges metadata for matched instruments.
    6. Saves the condensed instrument-level report.
    """
    print(f"--- Starting Instrument-Level Merge (No Modes) ---")
    if not os.path.exists(CEOS_PROCESSED) or not os.path.exists(OSCAR_PROCESSED):
        print("Error: Input files missing.")
        return

    df_ceos = pd.read_excel(CEOS_PROCESSED)
    df_oscar = pd.read_excel(OSCAR_PROCESSED)

    # 1. COLLAPSE OSCAR modes immediately to prevent mode-level duplicates
    print("Collapsing OSCAR modes...")
    df_oscar_collapsed = df_oscar.groupby(['Sat_Acronym', 'Inst_Full_Name'], as_index=False).first()

    # Pre-processing
    df_ceos['norm_sat'] = df_ceos['Sat_Full_Name'].apply(normalize_name)
    df_oscar_collapsed['norm_sat'] = df_oscar_collapsed['Sat_Acronym'].apply(normalize_name)
    df_ceos['parsed_launch'] = df_ceos['Sat_Launch'].apply(parse_date)
    df_oscar_collapsed['parsed_launch'] = df_oscar_collapsed['Sat_Launch'].apply(parse_date)

    llm_cache = {}
    cache_lock = threading.Lock()
    verified_matches = []

    unique_o_sats = df_oscar_collapsed[['Sat_Acronym', 'Sat_Launch', 'norm_sat', 'parsed_launch', 'Sat_Agency']].drop_duplicates('Sat_Acronym').to_dict('records')
    unique_c_sats = df_ceos[['Sat_Full_Name', 'Sat_Launch', 'norm_sat', 'parsed_launch', 'Sat_Agency']].drop_duplicates('Sat_Full_Name').to_dict('records')

    print("Checking satellite matches with LLM...")
    potential_pairs = []
    for o_sat in unique_o_sats:
        o_name = o_sat['norm_sat']
        o_acr = o_sat['Sat_Acronym'].lower()
        o_year = o_sat['parsed_launch'].year if o_sat['parsed_launch'] else None
        for c_sat in unique_c_sats:
            c_name = c_sat['norm_sat']
            c_year = c_sat['parsed_launch'].year if c_sat['parsed_launch'] else None
            
            if o_acr == c_name or o_name == c_name:
                verified_matches.append((o_sat['Sat_Acronym'], c_sat['Sat_Full_Name']))
                continue
                
            if o_year and c_year and abs(o_year - c_year) <= 1:
                potential_pairs.append((o_sat, c_sat))

    def check_pair(pair):
        o_sat, c_sat = pair
        cache_key = (o_sat['Sat_Acronym'], c_sat['Sat_Full_Name'])
        with cache_lock:
            if cache_key in llm_cache: return cache_key, llm_cache[cache_key]
        result = ask_llm_verification(o_sat, c_sat)
        with cache_lock: llm_cache[cache_key] = result
        return cache_key, result

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(check_pair, p): p for p in potential_pairs}
        for future in as_completed(futures):
            key, is_match = future.result()
            if is_match: verified_matches.append(key)

    match_set = set((normalize_name(o), normalize_name(c)) for o, c in verified_matches)
    
    merged_data = []
    oscar_indices_used = set()
    ceos_indices_used = set()

    print("Merging instrument rows...")
    for i, o_row in df_oscar_collapsed.iterrows():
        o_sat_norm = o_row['norm_sat']
        o_inst_acr = str(o_row['Inst_Acronym']).lower().strip() if pd.notna(o_row['Inst_Acronym']) else ""
        o_inst_full = str(o_row['Inst_Full_Name']).lower().strip() if pd.notna(o_row['Inst_Full_Name']) else ""
        
        best_j = -1
        best_score = -1
        for j, c_row in df_ceos.iterrows():
            if (o_sat_norm, c_row['norm_sat']) in match_set:
                c_inst_acr = str(c_row['Inst_Acronym']).lower().strip() if pd.notna(c_row['Inst_Acronym']) else ""
                c_inst_full = str(c_row['Inst_Full_Name']).lower().strip() if pd.notna(c_row['Inst_Full_Name']) else ""
                
                score = 0
                if o_inst_acr and c_inst_acr and o_inst_acr == c_inst_acr: score = 100
                elif o_inst_acr and o_inst_acr in c_inst_full: score = 80
                elif c_inst_acr and c_inst_acr in o_inst_full: score = 80
                elif o_inst_full and c_inst_full and difflib.SequenceMatcher(None, o_inst_full, c_inst_full).ratio() > 0.8: score = 70
                
                if score > best_score:
                    best_score = score
                    best_j = j
        
        if best_j != -1 and best_score >= 70:
            merged_row = merge_core_fields(o_row.to_dict(), df_ceos.iloc[best_j].to_dict())
            merged_data.append(merged_row)
            oscar_indices_used.add(i)
            ceos_indices_used.add(best_j)

    name_to_acr = {}
    acr_to_name = {}
    for o_acr, c_full in verified_matches:
        name_to_acr[c_full] = o_acr
        acr_to_name[o_acr] = c_full

    for i, o_row in df_oscar_collapsed.iterrows():
        if i not in oscar_indices_used:
            row = o_row.to_dict()
            row['Merge_Source'] = "OSCAR-Only"
            if pd.isna(row.get('Sat_Full_Name')) and row['Sat_Acronym'] in acr_to_name:
                row['Sat_Full_Name'] = acr_to_name[row['Sat_Acronym']]
            merged_data.append(row)

    for j, c_row in df_ceos.iterrows():
        if j not in ceos_indices_used:
            row = c_row.to_dict()
            row['Merge_Source'] = "CEOS-Only"
            if (pd.isna(row.get('Sat_Acronym')) or str(row.get('Sat_Acronym')).lower() == 'nan') and row['Sat_Full_Name'] in name_to_acr:
                row['Sat_Acronym'] = name_to_acr[row['Sat_Full_Name']]
            merged_data.append(row)

    df_final = pd.DataFrame(merged_data)
    
    print("Sorting and grouping results...")
    df_final['sort_sat'] = df_final['Sat_Acronym'].fillna(df_final['Sat_Full_Name'])
    df_final = df_final.sort_values(by=['sort_sat', 'Inst_Full_Name'], na_position='last')
    df_final = df_final.drop(columns=['sort_sat'])
    
    final_cols = ['Merge_Source'] + CORE_COLUMNS
    df_final = df_final[[c for c in final_cols if c in df_final.columns]]
    
    df_final.to_excel(INSTRUMENT_MERGE, index=False)
    print(f"Done! Saved {len(df_final)} instrument rows to {INSTRUMENT_MERGE}")

if __name__ == "__main__":
    main()
