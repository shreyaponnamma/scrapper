# Setup Guide

This guide ensures you have everything needed to run the satellite data pipeline.

## Prerequisites

- **Python 3.9+**
- **pip** (Python package manager)
- **Ollama** (Optional, but required for LLM-verified merging)
    - Download from [ollama.com](https://ollama.com)
    - Pull the models: `ollama pull llama3.2:1b` (or 8b for better accuracy)

## Installation

1.  **Clone/Copy the repository**:
    Ensure you are in the `sat-scrapper` directory (or the `clean_code` folder if you haven't renamed it yet).
    ```bash
    cd clean_code  # Or cd sat-scrapper
    ```

2.  **Create a virtual environment**:
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\\Scripts\\activate
    ```

3.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Install Playwright browsers**:
    The scrapers use Playwright for headless browsing.
    ```bash
    playwright install chromium
    # Note: On some systems (e.g., Linux), you may also need to run:
    # playwright install-deps
    ```

## Configuration

The pipeline settings are located in `scripts/utils/config.py`. Here you can configure:
- Data input/output paths.
- Ollama endpoint and model name.
- Fuzzy matching thresholds.

### Ollama Setup
If you want to use the LLM-merge feature:
1. Start the Ollama server: `ollama serve`.
2. Ensure the models are pulled.
3. The merging script will automatically check for connection to `http://localhost:11434`.

**Note on Models**: The default model is `llama3.2:1b` for speed. If you have a dedicated GPU and notice low matching accuracy, you can change the `OLLAMA_MODEL` in `scripts/utils/config.py` to `llama3.2:3b` or `8b`.

## Running Tests
(Future: Add test instructions here)
