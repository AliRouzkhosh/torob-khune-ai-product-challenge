"""Canonical source aliases/display names. Dataset values are never rewritten."""
import json,re
from functools import lru_cache
from pathlib import Path
def normalized(value):
    return re.sub(r'\s+',' ',str(value).translate(str.maketrans('يك','یک')).replace('\u200c',' ').strip()).casefold()
REGISTRY=json.loads(Path(__file__).with_suffix('.json').read_text(encoding='utf8'))
# Source spellings of the same Persian neighborhood share one canonical record.
_merged={}
for _row in REGISTRY:
    _key=normalized(_row['display_fa'])
    if _key in _merged:
        _merged[_key]['aliases']=sorted(set(_merged[_key]['aliases']+_row['aliases']))
        _merged[_key]['source_labels']=sorted(set(_merged[_key]['source_labels']+_row['source_labels']))
    else: _merged[_key]=_row
REGISTRY=list(_merged.values())
INDEX={normalized(alias):row for row in REGISTRY for alias in row['aliases']}
def entry(value):return INDEX.get(normalized(value))
def location_key(value):return entry(value)['key'] if entry(value) else value
def display_location(value):return entry(value)['display_fa'] if entry(value) else value
def source_labels(values):
    return sorted({source for value in values for source in (entry(value)['source_labels'] if entry(value) else [value])} | set(values))
def workplace_label(value):return 'تعیین نشده' if value=='none' else display_location(value)
@lru_cache(maxsize=1)
def workplace_choices():return tuple([('none','تعیین نشده')]+sorted({(row['key'],row['display_fa']) for row in REGISTRY if row['classification'] in ('mapped','Persian')},key=lambda x:x[1]))
def normalize_location_text(text):
    # Longest aliases first; boundaries avoid interpreting a smaller district inside another.
    return _ALIAS_PATTERN.sub(lambda m:_ALIASES[m.group(1).casefold()],text)

_ALIASES={alias.casefold():row['display_fa'] for row in REGISTRY for alias in row['aliases'] if alias!=row['display_fa']}
_ALIAS_PATTERN=re.compile(r'(?<![\w])('+ '|'.join(re.escape(a) for a in sorted(_ALIASES,key=len,reverse=True))+r')(?:ه)?(?![\w])',re.I)
