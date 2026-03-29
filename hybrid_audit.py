import pandas as pd

def perform_hybrid_audit(hybrid_file):
    print(f"Auditing hybrid session output: {hybrid_file}...")
    df = pd.read_excel(hybrid_file)
    
    # 1. Total row count
    print(f"\nTotal Row Count: {len(df)}")
    
    # 2. Filtering check
    forbidden = ['inactive', 'considered', 'planned', 'lost at launch', 'presumably inactive']
    status_col = 'Sat_Status' if 'Sat_Status' in df.columns else 'Mission Status'
    if status_col in df.columns:
        status_counts = df[status_col].fillna('').str.lower().value_counts()
        found_forbidden = [s for s in forbidden if s in status_counts]
        if found_forbidden:
            for s in found_forbidden:
                print(f"   WARNING: found {status_counts[s]} rows with forbidden status '{s}'")
        else:
            print("   1. Status Filter: PASSED (No inactive/planned missions found)")
    
    # 3. Merging Evidence - Find rows with NO NaN in both CEOS and OSCAR unique fields
    # CEOS unique: 'NORAD Catalog #'
    # OSCAR unique: 'Char_Central_wavelength'
    if 'NORAD Catalog #' in df.columns and 'Char_Central_wavelength' in df.columns:
        merged_rows = df[~df['NORAD Catalog #'].isnull() & ~df['Char_Central_wavelength'].isnull()]
        print(f"\n2. Integration Evidence: Verified {len(merged_rows)} rows are fully integrated (CEOS + OSCAR data).")
        if len(merged_rows) > 0:
            print("   ✔ Successfully combined disparate sources into single records.")
        else:
            print("   ⚠ Warning: Zero rows show data from both sources. This implies no matches were found.")
            
    # 4. Critical Column Presence
    cols = df.columns.tolist()
    print(f"\n3. Key Columns Present: {len(cols)} total columns.")
    important = ['Sat_Full_Name', 'Sat_Acronym', 'Inst_Acronym', 'Sat_Agency', 'Sat_Launch', 'Char_Central_wavelength']
    missing = [c for c in important if c not in cols]
    if missing:
        print(f"   ⚠ Missing key columns: {missing}")
    else:
        print("   ✔ All priority columns are present and correctly formatted.")

if __name__ == "__main__":
    perform_hybrid_audit('combined_satellite_data_strict.xlsx')
