# Code Walkthrough

This document explains how the code is organized, what each major script does, and how data moves through the pipeline. It is meant for a developer who is taking over the project and needs to understand the implementation, not just the setup steps.

## 1. What the project does

The project collects satellite and instrument data from two external sources:

- CEOS mission handbook data
- WMO OSCAR satellite data

The code then:

- scrapes the source pages
- standardizes the columns into one schema
- merges the datasets into final outputs
- optionally uses a local Ollama model to help resolve ambiguous matches

The main goal is to produce a clean, flattened dataset that can be used in spreadsheets or downstream analysis.

## 2. Main code flow

The intended execution order is:

1. `scripts/scrapers/ceos_scrapper.py`
2. `scripts/scrapers/wmo_oscar_scrapper.py`
3. `scripts/processing/standardize_ceos.py`
4. `scripts/processing/standardize_oscar.py`
5. `scripts/integration/unified_merge.py`
6. `scripts/integration/instrument_merge.py`

The orchestrator in `main.py` can run these steps from the command line.

## 3. Directory roles

### `data/raw/`
Raw source exports from the scrapers. These are the first files written by the pipeline.

### `data/processed/`
Standardized versions of the raw exports. This is where source-specific column names are mapped to the shared schema.

### `data/final/`
Final merged outputs. These are the files a downstream user should consume.

### `scripts/scrapers/`
Web scraping logic for the source websites.

### `scripts/processing/`
Normalization and schema-alignment code.

### `scripts/integration/`
Matching and merging logic.

### `scripts/utils/`
Shared constants and configuration.

### `scripts/legacy/`
Preserved older versions of scripts and experimental code. These are kept for reference and should not be treated as the current pipeline entry points.

## 4. Script reference

### `main.py`
The command-line entry point. It accepts flags such as `--scrape`, `--process`, `--merge`, and `--all`.

What it does:

- runs the requested pipeline stage(s)
- launches the individual scripts as subprocesses
- keeps the project runnable from a single command

What to know:

- it does not contain the business logic itself
- it assumes the project root is on `PYTHONPATH`
- it is the easiest place to start if you want to understand runtime order

### `scripts/utils/config.py`
Central configuration file.

It defines:

- base directories
- raw/processed/final output paths
- Ollama endpoint and model name
- fuzzy matching threshold values

Why it matters:

- if a path changes, update it here first
- if the LLM model changes, update it here first
- this file is the single source of truth for pipeline settings

### `scripts/scrapers/ceos_scrapper.py`
Scrapes mission and instrument details from the CEOS handbook site.

What it produces:

- a raw Excel file containing CEOS mission data

Key behavior:

- collects mission links from the CEOS index page
- opens each mission page and extracts structured fields
- handles nested details like mission metadata and instruments
- writes the raw CEOS dataset to the raw data folder

Important assumptions:

- the CEOS page structure is stable enough for the selectors used in the scraper
- network access is available during execution
- long scraping runs can take time because each mission is visited individually

### `scripts/scrapers/wmo_oscar_scrapper.py`
Scrapes satellite data from the WMO OSCAR portal.

What it produces:

- a raw Excel file containing OSCAR satellite data

Key behavior:

- loads the satellite list page in Playwright
- scrolls through the dynamic table to collect all entries
- extracts detailed satellite and instrument data
- writes the raw OSCAR dataset to the raw data folder

Important assumptions:

- the table is dynamically loaded, so the scraper depends on browser automation
- the site may require scrolling and waiting for data to appear
- the scraper expects Playwright to be installed correctly

### `scripts/processing/standardize_ceos.py`
Converts the CEOS raw export into the shared schema.

What it does:

- renames CEOS source columns into the canonical column names
- adds missing standard columns when the source does not provide them
- normalizes fields such as numeric values and dates
- writes the processed CEOS file

### `scripts/processing/standardize_oscar.py`
Converts the OSCAR raw export into the shared schema.

What it does:

- aligns OSCAR fields with the same canonical schema
- cleans dates, names, and numeric fields
- writes the processed OSCAR file

Why this layer matters:

- the merge scripts assume both datasets already speak the same column language
- if a new source is added later, it should be standardized here first

### `scripts/integration/unified_merge.py`
Performs the broader merge across standardized datasets.

What it does:

- loads the processed CEOS and OSCAR files
- compares satellite names using fuzzy matching
- applies date-based filtering to reduce false matches
- uses Ollama for ambiguous decisions when needed
- writes the final merged output

### `scripts/integration/instrument_merge.py`
Produces the instrument-level merged output.

What it does:

- focuses on the instrument-bearing rows
- merges core satellite and instrument metadata
- keeps the output centered on the columns most useful for downstream analysis

## 5. How matching works

The merge pipeline uses a layered decision approach.

### Step 1: Normalize names
Names are cleaned before comparison by removing punctuation, case differences, and common words such as "Mission" or "Instrument".

### Step 2: Fuzzy match candidates
The code uses similarity scoring to find likely pairs.

### Step 3: Check dates
Launch and end-of-life dates are used to reject obviously incompatible matches.

### Step 4: Ask the local LLM if needed
If a case is still ambiguous, the code can query Ollama.

The code is designed this way so the most obvious matches are handled automatically, while edge cases get a second opinion.

## 6. Shared schema

The standard column names are the contract between all stages of the pipeline.

Examples include:

- `Sat_Full_Name`
- `Sat_Agency`
- `Sat_Status`
- `Sat_Launch`
- `Inst_Full_Name`
- `Inst_Acronym`
- `Inst_Description`

If you change one of these names, check every downstream script that reads the standardized files.

## 7. What a new maintainer should read first

If you are taking over the project, read in this order:

1. `README.md` for the project summary
2. `SETUP.md` for install and runtime prerequisites
3. `CODE_WALKTHROUGH.md` for the implementation overview
4. `DOCUMENTATION.md` for schema and merge details
5. `scripts/utils/config.py` for runtime configuration

## 8. Common maintenance tasks

### Change an output filename
Update `scripts/utils/config.py`.

### Change the LLM model
Update `OLLAMA_MODEL` in `scripts/utils/config.py`.

### Add a new source
Usually requires changes in three places:

- create a scraper under `scripts/scrapers/`
- create a standardizer under `scripts/processing/`
- update merging logic if the new source should participate in final outputs

### Debug a broken run
Check the pipeline in this order:

1. raw scraper output exists
2. processed files exist
3. merge input files have the expected columns
4. Ollama is running if LLM verification is enabled

## 9. Notes on legacy code

The `scripts/legacy/` folder preserves older script versions and experimental variants. These can help explain historical decisions, but they are not the primary implementation path.

If you are trying to understand current behavior, prefer the non-legacy scripts first.

## 10. Bottom line

The codebase is organized enough that a new developer should be able to follow it if they have the setup guide plus this walkthrough. The main thing to understand is that the project is a pipeline: scrape, standardize, then merge.

For a fuller operational handover, also read [HANDOVER_GUIDE.md](HANDOVER_GUIDE.md), which includes troubleshooting, extension guidance, and a script inventory from a maintainer's perspective.
