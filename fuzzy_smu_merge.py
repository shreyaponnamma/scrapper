import pandas as pd
import numpy as np
import re
import difflib

# --- CONFIGURATION ---
CEOS_PATH = 'ceos_enriched_llm_full.xlsx'
OSCAR_PATH = 'oscar_reformatted_to_smu.xlsx'
OUTPUT_PATH = 'satellite_database_master_v2.xlsx'

def normalize(text):
    """Normalize strings for matching: lowercase, remove non-alphanumeric, strip 'mission'."""
    if not isinstance(text, str) or pd.isna(text): 
        return ""
    text = text.lower()
    text = re.sub(r'\(.*?\)', '', text) # Remove anything in parentheses
    text = re.sub(r'\bmission\b', '', text)
    text = re.sub(r'[^a-z0-9]', '', text)
    return text.strip()

def fuzzy_match(str1, str2, threshold=0.9):
    """Returns True if the similarity ratio is above the threshold."""
    if not str1 or not str2:
        return False
    return difflib.SequenceMatcher(None, str1, str2).ratio() >= threshold

def merge_v2():
    print(f"Loading CEOS data from: {CEOS_PATH}")
    df_ceos = pd.read_excel(CEOS_PATH)
    
    print(f"Loading OSCAR reformatted data from: {OSCAR_PATH}")
    df_oscar = pd.read_excel(OSCAR_PATH)

    # Pre-calculate normalized keys for both
    df_ceos['norm_sat'] = df_ceos['SatelliteName'].apply(normalize)
    df_ceos['norm_inst'] = df_ceos['SensorName'].apply(normalize)
    
    df_oscar['norm_sat'] = df_oscar['SatelliteName'].apply(normalize)
    df_oscar['norm_inst'] = df_oscar['SensorName'].apply(normalize)

    print("\nStarting Bi-directional Fuzzy Merge...")
    
    enriched_records = []
    enrichment_count = 0

    # Group OSCAR by satellite for faster lookup
    oscar_by_sat = {sat: group for sat, group in df_oscar.groupby('norm_sat')}
    oscar_sats = list(oscar_by_sat.keys())

    for idx, ceos_row in df_ceos.iterrows():
        ceos_sat = ceos_row['norm_sat']
        ceos_inst = ceos_row['norm_inst']
        
        match_found = False
        potential_oscar_rows = pd.DataFrame()

        # STEP 1: Exact Satellite Match
        if ceos_sat in oscar_by_sat:
            potential_oscar_rows = oscar_by_sat[ceos_sat]
        else:
            # STEP 2: Fuzzy Satellite Match (if no exact match)
            # Find the closest satellite name in OSCAR
            close_sats = difflib.get_close_matches(ceos_sat, oscar_sats, n=1, cutoff=0.9)
            if close_sats:
                potential_oscar_rows = oscar_by_sat[close_sats[0]]

        if not potential_oscar_rows.empty:
            # STEP 3: Instrument Matching within the matched Satellite
            # Try exact first
            inst_match = potential_oscar_rows[potential_oscar_rows['norm_inst'] == ceos_inst]
            
            # If no exact, try fuzzy instrument match
            if inst_match.empty:
                oscar_insts = potential_oscar_rows['norm_inst'].tolist()
                close_insts = difflib.get_close_matches(ceos_inst, oscar_insts, n=1, cutoff=0.85)
                if close_insts:
                    inst_match = potential_oscar_rows[potential_oscar_rows['norm_inst'] == close_insts[0]]

            if not inst_match.empty:
                # Merge the data - Prioritize CEOS for basics, OSCAR for technical details
                matched_oscar = inst_match.iloc[0]
                
                # Create enriched record
                new_record = ceos_row.to_dict()
                
                # Fill missing details from OSCAR if they exist
                for col in df_oscar.columns:
                    if col not in ['norm_sat', 'norm_inst', 'SatelliteName', 'SensorName']:
                        # If CEOS is null or empty, take from OSCAR
                        if pd.isna(new_record.get(col)) or str(new_record.get(col)).strip() == '':
                            new_record[col] = matched_oscar[col]
                
                new_record['Source'] = 'CEOS+OSCAR(Fuzzy)'
                enriched_records.append(new_record)
                enrichment_count += 1
                match_found = True

        if not match_found:
            # Add original CEOS row if no match found
            rec = ceos_row.to_dict()
            rec['Source'] = 'CEOS Only'
            enriched_records.append(rec)

    # Create the base merged dataframe
    merged_df = pd.DataFrame(enriched_records)

    # STEP 4: Add OSCAR-only satellites (those that weren't matched at all)
    matched_oscar_sats = set(merged_df[merged_df['Source'].str.contains('OSCAR', na=False)]['norm_sat'])
    oscar_only = df_oscar[~df_oscar['norm_sat'].isin(matched_oscar_sats)].copy()
    oscar_only['Source'] = 'OSCAR Only'
    
    final_df = pd.concat([merged_df, oscar_only], ignore_index=True)

    # Cleanup internal columns
    final_df = final_df.drop(columns=['norm_sat', 'norm_inst'], errors='ignore')

    # Save
    print(f"\nMerge Complete!")
    print(f"Total rows in final database: {len(final_df)}")
    print(f"CEOS records enriched with OSCAR data: {enrichment_count}")
    print(f"OSCAR-only records added: {len(oscar_only)}")
    
    final_df.to_excel(OUTPUT_PATH, index=False)
    print(f"Saved to: {OUTPUT_PATH}")

if __name__ == "__main__":
    merge_v2()
