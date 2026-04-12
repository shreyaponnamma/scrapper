# Satellite Data Mapping Report

This report summarizes the transformation logic used to convert merged OSCAR and CEOS data into the standardized **SMU Database Template**.

---

## 1. Current Implementation (Active)
These mappings are already implemented in `reformat_to_smu.py`.

| SMU Column | Source Column(s) | Transformation Logic |
| :--- | :--- | :--- |
| **SatelliteName** | `Sat_Full_Name` | Primary name from combined dataset. |
| **SatelliteAcronym** | `Sat_Acronym` | Short identifier for the satellite. |
| **IntDesignator** | `International Designator` | Standard international flight identifier. |
| **SatelliteCatalogNumber** | `NORAD Catalog #` | Public tracking ID (NORAD). |
| **ProviderName** | `Sat_Agency` | Organizations responsible for the mission. |
| **ConstellationName** | `Sat_Full_Name` | Currently extracted as the first word of the name. |
| **SensorName** | `Inst_Full_Name` | The full name of the primary instrument. |
| **SensorCategory** | `Inst_Full_Name`, `DS` | **Heuristic/LLM**: Categorized as `Active` or `Passive`. |
| **SensorClass** | `Inst_Full_Name`, `DS` | **Heuristic/LLM**: Categorized as `Radio` or `EO/IR`. |
| **SensorMode** | `Inst_Full_Name`, `DS` | **Heuristic/LLM**: `SAR`, `MSI`, `PAN`, `HSI`, `RF`, `AIS`, `ADS-B`. |
| **SensorModeTechnique** | `Inst_Full_Name`, `DS` | **Heuristic/LLM**: `Pushbroom`, `Stripmap`, `Whisk-Broom`, etc. |
| **Bands** | `Char_No._of_channels`, etc. | Aggregated numeric count of spectral bands. |
| **SpectralRange** | `Waveband`, `Char_Spectral` | Describes the wavelength or frequency band. |
| **Altitude_km** | `Sat_Altitude` | Normalized to a numeric integer/float. |
| **SpatialResAcross_m** | `Inst_Resolution` | Normalized numeric value in meters. |
| **SpatialResClass** | `Inst_Resolution` | Raw string describing the resolution class. |
| **SwathWidth_km** | `Swath` | Normalized numeric value in kilometers. |

---

## 2. Proposed Enhancements (Ready to Implement)
These mappings can be automated using existing data in the `combined_satellite_data_strict.xlsx` file.

| SMU Column | Source Column(s) | Proposed Transformation Logic |
| :--- | :--- | :--- |
| **FoRAcrossTrackLeft_deg**| `Char_Field_of_regard` | Parse values like "500 km". Use `arctan(dist/alt)` to convert distance to degrees. |
| **FoRAcrossTrackRight_deg**| `Char_Field_of_regard` | Same as Left (most sensors have symmetrical FoR). |
| **Taskable** | `Char_Field_of_regard` | Set to `True` if a non-null Field of Regard exists. |
| **SubsetName** | `Sat_Full_Name` | Extract suffixes like "N1", "A", or "B" from the satellite name. |
| **SpatialResAlong_m** | `Inst_Resolution` | Default to value of `SpatialResAcross_m` if no specific "Along-Track" data exists. |
| **SwathLength_km** | `Char_Swath` | Detect patterns like "7.3x3.1" and extract the first dimension. |
| **Comment** | `Char_Comment` | Direct mapping of technical notes from OSCAR. |

---

## 3. Future Roadmap (Manual or New Sources)
These columns remain unpopulated and would require deeper research or manual entry.

*   **ClusterName**: Often refers to specific mission clusters or groups not yet standardized in OSCAR/CEOS.
*   **FoRAlongTrack (Front/Back)**: Information on along-track steering (pitch) is significantly rarer than cross-track (roll) in public datasets.
*   **Resolution Detail**: Separating "Along-Track" from "Across-Track" resolution requires specific technical datasheets for every instrument if they aren't square.

---

> [!TIP]
> **Next Step**: I recommend updating `reformat_to_smu.py` to include the **Section 2** enhancements to significantly increase the data density of your final Excel output.
