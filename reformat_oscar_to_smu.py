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

def get_first_valid(row, cols):
    """Pick the first non-null value from a list of columns."""
    for c in cols:
        val = row.get(c)
        if pd.notna(val) and str(val).strip().lower() not in ['nan', 'tbd', 'unknown', 'n/a']:
            return val
    return np.nan

def clean_oscar_bands(row):
    """Search multiple columns for band/channel counts."""
    cols = ['Char_No._of_channels', 'Char_No._of_bands', 'Char_Channel_number', 'Char_Channel_No.', 'Char_No.', 'Char_Number_of_channels']
    val = get_first_valid(row, cols)
    if pd.isna(val): return np.nan
    match = re.search(r'(\d+)', str(val))
    return int(match.group(1)) if match else np.nan

def clean_oscar_swath(row):
    """Search multiple columns for swath width."""
    cols = ['Char_Swath', 'Char_Footprint', 'Char_Footprint_(m)', 'Char_Footprint_km_at_nadir']
    val = get_first_valid(row, cols)
    if pd.isna(val): return np.nan
    match = re.search(r'(\d+(?:\.\d+)?)', str(val))
    if match:
        num = float(match.group(1))
        # Heuristic: if value > 1000 and column doesn't specify km, it might be meters
        if num > 3000: return num / 1000.0 # Convert meters to km
        return num
    return np.nan

def reformat_oscar_to_smu(input_path, output_path):
    print(f"Reading {input_path}...")
    df = pd.read_excel(input_path)
    
    smu_records = []
    
    for _, row in df.iterrows():
        sat_name = str(row.get('Sat_Acronym', 'N/A'))
        inst_name = str(row.get('Inst_Acronym', 'N/A'))
        agency = str(row.get('Sat_Agency', 'N/A')).split(',')[0].strip()
        status = str(row.get('Sat_Status', ''))
        
        # Altitude
        alt = extract_altitude(row.get('Sat_Altitude'))
        
        # Bands
        bands = clean_oscar_bands(row)
        
        # Swath
        swath = clean_oscar_swath(row)

        # Resolution (OSCAR often lists this in km for low-res, m for high-res)
        res_raw = get_first_valid(row, ['Inst_Resolution', 'Char_Resolution', 'Char_Spatial_Resolution'])
        res = np.nan
        if pd.notna(res_raw):
            match = re.search(r'(\d+(?:\.\d+)?)', str(res_raw))
            if match:
                res = float(match.group(1))
                if 'km' in str(res_raw).lower() or res < 5: # If < 5 and not specified, usually km (e.g. 1.1km)
                    res *= 1000 # Convert to meters
        
        smu_row = {
            'SatelliteName': sat_name,
            'ProviderName': agency,
            'SensorName': inst_name,
            'Altitude_km': alt,
            'Bands': bands,
            'SwathWidth_km': swath,
            'SpatialResAcross_m': res,
            'Taskable': 'Y' if 'operational' in status.lower() else 'N',
            'Source': 'OSCAR'
        }
        smu_records.append(smu_row)
        
    oscar_smu = pd.DataFrame(smu_records)
    oscar_smu.to_excel(output_path, index=False)
    print(f"Success! Comprehensive OSCAR reformatted and saved to {output_path}")

if __name__ == "__main__":
    reformat_oscar_to_smu('oscar_satellite_data_full_perfection.xlsx', 'oscar_reformatted_to_smu.xlsx')
