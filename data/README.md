# Data and reproducibility

The source project contained a bounded **651,239-byte Parquet subset of 3,600 anonymized historical Divar rental records**, not the full archive. The working SQLite database contained 3,000 imported real listings and 12 separately seeded synthetic listings. Neither file is included in this public copy. Generated import/audit dumps and the old SQLite backup are also excluded.

Source: [Divar official real-estate archive](https://huggingface.co/datasets/divarofficial/real_estate_ads). Earlier project provenance identifies the dataset card license as ODbL. Live verification of that card was unavailable during public preparation; this statement is historical provenance, not a new rights determination. Review the current card, attribution and database-license obligations before obtaining or redistributing data. No application-wide license is inferred from the dataset license.

## Included offline demo

Run migrations, `manage.py seed_demo`, and `manage.py seed_demo_user`, with `DATA_MODE=synthetic` as shown in the root README. This recreates the existing 12 curated synthetic examples, not fabricated replacement Divar records. No raw source ads, working database, credentials or demo password ship here.

## Optional historical real mode

After reviewing acquisition terms, the existing bounded download script and offline importer can reconstruct an inventory from the upstream archive:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-import.txt
.\.venv\Scripts\python.exe scripts/prepare_divar_subset.py
.\.venv\Scripts\python.exe manage.py import_divar_rentals --source data/raw/tehran-rentals.parquet --limit 3000 --money-unit toman --report data/import-summary.json
$env:DATA_MODE = "real"
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

Run migrations first. `seed_demo` preserves the synthetic mode independently. Acquisition requires network access and PyArrow; it selects Tehran residential-rent/apartment-rent records from bounded Parquet ranges rather than scraping live listings or downloading the full archive. Import accepts CSV without PyArrow. `--money-unit rial` is available if the actual input uses rial; confirm upstream units rather than assuming them.

The acquisition script records the current upstream revision, so future downloads may differ from the original subset. The exact original subset and 3,000-record ranking are **not reproducible from public files alone**. The importer itself was checked against the withheld original subset in a disposable database during preparation; network acquisition was not re-run. Its default limit is 3,000 accepted unique rows, bounded to 5,000, with a 100,000-row scan cap. Reimport updates stable identities; `--clear` replaces real inventory transactionally only after usable rows are read, preserving synthetic IDs.

Money is canonical integer toman, construction years use the Persian calendar, missing evidence remains unknown, and coordinates/proximity are approximate. Data is historical and does not establish current prices, availability, verified seller claims or travel times. Images are illustrative and **not original Divar listing photos**. Keep local acquired files and generated reports ignored.

For an optional local audit after importing approved real data, run `python scripts/audit_divar_subset.py`. It samples up to 20 records, checks coverage and runs the three frozen demo scenarios, writing ignored `data/divar-audit.json`. That generated report contains source-record text and must remain local. The script refuses to fabricate an audit when no real listings are imported.
