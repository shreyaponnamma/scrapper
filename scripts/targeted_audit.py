import pandas as pd

def check_suspicious_cases(merged_file):
    df = pd.read_excel(merged_file)
    
    # Cases to check based on the log
    suspicious_acronyms = ['DubaiSat-3', 'Diwata-2', 'CAS 500-3', 'CAS500-2', 'GF-11-03', 'GF-14']
    
    print("--- TARGETED LOGICAL AUDIT ---")
    for acr in suspicious_acronyms:
        # Check if they exist as Acronym or in Full Name
        match = df[df['Sat_Acronym'].str.contains(acr, na=False) | df['Sat_Full_Name'].str.contains(acr, na=False)]
        if not match.empty:
            print(f"\nMatch found for '{acr}':")
            for _, row in match.iterrows():
                print(f"  Result Name: {row['Sat_Full_Name']}")
                print(f"  Acronym: {row['Sat_Acronym']}")
                print(f"  Agency: {row['Sat_Agency']}")
                print(f"  Launch: {row['Sat_Launch']}")
        else:
            print(f"\nNo match found for '{acr}' (Likely rejected or only exists in one source without being merged incorrectly)")

    # Check for cases where Sat_Acronym and Sat_Full_Name seem totally unrelated
    # We don't have the original 'Sat_Acronym' from OSCAR vs 'Satellite Full Name' from CEOS anymore 
    # but we can check if 'Sat_Full_Name' contains the words in 'Sat_Acronym'
    
    def is_logic_ok(row):
        acr = str(row.get('Sat_Acronym', '')).lower()
        full = str(row.get('Sat_Full_Name', '')).lower()
        if acr == 'nan' or not acr: return True
        # Simple check: at least one word or part of acronym should be in full name
        words = [w for w in acr.split() if len(w) > 2]
        if not words: return True
        return any(w in full for w in words)

    failures = df[~df.apply(is_logic_ok, axis=1)]
    if not failures.empty:
        print(f"\n--- POTENTIAL MISMATCHES ({len(failures)} found) ---")
        for _, row in failures.sample(min(10, len(failures))).iterrows():
            print(f"  {row['Sat_Acronym']} <== matched with ==> {row['Sat_Full_Name']}")
    else:
        print("\nAll merged name pairs passed the basic substring check.")

if __name__ == "__main__":
    check_suspicious_cases('combined_satellite_data_strict.xlsx')
