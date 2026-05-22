import pandas as pd
import numpy as np
import os

# --- CONFIGURATION ---
INPUT_FILE = "../raw_data/satellite_data_full.xlsx"
OUTPUT_FILE = "../results/ceos_standardized.xlsx"

# The "Ground Truth" (Multi-SMU Style) Mapping
# Format: { "Source Column": "Standardized Name" }
GROUND_TRUTH_MAP = {
    "Satellite Full Name": "Sat_Full_Name",
    "Mission Agencies": "Sat_Agency",
    "Mission Status": "Sat_Status",
    "Launch Date": "Sat_Launch",
    "EOL Date": "Sat_EOL",
    "Orbit Altitude": "Sat_Altitude",
    "Instrument Full Name": "Inst_Full_Name",
    "Resolution": "Inst_Resolution",
    "Swath": "Inst_Swath",
    "Accuracy": "Inst_Accuracy",
    "Waveband": "Inst_Waveband"
}

def standardize_ceos():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found.")
        return

    print(f"Reading {INPUT_FILE}...")
    df = pd.read_excel(INPUT_FILE)

    # 1. Rename based on ground truth map
    # We use a copy to avoid losing data
    df_std = df.rename(columns=GROUND_TRUTH_MAP)

    # 2. Add extra columns that are standard in the merge but missing in CEOS
    # We initialize them as empty if they don't exist to ensure schema compatibility later
    std_cols = ["Sat_Acronym", "Inst_Acronym", "Inst_Description"]
    for col in std_cols:
        if col not in df_std.columns:
            df_std[col] = np.nan

    # 3. Clean up specific fields (example: Altitude)
    if "Sat_Altitude" in df_std.columns:
        df_std["Sat_Altitude"] = df_std["Sat_Altitude"].astype(str).str.replace(" km", "").str.strip()

    print(f"Standardization complete. (Columns: {len(df_std.columns)})")
    
    # Save to clean_code/raw_data/
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    df_std.to_excel(OUTPUT_FILE, index=False)
    print(f"Saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    standardize_ceos()
