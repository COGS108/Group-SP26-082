"""
One-time scraper for ProSportsTransactions NBA injury/rest log.

Run this ONCE locally. It saves the result to data/00-raw/pst_transactions_raw.csv,
which the notebook then reads from. Do NOT run this from inside the notebook.

Designed to be polite to PST:
  - 5-second delay between requests (slower than typical scrapers)
  - Custom User-Agent identifying us as a student project
  - Saves progress to disk after each page (so a network blip doesn't lose work)
  - Resumes from where it left off if you re-run after an interruption
  - Hard stop after MAX_PAGES so it can't run away
"""

import os
import time
import pandas as pd
import requests
from io import StringIO

OUT_PATH = 'data/00-raw/pst_transactions_raw.csv'
PROGRESS_PATH = 'data/00-raw/.pst_progress.txt'

# Polite headers — identify the request as a student project
HEADERS = {
    'User-Agent': ('COGS108-Student-Project/1.0 (UCSD undergraduate course; '
                   'one-time data pull for academic analysis)'),
}

BASE = ('https://www.prosportstransactions.com/basketball/Search/SearchResults.php'
        '?Player=&Team=&BeginDate=2017-10-17&EndDate=2025-04-13'
        '&ILChkBx=yes&InactiveChkBx=yes&Submit=Search&start={start}')

SLEEP_SECONDS = 5    # be polite — slower than necessary
MAX_PAGES = 400      # hard ceiling; ~8 seasons typically fits under this

def load_progress():
    """Resume from last saved page if script was interrupted."""
    if os.path.exists(PROGRESS_PATH):
        with open(PROGRESS_PATH) as f:
            return int(f.read().strip())
    return 0

def save_progress(start):
    with open(PROGRESS_PATH, 'w') as f:
        f.write(str(start))

def main():
    os.makedirs('data/00-raw', exist_ok=True)

    # Load any pages we already pulled (resume support)
    if os.path.exists(OUT_PATH):
        existing = pd.read_csv(OUT_PATH)
        all_rows = [existing]
        print(f"Resuming: {len(existing)} rows already saved")
    else:
        all_rows = []

    start = load_progress()
    print(f"Starting at page offset {start}")
    print(f"Sleep between requests: {SLEEP_SECONDS}s")
    print(f"Hard ceiling: {MAX_PAGES} pages")
    print()

    while start < MAX_PAGES * 25:
        url = BASE.format(start=start)
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
        except Exception as e:
            print(f"  network error at start={start}: {e}")
            print(f"  saving progress and stopping — re-run to resume")
            save_progress(start)
            break

        if resp.status_code != 200:
            print(f"  HTTP {resp.status_code} at start={start} — stopping")
            save_progress(start)
            break

        # Parse the HTML table
        try:
            tbl = pd.read_html(StringIO(resp.text))[0]
        except ValueError:
            # No tables on this page — we've hit the end of results
            print(f"  no table at start={start} — reached end of results")
            break

        # Drop the repeated header row (first row of every page)
        tbl = tbl.iloc[1:].copy()
        tbl.columns = ['date', 'team', 'acquired', 'relinquished', 'notes']

        if len(tbl) == 0:
            print(f"  empty page at start={start} — reached end")
            break

        all_rows.append(tbl)

        # Save after every page so a crash doesn't lose data
        combined = pd.concat(all_rows, ignore_index=True)
        combined = combined.drop_duplicates()
        combined.to_csv(OUT_PATH, index=False)

        print(f"  page start={start}: pulled {len(tbl)} rows (total saved: {len(combined)})")

        start += 25
        save_progress(start)
        time.sleep(SLEEP_SECONDS)

    # Final cleanup
    if all_rows:
        combined = pd.concat(all_rows, ignore_index=True).drop_duplicates()
        combined.to_csv(OUT_PATH, index=False)
        print(f"\nDone. {len(combined)} total rows saved to {OUT_PATH}")
    else:
        print("\nNo rows pulled — check the URL or network.")

    # Clear progress file so next run starts fresh (only after success)
    if os.path.exists(PROGRESS_PATH):
        os.remove(PROGRESS_PATH)

if __name__ == '__main__':
    main()