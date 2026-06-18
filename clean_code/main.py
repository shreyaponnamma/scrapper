import argparse
import sys
import os
import asyncio
import subprocess

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def run_script(path):
    """Utility to run a subprocess script with project root in PYTHONPATH."""
    print(f"\n>>> Running: {path}")
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.dirname(os.path.abspath(__file__))
    result = subprocess.run([sys.executable, path], env=env)
    if result.returncode != 0:
        print(f"Error: {path} failed with exit code {result.returncode}")
        return False
    return True

async def run_pipeline(args):
    """Orchestrates the data pipeline."""
    
    # 1. Scraping
    if args.scrape or args.all:
        print("=== Phase 1: Scraping ===")
        # Note: Scrapers are async, but we run them via subprocess for simplicity in orchestrator
        # or we could import their main functions. Since we want them as standalone too, 
        # subprocess is cleaner for the 'clean code' requirement.
        run_script("scripts/scrapers/ceos_scrapper.py")
        run_script("scripts/scrapers/wmo_oscar_scrapper.py")

    # 2. Processing
    if args.process or args.all:
        print("=== Phase 2: Processing & Standardization ===")
        run_script("scripts/processing/standardize_ceos.py")
        run_script("scripts/processing/standardize_oscar.py")

    # 3. Integration
    if args.merge or args.all:
        print("=== Phase 3: Integration & Merging ===")
        run_script("scripts/integration/unified_merge.py")
        run_script("scripts/integration/instrument_merge.py")

    print("\n✓ Pipeline execution complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Satellite Data Pipeline Orchestrator")
    parser.add_argument("--scrape", action="store_true", help="Run scrapers only")
    parser.add_argument("--process", action="store_true", help="Run standardization only")
    parser.add_argument("--merge", action="store_true", help="Run merging logic only")
    parser.add_argument("--all", action="store_true", help="Run the entire pipeline from scratch")
    
    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)
        
    args = parser.parse_args()
    asyncio.run(run_pipeline(args))
