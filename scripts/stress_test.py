import pandas as pd
import numpy as np
import re
from dateutil import parser

def parse_date(date_str):
    if pd.isna(date_str) or not str(date_str).strip(): return None
    try: return parser.parse(str(date_str), fuzzy=True)
    except: return None

def stress_test(merged_file, oscar_file, ceos_file):
    print("--- INITIATING MAXIMUM STRESS TEST (V2) ---")
    df = pd.read_excel(merged_file)
    df_oscar = pd.read_excel(oscar_file)
    df_ceos = pd.read_excel(ceos_file)

    # 1. Math Check
    total_rows = len(df)
    
    # Sat_URL is unique to OSCAR. 
    # NORAD Catalog # or International Designator or presence in CEOS original subset
    # Let's check for columns that were populated from CEOS
    has_oscar = df['Sat_URL'].notnull()
    # If it was in CEOS, it will have a 'Sat_Full_Name' that matches one of the CEOS names
    ceos_names = set(df_ceos['Satellite Full Name'].unique())
    has_ceos = df['Sat_Full_Name'].isin(ceos_names)
    
    both_mask = has_oscar & has_ceos
    both = both_mask.sum()
    only_oscar = (has_oscar & ~has_ceos).sum()
    only_ceos = (has_ceos & ~has_oscar).sum()
    
    print(f"Total Combined Records: {total_rows}")
    print(f"  Merged (Both Sources): {both}")
    print(f"  Unique to OSCAR: {only_oscar}")
    print(f"  Unique to CEOS: {only_ceos}")

    # 2. CRITICAL DATE CONFLICT CHECK
    print("\n--- CHECKING FOR TEMPORAL CONFLICTS ---")
    oscar_lookup = df_oscar.groupby('Sat_Acronym')['Sat_Launch'].first().to_dict()
    ceos_lookup = df_ceos.groupby('Satellite Full Name')['Launch Date'].first().to_dict()

    merged_rows = df[both_mask]
    error_count = 0
    for idx, row in merged_rows.iterrows():
        o_acr = row['Sat_Acronym']
        c_full = row['Sat_Full_Name']
        
        o_date_str = oscar_lookup.get(o_acr)
        c_date_str = ceos_lookup.get(c_full)
        
        o_date = parse_date(o_date_str)
        c_date = parse_date(c_date_str)
        
        if o_date and c_date:
            diff = abs((o_date - c_date).days)
            if diff > 15: # Strict window
                print(f"❌ CRITICAL CONFLICT: {o_acr} (OSCAR) joined with {c_full} (CEOS)")
                print(f"   OSCAR Launch: {o_date_str} | CEOS Launch: {c_date_str}")
                print(f"   Reason: Date discrepancy of {diff} days exceeds strict tolerance.")
                error_count += 1
                
    if error_count == 0:
        print("✅ SUCCESS: Zero temporal conflicts found in merged records.")
    else:
        print(f"⚠️ TOTAL CRITICAL ERRORS FOUND: {error_count}")

    # 3. VERSION DRIFT CHECK (Paranoid Mode)
    print("\n--- VERSION DRIFT CHECK ---")
    version_errors = 0
    for idx, row in merged_rows.iterrows():
        o_name = str(row['Sat_Acronym'])
        c_name = str(row['Sat_Full_Name'])
        
        # Check if numbers match (Allow subsets like OceanSat-3 (EOS-06) vs OceanSat-3)
        o_nums = set(re.findall(r'\d+', o_name))
        c_nums = set(re.findall(r'\d+', c_name))
        if o_nums and c_nums:
            if not (o_nums & c_nums): # No common numbers
                print(f"❌ VERSION ERROR: {o_name} <-> {c_name} (No common numbers: {o_nums} vs {c_nums})")
                version_errors += 1
            else:
                # Check for single-digit contradictions (e.g., 2-1 vs 2-3)
                d1 = {n for n in o_nums if len(n) == 1}
                d2 = {n for n in c_nums if len(n) == 1}
                if d1 and d2 and d1 != d2:
                    print(f"❌ VERSION ERROR: {o_name} <-> {c_name} (Conflicting sub-versions: {d1} vs {d2})")
                    version_errors += 1
            
    if version_errors == 0:
        print("✅ SUCCESS: No version number drift detected.")
    else:
        print(f"⚠️ TOTAL VERSION ERRORS: {version_errors}")

if __name__ == "__main__":
    stress_test('combined_satellite_data_strict.xlsx', 'oscar_satellite_data_full_perfection.xlsx', 'satellite_data_full.xlsx')
