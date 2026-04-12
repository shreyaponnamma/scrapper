import pandas as pd

def master_audit(merged_file):
    print(f"--- MASTER FINAL AUDIT: {merged_file} ---")
    df = pd.read_excel(merged_file)
    
    # 1. Check for Duplicate Rows
    dupes_count = df.duplicated().sum()
    if dupes_count > 0:
        print(f"❌ ERROR: Found {dupes_count} exact duplicate rows!")
        # df.drop_duplicates(inplace=True) # Optionally fix it
    else:
        print("✅ SUCCESS: No duplicate rows found.")

    # 2. Check for "Ghost" or Duplicate Columns
    cols = df.columns.tolist()
    bad_cols = [c for c in cols if '_ceos' in c or '_oscar' in c or 'merge_key' in c or 'mapped' in c]
    if bad_cols:
        print(f"❌ WARNING: Potential stray columns found: {bad_cols}")
    else:
        print("✅ SUCCESS: All columns consolidated correctly.")

    # 3. Check for specific Satellite+Instrument duplicates
    # Since each row should be a unique sensor on a satellite
    if 'Sat_Full_Name' in df.columns and 'Inst_Full_Name' in df.columns:
        key_dupes = df.duplicated(subset=['Sat_Full_Name', 'Inst_Full_Name']).sum()
        if key_dupes > 0:
            print(f"❌ WARNING: {key_dupes} rows share identical Satellite + Instrument names. (Check if multiple records exist for one sensor)")
        else:
            print("✅ SUCCESS: Every Satellite+Instrument combination is unique.")

    # 4. Logical Range Checks
    print("\n--- LOGICAL RANGE CHECKS ---")
    # check for impossible altitudes (e.g. 0 or > 40000 for non-GEO)
    if 'Sat_Altitude' in df.columns:
        altitudes = pd.to_numeric(df['Sat_Altitude'], errors='coerce')
        extreme_alt = df[(altitudes < 100) | (altitudes > 40000)]
        if not extreme_alt.empty:
            print(f"ℹ️ NOTE: Found {len(extreme_alt)} missions with unusual altitudes (Check if intentional).")

    # 5. Null Value Scan
    print("\n--- DATA COMPLETENESS ---")
    null_report = df.isnull().sum()
    important_cols = ['Sat_Full_Name', 'Sat_Agency', 'Sat_Status']
    for col in important_cols:
        if col in df.columns:
            nulls = null_report[col]
            print(f"  {col}: {len(df)-nulls}/{len(df)} records complete.")

if __name__ == "__main__":
    master_audit('combined_satellite_data_strict.xlsx')
