# Documentation & Data Mapping

## Overview
The goal of this project is to unify satellite mission data from two primary sources:
1.  **CEOS (Committee on Earth Observation Satellites)**: Detailed mission and instrument handbook.
2.  **WMO OSCAR (Observing Systems Capability Analysis and Review Tool)**: Comprehensive satellite status and observation capabilities.
3.  **Skyrocket Space Launch Chronicle**: Auxiliary source used to enrich the database with recent satellite launch records (specifically target series like ICEYE and Elektro).

## Unified Schema
All sources are transformed into a standard format (often referred to as "Multi-SMU Style") before merging.

### Definition: Multi-SMU Style
The **Multi-SMU (Satellite Mission Unit)** style is a flattened data schema used to handle "one-to-many" relationships. In this format:
- Every row represents a unique combination of **Satellite + Instrument**.
- If a satellite has 5 instruments, it will have 5 rows in the data, each containing the same satellite metadata but unique instrument specs.
- This ensures the dataset is compatible with standard spreadsheet analysis tools without requiring nested data structures.

### Satellite Fields
| Unified Name | Description |
| :--- | :--- |
| `Sat_Full_Name` | Complete mission name (e.g., "Sentinel-1A") |
| `Sat_Acronym` | Short name (e.g., "S1A") |
| `Sat_Agency` | Main operating agency (e.g., "ESA") |
| `Sat_Status` | Current operational state (Operational, Decayed, etc.) |
| `Sat_Launch` | Launch date |
| `Sat_EOL` | End-of-life/Decommission date |
| `Sat_Altitude` | Operational orbit altitude (in km) |

### Instrument Fields
| Unified Name | Description |
| :--- | :--- |
| `Inst_Full_Name` | Detailed instrument name |
| `Inst_Acronym` | Instrument short name (e.g., "SAR") |
| `Inst_Description`| Free-text description of capabilities |
| `Inst_Waveband` | Spectral bands covered |

## Merge Logic
The integration process uses a hybrid approach:
1.  **Fuzzy Name Matching**: Standardizes names (removing spaces, case-folding) and uses `difflib.SequenceMatcher` to find candidates.
2.  **Timeline Filtering**: Compares launch and EOL dates to ensure matched satellites are temporal successors or the same unit.
3.  **LLM Verification**: Highly ambiguous cases are sent to a local LLM (defaults to `llama3.2:1b`) with a prompt to decide if Entity A and Entity B refer to the same satellite or instrument.

Additionally, the **Skyrocket Scraper** uses a direct merge pattern to enrich the final database:
- It scrapes launched satellites from target series.
- It validates the COSPAR IDs (filtering out planned, failed, or TBD launches).
- It checks if the satellite name or COSPAR ID already exists in the merged database (`instrument_level_merge.xlsx`).
- If not present, it appends the new record directly with `Merge_Source` marked as `'Skyrocket'`.

## Data Lineage
- `data/raw/`: Scraped HTML tables saved as Excel/CSV.
- `data/processed/`: Intermediate files with standardized column names and numeric extraction.
- `data/final/`: The source-of-truth merged file.

## Legacy Code
Old versions of scripts, experimental logic, and alternative reformatting attempts are preserved in `scripts/legacy/`. These are not part of the main pipeline but are kept for reference to ensure no logic is lost during the cleanup.

## Related Docs
- [Code Walkthrough](CODE_WALKTHROUGH.md)
- [Handover Guide](HANDOVER_GUIDE.md)
- [Setup Guide](SETUP.md)

