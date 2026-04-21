import pandas as pd
import requests
import json
import os
import numpy as np
import time

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
        return json.loads(res.json()['response'])
    except Exception:
        return None

def enrich_efficiently():
    target_file = "ceos_reformatted_to_smu.xlsx"
    output_file = "ceos_enriched_llm_full.xlsx"
    
    print("Loading database...")
    df = pd.read_excel(target_file)
    
    # Identify candidates for enrichment
    mask = (pd.isna(df['Bands']) | pd.isna(df['FoRAcrossTrackLeft_deg'])) & df['Comment'].notna()
    candidates = df[mask].index.tolist()
    
    total = len(candidates)
    print(f"Total rows needing enrichment: {total}")
    
    start_time = time.time()
    
    for count, idx in enumerate(candidates):
        # Progress logging
        if count % 10 == 0 and count > 0:
            elapsed = time.time() - start_time
            avg_time = elapsed / count
            eta = (total - count) * avg_time
            print(f">>> Progress: {count}/{total} | ETA: {eta/60:.1f} mins", flush=True)
            # Periodic save
            df.to_excel(output_file, index=False)
            
        comment = str(df.at[idx, 'Comment'])
        result = ask_llm(comment)
        
        if result:
            # 1. Bands Extraction
            bands_val = result.get('bands')
            if pd.isna(df.at[idx, 'Bands']) and bands_val:
                if str(bands_val) in comment:
                    try:
                        df.at[idx, 'Bands'] = int(bands_val)
                    except: pass
            
            # 2. FoR Extraction
            for_val = result.get('for_deg')
            if pd.isna(df.at[idx, 'FoRAcrossTrackLeft_deg']) and for_val is not None:
                # Handle cases where LLM returns a dict instead of a number
                if isinstance(for_val, dict):
                    for_val = next(iter(for_val.values())) if for_val else None
                
                try:
                    num_val = float(for_val)
                    if str(for_val) in comment or num_val == 0.0:
                        df.at[idx, 'FoRAcrossTrackLeft_deg'] = num_val
                        df.at[idx, 'FoRAcrossTrackRight_deg'] = num_val
                except (ValueError, TypeError):
                    pass

    # Final save
    df.to_excel(output_file, index=False)
    print(f"\nSUCCESS: Full enrichment complete. Saved to {output_file}")

if __name__ == "__main__":
    enrich_efficiently()
