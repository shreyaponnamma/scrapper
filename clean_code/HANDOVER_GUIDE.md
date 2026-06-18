# Handover Guide

This document is the maintainer-facing handover for the satellite scraping project. It is written for someone who is new to the codebase and needs enough context to run, debug, and extend the pipeline without asking the original author for clarification.

## 1. Project Purpose

The project collects satellite and instrument metadata from two sources and turns them into standardized Excel outputs:

- CEOS mission handbook data
- WMO OSCAR satellite data

The workflow is designed to:

- scrape source websites
- normalize the source-specific fields into a common schema
- merge the datasets into final outputs
- optionally use a local Ollama model to help resolve ambiguous matches

The final outputs are intended for spreadsheet analysis and downstream data processing.

## 2. Repository Layout

The current code is organized as follows:

- `main.py` - CLI entry point that runs the pipeline stages
- `scripts/scrapers/` - web scrapers for CEOS and WMO OSCAR
- `scripts/processing/` - standardization scripts that align source data into a shared schema
- `scripts/integration/` - merge scripts that combine the processed datasets
- `scripts/utils/` - shared configuration
- `scripts/legacy/` - archived previous versions and experimental variants
- `data/raw/` - raw scraper outputs
- `data/processed/` - standardized intermediate files
- `data/final/` - final merged outputs

## 3. How the Pipeline Works

The pipeline has four conceptual stages:

### Stage 1: Scraping
The scraper scripts fetch data from the upstream source websites and write the raw outputs into `data/raw/`.

### Stage 2: Standardization
The processing scripts map source-specific column names into a common schema and clean values such as names, dates, and numeric fields.

### Stage 3: Integration
The merge scripts load the standardized datasets, compare records using fuzzy matching and date checks, and write the merged outputs into `data/final/`.

### Stage 4: Review and maintenance
The documentation, configuration, and legacy scripts are there to help future maintainers understand the decisions and reproduce the pipeline.

## 4. Script Inventory

### `main.py`
Entry point for the command line.

Supported flags:

- `--scrape` - run both scrapers
- `--process` - run both standardization scripts
- `--merge` - run both merge scripts
- `--all` - run the entire pipeline from scratch

Important behavior:

- scripts are launched as subprocesses
- the orchestrator prints a failure if one script exits non-zero
- the current implementation does not stop the remaining stages automatically after a failure
- if you are debugging a failure, inspect the terminal output from the first script that failed

### `scripts/utils/config.py`
Central configuration file.

It defines:

- the project base directory
- raw/processed/final file locations
- the Ollama endpoint
- the default Ollama model
- fuzzy matching thresholds

This file is the first place to update if output paths, filenames, or the model change.

### `scripts/scrapers/ceos_scrapper.py`
Scrapes CEOS mission pages.

Inputs:

- CEOS mission index page
- individual mission pages

Outputs:

- raw CEOS spreadsheet in `data/raw/`

What it extracts:

- mission names
- agencies
- launch and end-of-life dates
- orbit details
- instrument fields and descriptions

Notes:

- it relies on page structure and selectors from the CEOS site
- if the site HTML changes, selector updates will likely be needed
- this script can take a long time because it visits many mission pages

### `scripts/scrapers/wmo_oscar_scrapper.py`
Scrapes the WMO OSCAR portal.

Inputs:

- WMO OSCAR satellites page

Outputs:

- raw OSCAR spreadsheet in `data/raw/`

What it extracts:

- satellite metadata
- instrument metadata
- fields exposed through the OSCAR portal

Notes:

- it uses Playwright because the page is dynamically rendered
- it scrolls through a long table to collect all entries
- browser installation and system dependencies must be available

### `scripts/processing/standardize_ceos.py`
Standardizes the raw CEOS export.

It typically:

- renames source columns to the shared schema
- adds missing standard columns
- normalizes numeric values
- writes `data/processed/ceos_standardized.xlsx`

### `scripts/processing/standardize_oscar.py`
Standardizes the raw OSCAR export.

It typically:

- aligns OSCAR columns with the shared schema
- cleans date and text fields
- writes `data/processed/oscar_standardized.xlsx`

### `scripts/integration/unified_merge.py`
Performs the main merge across the standardized files.

It typically:

- loads both processed datasets
- normalizes names for comparison
- applies fuzzy matching
- filters matches with date logic
- optionally asks Ollama about ambiguous cases
- writes `data/final/merged_satellite_data_complete.xlsx`

### `scripts/integration/instrument_merge.py`
Produces the instrument-level merge.

It typically:

- keeps the merge focused on instrument-bearing rows
- preserves the most useful satellite and instrument fields
- writes `data/final/instrument_level_merge.xlsx`

## 5. Important Data Contracts

The shared schema is the main contract between scripts.

Key satellite columns:

- `Sat_Full_Name`
- `Sat_Acronym`
- `Sat_Agency`
- `Sat_Status`
- `Sat_Launch`
- `Sat_EOL`
- `Sat_Altitude`

Key instrument columns:

- `Inst_Full_Name`
- `Inst_Acronym`
- `Inst_Description`
- `Inst_Waveband`

If you change any of these names, update every downstream script that reads standardized files.

## 6. Matching Logic

The merge process uses a layered approach:

1. Normalize names by removing punctuation and common terms.
2. Score candidate matches with fuzzy matching.
3. Use launch and end-of-life dates to reject incompatible matches.
4. Query the local LLM when the result is still ambiguous.

This design keeps the common cases fast while reserving the model for difficult matches.

## 7. Configuration Notes

A new maintainer should know these details:

- the project currently defaults to `llama3.2:1b`
- the Ollama server is expected at `http://localhost:11434`
- raw, processed, and final output folders are created automatically if they do not exist
- `OSCAR_RAW_JSON` exists in config as a placeholder, but the current pipeline writes Excel outputs

## 8. Runtime Expectations

Typical operational expectations:

- scraping is the slowest stage
- the first full scrape can take a long time because each source page is visited
- the pipeline depends on network availability
- the merge stage depends on processed input files being present

If a stage fails, validate the upstream stage first. Most merge problems are caused by missing or malformed processed files.

## 9. Troubleshooting Checklist

If the pipeline fails, check in this order:

1. Is the Python environment activated?
2. Are the required packages installed from `requirements.txt`?
3. Did Playwright browsers install successfully?
4. Are the raw files present in `data/raw/`?
5. Did the processing scripts generate files in `data/processed/`?
6. Are the standardized files missing expected columns?
7. Is Ollama running if the merge stage uses it?
8. Did a scraper site change its HTML or table structure?

## 10. How to Extend the Project

### Add a new source

- create a new scraper in `scripts/scrapers/`
- standardize it in `scripts/processing/`
- decide whether it should be included in the merge stage
- update the docs and config to explain the new source

### Change the final schema

- update the standardizer scripts
- update the merge scripts
- update the documentation tables in `DOCUMENTATION.md`
- update any downstream consumers that expect the old column names

### Change the LLM model

- edit `OLLAMA_MODEL` in `scripts/utils/config.py`
- document the reason for the model change if it affects output quality or speed

## 11. Legacy Code

The `scripts/legacy/` folder is an archive of older versions and experimental code paths.

Use it for reference only. It is useful for understanding how the project evolved, but it should not be treated as the active pipeline.

## 12. Handover Summary

If someone new is taking over this project, the minimum reading order should be:

1. `README.md`
2. `SETUP.md`
3. `CODE_WALKTHROUGH.md`
4. `HANDOVER_GUIDE.md`
5. `DOCUMENTATION.md`
6. `scripts/utils/config.py`

That sequence gives a new maintainer enough context to install the environment, understand the pipeline, and maintain the code safely.
