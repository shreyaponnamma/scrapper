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
        if pd.notna(val) and str(val).strip().lower() not in ['nan', 'tbd', 'unknown', 'n/a', 'none listed']:
            return val
    return np.nan

def infer_oscar_sensor_info(row):
    """
    Infers SensorCategory, SensorClass, and SensorModeTechnique 
    based on the instrument name and description.
    """
    name = str(row.get('Inst_Acronym', '')).upper()
    full_name = str(row.get('Inst_Full_Name', '')).lower()
    scanning = str(row.get('Inst_Scanning', '')).lower()
    desc = str(row.get('Inst_Description', '')).lower()
    
    category = "Passive"
    sensor_class = "Optical"
    technique = "Imager"
    
    # Text block for keyword matching
    text = f"{name} {full_name} {scanning} {desc}"
    
    if any(k in text for k in ['sar', 'radar', 'altimeter', 'scatterometer', 'active', 'microwave', 'palsar', 'ais', 'ro ', 'gnss']):
        category = "Active" if not any(x in text for x in ['ais', 'ro ', 'gnss']) else "Passive"
        sensor_class = "Radio"
        if any(x in text for x in ['radar', 'sar', 'palsar']):
            technique = "SAR"
    elif any(k in text for k in ['lidar', 'laser', 'icesat']):
        category = "Active"
        sensor_class = "Lidar"
    elif any(k in text for k in ['hyperspectral', 'spectrometer', 'sounding', 'spectral', 'cris', 'iasi', 'airs']):
        sensor_class = "Spectrometer"
        technique = "Sounder" if 'sound' in text else "Pushbroom"
    elif any(k in text for k in ['microwave radiator', 'mhs', 'amsub', 'atms', 'radiometer']):
        if sensor_class != "Radio": # Don't overwrite Active Radio
            sensor_class = "Microwave Radiometer"
            technique = "Sounder"
            
    # Refine Technique from scanning column
    if 'interferometer' in text: technique = "Interferometer"
    elif 'whiskbroom' in text: technique = "Whiskbroom"
    elif 'pushbroom' in text: technique = "Pushbroom"
    elif 'conical' in text: technique = "Conical Scanner"
    elif 'cross-track' in text: technique = "Cross-track Scanner"
    
    return category, sensor_class, technique

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
        # Heuristic: if value > 3000 and column doesn't specify km, it might be meters
        if num > 3000: return num / 1000.0 # Convert meters to km
        return num
    return np.nan

def extract_for_val(row):
    """Try to extract Field of Regard values."""
    val = get_first_valid(row, ['Char_Field-of-Regard', 'Char_Field_of_regard', 'Char_Beamwidth_(deg)'])
    if pd.isna(val): return np.nan
    match = re.search(r'(\d+(?:\.\d+)?)', str(val))
    return float(match.group(1)) if match else np.nan

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

        # Mode
        mode = get_first_valid(row, ['Char_Operation_mode', 'Char_Mode', 'Char_Spectral_Mode'])
        if pd.isna(mode): mode = "Standard"

        # High-level info
        cat, s_class, tech = infer_oscar_sensor_info(row)

        # Resolution
        res_raw = get_first_valid(row, ['Inst_Resolution', 'Char_Resolution', 'Char_Spatial_Resolution', 'Char_Resolution_(m)', 'Char_Resolution_(km)'])
        res = np.nan
        if pd.notna(res_raw):
            match = re.search(r'(\d+(?:\.\d+)?)', str(res_raw))
            if match:
                res = float(match.group(1))
                if 'km' in str(res_raw).lower() or (res < 50 and 'm' not in str(res_raw).lower()): 
                    res *= 1000 # Convert to meters
        
        res_class = np.nan

        # Field of Regard
        for_val = extract_for_val(row)
        for_l = for_r = np.nan
        if pd.notna(for_val) and (for_val < 50 or "deg" in str(get_first_valid(row, ['Char_Field-of-Regard', 'Char_Field_of_regard', 'Char_Beamwidth_(deg)'])).lower()):
            for_l = for_r = for_val

        # Spectral Range
        spec_raw = get_first_valid(row, ['Char_Spectral_Range', 'Char_Spectral_range', 'Char_Spectral_interval'])
        spec_range = str(spec_raw) if pd.notna(spec_raw) else np.nan

        smu_row = {
            'SatelliteName': sat_name,
            'IntDesignator': row.get('International Designator', np.nan),
            'SatelliteCatalogNumber': row.get('NORAD Catalog #', np.nan),
            'ProviderName': agency,
            'ConstellationName': np.nan,
            'ClusterName': np.nan,
            'SubsetName': np.nan,
            'SensorName': inst_name,
            'SensorCategory': cat,
            'SensorClass': s_class,
            'SensorMode': mode,
            'SensorModeTechnique': tech,
            'Bands': bands,
            'SpectralRange': spec_range,
            'Altitude_km': alt,
            'SpatialResAcross_m': res,
            'SpatialResAlong_m': res,
            'SpatialResClass': np.nan,
            'SwathWidth_km': swath,
            'SwathLength_km': np.nan,
            'FoRAcrossTrackLeft_deg': for_l,
            'FoRAcrossTrackRight_deg': for_r,
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
