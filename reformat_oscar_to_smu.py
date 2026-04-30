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
        res_raw = get_first_valid(row, ['Inst_Resolution', 'Char_Resolution', 'Char_Spatial_Resolution', 'Char_Resolution_(m)', 'Char_Resolution_(km)'])
        res = np.nan
        if pd.notna(res_raw):
            match = re.search(r'(\d+(?:\.\d+)?)', str(res_raw))
            if match:
                res = float(match.group(1))
                if 'km' in str(res_raw).lower() or (res < 50 and 'm' not in str(res_raw).lower()): 
                    res *= 1000 # Convert to meters
        
        # Spectral Range
        spec_raw = get_first_valid(row, ['Char_Spectral_Range', 'Char_Spectral_range', 'Char_Spectral_interval'])
        spec_range = np.nan
        if pd.notna(spec_raw):
            spec_range = str(spec_raw)

        smu_row = {
            'SatelliteName': sat_name,
            'IntDesignator': row.get('International Designator', np.nan),
            'SatelliteCatalogNumber': row.get('NORAD Catalog #', np.nan),
            'ProviderName': agency,
            'ConstellationName': np.nan,
            'ClusterName': np.nan,
            'SubsetName': np.nan,
            'SensorName': inst_name,
            'SensorCategory': np.nan,
            'SensorClass': np.nan,
            'SensorMode': 'Standard',
            'SensorModeTechnique': np.nan,
            'Bands': bands,
            'SpectralRange': spec_range,
            'Altitude_km': alt,
            'SpatialResAcross_m': res,
            'SpatialResAlong_m': res,
            'SpatialResClass': np.nan,
            'SwathWidth_km': swath,
            'SwathLength_km': np.nan,
            'FoRAcrossTrackLeft_deg': np.nan,
            'FoRAcrossTrackRight_deg': np.nan,
            'FoRAlongTrackFront_deg': np.nan,
            'FoRAlongTrackBack_deg': np.nan,
            'Comment': f"OSCAR Full Name: {row.get('Inst_Full_Name', '')}",
            'Taskable': 'Y' if 'operational' in status.lower() else 'N'
        }
        smu_records.append(smu_row)
        
    oscar_smu = pd.DataFrame(smu_records)
    
    # Ensure all 26 columns are present and in order
    template_cols = [
        'SatelliteName', 'IntDesignator', 'SatelliteCatalogNumber', 'ProviderName', 
        'ConstellationName', 'ClusterName', 'SubsetName', 'SensorName', 
        'SensorCategory', 'SensorClass', 'SensorMode', 'SensorModeTechnique', 
        'Bands', 'SpectralRange', 'Altitude_km', 'SpatialResAcross_m', 
        'SpatialResAlong_m', 'SpatialResClass', 'SwathWidth_km', 'SwathLength_km', 
        'FoRAcrossTrackLeft_deg', 'FoRAcrossTrackRight_deg', 'FoRAlongTrackFront_deg', 
        'FoRAlongTrackBack_deg', 'Comment', 'Taskable'
    ]
    
    for col in template_cols:
        if col not in oscar_smu.columns:
            oscar_smu[col] = np.nan
            
    oscar_smu = oscar_smu[template_cols]
    oscar_smu.to_excel(output_path, index=False)
    print(f"Success! Comprehensive OSCAR reformatted with 26 columns and saved to {output_path}")

if __name__ == "__main__":
    reformat_oscar_to_smu('oscar_satellite_data_full_perfection.xlsx', 'oscar_reformatted_to_smu.xlsx')
