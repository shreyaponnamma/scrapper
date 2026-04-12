import pandas as pd

def probe_duplicates(merged_file):
    df = pd.read_excel(merged_file)
    # Find a pair with duplicates
    counts = df.groupby(['Sat_Full_Name', 'Inst_Full_Name']).size()
    dupe_keys = counts[counts > 1].index.tolist()
    
    if dupe_keys:
        target_sat, target_inst = dupe_keys[0]
        print(f"--- PROBING DUPLICATE SENSOR: {target_sat} | {target_inst} ---")
        rows = df[(df['Sat_Full_Name'] == target_sat) & (df['Inst_Full_Name'] == target_inst)]
        print(rows.to_string())
    else:
        print("No duplicates found to probe.")

if __name__ == "__main__":
    probe_duplicates('combined_satellite_data_strict.xlsx')
