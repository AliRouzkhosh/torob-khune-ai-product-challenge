"""Import only a bounded, filtered offline subset; never fetch live Divar ads."""
import csv
import json
from collections import Counter
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from finder.models import Listing
from finder.importing import normalize_record, SkipRecord, text

REQUIRED = {'city_slug', 'cat2_slug', 'cat3_slug', 'title', 'credit_value', 'rent_value', 'building_size', 'rooms_count'}


def source_rows(path):
    if path.suffix.lower() == '.csv':
        with path.open(encoding='utf-8-sig', newline='') as stream:
            reader = csv.DictReader(stream)
            if not REQUIRED <= set(reader.fieldnames or []): raise CommandError('Missing source columns: ' + ', '.join(sorted(REQUIRED-set(reader.fieldnames or []))))
            yield from reader
    elif path.suffix.lower() in ('.parquet', '.pq'):
        try: import pyarrow.parquet as pq
        except ImportError as exc: raise CommandError('Parquet requires: python -m pip install -r requirements-import.txt. CSV needs no extra package.') from exc
        source = pq.ParquetFile(path)
        if not REQUIRED <= set(source.schema_arrow.names): raise CommandError('Parquet is missing required Divar columns.')
        for batch in source.iter_batches(batch_size=1024):
            yield from batch.to_pylist()
    else: raise CommandError('Use a local UTF-8 CSV or Parquet file.')


class Command(BaseCommand):
    help = 'Import a bounded Tehran apartment-rent subset from the official anonymized Divar schema.'

    def add_arguments(self, parser):
        parser.add_argument('--source', required=True)
        parser.add_argument('--limit', type=int, default=3000)
        parser.add_argument('--city', default='tehran', choices=['tehran'])
        parser.add_argument('--clear', action='store_true', help='Replace real rows only, atomically; synthetic rows are preserved.')
        parser.add_argument('--max-rows', type=int, default=100000, help='Stop scanning raw rows at this bound.')
        parser.add_argument('--money-unit', choices=['toman', 'rial'], default='toman')
        parser.add_argument('--report', help='Optional JSON summary output path.')

    def handle(self, *args, **options):
        path = Path(options['source'])
        if not path.is_file(): raise CommandError('Source file not found. Download the official archive and supply --source <local.csv|local.parquet>.')
        if not 1 <= options['limit'] <= 5000: raise CommandError('--limit must be between 1 and 5000.')
        if not 1 <= options['max_rows'] <= 100000: raise CommandError('--max-rows must be between 1 and 100000; preprocess larger archives first.')
        counts, skipped, records = Counter(), Counter(), {}
        rows = source_rows(path)
        try:
            for row in rows:
                counts['raw_rows_read'] += 1
                if text(row.get('city_slug')).lower() != options['city']: skipped['other_city'] += 1
                else:
                    counts['tehran_rows'] += 1
                    if row.get('cat2_slug') != 'residential-rent' or row.get('cat3_slug') != 'apartment-rent': skipped['other_category'] += 1
                    else:
                        counts['rental_apartment_rows'] += 1
                        try: record = normalize_record(row, options['money_unit'])
                        except SkipRecord as exc: skipped[str(exc)] += 1
                        else:
                            if record['source_id'] in records: skipped['duplicate'] += 1
                            else: records[record['source_id']] = record
                if len(records) >= options['limit'] or counts['raw_rows_read'] >= options['max_rows']: break
        except (OSError, UnicodeError, csv.Error) as exc: raise CommandError(f'Could not read source: {exc}') from exc
        finally: rows.close()
        if not records: raise CommandError('No usable rows; database unchanged. Counts: ' + json.dumps(dict(skipped), ensure_ascii=False))
        values = list(records.values())
        existing = Listing.objects.filter(source_id__in=records).count()
        with transaction.atomic():
            Listing.objects.bulk_create([Listing(**r) for r in values], batch_size=200,
                update_conflicts=True, unique_fields=['source_id'], update_fields=[k for k in values[0] if k not in ('id','source_id')])
            if options['clear']: Listing.objects.filter(data_source='real').exclude(source_id__in=records).delete()
        for field in ('neighborhood','latitude','construction_year'):
            counts['missing_' + {'latitude':'coordinates','construction_year':'year'}.get(field,field)] = sum(r[field] is None or r[field] == '' for r in values)
        for key in ('parking','elevator','storage'):
            counts[key+'_known'] = sum(r[key] is not None for r in values)
            counts[key+'_true'] = sum(r[key] is True for r in values)
        for key in ('natural_light','quietness','layout_quality','access_quality','renovation_claim'):
            counts[key+'_signal'] = sum(r[key] is not None for r in values)
        report = {'source': str(path.resolve()), 'money_unit': options['money_unit'], **dict(counts),
                  'imported': len(values), 'created': len(values)-existing, 'updated': existing,
                  'skipped': sum(skipped.values()), 'skipped_reasons': dict(skipped),
                  'stopped_at_limit': len(values)>=options['limit'], 'scan_cap_reached': counts['raw_rows_read']>=options['max_rows']}
        self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
        if options['report']: Path(options['report']).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
