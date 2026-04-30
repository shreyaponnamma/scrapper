# Satellite Data Processing - Workspace Documentation

This document provides a comprehensive overview of the satellite data pipeline, the Python scripts responsible for each processing stage, and the resulting Excel datasets.

## 1. Data Collection Phase (Scrapers)
These scripts retrieve raw data from the official CEOS and WMO OSCAR websites.

| Script Name | Resulting Excel | Content Description |
| :--- | :--- | :--- |
| `scraper.py` | `satellite_data_full.xlsx` | **Raw CEOS MIM Data**: Contains mission names, agencies, status, and raw resolution/swath text. |
| `scraper_wmo.py` | `oscar_satellite_data_full_perfection.xlsx` | **Raw OSCAR Data**: The most detailed dataset containing 188 instrument-specific characterization columns. |

---

## 2. Reformatting & Standardization Phase
These scripts transform raw, unstructured text into the standardized **26-column SMU schema**.

| Script Name | Resulting Excel | Transformation Details |
| :--- | :--- | :--- |
| `reformat_ceos_to_smu.py` | `ceos_reformatted_to_smu.xlsx` | Splits CEOS rows by mode. Separates Across/Along resolution and maps spectral ranges to categorical designations (VIS, NIR, etc.). |
| `reformat_oscar_to_smu.py` | `oscar_reformatted_to_smu.xlsx` | Maps the 188 raw OSCAR attributes into the 26 SMU columns. Extracts SNR, NEDT, and accuracy data. |

---

## 3. Enrichment Phase (AI / LLM)
These scripts use the **Ollama (Llama 3.2)** model to fill in missing gaps in the data.

| Script Name | Resulting Excel | Purpose |
| :--- | :--- | :--- |
| `enrich_with_llm.py` | `ceos_enriched_llm.xlsx` | Applies LLM logic to fill missing resolution and spectral data for a subset of CEOS missions. |
| `enrich_all_llm.py` | `ceos_enriched_llm_full.xlsx` | Complete AI enrichment for the entire CEOS dataset. |

---

## 4. Merging & Final Database Construction
These scripts combine data from multiple sources to create a unified satellite database.

| Script Name | Resulting Excel | Logic |
| :--- | :--- | :--- |
| `ultimate_smu_merge.py` | **`satellite_database_master.xlsx`** | **Primary Final Database**: Merges `ceos_enriched_llm_full.xlsx` and `oscar_reformatted_to_smu.xlsx`. Uses CEOS as the base and enriches it with OSCAR instrument details. |
| `hybrid_combine_sat_data.py` | `combined_satellite_data_strict.xlsx` | Creates a comprehensive hybrid file by performing a strict match between satellites in both databases. |
| `reformat_to_smu.py` | `final_SMU_database.xlsx` | Takes a combined hybrid file and reformats it using the ground truth template (`2026-02-24_Multi-SMU_database.xlsx`) as a reference. |

---

## 5. Audit & Comparison Tools
Used to verify the accuracy of the generated data against references.

| Script Name | Purpose |
| :--- | :--- |
| `compare_reports.py` | Audits the overlap between reformatted files and the ground truth template. |
| `scripts/accuracy_benchmark.py` | Calculates the precision of extracted values compared to manually verified data. |

## Summary of Reference Files
*   **`2026-02-24_Multi-SMU_database.xlsx`**: The original Ground Truth template provided for schema and formatting reference.
