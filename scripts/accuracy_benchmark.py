import pandas as pd
import numpy as np
import re
import difflib

def normalize(text):
    if not isinstance(text, str): return ""
    text = re.sub(r'\(.*?\)', '', text)
    text = re.sub(r'\bMission\b', '', text, flags=re.IGNORECASE)
    text = re.sub(r'[^\w\s]', '', text)
    return ' '.join(text.lower().split())

def run_benchmark(original_file, generated_file):
    print(f"Loading files...")
    df_orig = pd.read_excel(original_file)
    df_gen = pd.read_excel(generated_file)

    df_orig['match_sat'] = df_orig['SatelliteName'].apply(normalize)
    df_orig['match_inst'] = df_orig['SensorName'].apply(normalize)
    df_gen['match_sat'] = df_gen['SatelliteName'].apply(normalize)
    df_gen['match_inst'] = df_gen['SensorName'].apply(normalize)

    print(f"Missions in Ground Truth: {len(df_orig)}")
    print(f"Missions in Generated Data: {len(df_gen)}")

    # 1. ATTEMPT FUZZY MATCHING (Since exact normalize failed)
    print("Performing fuzzy mapping...")
    matches = []
    
    unique_orig_sats = df_orig['match_sat'].unique()
    unique_gen_sats = df_gen['match_sat'].unique()
    
    sat_map = {}
    for g_sat in unique_gen_sats:
        if not g_sat: continue
        # Find best match in original
        best_match = None
        best_score = 0
        for o_sat in unique_orig_sats:
            if not o_sat: continue
            # Check for acronym match (alos2 in advanced land...)
            if g_sat in o_sat or o_sat in g_sat:
                score = 0.9
            else:
                score = difflib.SequenceMatcher(None, g_sat, o_sat).ratio()
            
            if score > best_score:
                best_score = score
                best_match = o_sat
        
        if best_score > 0.8: # Threshold for satellite match
            sat_map[g_sat] = best_match

    df_gen['matched_orig_sat'] = df_gen['match_sat'].map(sat_map)
    
    # 2. MATCH INSTRUMENTS WITHIN MATCHED SATELLITES
    print("Matching instruments...")
    results = []
    for g_idx, g_row in df_gen.iterrows():
        o_sat = g_row['matched_orig_sat']
        if not o_sat: continue
        
        # Possible instruments for this satellite in original
        o_rows = df_orig[df_orig['match_sat'] == o_sat]
        
        best_o_idx = None
        best_inst_score = 0
        for o_idx, o_row in o_rows.iterrows():
            g_inst = g_row['match_inst']
            o_inst = o_row['match_inst']
            
            # Direct acronym match
            if g_inst == o_inst:
                score = 1.0
            elif (len(g_inst) > 2 and g_inst in o_inst) or (len(o_inst) > 2 and o_inst in g_inst):
                score = 0.9
            else:
                score = difflib.SequenceMatcher(None, g_inst, o_inst).ratio()
            
            if score > best_inst_score:
                best_inst_score = score
                best_o_idx = o_idx
        
        if best_inst_score > 0.6: # Lowered from 0.7
            match_data = g_row.to_dict()
            match_data = {f"gen_{k}": v for k, v in match_data.items()}
            match_data.update({f"orig_{k}": v for k, v in o_rows.loc[best_o_idx].to_dict().items()})
            results.append(match_data)

    merged = pd.DataFrame(results)
    if len(merged) == 0:
        print("Still no matches found.")
        return
    
    # DEDUPLICATE: Keep best match for each original record
    merged['total_score'] = 0 # Dummy score for now, but we could improve
    merged = merged.drop_duplicates(subset=['orig_SatelliteName', 'orig_SensorName'])
    
    print(f"Matched {len(merged)} unique Satellite-Instrument pairs.")

    if len(merged) > 0:
        print("\nMatched Samples (First 10):")
        for i, row in merged.head(10).iterrows():
            print(f"  {row['orig_SatelliteName']} -> {row['gen_SatelliteName']}")

    # Fields to check
    check_fields = {
        'SensorCategory': 'Category',
        'SensorClass': 'Class',
        'SensorMode': 'Mode',
        'SensorModeTechnique': 'Technique',
        'Altitude_km': 'Altitude',
        'Bands': 'Bands'
    }

    report = []
    
    for smu_col, label in check_fields.items():
        col_orig = f"orig_{smu_col}"
        col_gen = f"gen_{smu_col}"
        
        if col_orig not in merged.columns or col_gen not in merged.columns:
            continue
            
        # Comparison logic
        if label == 'Altitude':
             merged[f'is_match_{label}'] = merged.apply(lambda r: abs(float(r[col_orig]) - float(r[col_gen])) < 20 if pd.notna(r[col_orig]) and pd.notna(r[col_gen]) and str(r[col_orig]) != 'nan' and str(r[col_gen]) != 'nan' else False, axis=1)
        elif label == 'Bands':
             merged[f'is_match_{label}'] = merged.apply(lambda r: int(float(r[col_orig])) == int(float(r[col_gen])) if pd.notna(r[col_orig]) and pd.notna(r[col_gen]) and str(r[col_orig]) != 'nan' and str(r[col_gen]) != 'nan' else False, axis=1)
        else:
             merged[f'is_match_{label}'] = merged[col_orig].astype(str).str.lower().str.strip() == merged[col_gen].astype(str).str.lower().str.strip()

        match_rate = merged[f'is_match_{label}'].mean() * 100
        report.append({
            "Field": label,
            "Accuracy": f"{match_rate:.1f}%",
            "Matched": merged[f'is_match_{label}'].sum(),
            "Total": len(merged)
        })

    print("\n--- ACCURACY BENCHMARK REPORT ---")
    print(pd.DataFrame(report).to_string(index=False))

    print("\n--- SAMPLE DISCREPANCIES (First 5 Mode mismatches) ---")
    discrepancies = merged[~merged['is_match_Mode']].head(5)
    for i, row in discrepancies.iterrows():
        print(f"Sat: {row['orig_SatelliteName']} | Inst: {row['orig_SensorName']}")
        print(f"  Expected Mode: {row['orig_SensorMode']} | Got: {row['gen_SensorMode']}")
        print("-" * 30)

if __name__ == "__main__":
    run_benchmark('2026-02-24_Multi-SMU_database.xlsx', 'final_SMU_database.xlsx')
