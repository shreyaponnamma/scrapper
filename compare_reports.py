import pandas as pd
import numpy as np

def compare_databases(file_a_path, file_b_path):
    print(f"Comparing:")
    print(f"A: {file_a_path}")
    print(f"B: {file_b_path}")
    
    # Load files
    df_a = pd.read_excel(file_a_path)
    df_b = pd.read_excel(file_b_path)
    
    # 1. Basic Stats
    print(f"\n--- Statistics ---")
    print(f"File A Rows: {len(df_a)}")
    print(f"File B Rows: {len(df_b)}")
    
    # 2. Overlapping Satellites
    sats_a = set(df_a['SatelliteName'].dropna().unique())
    sats_b = set(df_b['SatelliteName'].dropna().unique())
    
    overlap = sats_a.intersection(sats_b)
    only_a = sats_a - overlap
    only_b = sats_b - overlap
    
    print(f"Overlapping Satellites: {len(overlap)}")
    print(f"Satellites only in A: {len(only_a)}")
    print(f"Satellites only in B: {len(only_b)}")
    
    if len(overlap) > 0:
        print("\n--- Samples of Overlapping Satellites ---")
        for s in list(overlap)[:5]:
            print(f"- {s}")
            
    # 3. Column Consistency Check
    cols_a = set(df_a.columns)
    cols_b = set(df_b.columns)
    
    if cols_a == cols_b:
        print("\nColumn Schema: Matches exactly.")
    else:
        print("\nColumn Schema: DIFFERS")
        print(f"Columns in A only: {cols_a - cols_b}")
        print(f"Columns in B only: {cols_b - cols_a}")
        
    # 4. Data Quality Comparison for an overlapping satellite (Aura for example)
    if 'Aura Mission' in overlap:
        print("\n--- Data Content Comparison (Example: Aura Mission) ---")
        row_a = df_a[df_a['SatelliteName'] == 'Aura Mission'].iloc[0]
        row_b = df_b[df_b['SatelliteName'] == 'Aura Mission'].iloc[0]
        
        comp_cols = ['SensorName', 'SensorClass', 'SensorMode', 'Bands', 'SpectralRange', 'SpatialResAcross_m']
        for col in comp_cols:
            val_a = row_a.get(col, 'N/A')
            val_b = row_b.get(col, 'N/A')
            status = "MATCH" if str(val_a) == str(val_b) else "DIFF"
            print(f"{col:20} | A: {val_a:20} | B: {val_b:20} | {status}")

if __name__ == "__main__":
    FILE_A = "/home/shreya/projects/scrapper/ceos_reformatted_to_smu.xlsx"
    FILE_B = "/home/shreya/projects/scrapper/2026-02-24_Multi-SMU_database.xlsx"
    compare_databases(FILE_A, FILE_B)
