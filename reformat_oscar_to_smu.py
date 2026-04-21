import pandas as pd
import numpy as np
import re

def normalize_name(name):
    if not isinstance(name, str): return ""
    return name.strip()

def extract_altitude(alt_str):
    if pd.isna(alt_str): return np.nan
    match = re.search(r'(\d+)', str(alt_str).replace(",", ""))
    return float(match.group(1)) if match else np.nan

def reformat_oscar_to_smu(input_path, output_path):
    print(f"Reading {input_path}...")
    df = pd.read_excel(input_path)
    
    smu_records = []
    
    for _, row in df.iterrows():
        # Map basic fields
        sat_name = str(row.get('Sat_Acronym', 'N/A'))
        inst_name = str(row.get('Inst_Acronym', 'N/A'))
        agency = str(row.get('Sat_Agency', '')).split(',')[0].strip()
        
        # Altitude
        alt = extract_altitude(row.get('Sat_Altitude'))
        
        # Bands - search across various Channel/Band columns in OSCAR
        bands = np.nan
        # Priority 1: "No. of channels" column
        if pd.notna(row.get('Char_No._of_channels')):
            bands = row.get('Char_No._of_channels')
        # Priority 2: "No. of bands" column
        elif pd.notna(row.get('Char_Spectral_bands')):
            bands = row.get('Char_Spectral_bands')
        
        # Field of Regard
        for_val = np.nan
        for_col = row.get('Char_Field-of-Regard') or row.get('Char_Field_of_regard')
        if pd.notna(for_col):
            match = re.search(r'(\d+(?:\.\d+)?)', str(for_col))
            if match:
                for_val = float(match.group(1))

        # Resolution
        res = row.get('Inst_Resolution')
        if isinstance(res, str):
            res_match = re.search(r'(\d+(?:\.\d+)?)', res)
            res = float(res_match.group(1)) if res_match else np.nan

        smu_row = {
            'SatelliteName': sat_name,
            'ProviderName': agency,
            'SensorName': inst_name,
            'SensorCategory': np.nan, # To be inferred or kept empty
            'SensorClass': np.nan,
            'SensorMode': np.nan, 
            'Altitude_km': alt,
            'Bands': bands,
            'FoRAcrossTrackLeft_deg': for_val,
            'FoRAcrossTrackRight_deg': for_val,
            'SpatialResAcross_m': res,
            'Source': 'OSCAR'
        }
        smu_records.append(smu_row)
        
    oscar_smu = pd.DataFrame(smu_records)
    oscar_smu.to_excel(output_path, index=False)
    print(f"Success! Reformatted OSCAR saved to {output_path}")

if __name__ == "__main__":
    reformat_oscar_to_smu('oscar_satellite_data_full_perfection.xlsx', 'oscar_reformatted_to_smu.xlsx')
