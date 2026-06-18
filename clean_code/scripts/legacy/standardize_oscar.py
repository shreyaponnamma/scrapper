import pandas as pd
import numpy as np
import re
import os

# --- CONFIGURATION ---
INPUT_FILE = "../raw_data/oscar_satellite_data_full_perfection.xlsx"
OUTPUT_FILE = "../results/oscar_standardized.xlsx"

# The "Ground Truth" (Multi-SMU Style) Mapping for OSCAR
# Note: Many OSCAR columns already follow the Sat_ / Inst_ prefix convention
GROUND_TRUTH_MAP = {
    "Sat_Full_Name": "Sat_Full_Name",
    "Sat_Agency": "Sat_Agency",
    "Sat_Status": "Sat_Status",
    "Sat_Launch": "Sat_Launch",
    "Sat_EOL": "Sat_EOL",
    "Sat_Altitude": "Sat_Altitude",
    "Inst_Full_Name": "Inst_Full_Name",
    "Inst_Resolution": "Inst_Resolution",
    "Inst_Description": "Inst_Description",
    "Inst_Acronym": "Inst_Acronym",
    "Sat_Acronym": "Sat_Acronym"
}

def extract_numeric(text):
    if pd.isna(text): return np.nan
    # Extract first number found (handles "800 km", "0.5m", etc.)
    match = re.search(r'(\d+(?:\.\d+)?)', str(text).replace(',', ''))
    return float(match.group(1)) if match else np.nan

def standardize_oscar():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found.")
        return

    print(f"Reading {INPUT_FILE}...")
    df = pd.read_excel(INPUT_FILE)

    # 1. Rename based on ground truth map
    # This ensures consistency even if column names had small variations
    df_std = df.rename(columns=GROUND_TRUTH_MAP)

    # 2. Add extra columns that are in the merge ground truth but might be missing/named differently in OSCAR
    # CEOS has 'Swath', OSCAR has 'swath' (lowercase). We keep both but normalize the main one.
    if "swath" in df_std.columns and "Inst_Swath" not in df_std.columns:
        df_std["Inst_Swath"] = df_std["swath"]

    # 3. Clean up fields
    # Numerical Extraction (Overwrites existing data as requested)
    if "Sat_Altitude" in df_std.columns:
        df_std["Sat_Altitude"] = df_std["Sat_Altitude"].apply(extract_numeric)
        
    if "Inst_Resolution" in df_std.columns:
        df_std["Inst_Resolution"] = df_std["Inst_Resolution"].apply(extract_numeric)
        
    if "Inst_Swath" in df_std.columns:
        df_std["Inst_Swath"] = df_std["Inst_Swath"].apply(extract_numeric)

    print(f"Standardization complete. (Columns: {len(df_std.columns)})")
    
    # Save to clean_code/raw_data/
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    df_std.to_excel(OUTPUT_FILE, index=False)
    print(f"Saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    standardize_oscar()
