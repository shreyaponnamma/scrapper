import pandas as pd
import numpy as np

def audit_results(merged_file):
    df = pd.read_excel(merged_file)
    
    # Identify rows that were successfully merged (have data from both sources)
    # Since we dropped original separate columns, we look for rows where we have both 
    # original name fields if they were preserved, or we rely on the logic that 
    # if it was an outer join, we can check for columns that are unique to one source.
    
    # Let's check which columns we have
    print("Columns in merged file:", df.columns.tolist())
    
    # In the code, many columns were combined using combine_first.
    # To really see if it's a "match", we'd ideally want to see the original names.
    # However, the code drops 'ceos_mapped_name' and others.
    
    # Let's look for rows where we have both Sat_Acronym (OSCAR) and NORAD Catalog # (CEOS-ish)
    # or other CEOS specific fields vs OSCAR specific fields.
    
    # For now, let's just sample rows and see if the fields look consistent.
    sample = df.sample(min(20, len(df)))
    
    print("\n--- SAMPLE OF COMBINED RECORDS ---")
    for idx, row in sample.iterrows():
        print(f"\nSatellite: {row.get('Sat_Full_Name', 'N/A')} ({row.get('Sat_Acronym', 'N/A')})")
        print(f"  Agency: {row.get('Sat_Agency', 'N/A')}")
        print(f"  Status: {row.get('Sat_Status', 'N/A')}")
        print(f"  Launch: {row.get('Sat_Launch', 'N/A')}")
        print(f"  Altitude: {row.get('Sat_Altitude', 'N/A')}")
        print(f"  Instrument: {row.get('Inst_Full_Name', 'N/A')}")

    # Let's also look for suspicious matches where names are very different
    # (This requires the mapping logic which is gone from the final file)
    
if __name__ == "__main__":
    audit_results('combined_satellite_data_strict.xlsx')
