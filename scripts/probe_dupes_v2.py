import pandas as pd

def probe_duplicates(merged_file):
    df = pd.read_excel(merged_file)
    # Ensure no trailing spaces
    df['Sat_Full_Name'] = df['Sat_Full_Name'].astype(str).str.strip()
    df['Inst_Full_Name'] = df['Inst_Full_Name'].astype(str).str.strip()
    
    counts = df.groupby(['Sat_Full_Name', 'Inst_Full_Name']).size()
    dupe_keys = counts[counts > 1].index.tolist()
    
    print(f"Total Unique Sat+Inst Keys: {len(counts)}")
    print(f"Total Keys with Duplicates: {len(dupe_keys)}")

    if dupe_keys:
        target_sat, target_inst = dupe_keys[0]
        print(f"\n--- PROBING DUPLICATE SENSOR: {target_sat} | {target_inst} ---")
        rows = df[(df['Sat_Full_Name'] == target_sat) & (df['Inst_Full_Name'] == target_inst)]
        # Print first 2 rows of this dupe pair
        for i, (idx, row) in enumerate(rows.iterrows()):
            print(f"\nRow {i+1}:")
            print(row.to_dict())
            if i >= 1: break # Only show 2
    else:
        print("No duplicates found to probe.")

if __name__ == "__main__":
    probe_duplicates('combined_satellite_data_strict.xlsx')
