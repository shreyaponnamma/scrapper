import pandas as pd
import numpy as np
import re
import difflib
import requests
import json
from datetime import datetime
from dateutil import parser

# --- SETTINGS ---
OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "llama3.2:1b"

def normalize_name(name):
    if not isinstance(name, str): return ""
    name = re.sub(r'\(.*?\)', '', name)
    name = re.sub(r'\bMission\b', '', name, flags=re.IGNORECASE)
    name = re.sub(r'[^\w\s-]', '', name)
    return ' '.join(name.lower().split())

def parse_date(date_str):
    """Robustly parse date strings."""
    if pd.isna(date_str) or not str(date_str).strip(): return None
    try:
        return parser.parse(str(date_str), fuzzy=True)
    except:
        return None

def extract_altitude(alt_str):
    """Normalize altitude to integer km."""
    if pd.isna(alt_str) or not str(alt_str).strip(): return None
    match = re.search(r'(\d+)', str(alt_str).replace(',', ''))
    return int(match.group(1)) if match else None

def is_strict_metadata_match(row_o, row_c):
    """
    Check if metadata (Agencies, Launch Date, Altitude) aligns sufficiently.
    Returns: (Match Score 0.0-1.0, Match Reason)
    """
    score = 0
    # 1. Date Check (Strongest indicator)
    d_o = parse_date(row_o['Sat_Launch'])
    d_c = parse_date(row_c['Launch Date'])
    if d_o and d_c:
        days_diff = abs((d_o - d_c).days)
        if days_diff < 15: score += 0.5 # Same date (allow 15d window for timezones/shifts)
        elif days_diff > 365: score -= 0.5 # Different year is very suspicious
    
    # 2. Altitude Check
    a_o = extract_altitude(row_o['Sat_Altitude'] if 'Sat_Altitude' in row_o else "")
    a_c = extract_altitude(row_c['Orbit Altitude'] if 'Orbit Altitude' in row_c else "")
    if a_o and a_c:
        if abs(a_o - a_c) < 50: score += 0.3 # Close altitude
        elif abs(a_o - a_c) > 300: score -= 0.3 # Major altitude difference
        
    # 3. Agency Check (Fuzzy)
    ag_o = str(row_o['Sat_Agency']).lower()
    ag_c = str(row_c['Mission Agencies']).lower()
    if ag_o in ag_c or ag_c in ag_o or difflib.SequenceMatcher(None, ag_o, ag_c).ratio() > 0.7:
        score += 0.2
        
    return score

def ask_ollama(name_oscar, name_ceos, agency_oscar, agency_ceos, date_oscar, date_ceos, alt_oscar, alt_ceos):
    prompt = f"""Task: Satellite Mission Verification
Is the mission in OSCAR exactly the same as the mission in CEOS?
    
OSCAR Details:
Name: {name_oscar} | Agency: {agency_oscar} | Launch: {date_oscar} | Alt: {alt_oscar}
    
CEOS Details:
Name: {name_ceos} | Agency: {agency_ceos} | Launch: {date_ceos} | Alt: {alt_ceos}
    
Rules: 
- Respond ONLY with 'YES' or 'NO'. 
- Respond 'YES' if they describe the same physical satellite/mission.
- Respond 'NO' if they belong to different constellations (e.g. A vs B) or different agencies.
Answer:"""
    try:
        data = {"model": OLLAMA_MODEL, "messages": [{"role": "user", "content": prompt}], "stream": False}
        res = requests.post(OLLAMA_URL, json=data, timeout=10)
        return "YES" in res.json()['message']['content'].strip().upper()
    except:
        return False

def combine_hybrid_strict(oscar_file, ceos_file, output_file):
    print(f"Strict Hybrid Fusion: {oscar_file} + {ceos_file}...")
    df_oscar = pd.read_excel(oscar_file)
    df_ceos = pd.read_excel(ceos_file)

    # Status Filtering
    forbidden = ['inactive', 'considered', 'planned', 'lost at launch', 'presumably inactive']
    df_oscar = df_oscar[~df_oscar['Sat_Status'].fillna('').str.lower().isin(forbidden)]
    df_ceos = df_ceos[~df_ceos['Mission Status'].fillna('').str.lower().isin(forbidden)]

    # Normalized keys
    df_oscar['merge_key'] = df_oscar['Sat_Acronym'].apply(normalize_name)
    df_ceos['merge_key'] = df_ceos['Satellite Full Name'].apply(normalize_name)
    
    unique_oscar = df_oscar[['Sat_Acronym', 'merge_key', 'Sat_Agency', 'Sat_Launch', 'Sat_Altitude']].drop_duplicates()
    unique_ceos = df_ceos[['Satellite Full Name', 'merge_key', 'Mission Agencies', 'Launch Date', 'Orbit Altitude']].drop_duplicates()

    mapping = {} 
    unmatched_ceos_list = list(unique_ceos.to_dict('records'))
    handled_ceos_indices = set()

    print(f"Analyzing {len(unique_oscar)} OSCAR entries for multi-field strict verification...")

    for i, oscar_row in unique_oscar.iterrows():
        o_name = oscar_row['Sat_Acronym']
        o_key = oscar_row['merge_key']
        
        found_match = False
        for j, c_row in enumerate(unmatched_ceos_list):
            if j in handled_ceos_indices: continue
            
            c_name = c_row['Satellite Full Name']
            c_key = c_row['merge_key']
            
            # 1. Similarity Level
            similarity = difflib.SequenceMatcher(None, o_key, c_key).ratio()
            
            # 2. Metadata Metadata Score
            meta_score = is_strict_metadata_match(oscar_row, c_row)
            
            # --- STRICT FUSION LOGIC ---
            # CASE A: Perfect Score (Name match + Date Match + Agency Match)
            if (similarity > 0.9 and meta_score >= 0.7):
                mapping[o_name] = c_name
                handled_ceos_indices.add(j)
                found_match = True
                break
                
            # CASE B: Ambiguous (Partial Name Match + Date/Altitude Match)
            elif (similarity > 0.55 and meta_score >= 0.5) or (similarity > 0.8):
                # Consult LLM for the "Final Tie-Breaker"
                if ask_ollama(o_name, c_name, oscar_row['Sat_Agency'], c_row['Mission Agencies'], 
                              oscar_row['Sat_Launch'], c_row['Launch Date'], 
                              oscar_row['Sat_Altitude'], c_row['Orbit Altitude']):
                    mapping[o_name] = c_name
                    handled_ceos_indices.add(j)
                    found_match = True
                    break
                    
    # Re-use the merge logic from previous version...
    df_oscar['ceos_mapped_name'] = df_oscar['Sat_Acronym'].map(mapping)
    merged = pd.merge(df_ceos, df_oscar, left_on=['Satellite Full Name'], right_on=['ceos_mapped_name'], how='outer', suffixes=('_ceos', '_oscar'))
    
    consolidated_cols = {'Satellite Full Name': 'Sat_Full_Name','Mission Agencies': 'Sat_Agency','Mission Status': 'Sat_Status','Launch Date': 'Sat_Launch','EOL Date': 'Sat_EOL','Orbit Altitude': 'Sat_Altitude','Instrument Full Name': 'Inst_Full_Name','Resolution': 'Inst_Resolution'}
    for c_col, o_col in consolidated_cols.items():
        src_ceos = f"{c_col}_ceos" if f"{c_col}_ceos" in merged.columns else c_col
        src_oscar = f"{o_col}_oscar" if f"{o_col}_oscar" in merged.columns else o_col
        if src_ceos in merged.columns and src_oscar in merged.columns:
            merged[o_col] = merged[src_ceos].combine_first(merged[src_oscar])
            if src_ceos != o_col: merged.drop(columns=[src_ceos], inplace=True)
            if src_oscar != o_col: merged.drop(columns=[src_oscar], inplace=True)
        elif src_ceos in merged.columns: merged.rename(columns={src_ceos: o_col}, inplace=True)
        elif src_oscar in merged.columns: merged.rename(columns={src_oscar: o_col}, inplace=True)

    merged.drop(columns=['merge_key', 'ceos_mapped_name', 'merge_key_oscar', 'merge_key_ceos'], inplace=True, errors='ignore')
    merged.to_excel(output_file, index=False)
    print(f"Strict Hybrid Integration complete! Result saved to {output_file}")

if __name__ == "__main__":
    combine_hybrid_strict('oscar_satellite_data_full_perfection.xlsx', 'satellite_data_full.xlsx', 'combined_satellite_data_strict.xlsx')
