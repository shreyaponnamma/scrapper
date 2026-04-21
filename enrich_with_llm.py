import pandas as pd
import requests
import json
import os
import numpy as np

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.2:1b"

def ask_llm(text):
    prompt = f"""
    STRICT DATA EXTRACTION TASK.
    Source Text: {text}
    
    EXTRACT ONLY IF EXPLICITLY WRITTEN:
    1. bands: number of spectral bands (integer)
    2. for_deg: Field of Regard / pointing / tilt angle in degrees (float)
    
    CRITICAL RULES:
    - ONLY extract values strictly present in the text above. 
    - Do NOT use outside knowledge. 
    - If a value is not explicitly mentioned, return null.
    - If "nadir" or "nadir-only" is mentioned without a tilt angle, return 0 for for_deg.
    - Return ONLY valid JSON.
    
    JSON:"""

    
    try:
        res = requests.post(OLLAMA_URL, json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "format": "json"
        }, timeout=60)
        resp_json = res.json()
        return json.loads(resp_json['response'])
    except Exception as e:
        print(f"  Error calling LLM: {e}")
        return None


def enrich():
    target_file = "ceos_reformatted_to_smu.xlsx"
    source_file = "satellite_data_full.xlsx"
    
    print("Loading data...")
    df = pd.read_excel(target_file)
    source_df = pd.read_excel(source_file)
    
    # Identify rows where FoR is missing but we have a comment (raw data)
    # We'll batch process 20 rows to start
    mask = df['FoRAcrossTrackLeft_deg'].isna() & df['Comment'].notna()
    sample_indices = df[mask].index[:20]
    
    print(f"Enriching {len(sample_indices)} rows with LLM...")
    
    for count, idx in enumerate(sample_indices):
        sat_name = df.at[idx, 'SatelliteName']
        print(f"[{count+1}/{len(sample_indices)}] Processing row {idx} for Sat: {sat_name}", flush=True)
        comment = df.at[idx, 'Comment']
        result = ask_llm(comment)
        
        if result:
            # 1. Update Bands with strict check
            bands_val = result.get('bands')
            if pd.isna(df.at[idx, 'Bands']) and bands_val:
                # Validation: Does the number appear in the comment?
                if str(bands_val) in comment:
                    try:
                        df.at[idx, 'Bands'] = int(bands_val)
                        print(f"  -> Updated Bands to {bands_val}")
                    except: pass
                else:
                    print(f"  !! Halucination check failed for Bands: {bands_val}")
            
            # 2. Update FoR with strict check
            for_val = result.get('for_deg') or result.get('across_track_left')
            if pd.isna(df.at[idx, 'FoRAcrossTrackLeft_deg']) and for_val is not None:
                # Validation: Does the number appear in the comment or is it 0?
                if str(for_val) in comment or float(for_val) == 0.0:
                    try:
                        val = float(for_val)
                        df.at[idx, 'FoRAcrossTrackLeft_deg'] = val
                        df.at[idx, 'FoRAcrossTrackRight_deg'] = val
                        print(f"  -> Updated FoR to {val}")
                    except: pass
                else:
                    print(f"  !! Halucination check failed for FoR: {for_val}")

    df.to_excel("ceos_enriched_llm.xlsx", index=False)


    print("\nEnrichment complete! Saved to ceos_enriched_llm.xlsx")

if __name__ == "__main__":
    enrich()
