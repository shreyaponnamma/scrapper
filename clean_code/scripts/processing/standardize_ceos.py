"""
Standardize CEOS satellite data by renaming columns and cleaning numeric fields.
Uses configurations from the central config file.
"""

import pandas as pd
import numpy as np
import re
import os
import sys

# Add the scripts directory to the path to import utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.config import CEOS_RAW_EXCEL, CEOS_PROCESSED

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

def extract_numeric(text):
    """
    Extract the first numeric value from a string (e.g., '800 km' -> 800.0).
    """
    if pd.isna(text): 
        return np.nan
    # Extract first number found (handles "800 km", "0.5m", etc.)
    match = re.search(r'(\d+(?:\.\d+)?)', str(text).replace(',', ''))
    return float(match.group(1)) if match else np.nan

def standardize_ceos():
    """
    Main function to read, standardize, and save CEOS data.
    """
    if not os.path.exists(CEOS_RAW_EXCEL):
        print(f"Error: {CEOS_RAW_EXCEL} not found.")
        return

    print(f"Reading {CEOS_RAW_EXCEL}...")
    df = pd.read_excel(CEOS_RAW_EXCEL)

    # 1. Rename based on ground truth map
    df_std = df.rename(columns=GROUND_TRUTH_MAP)

    # 2. Add extra columns that are standard in the merge but missing in CEOS
    std_cols = ["Sat_Acronym", "Inst_Acronym", "Inst_Description"]
    for col in std_cols:
        if col not in df_std.columns:
            df_std[col] = np.nan

    # 3. Clean up specific fields
    if "Sat_Altitude" in df_std.columns:
        df_std["Sat_Altitude"] = df_std["Sat_Altitude"].apply(extract_numeric)
    
    if "Inst_Resolution" in df_std.columns:
        df_std["Inst_Resolution"] = df_std["Inst_Resolution"].apply(extract_numeric)
        
    if "Inst_Swath" in df_std.columns:
        df_std["Inst_Swath"] = df_std["Inst_Swath"].apply(extract_numeric)
    
    if "Sat_Full_Name" in df_std.columns:
        df_std["Sat_Full_Name"] = df_std["Sat_Full_Name"].astype(str).replace(to_replace=r"(?i)\s+Mission$", value="", regex=True).str.strip()
        
    if "Inst_Full_Name" in df_std.columns:
        df_std["Inst_Full_Name"] = df_std["Inst_Full_Name"].astype(str).replace(to_replace=r"(?i)\s+Instrument$", value="", regex=True).str.strip()

    print(f"Standardization complete. (Columns: {len(df_std.columns)})")
    
    # Save to processed data directory
    os.makedirs(os.path.dirname(CEOS_PROCESSED), exist_ok=True)
    df_std.to_excel(CEOS_PROCESSED, index=False)
    print(f"Saved to {CEOS_PROCESSED}")

if __name__ == "__main__":
    standardize_ceos()
