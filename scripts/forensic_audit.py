import pandas as pd
import numpy as np
import re
import difflib
from dateutil import parser

def normalize_name(name):
    if not isinstance(name, str): return ""
    name = re.sub(r'\(.*?\)', '', name)
    name = re.sub(r'\bMission\b', '', name, flags=re.IGNORECASE)
    name = re.sub(r'[^\w\s-]', '', name)
    return ' '.join(name.lower().split())

def parse_date(date_str):
    if pd.isna(date_str) or not str(date_str).strip(): return None
    try: return parser.parse(str(date_str), fuzzy=True)
    except: return None

def extract_numbers(name):
    return set(re.findall(r'\d+', name))

def have_conflicting_numbers(name1, name2):
    """Check if names contain different version/series numbers (Ultra-Strict)."""
    nums1 = extract_numbers(name1)
    nums2 = extract_numbers(name2)
    # If both have numbers, they must have the EXACT SAME SET of numbers
    if nums1 and nums2:
        if nums1 != nums2:
            return True
    
    # Also check for letter versioning (A vs B)
    letters1 = set(re.findall(r'\b[A-Da-d]\b', name1.upper()))
    letters2 = set(re.findall(r'\b[A-Da-d]\b', name2.upper()))
    if letters1 and letters2 and letters1 != letters2:
        return True
        
    return False

def deep_audit(oscar_file, ceos_file, merged_file):
    print("Initiating Deep Forensic Audit...")
    df_oscar = pd.read_excel(oscar_file)
    df_ceos = pd.read_excel(ceos_file)
    df_merged = pd.read_excel(merged_file)

    # We need to find which CEOS rows were merged with which OSCAR rows
    # The output file unfortunately lost the join keys. 
    # For a forensic audit, we'll re-run the logic in a "dry run" mode and list every match.
    
    # Pre-process
    df_oscar['merge_key'] = df_oscar['Sat_Acronym'].apply(normalize_name)
    df_ceos['merge_key'] = df_ceos['Satellite Full Name'].apply(normalize_name)
    
    unique_oscar = df_oscar[['Sat_Acronym', 'merge_key', 'Sat_Agency', 'Sat_Launch', 'Sat_Altitude']].drop_duplicates()
    unique_ceos = df_ceos[['Satellite Full Name', 'merge_key', 'Mission Agencies', 'Launch Date', 'Orbit Altitude']].drop_duplicates()
    
    unique_oscar['parsed_launch'] = unique_oscar['Sat_Launch'].apply(parse_date)
    unique_ceos['parsed_launch'] = unique_ceos['Launch Date'].apply(parse_date)
    
    matches_to_verify = []
    
    # Re-run the core logic to identify what was matched
    for _, o_row in unique_oscar.iterrows():
        o_name = o_row['Sat_Acronym']
        o_key = o_row['merge_key']
        o_date = o_row['parsed_launch']
        
        for _, c_row in unique_ceos.iterrows():
            c_name = c_row['Satellite Full Name']
            c_key = c_row['merge_key']
            c_date = c_row['parsed_launch']
            
            # Use the Ultra-Strict logic
            if have_conflicting_numbers(o_name, c_name): continue
            
            similarity = difflib.SequenceMatcher(None, o_key, c_key).ratio()
            
            # Check Agency mismatch
            ag_o = str(o_row['Sat_Agency']).lower()
            ag_c = str(c_row['Mission Agencies']).lower()
            agency_match = (ag_o in ag_c or ag_c in ag_o)
            
            # Check Date proximity
            date_match = False
            if o_date and c_date:
                if abs((o_date - c_date).days) <= 15:
                    date_match = True

            # If it's a match that would have been accepted
            if (similarity > 0.9 or (similarity > 0.6 and agency_match and date_match)):
                matches_to_verify.append({
                    'OSCAR': o_name,
                    'CEOS': c_name,
                    'Similarity': similarity,
                    'OSCAR_Agency': o_row['Sat_Agency'],
                    'CEOS_Agency': c_row['Mission Agencies'],
                    'OSCAR_Launch': o_row['Sat_Launch'],
                    'CEOS_Launch': c_row['Launch Date']
                })

    audit_df = pd.DataFrame(matches_to_verify)
    
    # 1. Check for Agency conflicts
    print(f"\nScanning {len(audit_df)} potential matches for conflicts...")
    
    # Rule: If Agency is totally different, it's an error.
    def check_agency_error(row):
        a1 = str(row['OSCAR_Agency']).lower()
        a2 = str(row['CEOS_Agency']).lower()
        # Common aliases
        if 'nasa' in a1 and 'nasa' in a2: return False
        if 'esa' in a1 and 'esa' in a2: return False
        if 'isro' in a1 and 'isro' in a2: return False
        if 'jaxa' in a1 and 'jaxa' in a2: return False
        if a1 in a2 or a2 in a1: return False
        return True

    agency_conflicts = audit_df[audit_df.apply(check_agency_error, axis=1)]
    
    # 2. Check for Name conflict (versioning)
    def check_version_error(row):
        n1 = row['OSCAR']
        n2 = row['CEOS']
        # Already handled by have_conflicting_numbers but let's be paranoid
        # Check for A vs B or 1 vs 2
        for v in ['A', 'B', 'C', 'D', '1', '2', '3', '4', '5']:
            if (f"-{v}" in n1 and f"-{v}" not in n2 and any(f"-{other}" in n2 for other in ['A','B','C','D','1','2','3','4','5'] if other != v)):
                return True
        return False

    version_conflicts = audit_df[audit_df.apply(check_version_error, axis=1)]

    print("\n--- AUDIT RESULTS ---")
    if agency_conflicts.empty and version_conflicts.empty:
        print("✅ SUCCESS: No logical conflicts found in merged pairs.")
    else:
        if not agency_conflicts.empty:
            print(f"❌ WARNING: {len(agency_conflicts)} Agency mismatches found!")
            print(agency_conflicts[['OSCAR', 'CEOS', 'OSCAR_Agency', 'CEOS_Agency']])
        if not version_conflicts.empty:
            print(f"❌ WARNING: {len(version_conflicts)} Version mismatches found!")
            print(version_conflicts[['OSCAR', 'CEOS']])

if __name__ == "__main__":
    deep_audit('oscar_satellite_data_full_perfection.xlsx', 'satellite_data_full.xlsx', 'combined_satellite_data_strict.xlsx')
