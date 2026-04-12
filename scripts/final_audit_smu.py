import pandas as pd
import numpy as np

def final_quality_check(transformed_file, source_file):
    print("--- FINAL QUALITY AUDIT ---")
    df_final = pd.read_excel(transformed_file)
    df_source = pd.read_excel(source_file)
    
    # 1. Row Parity
    print(f"Row Count Consistency: {'✅ MATCH' if len(df_final) == len(df_source) else '❌ DISCREPANCY'}")
    print(f"  Source Records: {len(df_source)}")
    print(f"  Final Records: {len(df_final)}")
    
    # 2. Categorization Performance
    cat_nulls = df_final['SensorCategory'].value_counts().get('Unknown', 0)
    class_nulls = df_final['SensorClass'].value_counts().get('Unknown', 0)
    print(f"\nCategorization Coverage:")
    print(f"  SensorCategory: {(len(df_final)-cat_nulls)/len(df_final)*100:.1f}% categorized.")
    print(f"  SensorClass: {(len(df_final)-class_nulls)/len(df_final)*100:.1f}% categorized.")

    # 3. Numeric Integrity
    alt_numeric = pd.to_numeric(df_final['Altitude_km'], errors='coerce').notnull().sum()
    res_numeric = pd.to_numeric(df_final['SpatialResAcross_m'], errors='coerce').notnull().sum()
    print(f"\nNumeric Extraction Integrity:")
    print(f"  Altitude (Numeric): {alt_numeric}/{len(df_final)} rows.")
    print(f"  Resolution (Numeric): {res_numeric}/{len(df_final)} rows.")

    # 4. Compare Column Sets
    source_cols = set(df_source.columns)
    final_cols = set(df_final.columns)
    
    new_cols = final_cols - source_cols
    # Map back to show what was renamed vs what was truly added
    print("\n--- NEW COLUMNS IN SMU DATABASE ---")
    for col in sorted(list(new_cols)):
        print(f"  [+] {col}")

if __name__ == "__main__":
    final_quality_check('final_SMU_database.xlsx', 'combined_satellite_data_strict.xlsx')
