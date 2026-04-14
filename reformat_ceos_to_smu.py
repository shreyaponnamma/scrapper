import pandas as pd
import numpy as np
import re
import os

def parse_resolutions(res_text):
    """
    Extracts numerical resolutions from text sentences.
    Robustly handles modes and range patterns while explicitly ignoring µm (wavelengths).
    """
    if pd.isna(res_text) or str(res_text).lower() == 'n/a' or str(res_text).strip() == '':
        return [(np.nan, np.nan, 'Standard')]
    
    res_text = str(res_text).lower()
    results = []

    # 1. Clean the text manually to remove patterns that cause false positives
    clean_text = re.sub(r'0\.\d+\s*(?:-|to)\s*0\.\d+\s*[µ\xb5u]m', '', res_text)
    clean_text = re.sub(r'\d+(?:\.\d+)?\s*[µ\xb5u]m', '', clean_text)
    clean_text = re.sub(r'\d+(?:\.\d+)?\s*nm', '', clean_text)
    clean_text = re.sub(r'0\.\d+\s*(?:-|to)\s*0\.\d+\b', '', clean_text) 
    clean_text = re.sub(r'\b0\.\d+(?!\s*m)\b', '', clean_text) 
    clean_text = re.sub(r'(\d+),(\d+)\s*m', r'\1.\2m', clean_text)

    # 2. Handle specific "Along x Across" or "Cross x Along" text patterns
    along_cross = re.search(r'(\d+(?:\.\d+)?)\s*km\s*along-track\s*[x×]\s*(\d+(?:\.\d+)?)\s*km\s*cross-track', clean_text)
    if along_cross:
        results.append((float(along_cross.group(2))*1000, float(along_cross.group(1))*1000, 'Standard'))

    # 3. Handle specific "[range x azimuth]" pattern (Range = Across, Azimuth = Along)
    if '[range x azimuth]' in clean_text:
        pairs = re.findall(r'(\d+(?:\.\d+)?)\s*[x×]\s*(\d+(?:\.\d+)?)(?!\s*km)', clean_text)
        for x, y in pairs:
            results.append((float(x), float(y), 'Standard'))

    # 4. Handle "XX x YY km" or "XX x YY m"
    km_pairs = re.findall(r'(\d+(?:\.\d+)?)\s*[x×]\s*(\d+(?:\.\d+)?)\s*km', clean_text)
    for x, y in km_pairs:
        results.append((float(x)*1000, float(y)*1000, 'Standard'))
    
    m_pairs = re.findall(r'(\d+(?:\.\d+)?)\s*[x×]\s*(\d+(?:\.\d+)?)\s*m\b', clean_text)
    for x, y in m_pairs:
        results.append((float(x), float(y), 'Standard'))

    # 5. Handle modes like "Spotlight: 1m"
    all_mode_matches = re.findall(r'(\w+(?:\s+\w+)?)\s+(?:mode|more)\s*\(?([\d\s\w\.,tm-]+)\)?', clean_text)
    all_mode_matches += re.findall(r'(\w+(?:\s+\w+)?):\s*([\d\s\w\.,tm-]+)(?=\.|$|\s+\w+:)', clean_text)
    
    for mode_name, res_part in all_mode_matches:
        mode_name = mode_name.strip().capitalize()
        # Look for dimensional pairs within mode first
        mode_pairs = re.findall(r'(\d+(?:\.\d+)?)\s*[x×]\s*(\d+(?:\.\d+)?)(?!\s*km)', res_part)
        if mode_pairs:
            for x, y in mode_pairs:
                results.append((float(x), float(y), mode_name))
        else:
            nums = re.findall(r'(\d+(?:\.\d+)?)\s*m\b', res_part)
            for n in nums:
                results.append((float(n), float(n), mode_name))

    # 6. Fallback: Range patterns "1.2m-3.6m"
    range_matches = re.findall(r'(\d+(?:\.\d+)?)\s*(?:-|to)\s*(\d+(?:\.\d+)?)\s*m', clean_text)
    for low, high in range_matches:
        results.append((float(low), float(low), 'High-Res'))
        results.append((float(high), float(high), 'Standard'))

    # 7. Final fallback: single "Xm"
    list_pattern = re.findall(r'\b(\d+(?:\.\d+)?)\s*m\b', clean_text)
    for val in list_pattern:
        v = float(val)
        results.append((v, v, 'Standard'))
    
    # 8. Best Resolution tag
    best_match = re.search(r'\[best resolution:\s*(\d+(?:\.\d+)?)\s*m\]', clean_text)
    if not results and best_match:
        val = float(best_match.group(1))
        results.append((val, val, 'Standard'))

    if not results:
        return [(np.nan, np.nan, 'Standard')]
    
    # Deduplicate while preserving order for stability
    unique_results = []
    seen = set()
    for r in results:
        if r not in seen:
            unique_results.append(r)
            seen.add(r)
            
    return unique_results

    if not results:
        return [(np.nan, np.nan, 'Standard')]
    
    # Deduplicate and sort by resolution (best first)
    unique_results = []
    seen = set()
    for r in sorted(results, key=lambda x: x[0] if not np.isnan(x[0]) else 9999):
        if r not in seen:
            unique_results.append(r)
            seen.add(r)
            
    return unique_results

def parse_swath(swath_text, target_mode=None):
    """
    Extracts swath width in km. 
    If a mode is provided, it tries to find the swath for that specific mode.
    """
    if pd.isna(swath_text) or str(swath_text).lower() == 'n/a':
        return np.nan
    
    text = str(swath_text).lower()
    
    # 1. If we have a specific mode (like Spotlight), look for "Spotlight mode: XXkm"
    if target_mode and target_mode != 'Standard':
        mode_swath = re.search(rf'{target_mode.lower()}\s*(?:mode)?:\s*(\d+(?:\.\d+)?)\s*km', text)
        if mode_swath:
            return float(mode_swath.group(1))

    # 2. Look for [Max Swath: XX km]
    max_match = re.search(r'\[max swath:\s*(\d+(?:\.\d+)?)\s*km\]', text)
    if max_match:
        return float(max_match.group(1))
        
    # 3. Fallback to any number followed by km
    all_km = re.findall(r'(\d+(?:\.\d+)?)\s*km', text)
    if all_km:
        return max([float(x) for x in all_km])
        
    return np.nan

def parse_bands(waveband_text):
    """Extracts band counts or specific designations (L-band, VIS) for the Bands column."""
    if pd.isna(waveband_text) or str(waveband_text).lower() == 'n/a':
        return np.nan
    text = str(waveband_text)
    bands = []
    
    # 1. Look for explicit counts like "36 bands"
    band_counts = re.findall(r'(\d+)\s*bands', text, re.I)
    if band_counts:
        bands.append(f"{band_counts[0]} bands")
    
    return ", ".join(bands) if bands else np.nan

def clean_spectral_range(waveband_text):
    """
    Cleans up the SpectralRange entries to match SMU ground truth format.
    Format: VIS, NIR, Red-Edge, SWIR, MWIR, TIR, UV, or X-band, L-band etc.
    NO numerical µm/nm values in this column.
    """
    if pd.isna(waveband_text) or str(waveband_text).lower() == 'n/a':
        return np.nan
    
    text = str(waveband_text)
    found = []
    
    # Standard SMU designations
    designations = {
        'Panchromatic': 'Panchromatic',
        'VIS': 'VIS',
        'Visible': 'VIS',
        'NIR': 'NIR',
        'Near-IR': 'NIR',
        'Near Infrared': 'NIR',
        'SWIR': 'SWIR',
        'Short-wave IR': 'SWIR',
        'MWIR': 'MWIR',
        'Mid-wave IR': 'MWIR',
        'TIR': 'TIR',
        'Thermal IR': 'TIR',
        'LWIR': 'TIR',
        'UV': 'UV',
        'Ultra-violet': 'UV',
        'Red-Edge': 'Red-Edge',
        'Hyperspectral': 'Hyperspectral',
        'L-band': 'L-band',
        'X-band': 'X-band',
        'C-band': 'C-band',
        'S-band': 'S-band',
        'P-band': 'P-band',
        'Ka-band': 'Ka-band',
        'Ku-band': 'Ku-band'
    }
    
    for key, val in designations.items():
        if re.search(rf'\b{key}\b', text, re.I):
            found.append(val)
            
    # Also handle numeric frequencies/wavelengths by mapping them to designations if necessary
    # Example: If it says 0.4 - 0.7 um, its VIS
    if not found:
        if re.search(r'0\.[4-7]\d*\s*[µu]m', text): found.append('VIS')
        if re.search(r'0\.[7-9]\d*\s*[µu]m|1\.[0-4]\d*\s*[µu]m', text): found.append('NIR')
        if re.search(r'1\.[5-9]\d*\s*[µu]m|2\.[0-5]\d*\s*[µu]m', text): found.append('SWIR')
        if re.search(r'8\s*-\s*12\s*[µu]m', text): found.append('TIR')

    if found:
        return ", ".join(list(dict.fromkeys(found)))
        
    return np.nan

def parse_for(row):
    """
    Attempts to extract Field of Regard (FoR) or field of view angles.
    Improved for off-nadir, pointing, and scan angles.
    """
    left, right, front, back = np.nan, np.nan, np.nan, np.nan
    # Focus on Swath and Accuracy columns where pointing info usually resides
    text = str(row.get('Swath', '')).lower() + " " + str(row.get('Accuracy', '')).lower()
    
    # 1. Look for explicit +/- XX.X degrees or +/-XX degrees
    pm_match = re.search(r'[±\+/-]\s*(\d+(?:\.\d+)?)\s*(?:deg|degrees)', text)
    if pm_match:
        val = float(pm_match.group(1))
        return val, val, np.nan, np.nan
    
    # 2. Look for "Agile platform giving ±50 deg" or "pointing ±35°"
    pointing_match = re.search(r'pointing\s*[±\+/-]\s*(\d+(?:\.\d+)?)\s*(?:deg|degrees)', text)
    if not pointing_match:
        pointing_match = re.search(r'off-track\s*[±\+/-]\s*(\d+(?:\.\d+)?)\s*(?:deg|degrees)', text)
    if not pointing_match:
        pointing_match = re.search(r'±\s*(\d+(?:\.\d+)?)\s*(?:deg|degrees)', text)
        
    if pointing_match:
        val = float(pointing_match.group(1))
        return val, val, np.nan, np.nan

    # 3. Handle specific tilt to one side (e.g. "tilt 12.2 deg to the west")
    tilt_match = re.search(r'tilt\s*(\d+(?:\.\d+)?)\s*(?:deg|degrees)', text)
    if tilt_match:
        val = float(tilt_match.group(1))
        # If it's a pull to one side, we assume it can look that far
        return val, val, np.nan, np.nan

    # 4. Handle "Scan +/- 20.3 deg"
    scan_match = re.search(r'scan\s*[±\+/-]\s*(\d+(?:\.\d+)?)\s*(?:deg|degrees)', text)
    if scan_match:
        val = float(scan_match.group(1))
        return val, val, np.nan, np.nan

    # 5. Handle "nadir only"
    if 'nadir' in text and not any(x in text for x in ['tilt', 'pointing', '±']):
        return 0.0, 0.0, 0.0, 0.0
        
    return left, right, front, back

def parse_swath(swath_text, target_mode=None):
    """
    Extracts swath width and length in km. 
    Handles patterns like "50 km x 50 km" or "10x10 km".
    """
    if pd.isna(swath_text) or str(swath_text).lower() == 'n/a':
        return np.nan, np.nan
    
    text = str(swath_text).lower()
    width, length = np.nan, np.nan
    
    # 1. Search for specific mode prefix if provided (e.g., Spotlight: 10x10 km)
    focused_text = text
    if target_mode and target_mode != 'Standard':
        mode_esc = re.escape(target_mode.lower())
        mode_match = re.search(rf'{mode_esc}\D*?([\d\s\.x×by,-]+?)\s*km', text)
        if mode_match:
            focused_text = mode_match.group(1)

    # 2. Look for X by Y patterns
    cross_match = re.search(r'(\d+(?:\.\d+)?)\s*[x×by]+\s*(\d+(?:\.\d+)?)\s*km', focused_text)
    if cross_match:
        width = float(cross_match.group(1))
        length = float(cross_match.group(2))
    else:
        # 3. Look for [Max Swath: XX km]
        max_match = re.search(r'\[max swath:\s*(\d+(?:\.\d+)?)\s*km\]', text)
        if max_match:
            width = float(max_match.group(1))
        else:
            # 4. Fallback to any number followed by km
            all_km = re.findall(r'(\d+(?:\.\d+)?)\s*km', text)
            if all_km:
                width = float(all_km[0])
                
    return width, length

def infer_sensor_info(inst_name, waveband, current_mode_guess):
    """
    Infers SensorCategory, SensorClass, SensorMode, and SensorModeTechnique 
    based on the Ground Truth schema (Radio/Optical/Spectrometer).
    """
    category = "Passive"
    sensor_class = "Optical"
    mode = "Standard"
    technique = "Imager"
    
    inst = str(inst_name).lower()
    wv = str(waveband).lower()
    text = inst + " " + wv
    mode_guess = str(current_mode_guess).lower()
    
    # Determine Class & Mode first
    if any(k in text for k in ['sar', 'radar', 'altimeter', 'scatterometer', 'active', 'microwave', 'palsar', 'ais', 'ro ', 'gnss']):
        category = "Active" if not any(x in text for x in ['ais', 'ro ', 'gnss']) else "Passive"
        sensor_class = "Radio"
        if any(x in text for x in ['radar', 'sar', 'palsar']):
            mode = "SAR"
        elif 'ais' in text:
            mode = "AIS"
        elif any(x in text for x in ['ro ', 'gnss']):
            mode = "Occultation"
    elif any(k in text for k in ['lidar', 'laser', 'icesat']):
        category = "Active"
        sensor_class = "Lidar"
    elif any(k in text for k in ['hyperspectral', 'spectrometer', 'sounding', 'spectral', 'cris', 'iasi', 'airs']):
        sensor_class = "Spectrometer"
        technique = "Sounder" if 'sound' in text else "Pushbroom"
    elif any(k in text for k in ['microwave radiator', 'mhs', 'amsub', 'atms']):
        sensor_class = "Microwave Radiometer"
        technique = "Sounder"

    # Determine Technique based on Class & Mode
    if sensor_class == "Radio":
        if mode == "SAR":
            if 'spotlight' in mode_guess: technique = "Spotlight"
            elif 'stripmap' in mode_guess: technique = "Stripmap"
            elif 'scan' in mode_guess: technique = "ScanSAR"
            elif 'fine' in mode_guess: technique = "Fine"
            else: technique = "SAR"
        elif mode in ["AIS", "Occultation"]:
            technique = "Receiver"

    # 3. Final refinement: If mode_guess was something specific, use it for mode/technique if empty
    if mode == "Standard" and mode_guess != "standard" and mode_guess != "nan":
        mode = mode_guess.capitalize()

    return category, sensor_class, mode, technique

def get_res_class(res):
    """Categorizes resolution into classes."""
    if pd.isna(res): return np.nan
    if res <= 1: return "Very High"
    if res <= 5: return "High"
    if res <= 30: return "Medium"
    return "Low"

def reformat_ceos_to_smu(input_path, output_path):
    print(f"Reading {input_path}...")
    df = pd.read_excel(input_path)
    
    smu_records = []
    
    for _, row in df.iterrows():
        # 1. Extract resolutions (returns list of tuples (across, along, mode))
        resolutions = parse_resolutions(row.get('Resolution', ''))
        
        # 3. Clean Agency (take first one if multiple)
        agency = str(row.get('Mission Agencies', 'N/A')).split('/')[0].strip()
        
        # 4. Extract numeric altitude
        altitude = np.nan
        alt_text = str(row.get('Orbit Altitude', ''))
        alt_match = re.search(r'(\d+(?:\.\d+)?)', alt_text)
        if alt_match:
            altitude = float(alt_match.group(1))

        # 5. Extract Bands
        waveband_raw = row.get('Waveband', '')
        # Check if this is a Radio/Radar sensor - for these, SMU SpectralRange is usually blank
        # Use a preliminary pass to see if it's Radio
        cat, s_class, _, _ = infer_sensor_info(
            row.get('Instrument Full Name', ''), 
            waveband_raw,
            'standard'
        )
        
        bands = parse_bands(waveband_raw)
        # If it's a Radio sensor (SAR/Radar), SMU usually leaves SpectralRange empty (N/A)
        # unless it's a specifically listed frequency.
        if s_class == "Radio":
            spectral_range = np.nan
        else:
            spectral_range = clean_spectral_range(waveband_raw)
        
        # 6. Extract Field of Regard (FoR)
        for_l, for_r, for_f, for_b = parse_for(row)

        # Create a row for each resolution found
        for res_across, res_along, mode_guess in resolutions:
            # 2. Extract swath (mode-specific if possible)
            swath_w, swath_l = parse_swath(row.get('Swath', ''), target_mode=mode_guess)
            
            # Infer details based on mode discovered during resolution parsing
            cat, s_class, final_mode, tech = infer_sensor_info(
                row.get('Instrument Full Name', ''), 
                row.get('Waveband', ''),
                mode_guess
            )
            
            # Apply Satellite Name Cleaning (Remove only the " Mission" suffix, preserving full names)
            sat_name = str(row.get('Satellite Full Name', 'N/A'))
            sat_name = re.sub(r'\s+Mission$', '', sat_name, flags=re.I)
            
            # Apply Sensor Name Cleaning (Remove " Instrument" suffix)
            sensor_name = str(row.get('Instrument Full Name', 'N/A'))
            sensor_name = re.sub(r'\s+Instrument$', '', sensor_name, flags=re.I)
            
            smu_row = {
                'SatelliteName': sat_name,
                'IntDesignator': row.get('International Designator', np.nan),
                'SatelliteCatalogNumber': row.get('NORAD Catalog #', np.nan),
                'ProviderName': agency,
                'ConstellationName': np.nan, 
                'ClusterName': np.nan,
                'SubsetName': np.nan,
                'SensorName': sensor_name,
                'SensorCategory': cat,
                'SensorClass': s_class,
                'SensorMode': final_mode,
                'SensorModeTechnique': tech,
                'Bands': bands, 
                'SpectralRange': spectral_range,
                'Altitude_km': altitude,
                'SpatialResAcross_m': res_across,
                'SpatialResAlong_m': res_along,
                'SpatialResClass': get_res_class(res_across),
                'SwathWidth_km': swath_w,
                'SwathLength_km': swath_l,
                'FoRAcrossTrackLeft_deg': for_l,
                'FoRAcrossTrackRight_deg': for_r,
                'FoRAlongTrackFront_deg': for_f,
                'FoRAlongTrackBack_deg': for_b,
                'Comment': f"Waveband: {waveband_raw} | Res: {row.get('Resolution', '')}",
                'Taskable': 'Y' if 'operational' in str(row.get('Mission Status', '')).lower() else 'N'
            }
            smu_records.append(smu_row)

    # Convert to DataFrame
    smu_df = pd.DataFrame(smu_records)
    
    # Ensure specific column order matching the Ground Truth
    target_cols = [
        'SatelliteName', 'IntDesignator', 'SatelliteCatalogNumber', 'ProviderName',
        'ConstellationName', 'ClusterName', 'SubsetName', 'SensorName',
        'SensorCategory', 'SensorClass', 'SensorMode', 'SensorModeTechnique',
        'Bands', 'SpectralRange', 'Altitude_km', 'SpatialResAcross_m',
        'SpatialResAlong_m', 'SpatialResClass', 'SwathWidth_km', 'SwathLength_km',
        'FoRAcrossTrackLeft_deg', 'FoRAcrossTrackRight_deg',
        'FoRAlongTrackFront_deg', 'FoRAlongTrackBack_deg', 'Comment', 'Taskable'
    ]
    
    smu_df = smu_df[target_cols]
    
    print(f"Reformatted {len(df)} rows into {len(smu_df)} SMU rows.")
    smu_df.to_excel(output_path, index=False)
    print(f"Success! File saved to {output_path}")

if __name__ == "__main__":
    INPUT_FILE = "/home/shreya/projects/scrapper/satellite_data_full.xlsx"
    OUTPUT_FILE = "/home/shreya/projects/scrapper/ceos_reformatted_to_smu.xlsx"
    
    if os.path.exists(INPUT_FILE):
        reformat_ceos_to_smu(INPUT_FILE, OUTPUT_FILE)
    else:
        print(f"Error: Could not find {INPUT_FILE}")
