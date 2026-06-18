import os

# Base directory for the sat-scrapper project
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Data Directories
DATA_RAW = os.path.join(BASE_DIR, "data", "raw")
DATA_PROCESSED = os.path.join(BASE_DIR, "data", "processed")
DATA_FINAL = os.path.join(BASE_DIR, "data", "final")

# Ensure directories exist
for d in [DATA_RAW, DATA_PROCESSED, DATA_FINAL]:
    os.makedirs(d, exist_ok=True)

# File Paths - Scraper Outputs
CEOS_RAW_EXCEL = os.path.join(DATA_RAW, "satellite_data_full.xlsx")
OSCAR_RAW_JSON = os.path.join(DATA_RAW, "oscar_raw.json") # Example if it was json
OSCAR_RAW_EXCEL = os.path.join(DATA_RAW, "oscar_satellites.xlsx")

# File Paths - Processing Outputs
CEOS_PROCESSED = os.path.join(DATA_PROCESSED, "ceos_standardized.xlsx")
OSCAR_PROCESSED = os.path.join(DATA_PROCESSED, "oscar_standardized.xlsx")

# File Paths - Final Merges
MERGED_COMPLETE = os.path.join(DATA_FINAL, "merged_satellite_data_complete.xlsx")
INSTRUMENT_MERGE = os.path.join(DATA_FINAL, "instrument_level_merge.xlsx")

# LLM Configuration
OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "llama3.2:1b"

# Thresholds
FUZZY_MATCH_THRESHOLD = 0.8
