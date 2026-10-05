# Data and reproducibility

## Included historical video-demo snapshot

[`divar_tehran_rentals_3000.fixture.json`](divar_tehran_rentals_3000.fixture.json) is a UTF-8 Django fixture containing exactly 3,000 real `finder.listing` objects from the stored demo inventory. Objects are ordered by primary key and preserve explicit PKs, stable source identities and every persisted model field, except for approved privacy substitutions in listing descriptions. No normalization or import enrichment was recomputed.

Direct telephone/contact substrings discovered during release review were replaced with `[شماره تماس حذف شد]`. No original contact values, individual contact hashes or identifying redaction records are distributed. The main/source database remains untouched. A schema-aware final scan found no apparent direct phone numbers, emails or external contact URLs in the retained listing text; hashed source identities are not treated as telephone numbers. This sanity check is not a guarantee that historical text has no other identifying information.

Source: [Divar official real-estate archive](https://huggingface.co/datasets/divarofficial/real_estate_ads). Upstream publication describes the data as historical and anonymized; upstream dataset attribution/license metadata identifies ODbL 1.0. The original bounded acquisition manifest records revision `e9446ee97b8e6eb9bd62bdfd7548f1bc8973be85`, with Tehran `residential-rent` / `apartment-rent` filters. The snapshot selects the exact 3,000 stored real identities, rather than downloading a new selection. The original 3,600-row Parquet acquisition, working SQLite database, synthetic rows and generated audit reports are excluded.

See [DATA_LICENSE_AND_ATTRIBUTION.md](DATA_LICENSE_AND_ATTRIBUTION.md) for the data-only notice and official terms. Dataset licensing does not automatically license the application source code under ODbL.

## Reproduce real mode

Create a Python 3.12 environment and install `requirements.txt` as shown in the root README. Start from a fresh local database:

```powershell
$env:DATA_MODE = "real"
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py loaddata data/divar_tehran_rentals_3000.fixture.json
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

No PyArrow or upstream download is required. `loaddata` restores historical stored state instead of rerunning normalization. It does not delete unrelated existing listings; a fresh database is required for the exact 3,000-row inventory. Synthetic mode remains available through `seed_demo` and `DATA_MODE=synthetic`, as documented in the root README.

Verification loaded only this fixture after migrations: 3,000 real listings, zero synthetic listings, zero persisted-field differences from the public fixture. The fixture differs from the original inventory only in four description fields containing approved contact-substring replacements. The locked flow returned **593 → 4 → 3 → 0 → 3**. Full ranked IDs/scores, compound elevator eligibility and visible UNKNOWN pet evidence matched the original demo behavior.

Public canonical SHA-256: `0bf4c96ee5d8acb75e15a8c63cb1f056e8b9819101c9ab76748066b11c39667a`. Canonicalization orders objects by numeric PK, includes model label, PK and every persisted non-PK field, then serializes JSON with sorted keys, UTF-8 unescaped Unicode and compact separators. It compares representations without changing values; this is not the pretty-printed file’s byte checksum.

## Optional upstream acquisition / re-import

The existing scripts and importer remain available for separate upstream-data experiments:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-import.txt
.\.venv\Scripts\python.exe scripts/prepare_divar_subset.py
.\.venv\Scripts\python.exe manage.py import_divar_rentals --source data/raw/tehran-rentals.parquet --limit 3000 --money-unit toman
```

Run migrations first. Acquisition needs network access and PyArrow. CSV import requires no extra package. Review upstream terms and verify source monetary units; `--money-unit rial` is supported for rial inputs. The snapshot retains the demo’s stored integer-toman values and Persian construction years.

A new upstream selection may differ. Current importer normalization also changes some historically stored labels, titles and derived evidence, so re-import is not the exact recorded-demo reproduction path. The importer is unchanged: it accepts at most 5,000 unique records, defaults to 3,000 and has a 100,000-row scan cap. `--clear` replaces real inventory while preserving synthetic rows. Keep acquired files and generated reports local and ignored; optional audit reports can contain listing text.

Records are historical and do not establish current price, availability, seller claims or travel time. Coordinates and proximity are approximate. Missing evidence remains unknown. No original Divar listing photographs are distributed; the application’s existing property images are illustrative.
