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
    d_o = row_o.get('parsed_launch')
    d_c = row_c.get('parsed_launch')
    
    if d_o and d_c and not pd.isna(d_o) and not pd.isna(d_c):
        days_diff = abs((d_o - d_c).days)
        if days_diff < 15: score += 0.5 # Same date (allow 15d window for timezones/shifts)
        elif days_diff > 365: score -= 0.5 # Different year is very suspicious
    
    # 2. Altitude Check
    a_o = row_o.get('parsed_alt')
    a_c = row_c.get('parsed_alt')
    
    if a_o and a_c and not pd.isna(a_o) and not pd.isna(a_c):
        if abs(a_o - a_c) < 50: score += 0.3 # Close altitude
        elif abs(a_o - a_c) > 300: score -= 0.3 # Major altitude difference
        
    # 3. Agency Check (Fuzzy)
    ag_o = str(row_o['Sat_Agency']).lower()
    ag_c = str(row_c['Mission Agencies']).lower()
    if ag_o in ag_c or ag_c in ag_o or difflib.SequenceMatcher(None, ag_o, ag_c).ratio() > 0.7:
        score += 0.2
    else:
        score -= 0.5 # Penalty for mismatched agencies
        
    return score

def extract_numbers(name):
    """Extract all numbers from a name, treating them as specific version identifiers."""
    # Find all digits, including those part of a string like N2-1
    return set(re.findall(r'\d+', name))

def have_conflicting_numbers(name1, name2):
    """Check if names contain different version/series numbers (Ultra-Strict)."""
    nums1 = extract_numbers(name1)
    nums2 = extract_numbers(name2)
    # If both have numbers, they must not CONTRADICT each other
    if nums1 and nums2:
        # Check for intersection. If they share a number, they are likely okay 
        # unless there's a different number that is a version (like 3 vs 4)
        common = nums1 & nums2
        if not common:
            return True # Totally different numbers
            
        # If they share a number but have other different numbers, 
        # we check if those differences are version-like (1-digit numbers)
        diff1 = nums1 - nums2
        diff2 = nums2 - nums1
        # If one has "3" and the other has "4", that's a conflict even if they share "123"
        for d in diff1 | diff2:
            if len(d) <= 2: # Likely a version/number identifier
                # If d is in one but a DIFFERENT small number is in the other, it's a conflict
                # This is tricky... usually if they share ANY version number, it's ok 
                # unless they have another number that is DIFFERENT.
                pass
        
    # Simplified Zero-Risk Logic:
    # If they have numbers, they must share the MOST IMPORTANT identifier.
    if nums1 and nums2:
        if not (nums1 & nums2): return True
        # If they share a number, we check for 'Meteor-M type' drift (N2-1 vs N2-3)
        # Check for single digits that differ
        d1 = {n for n in nums1 if len(n) == 1}
        d2 = {n for n in nums2 if len(n) == 1}
        if d1 and d2 and d1 != d2:
            return True

    # Also check for letter versioning (A vs B)
    letters1 = set(re.findall(r'\b[A-Da-d]\b', name1.upper()))
    letters2 = set(re.findall(r'\b[A-Da-d]\b', name2.upper()))
    if letters1 and letters2 and letters1 != letters2:
        return True
        
    return False

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
- Respond 'NO' if they belong to different constellations, different agencies, or DIFFERENT VERSIONS (e.g. 1 vs 2, A vs B). 
- If one name has a number/letter and the other has a DIFFERENT one, respond 'NO'.
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
    
    # DEDUPLICATION: Ensure source files don't have redundant rows for the same Sat/Inst
    df_oscar = df_oscar.drop_duplicates()
    df_ceos = df_ceos.drop_duplicates()
    
    unique_oscar = df_oscar[['Sat_Acronym', 'merge_key', 'Sat_Agency', 'Sat_Launch', 'Sat_Altitude']].drop_duplicates()
    unique_ceos = df_ceos[['Satellite Full Name', 'merge_key', 'Mission Agencies', 'Launch Date', 'Orbit Altitude']].drop_duplicates()

    print("Pre-parsing dates and altitudes for performance optimization...")
    unique_oscar['parsed_launch'] = unique_oscar['Sat_Launch'].apply(parse_date)
    unique_oscar['parsed_alt'] = unique_oscar['Sat_Altitude'].apply(extract_altitude)
    unique_ceos['parsed_launch'] = unique_ceos['Launch Date'].apply(parse_date)
    unique_ceos['parsed_alt'] = unique_ceos['Orbit Altitude'].apply(extract_altitude)

    mapping = {} 
    unmatched_ceos_list = list(unique_ceos.to_dict('records'))

    print("Optimizing search space...")
    # 1. Create a fast lookup for exact name matches
    ceos_lookup = {row['merge_key']: (idx, row['Satellite Full Name']) for idx, row in enumerate(unmatched_ceos_list)}
    
    # 2. Group CEOS by launch year for candidate filtering
    ceos_by_year = {}
    for idx, row in enumerate(unmatched_ceos_list):
        year = row['parsed_launch'].year if row['parsed_launch'] and not pd.isna(row['parsed_launch']) else None
        if year:
            ceos_by_year.setdefault(year, []).append(idx)

    processed_count = 0
    match_count = 0
    
    # Track which CEOS indices are matched
    handled_ceos_indices = set()

    for i, oscar_row in unique_oscar.iterrows():
        processed_count += 1
        if processed_count % 20 == 0:
            print(f" Progress: Processed {processed_count}/{len(unique_oscar)} missions... (Matches found: {match_count})")
            
        o_name = oscar_row['Sat_Acronym']
        o_key = oscar_row['merge_key']
        o_year = oscar_row['parsed_launch'].year if oscar_row['parsed_launch'] and not pd.isna(oscar_row['parsed_launch']) else None
        
        # --- PHASE 1: EXACT MATCH ---
        if o_key in ceos_lookup:
            c_idx, c_name = ceos_lookup[o_key]
            if c_idx not in handled_ceos_indices:
                mapping[o_name] = c_name
                handled_ceos_indices.add(c_idx)
                match_count += 1
                continue

        # --- PHASE 2: FILTERED FUZZY MATCH ---
        # Only check CEOS missions launched in the same year (+/- 1 year) or with no date
        candidates = []
        if o_year:
            for y in [o_year - 1, o_year, o_year + 1]:
                candidates.extend(ceos_by_year.get(y, []))
        
        # Add CEOS missions with no date as fallback candidates
        candidates.extend([idx for idx, row in enumerate(unmatched_ceos_list) if not row['parsed_launch'] or pd.isna(row['parsed_launch'])])
        
        # De-duplicate candidates
        candidate_indices = set(candidates)
        
        best_match = None
        best_score = 0
        
        for j in candidate_indices:
            if j in handled_ceos_indices: continue
            
            c_row = unmatched_ceos_list[j]
            c_name = c_row['Satellite Full Name']
            c_key = c_row['merge_key']
            
            # Quick check: is the acronym inside the full name?
            if o_key and o_key in c_key:
                similarity = 0.95
            # ULTRA-STRICT: Check for numeric version conflicts first
            if have_conflicting_numbers(o_name, c_name):
                continue

            similarity = difflib.SequenceMatcher(None, o_key, c_key).ratio()
            
            if similarity < 0.4: continue # Too different
            
            meta_score = is_strict_metadata_match(oscar_row, c_row)
            
            # CASE A: Strong Match (No LLM needed)
            if (similarity > 0.9 and meta_score >= 0.7):
                best_match = (j, c_name)
                break # Found a solid match
                
            # CASE B: Ambiguous (Consult LLM)
            elif (similarity > 0.55 and meta_score >= 0.5):
                print(f"   [LLM Check] {o_name} vs {c_name}...")
                if ask_ollama(o_name, c_name, oscar_row['Sat_Agency'], c_row['Mission Agencies'], 
                              oscar_row['Sat_Launch'], c_row['Launch Date'], 
                              oscar_row['Sat_Altitude'], c_row['Orbit Altitude']):
                    best_match = (j, c_name)
                    break
        
        if best_match:
            mapping[o_name] = best_match[1]
            handled_ceos_indices.add(best_match[0])
            match_count += 1
                    
    # Re-use the merge logic from previous version...
    df_oscar['ceos_mapped_name'] = df_oscar['Sat_Acronym'].map(mapping)
    
    print("Mapping instruments to avoid combinatorial explosion...")
    df_ceos['ceos_mapped_instrument'] = None
    df_oscar['oscar_mapped_instrument'] = df_oscar.get('Inst_Acronym', pd.Series(dtype=str)).fillna(df_oscar.get('Inst_Full_Name', ''))
    
    total_inst = len(df_ceos)
    for idx, (i, c_row) in enumerate(df_ceos.iterrows()):
        if idx % 50 == 0:
            print(f" Progress: Mapping instruments {idx}/{total_inst}...")
        c_sat = c_row.get('Satellite Full Name', '')
        c_inst = str(c_row.get('Instrument Full Name', ''))
        if not c_inst or c_inst == 'nan' or pd.isna(c_sat):
            continue
            
        o_rows = df_oscar[df_oscar['ceos_mapped_name'] == c_sat]
        if o_rows.empty:
            continue
            
        o_insts = o_rows['oscar_mapped_instrument'].dropna().unique()
        best_match = None
        best_score = 0
        for o_inst in o_insts:
            o_inst_str = str(o_inst)
            if not o_inst_str or o_inst_str == 'nan': continue
            
            # ULTRA-STRICT: Check for numeric version conflicts in instruments
            if have_conflicting_numbers(c_inst, o_inst_str):
                continue

            score = difflib.SequenceMatcher(None, c_inst.lower(), o_inst_str.lower()).ratio()
            if c_inst.lower() in o_inst_str.lower() or o_inst_str.lower() in c_inst.lower():
                score += 0.3
                
            if score > best_score:
                best_score = score
                best_match = o_inst
                
        if best_score > 0.8: # Raised from 0.5 for absolute strictness
            df_ceos.at[i, 'ceos_mapped_instrument'] = best_match

    # Fill unmapped instruments with dummy keys to prevent NaN-NaN cross joins
    df_ceos['ceos_mapped_instrument'] = df_ceos['ceos_mapped_instrument'].fillna(('ceos_dummy_' + df_ceos.index.astype(str)).to_series())
    df_oscar['oscar_mapped_instrument'] = df_oscar['oscar_mapped_instrument'].replace('', pd.NA)
    df_oscar['oscar_mapped_instrument'] = df_oscar['oscar_mapped_instrument'].fillna(('oscar_dummy_' + df_oscar.index.astype(str)).to_series())

    # Reverted aggregation to preserve detailed instrument modes (Option B)
    merged = pd.merge(df_ceos, df_oscar, 
                      left_on=['Satellite Full Name', 'ceos_mapped_instrument'], 
                      right_on=['ceos_mapped_name', 'oscar_mapped_instrument'], 
                      how='outer', suffixes=('_ceos', '_oscar'))
    
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

    merged.drop(columns=['merge_key', 'ceos_mapped_name', 'merge_key_oscar', 'merge_key_ceos', 'ceos_mapped_instrument', 'oscar_mapped_instrument'], inplace=True, errors='ignore')

    # Reorder columns: Names -> Basic Details -> Instrument Data/Others
    names_cols = ['Sat_Full_Name', 'Sat_Acronym']
    basic_cols = ['Sat_Agency', 'Sat_Status', 'Sat_Launch', 'Sat_EOL', 'Sat_Altitude', 'NORAD Catalog #', 'International Designator', 'Sat_URL']
    
    all_cols = list(merged.columns)
    final_cols = []
    for c in names_cols:
        if c in all_cols:
            final_cols.append(c)
            all_cols.remove(c)
    for c in basic_cols:
        if c in all_cols:
            final_cols.append(c)
            all_cols.remove(c)
            
    final_cols.extend(all_cols)
    merged = merged[final_cols]

    # FINAL DEDUPLICATION: Remove any duplicates created during the outer join 
    # based on the main identifying columns
    merged.drop_duplicates(inplace=True)
    
    # Remove rows where crucial names are missing
    merged.dropna(subset=['Sat_Full_Name'], inplace=True)

    merged.to_excel(output_file, index=False)
    print(f"Strict Hybrid Integration complete! Result saved to {output_file}")

if __name__ == "__main__":
    combine_hybrid_strict('oscar_satellite_data_full_perfection.xlsx', 'satellite_data_full.xlsx', 'combined_satellite_data_strict.xlsx')
