import pandas as pd
import numpy as np
import re
import difflib
import requests
import json
import os
from datetime import datetime
from dateutil import parser
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# --- CONFIGURATION ---
INPUT_CEOS = "clean_code/results/ceos_standardized.xlsx"
INPUT_OSCAR = "clean_code/results/oscar_standardized.xlsx"
OUTPUT_FILE = "clean_code/results/merged_satellite_data_complete.xlsx"

OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "llama3.2:1b"

# --- HELPERS ---

def has_gpu():
    """
    Checks if Ollama has access to a GPU.
    Since we can't easily check torch in this venv, we probe system info or assume Ollama handles it.
    """
    try:
        # On macOS, check for Metal/Apple Silicon. 
        # For simplicity, we'll check if we are on Darwin
        import platform
        return platform.system() == "Darwin" 
    except:
        return False

def normalize_name(name):
    if not isinstance(name, str) or pd.isna(name): return ""
    # Remove version indicators/numbers etc for candidate search
    name = re.sub(r'\(.*?\)', '', name)
    name = re.sub(r'\bMission\b', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\bInstrument\b', '', name, flags=re.IGNORECASE)
    # Remove all non-alphanumeric for very aggressive comparison
    return re.sub(r'[^a-z0-9]', '', name.lower())

def parse_date(date_str):
    if pd.isna(date_str) or not str(date_str).strip() or str(date_str).lower() == 'n/a': return None
    try:
        return parser.parse(str(date_str), fuzzy=True)
    except:
        return None

def extract_altitude(alt_str):
    if pd.isna(alt_str) or not str(alt_str).strip() or str(alt_str).lower() == 'n/a': return None
    match = re.search(r'(\d+)', str(alt_str).replace(',', ''))
    return int(match.group(1)) if match else None

def extract_numbers(name):
    return set(re.findall(r'\d+', str(name)))

def have_conflicting_numbers(name1, name2):
    nums1 = extract_numbers(name1)
    nums2 = extract_numbers(name2)
    if nums1 and nums2:
        if not (nums1 & nums2): return True # No common numbers
        # Check for specific version differences (e.g., Sat-1 vs Sat-2)
        d1 = {n for n in nums1 if len(n) == 1}
        d2 = {n for n in nums2 if len(n) == 1}
        if d1 and d2 and d1 != d2:
            return True
    
    # Check for letter versions (A vs B)
    letters1 = set(re.findall(r'\b[A-Da-d]\b', str(name1).upper()))
    letters2 = set(re.findall(r'\b[A-Da-d]\b', str(name2).upper()))
    if letters1 and letters2 and letters1 != letters2:
        return True
    return False

def ask_llm_verification(o_row, c_row):
    """
    Verifies if two satellite missions are the same using Local LLM.
    """
    prompt = f"""Compare these two satellites and say if they are the SAME physical spacecraft.
OSCAR: {o_row['Sat_Acronym']} ({o_row['Sat_Agency']}) Launched: {o_row['Sat_Launch']}
CEOS: {c_row['Sat_Full_Name']} ({c_row['Sat_Agency']}) Launched: {c_row['Sat_Launch']}

Rules:
1. 'Sentinel-1A' and 'Sentinel-1B' are DIFFERENT.
2. If the launch year is the same and names are similar, it is likely the SAME.
3. Reply 'YES' or 'NO'.

Output:"""
    try:
        data = {"model": OLLAMA_MODEL, "messages": [{"role": "user", "content": prompt}], "stream": False, "options": {"temperature": 0}}
        res = requests.post(OLLAMA_URL, json=data, timeout=15)
        response_text = res.json()['message']['content'].strip().upper()
        return "YES" in response_text
    except Exception as e:
        return False

def merge_records(oscar_part, ceos_part):
    """
    Merges two records into one, following a smart trust hierarchy:
    - Orbit/Altitude: Prefer OSCAR (usually more specific)
    - Instrument Specs: Prefer the more specific/informative value
    - Dates: Prefer the most specific string (e.g., full date over year)
    - Agencies: Combine unique agencies from both sources
    """
    # Start with CEOS as base and update with OSCAR to preserve OSCAR's mode-specific data
    new_row = ceos_part.copy()
    
    for key, o_val in oscar_part.items():
        c_val = ceos_part.get(key)
        
        # If OSCAR is effectively empty, we keep CEOS's value (which is already in new_row)
        if pd.isna(o_val) or str(o_val).lower() in ['n/a', 'nan', '']:
            continue
            
        # If CEOS is empty but OSCAR has data, take OSCAR
        if pd.isna(c_val) or str(c_val).lower() in ['n/a', 'nan', '']:
            new_row[key] = o_val
            continue
            
        # If both have data, apply field-specific merging
        if key == 'Sat_Agency':
            # Combine unique agencies
            ag_o = [s.strip() for s in str(o_val).split('/') if s.strip()]
            ag_c = [s.strip() for s in str(c_val).split('/') if s.strip()]
            combined = list(dict.fromkeys(ag_o + ag_c))
            new_row[key] = " / ".join(combined)
            
        elif key in ['Sat_Launch', 'Sat_EOL']:
            # Prefer the longer/more specific date string
            if len(str(o_val)) >= len(str(c_val)):
                new_row[key] = o_val
            else:
                new_row[key] = c_val
                
        elif key == 'Sat_Altitude':
            # Prefer OSCAR for altitude as it's often more precise in their DB
            new_row[key] = o_val
            
        elif key in ['Inst_Resolution', 'Inst_Swath', 'Inst_Accuracy']:
            # For instrument modes, OSCAR's value is what makes the row unique, so it MUST win
            new_row[key] = o_val
            
        else:
            # For other fields, OSCAR normally wins as it's the primary driver of the merged row count
            new_row[key] = o_val
    
    new_row['Merge_Source'] = "OSCAR+CEOS"
    return new_row

def main():
    print(f"--- Starting Advanced Parallel Merge ---")
    print(f"Device capability check: {'GPU found' if has_gpu() else 'CPU only'} (Ollama will auto-manage)")

    if not os.path.exists(INPUT_CEOS) or not os.path.exists(INPUT_OSCAR):
        print("Error: Input files missing.")
        return

    df_ceos = pd.read_excel(INPUT_CEOS)
    df_oscar = pd.read_excel(INPUT_OSCAR)

    # 1. Pre-processing
    df_ceos['merged_flag'] = False
    df_oscar['merged_flag'] = False
    
    # Harmonize launch keys for comparison
    df_ceos['parsed_launch'] = df_ceos['Sat_Launch'].apply(parse_date)
    df_oscar['parsed_launch'] = df_oscar['Sat_Launch'].apply(parse_date)
    
    # Prep merge keys
    df_ceos['norm_sat'] = df_ceos['Sat_Full_Name'].apply(normalize_name)
    df_oscar['norm_sat'] = df_oscar['Sat_Acronym'].apply(normalize_name)
    df_ceos['norm_inst'] = df_ceos['Inst_Full_Name'].apply(normalize_name)
    df_oscar['norm_inst'] = df_oscar['Inst_Full_Name'].apply(normalize_name)

    # Cache for LLM results: (norm_oscar_sat_key, norm_ceos_sat_key) -> bool
    llm_cache = {}
    cache_lock = threading.Lock()
    merged_data = []

    # Get unique satellite definitions based on name/launch
    unique_o_sats = df_oscar[['Sat_Acronym', 'Sat_Launch', 'norm_sat', 'parsed_launch']].drop_duplicates()
    # Add back other fields for the LLM (taking first occurrence)
    unique_o_sats = unique_o_sats.merge(df_oscar[['Sat_Acronym', 'Sat_Agency', 'Sat_Altitude']].drop_duplicates('Sat_Acronym'), on='Sat_Acronym', how='left').to_dict('records')
    
    unique_c_sats = df_ceos[['Sat_Full_Name', 'Sat_Launch', 'norm_sat', 'parsed_launch']].drop_duplicates()
    unique_c_sats = unique_c_sats.merge(df_ceos[['Sat_Full_Name', 'Sat_Agency', 'Sat_Altitude']].drop_duplicates('Sat_Full_Name'), on='Sat_Full_Name', how='left').to_dict('records')

    print(f"Identifying potential satellite matches...")
    potential_pairs = []
    verified_matches = []
    
    for o_sat in unique_o_sats:
        o_name = o_sat['norm_sat']
        o_acr = o_sat['Sat_Acronym'].lower()
        o_year = o_sat['parsed_launch'].year if o_sat['parsed_launch'] else None
        
        for c_sat in unique_c_sats:
            c_name = c_sat['norm_sat']
            c_full = c_sat['Sat_Full_Name'].lower()
            c_year = c_sat['parsed_launch'].year if c_sat['parsed_launch'] else None
            
            # Fast filter
            year_match = False
            if o_year and c_year:
                if abs(o_year - c_year) <= 1: year_match = True
            elif not o_year or not c_year:
                year_match = True # Assume possible if one is missing
            
            if not year_match: continue
            
            # If names are identical or very clear overlap, skip LLM
            if o_acr == c_full or o_acr == c_name or o_name == c_name:
                verified_matches.append((o_sat['Sat_Acronym'], c_sat['Sat_Full_Name']))
                continue
                
            similarity = difflib.SequenceMatcher(None, o_name, c_name).ratio()
            if similarity < 0.7 and not (o_acr and o_acr in c_full): continue
            
            if have_conflicting_numbers(o_sat['Sat_Acronym'], c_sat['Sat_Full_Name']): continue
            
            potential_pairs.append((o_sat, c_sat))

    print(f"Skipped LLM for {len(verified_matches)} obvious matches.")
    print(f"Verifying {len(potential_pairs)} complex matches using LLM...")
    
    # verified_matches already contains obvious matches, we just add llm ones to it
    def check_pair(pair):
        o_sat, c_sat = pair
        # Use simpler keys for cache
        cache_key = (o_sat['Sat_Acronym'], c_sat['Sat_Full_Name'])
        with cache_lock:
            if cache_key in llm_cache:
                return cache_key, llm_cache[cache_key]
        
        result = ask_llm_verification(o_sat, c_sat)
        with cache_lock:
            llm_cache[cache_key] = result
        return cache_key, result

    # Using ThreadPoolExecutor for I/O bound LLM calls
    # Max workers balances speed vs Ollama capacity
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(check_pair, pair): pair for pair in potential_pairs}
        for i, future in enumerate(as_completed(futures)):
            if i % 50 == 0:
                print(f"  LLM Verification Progress: {i}/{len(potential_pairs)}...")
            key, is_match = future.result()
            if is_match:
                verified_matches.append(key)

    # Convert to set for fast lookup - use normalized names for the key
    verified_norm_set = set()
    for o_raw, c_raw in verified_matches:
        verified_norm_set.add((normalize_name(o_raw), normalize_name(c_raw)))

    print(f"Final verified satellite pairs: {len(verified_norm_set)}")

    print("Executing final data merge...")
    # Track which rows have been successfully merged to avoid duplicate source rows
    oscar_merged_indices = set()
    ceos_merged_indices = set()

    for i, o_row in df_oscar.iterrows():
        o_sat_norm = o_row['norm_sat']
        o_inst_acr = str(o_row['Inst_Acronym']).lower().strip() if pd.notna(o_row['Inst_Acronym']) else ""
        o_inst_full = str(o_row['Inst_Full_Name']).lower().strip() if pd.notna(o_row['Inst_Full_Name']) else ""
        
        # Try to find a match in ALL CEOS rows (not just unmerged ones)
        # We calculate a match score to pick the single best CEOS row for this OSCAR mode
        best_match_j = -1
        best_match_score = -1
        
        for j, c_row in df_ceos.iterrows():
            c_sat_norm = c_row['norm_sat']
            
            if (o_sat_norm, c_sat_norm) in verified_norm_set:
                # Same satellite, check instrument
                c_inst_acr = str(c_row['Inst_Acronym']).lower().strip() if pd.notna(c_row['Inst_Acronym']) else ""
                c_inst_full = str(c_row['Inst_Full_Name']).lower().strip() if pd.notna(c_row['Inst_Full_Name']) else ""
                
                # Calculation of instrument match score
                current_score = 0
                
                # 1. Acronym to Acronym (Highest Priority)
                if o_inst_acr and c_inst_acr and o_inst_acr == c_inst_acr:
                    current_score = 100
                # 2. Acronym to Full Name
                elif o_inst_acr and o_inst_acr in c_inst_full:
                    current_score = 80
                elif c_inst_acr and c_inst_acr in o_inst_full:
                    current_score = 80
                # 3. Fuzzy match on full names
                elif o_inst_full and c_inst_full:
                    sim = difflib.SequenceMatcher(None, o_inst_full, c_inst_full).ratio()
                    if sim > 0.8:
                        current_score = 60 + (sim * 20)
                
                if current_score > best_match_score:
                    best_match_score = current_score
                    best_match_j = j

        if best_match_j != -1 and best_match_score >= 60:
            merged_row = merge_records(o_row.to_dict(), df_ceos.iloc[best_match_j].to_dict())
            merged_data.append(merged_row)
            oscar_merged_indices.add(i)
            # We flag this CEOS row as "partially used" to prevent it being added as "CEOS-Only" later
            ceos_merged_indices.add(best_match_j)

    # Final collection: 
    # 1. All OSCAR that didn't match
    for i, o_row in df_oscar.iterrows():
        if i not in oscar_merged_indices:
            row = o_row.to_dict()
            row['Merge_Source'] = "OSCAR-Only"
            merged_data.append(row)

    # 2. All CEOS that didn't match
    for j, c_row in df_ceos.iterrows():
        if j not in ceos_merged_indices:
            row = c_row.to_dict()
            row['Merge_Source'] = "CEOS-Only"
            merged_data.append(row)

    # 3. Save
    df_merged = pd.DataFrame(merged_data)
    
    # Remove internal helper columns before saving
    cols_to_drop = ['merged_flag', 'parsed_launch', 'norm_sat', 'norm_inst']
    df_merged = df_merged.drop(columns=[c for c in cols_to_drop if c in df_merged.columns])
    
    # Ensure correct column ordering (Names first)
    cols = df_merged.columns.tolist()
    priority_cols = ['Merge_Source', 'Sat_Full_Name', 'Sat_Acronym', 'Inst_Full_Name', 'Inst_Acronym']
    other_cols = [c for c in cols if c not in priority_cols]
    df_merged = df_merged[priority_cols + other_cols]

    print(f"Merge Complete! Total Records: {len(df_merged)}")
    print(f"- Matches (including multi-mode): {len(oscar_merged_indices)}")
    print(f"- OSCAR Only: {len(df_oscar) - len(oscar_merged_indices)}")
    print(f"- CEOS Only: {len(df_ceos) - len(ceos_merged_indices)}")

    df_merged.to_excel(OUTPUT_FILE, index=False)
    print(f"File saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
