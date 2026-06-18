# Satellite Data Scraper & Integration Pipeline

This repository contains a unified pipeline for scraping, standardizing, and merging satellite and instrument data from multiple sources (CEOS and WMO OSCAR). It's designed to provide a "Ground Truth" dataset for satellite-borne instrument missions.

## Project Structure

```text
sat-scrapper/
├── data/
│   ├── raw/                # Unprocessed output from scrapers
│   ├── processed/          # Standardized data (ready for merging)
│   └── final/              # Final merged datasets
├── scripts/
│   ├── scrapers/           # Web scrapers for CEOS and WMO OSCAR
│   ├── processing/         # Data cleaning and standardization logic
│   ├── integration/        # Merging logic (fuzzy matching + LLM verification)
│   └── utils/              # Shared helper functions
├── main.py                 # Orchestrator to run the full pipeline
├── requirements.txt        # Python dependencies
├── SETUP.md                # Installation and environment setup guide
└── DOCUMENTATION.md        # Technical details on data mapping and merge logic
```

## Data Workflow

1.  **Scraping**: `scripts/scrapers/` fetch the latest lists of satellites and instruments.
2.  **Standardization**: `scripts/processing/` maps source-specific fields to a unified schema (e.g., `Sat_Full_Name`, `Inst_Acronym`).
3.  **Integration**: `scripts/integration/` performs fuzzy matching on mission names and uses Local LLMs (Ollama) to verify ambiguous matches, resulting in a deduplicated master list.

## Quick Start

### 1. Setup
Follow the instructions in [SETUP.md](SETUP.md) to install dependencies and configure Ollama.

### 2. Run the Pipeline
You can run the full pipeline using the orchestrator:

```bash
python main.py --all
```

*Note: The first run (scraping) can take 30-60 minutes depending on network speed, as it scans thousands of mission pages.*

Or run specific components:
```bash
python main.py --scrape
python main.py --process
python main.py --merge
```

## Maintenance
Documents for future developers:
- [Data Mapping Guide](DOCUMENTATION.md)
- [Setup Guide](SETUP.md)

---
*Created as part of the Fraunhofer Satellite Data project.*
