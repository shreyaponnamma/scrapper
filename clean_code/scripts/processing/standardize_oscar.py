"""
Standardize OSCAR satellite data by renaming columns and cleaning numeric fields.
Uses configurations from the central config file.
"""

import pandas as pd
import numpy as np
import re
import os
import sys

# Add the scripts directory to the path to import utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.config import OSCAR_RAW_EXCEL, OSCAR_PROCESSED

# The "Ground Truth" (Multi-SMU Style) Mapping for OSCAR
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
    """
    Extract the first numeric value from a string (e.g., '800 km' -> 800.0).
    """
    if pd.isna(text): 
        return np.nan
    # Extract first number found (handles "800 km", "0.5m", etc.)
    match = re.search(r'(\d+(?:\.\d+)?)', str(text).replace(',', ''))
    return float(match.group(1)) if match else np.nan

def standardize_oscar():
    """
    Main function to read, standardize, and save OSCAR data.
    """
    if not os.path.exists(OSCAR_RAW_EXCEL):
        print(f"Error: {OSCAR_RAW_EXCEL} not found.")
        return

    print(f"Reading {OSCAR_RAW_EXCEL}...")
    df = pd.read_excel(OSCAR_RAW_EXCEL)

    # 1. Rename based on ground truth map
    df_std = df.rename(columns=GROUND_TRUTH_MAP)

    # 2. Add extra columns that are in the merge ground truth but might be missing
    if "swath" in df_std.columns and "Inst_Swath" not in df_std.columns:
        df_std["Inst_Swath"] = df_std["swath"]

    # 3. Clean up fields
    if "Sat_Altitude" in df_std.columns:
        df_std["Sat_Altitude"] = df_std["Sat_Altitude"].apply(extract_numeric)
        
    if "Inst_Resolution" in df_std.columns:
        df_std["Inst_Resolution"] = df_std["Inst_Resolution"].apply(extract_numeric)
        
    if "Inst_Swath" in df_std.columns:
        df_std["Inst_Swath"] = df_std["Inst_Swath"].apply(extract_numeric)

    print(f"Standardization complete. (Columns: {len(df_std.columns)})")
    
    # Save to processed data directory
    os.makedirs(os.path.dirname(OSCAR_PROCESSED), exist_ok=True)
    df_std.to_excel(OSCAR_PROCESSED, index=False)
    print(f"Saved to {OSCAR_PROCESSED}")

if __name__ == "__main__":
    standardize_oscar()
