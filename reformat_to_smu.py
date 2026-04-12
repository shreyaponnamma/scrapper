import pandas as pd
import numpy as np
import re
import requests
import json
import time

# --- SETTINGS ---
OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "llama3.2:1b"

def extract_numeric(text):
    if pd.isna(text): return None
    # Remove commas and handle strings
    text_str = str(text).replace(',', '')
    match = re.search(r'(\d+(?:\.\d+)?)', text_str)
    return float(match.group(1)) if match else None

def get_sensor_categories(name, description, op_mode=""):
    name_str = str(name).upper()
    desc_str = str(description).lower()
    op_str = str(op_mode).lower()
    text = f"{name_str} {desc_str} {op_str}"
    
    # 0. FAMOUS INSTRUMENTS KNOWLEDGE BASE (Instant & Accurate)
    FAMOUS = {
        'MODIS': ('Passive', 'EO/IR', 'MSI', 'Whisk-Broom'),
        'VIIRS': ('Passive', 'EO/IR', 'MSI', 'Whisk-Broom'),
        'AIRS': ('Passive', 'EO/IR', 'MSI', 'Whisk-Broom'),
        'IASI': ('Passive', 'EO/IR', 'HSI', 'Whisk-Broom'),
        'CERES': ('Passive', 'EO/IR', 'MSI', 'Whisk-Broom'),
        'OLCI': ('Passive', 'EO/IR', 'MSI', 'Pushbroom'),
        'SLSTR': ('Passive', 'EO/IR', 'MSI', 'Whisk-Broom'),
        'TROPOMI': ('Passive', 'EO/IR', 'HSI', 'Pushbroom'),
        'MSI': ('Passive', 'EO/IR', 'MSI', 'Pushbroom'),
        'SAR-X': ('Active', 'Radio', 'SAR', 'Stripmap'),
        'SAR-C': ('Active', 'Radio', 'SAR', 'Stripmap'),
        'SAR-L': ('Active', 'Radio', 'SAR', 'Stripmap'),
        'SAR-S': ('Active', 'Radio', 'SAR', 'Stripmap'),
        'ASAR': ('Active', 'Radio', 'SAR', 'ScanSAR'),
        'PANS': ('Passive', 'EO/IR', 'PAN', 'Pushbroom'),
        'AMSU': ('Passive', 'Radio', 'RF', 'Whisk-Broom'),
        'MHS': ('Passive', 'Radio', 'RF', 'Whisk-Broom'),
        'AVHRR': ('Passive', 'EO/IR', 'MSI', 'Whisk-Broom'),
        'ETM+': ('Passive', 'EO/IR', 'MSI', 'Whisk-Broom'),
        'OLI': ('Passive', 'EO/IR', 'MSI', 'Pushbroom'),
        'TIRS': ('Passive', 'EO/IR', 'MSI', 'Pushbroom'),
    }
    
    for key, vals in FAMOUS.items():
        if key in name_str:
            return {"category": vals[0], "class": vals[1], "mode": vals[2], "technique": vals[3]}

    # 1. TECHNICAL SIGNATURE MAPPING (Deterministic)
    text_lower = text.lower()
    # Active/Passive logic
    active_keywords = ['radar', 'sar', 'lidar', 'altimeter', 'scatterometer', 'laser', 'active', 'alt']
    passive_keywords = ['radiometer', 'passive', 'sounder', 'imager', 'spectrometer', 'camera', 'imaging', 'spectro']
    
    is_active = any(k in text_lower for k in active_keywords)
    if any(k in text_lower for k in ['radiometer', 'sounder', 'spectrometer', 'hyperspectral', 'passive']):
        is_active = False

    # Radio/EO/IR logic
    radio_keywords = ['microwave', 'radar', 'sar', 'ghz', 'mhz', 'c-band', 'l-band', 'x-band', 'ku-band', 'ka-band', 'radio', 'frequency']
    eo_ir_keywords = ['infrared', 'visible', 'optical', 'spectral', 'tir', 'nir', 'swir', 'nm', 'um', 'wavelength', 'micro-meter', 'imager', 'spectrometer', 'camera', 'vis', 'spectral']
    
    is_radio = any(k in text_lower for k in radio_keywords)
    is_eo_ir = any(k in text_lower for k in eo_ir_keywords)

    final_cat = "Active" if is_active else "Passive"
    if is_radio and not is_eo_ir: final_cls = "Radio"
    elif is_eo_ir: final_cls = "EO/IR"
    elif is_radio: final_cls = "Radio"
    else: final_cls = "Unknown"

    # Heuristic for Mode
    final_mode = "Unknown"
    if 'sar' in text_lower or 'synthetic aperture' in text_lower: final_mode = "SAR"
    elif 'pan' in text_lower or 'panchromatic' in text_lower or ' vhr' in text_lower: final_mode = "PAN"
    elif 'hsi' in text_lower or 'hyperspectral' in text_lower: final_mode = "HSI"
    elif 'msi' in text_lower or 'multispectral' in text_lower or 'multi-spectral' in text_lower: final_mode = "MSI"
    elif 'optical' in text_lower or 'imager' in text_lower: final_mode = "MSI"
    elif 'alt' in text_lower or 'alti' in text_lower or 'altimeter' in text_lower: final_mode = "RF"
    elif 'scat' in text_lower or 'scatterometer' in text_lower: final_mode = "RF"
    elif 'ais' in text_lower or 'ais' in text_lower: final_mode = "AIS"
    elif 'ads-b' in text_lower or 'ads-b' in text_lower: final_mode = "ADS-B"
    elif is_radio: final_mode = "RF"
    
    # Heuristic for Technique
    final_tech = "Unknown"
    if 'spotlight' in text_lower: final_tech = "Spotlight"
    elif 'stripmap' in text_lower: final_tech = "Stripmap"
    elif 'scansar' in text_lower: final_tech = "ScanSAR"
    elif 'pushbroom' in text_lower or 'push-broom' in text_lower: final_tech = "Pushbroom"
    elif 'whisk-broom' in text_lower or 'whiskbroom' in text_lower or 'whisk ' in text_lower: final_tech = "Whisk-Broom"
    elif 'receiver' in text_lower or 'ais' in text_lower: final_tech = "Receiver"
    elif 'frame' in text_lower: final_tech = "Frame"
    elif final_mode == "MSI": final_tech = "Pushbroom"
    elif final_mode == "HSI": final_tech = "Pushbroom" # Default for HSI
    elif final_mode == "SAR": final_tech = "Stripmap"

    # 2. LLM FALLBACK
    if (final_mode == "Unknown" or final_tech == "Unknown") and not (desc_str == 'nan' or desc_str == ''):
        prompt = f"""Task: Categorize instrument.
Name: {name} | Desc: {description}
Choose one value for each field from these lists:
- category: [Active, Passive]
- class: [Radio, EO/IR]
- mode: [SAR, MSI, PAN, HSI, RF, AIS, ADS-B]
- technique: [Stripmap, Spotlight, ScanSAR, Receiver, Mono, Pushbroom, Whisk-Broom, Frame]

Return ONLY JSON: {{"category": "...", "class": "...", "mode": "...", "technique": "..."}}"""
        
        try:
            data = {"model": OLLAMA_MODEL, "messages": [{"role": "user", "content": prompt}], "stream": False}
            res = requests.post(OLLAMA_URL, json=data, timeout=5) # Reduced timeout for performance
            content = res.json()['message']['content']
            match = re.search(r'\{.*\}', content.replace('\n', ' '))
            if match:
                parsed = json.loads(match.group(0))
                if final_cat == "Unknown": final_cat = "Active" if "active" in str(parsed.get('category')).lower() else "Passive"
                if final_cls == "Unknown": final_cls = "Radio" if "radio" in str(parsed.get('class')).lower() else "EO/IR"
                if final_mode == "Unknown":
                    m_llm = str(parsed.get('mode')).upper()
                    for m in ['SAR', 'MSI', 'PAN', 'HSI', 'RF', 'AIS', 'ADS-B']:
                        if m in m_llm:
                            final_mode = m
                            break
                if final_tech == "Unknown": final_tech = parsed.get('technique')
        except:
            pass

    # Final cleanup
    if final_tech == "Unknown" and pd.notna(op_mode) and str(op_mode).strip() != "":
        final_tech = str(op_mode)

    return {"category": final_cat, "class": final_cls, "mode": final_mode, "technique": final_tech}

def extract_bands(row):
    # Sources: 'Char_No._of_channels', 'Char_Channel_Number', 'Waveband'
    # 1. Direct columns
    for col in ['Char_No._of_channels', 'Char_Channel_number', 'Char_No.', 'Char_Number_of_channels', 'Char_Channel_Number']:
        if col in row and pd.notna(row[col]):
            num = extract_numeric(row[col])
            if num: return int(num)
            
    # 2. Parse Waveband
    waveband = str(row.get('Waveband', '')).lower()
    if waveband and waveband != 'nan':
        # "X and Y" pattern (e.g., 10.5 and 12.0)
        und_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:and|&)\s*(\d+(?:\.\d+)?)', waveband)
        if und_match:
            return 2
            
        match = re.search(r'(\d+)\s*(?:channels|bands|parts)', waveband)
        if match:
            return int(match.group(1))
        # Count segments
        if ';' in waveband or ',' in waveband:
            parts = [p for p in re.split(r'[;,]', waveband) if any(c.isdigit() for c in p)]
            if len(parts) > 1: return len(parts)

    # 3. Defaults
    mode = str(row.get('SensorMode', '')).upper()
    if mode == 'SAR': return 1
    if mode == 'PAN': return 1
    if mode == 'RF': return 1
    return None

def extract_spectral_range(row):
    name_desc = f"{str(row.get('Inst_Full_Name', ''))} {str(row.get('Inst_Description', ''))}"
    waveband = str(row.get('Waveband', ''))
    text = f"{name_desc} {waveband}"
    
    # 1. Radio bands
    match = re.search(r'\b([A-Za-z]+[- ]Band)\b', text, re.I)
    if match: return match.group(1).title()
    
    # 2. Wavelength ranges from Waveband
    if pd.notna(row.get('Waveband')) and str(row.get('Waveband')) != 'nan':
        wb = str(row.get('Waveband'))
        if ':' in wb: return wb.split(':')[0].strip()
        return wb[:60]
    
    # 3. Fallbacks
    for col in ['Char_Spectral_Range', 'Char_Spectral_range', 'Char_Band']:
        if col in row and pd.notna(row[col]): return str(row[col])
        
    return None

def transform_to_smu(source_file, target_template, output_file):
    print(f"Transforming {source_file} to SMU format...")
    df = pd.read_excel(source_file)
    
    # 1. Categorize Instruments
    unique_inst = df[['Inst_Full_Name', 'Inst_Description', 'Char_Operation_mode']].drop_duplicates().reset_index(drop=True)
    print(f"Found {len(unique_inst)} unique instrument configurations to categorize.")
    
    mapping_results = {}
    for idx, row in unique_inst.iterrows():
        name = row['Inst_Full_Name']
        desc = row['Inst_Description']
        op = row['Char_Operation_mode']
        if (idx + 1) % 10 == 0 or (idx + 1) == len(unique_inst):
            print(f"  Progress: {idx + 1}/{len(unique_inst)} categorized...")
        res = get_sensor_categories(name, desc, op)
        mapping_results[(name, desc, op)] = res

    # 2. Map Categorization Back
    df['SensorCategory'] = df.apply(lambda r: mapping_results.get((r['Inst_Full_Name'], r['Inst_Description'], r['Char_Operation_mode']), {}).get('category', 'Unknown'), axis=1)
    df['SensorClass'] = df.apply(lambda r: mapping_results.get((r['Inst_Full_Name'], r['Inst_Description'], r['Char_Operation_mode']), {}).get('class', 'Unknown'), axis=1)
    df['SensorMode'] = df.apply(lambda r: mapping_results.get((r['Inst_Full_Name'], r['Inst_Description'], r['Char_Operation_mode']), {}).get('mode', 'Unknown'), axis=1)
    df['SensorModeTechnique'] = df.apply(lambda r: mapping_results.get((r['Inst_Full_Name'], r['Inst_Description'], r['Char_Operation_mode']), {}).get('technique', 'Unknown'), axis=1)

    # 3. Extract Bands & Spectral Range
    print("Extracting Bands and Spectral Ranges...")
    df['Bands'] = df.apply(extract_bands, axis=1)
    df['SpectralRange'] = df.apply(extract_spectral_range, axis=1)

    # 4. Standard Field Mapping
    mapping = {
        'Sat_Full_Name': 'SatelliteName',
        'Sat_Acronym': 'SatelliteAcronym',
        'International Designator': 'IntDesignator',
        'NORAD Catalog #': 'SatelliteCatalogNumber',
        'Sat_Agency': 'ProviderName',
        'Inst_Full_Name': 'SensorName',
        'Sat_Altitude': 'Altitude_km',
        'Swath': 'SwathWidth_km_text',
        'Inst_Resolution': 'SpatialResClass'
    }
    
    df_smu = df.rename(columns=mapping)
    
    # 5. Technical Field Normalization
    df_smu['Altitude_km'] = df_smu['Altitude_km'].apply(extract_numeric)
    df_smu['SwathWidth_km'] = df_smu['SwathWidth_km_text'].apply(extract_numeric)
    df_smu['SpatialResAcross_m'] = df_smu['SpatialResClass'].apply(extract_numeric)
    
    # Constellation Logic
    if 'SatelliteName' in df_smu.columns:
        df_smu['ConstellationName'] = df_smu['SatelliteName'].apply(lambda x: str(x).split('-')[0].split(' ')[0] if pd.notna(x) else np.nan)

    # 6. Template Alignment
    template_cols = ['SatelliteName', 'IntDesignator', 'SatelliteCatalogNumber', 'ProviderName', 'ConstellationName', 'ClusterName', 'SubsetName', 'SensorName', 'SensorCategory', 'SensorClass', 'SensorMode', 'SensorModeTechnique', 'Bands', 'SpectralRange', 'Altitude_km', 'SpatialResAcross_m', 'SpatialResAlong_m', 'SpatialResClass', 'SwathWidth_km', 'SwathLength_km', 'FoRAcrossTrackLeft_deg', 'FoRAcrossTrackRight_deg', 'FoRAlongTrackFront_deg', 'FoRAlongTrackBack_deg', 'Comment', 'Taskable']
    
    for col in template_cols:
        if col not in df_smu.columns:
            df_smu[col] = np.nan
            
    df_smu = df_smu[template_cols]
    df_smu.to_excel(output_file, index=False)
    print(f"Success! Final SMU database saved to {output_file}")

if __name__ == "__main__":
    transform_to_smu('combined_satellite_data_strict.xlsx', '2026-02-24_Multi-SMU_database.xlsx', 'final_SMU_database.xlsx')
