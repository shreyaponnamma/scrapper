import pandas as pd

def check_data_loss(oscar_file, ceos_file, output_file):
    df_merged = pd.read_excel(output_file)
    print(f"Merged Dataset Shape: {df_merged.shape}")
    
    # Check for specific technical columns from OSCAR to ensure they survived
    oscar_cols = pd.read_excel(oscar_file, nrows=1).columns.tolist()
    char_cols = [c for c in oscar_cols if c.startswith('Char_')]
    
    missing_from_merged = [c for c in char_cols if c not in df_merged.columns]
    
    print("\n--- COLUMN SURVIVAL CHECK ---")
    if not missing_from_merged:
        print(f"✅ SUCCESS: All {len(char_cols)} OSCAR technical characterization columns were preserved.")
    else:
        print(f"❌ WARNING: {len(missing_from_merged)} columns were lost: {missing_from_merged}")

    # Check for unique CEOS columns
    ceos_cols = pd.read_excel(ceos_file, nrows=1).columns.tolist()
    unique_ceos = ['Swath', 'Accuracy', 'Waveband']
    missing_ceos = [c for c in unique_ceos if c not in df_merged.columns]
    if not missing_ceos:
        print(f"✅ SUCCESS: CEOS unique columns ({unique_ceos}) were preserved.")
    else:
        print(f"❌ WARNING: CEOS columns lost: {missing_ceos}")

    # Check for "Conflict Loss"
    # We can't do this easily from the final file alone because sources were merged.
    # But we can look for any nulls in columns that should have data.
    print("\n--- DATA DENSITY CHECK ---")
    important = ['Sat_Agency', 'Sat_Launch', 'Inst_Full_Name']
    for col in important:
        if col in df_merged.columns:
            filled = df_merged[col].notnull().sum()
            print(f"  {col}: {filled}/{len(df_merged)} rows populated.")

if __name__ == "__main__":
    check_data_loss('oscar_satellite_data_full_perfection.xlsx', 'satellite_data_full.xlsx', 'combined_satellite_data_strict.xlsx')
