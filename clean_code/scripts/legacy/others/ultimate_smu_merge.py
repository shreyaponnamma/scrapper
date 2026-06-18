import pandas as pd
import numpy as np
import re
import difflib

def normalize(name):
    if not isinstance(name, str): return ""
    name = re.sub(r'\(.*?\)', '', name)
    name = re.sub(r'[^\w\s]', '', name)
    return ' '.join(name.lower().split())

def merge_databases(ceos_path, oscar_path, output_path):
    print(f"Loading datasets...")
    df_ceos = pd.read_excel(ceos_path)
    df_oscar = pd.read_excel(oscar_path)
    
    # 1. Normalize names for matching
    df_ceos['match_sat'] = df_ceos['SatelliteName'].apply(normalize)
    df_ceos['match_inst'] = df_ceos['SensorName'].apply(normalize)
    df_oscar['match_sat'] = df_oscar['SatelliteName'].apply(normalize)
    df_oscar['match_inst'] = df_oscar['SensorName'].apply(normalize)
    
    # 2. Map OSCAR rows to CEOS rows where they match
    print("Finding matches between CEOS and OSCAR...")
    unique_ceos_sats = df_ceos['match_sat'].unique()
    unique_oscar_sats = df_oscar['match_sat'].unique()
    
    sat_map = {}
    for o_sat in unique_oscar_sats:
        if not o_sat: continue
        # Fuzzy match to CEOS
        best_match = None
        best_score = 0
        for c_sat in unique_ceos_sats:
            if o_sat == c_sat: score = 1.0
            elif o_sat in c_sat or c_sat in o_sat: score = 0.9
            else: score = difflib.SequenceMatcher(None, o_sat, c_sat).ratio()
            
            if score > best_score:
                best_score = score
                best_match = c_sat
        
        if best_score > 0.8:
            sat_map[o_sat] = best_match

    # 3. Integrate OSCAR data into CEOS with Smart Conflict Resolution
    print("Performing Cell-Level Best-of-Both Merge...")
    count_enriched = 0
    
    # We will create a fresh combined list to avoid mutating the original df_ceos in place improperly
    final_records = []
    
    for idx, c_row in df_ceos.iterrows():
        new_row = c_row.to_dict()
        match_sat = sat_map.get(c_row['match_sat'])
        
        if match_sat:
            o_rows = df_oscar[df_oscar['match_sat'] == c_row['match_sat']]
            if not o_rows.empty:
                o_row = o_rows.iloc[0] # Best match
                
                # SMART CONFLICT RESOLUTION:
                # 1. Altitude: Prefer OSCAR (proven 84% accuracy)
                if pd.notna(o_row['Altitude_km']):
                    new_row['Altitude_km'] = o_row['Altitude_km']
                
                # 2. Bands: Pick the MAXIMUM (more detailed spectral count)
                c_bands = c_row.get('Bands', 0)
                o_bands = o_row.get('Bands', 0)
                if pd.notna(o_bands) and (pd.isna(c_bands) or o_bands > c_bands):
                    new_row['Bands'] = o_bands

                # 3. Resolution: Pick the MINIMUM (the highest resolution value)
                c_res = c_row.get('SpatialResAcross_m', 99999)
                o_res = o_row.get('SpatialResAcross_m', 99999)
                if pd.notna(o_res) and (pd.isna(c_res) or o_res < c_res):
                    new_row['SpatialResAcross_m'] = o_res
                
                # 4. Provider: Prefer OSCAR (Standardized names)
                if pd.notna(o_row['ProviderName']):
                    new_row['ProviderName'] = o_row['ProviderName']

                # Mark as dual-sourced
                new_row['Source'] = 'CEOS+OSCAR'
                count_enriched += 1
        
        final_records.append(new_row)

    # 4. Add OSCAR-only missions
    print(f"Adding OSCAR-only missions...")
    oscar_matched_keys = set(sat_map.keys())
    oscar_only_df = df_oscar[~df_oscar['match_sat'].isin(oscar_matched_keys)]
    
    # Clean up and Combine
    df_ceos_final = pd.DataFrame(final_records)
    final_df = pd.concat([df_ceos_final, oscar_only_df], ignore_index=True)
    final_df = final_df.drop(columns=['match_sat', 'match_inst'])

    
    # 5. Save final master database
    final_df.to_excel(output_path, index=False)
    print(f"SUCCESS!")
    print(f"- Base CEOS rows: {len(df_ceos)}")
    print(f"- OSCAR-only missions added: {len(oscar_only_df)}")
    print(f"- CEOS records enriched with OSCAR data: {count_enriched}")
    print(f"- Final Master Database saved to: {output_path}")

if __name__ == "__main__":
    merge_databases('ceos_enriched_llm_full.xlsx', 'oscar_reformatted_to_smu.xlsx', 'satellite_database_master.xlsx')
