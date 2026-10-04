"""v0.9-D compound housing logic.

This module keeps *relationships between criteria* explicit instead of flattening them
into global filters.  It deliberately has no Django dependency so parser/ranking tests
can exercise the logic without a web runtime.

Supported families:
- relative priorities (A > B);
- conditional requirements/relaxations;
- controlled exceptions;
- progressive fallback search plans.
"""
from __future__ import annotations

from copy import deepcopy
import re

from .language import normalize_persian, number_value, SMALL_NUMBER_TOKEN
from .evidence_features import YES, evidence_feature_state, extract_listing_evidence
from .locations import workplace_distance

PRIORITY_ORDER = {'ignored': 0, 'low': 1, 'medium': 2, 'high': 3, 'very_high': 4}
NEW_BUILD_YEAR = 1398
DEFAULT_CLOSE_COMMUTE_KM = 2.0

LOGIC_DEFAULT = {
    'relative_priorities': [],
    'conditionals': [],
    'fallbacks': [],
}

BASE_PRIORITY_PATTERNS = {
    'natural_light': r'نور(?:گیری|گیر)?|روشن|آفتاب',
    'area': r'متراژ|مساحت|فضای\s*خانه',
    'parking': r'پارکینگ|جای\s*پارک',
    'elevator': r'آسانسور',
    'storage': r'انباری|انبار',
    'quietness': r'آرامش|آروم|آرام|ساکت|دنج|خلوت',
    'building_age': r'نوساز|ساختمان\s*جدید|سن\s*بنا|قدیمی',
    'commute': r'رفت\s*و\s*آمد|مسیر|نزدیکی\s*به\s*محل\s*کار|فاصله\s*تا\s*محل\s*کار',
    'budget': r'بودجه|قیمت|هزینه|اجاره|ودیعه|رهن',
}
EVIDENCE_PRIORITY_PATTERNS = {
    'near_metro': r'مترو',
    'near_brt': r'BRT',
    'open_view': r'ویو(?:\s*باز)?|دید\s*باز',
    'privacy': r'حریم\s*خصوصی|مشرف',
    'single_unit': r'تک\s*واحدی',
    'low_density': r'کم\s*واحد|ساختمان\s*شلوغ',
    'furnished': r'مبله|فرنیش',
    'security_24h': r'نگهبان|نگهبانی',
    'cctv': r'دوربین\s*مدار\s*بسته',
}

BASE_LABELS = {
    'natural_light': 'نورگیری', 'area': 'متراژ', 'parking': 'پارکینگ',
    'elevator': 'آسانسور', 'storage': 'انباری', 'quietness': 'آرامش',
    'building_age': 'نوساز بودن', 'commute': 'رفت‌وآمد', 'budget': 'بودجه',
}
EVIDENCE_LABELS = {
    'near_metro': 'نزدیکی به مترو', 'near_brt': 'نزدیکی به BRT',
    'open_view': 'دید باز', 'privacy': 'حریم خصوصی', 'single_unit': 'تک‌واحدی',
    'low_density': 'ساختمان کم‌واحد', 'furnished': 'مبله',
    'security_24h': 'نگهبانی', 'cctv': 'دوربین مداربسته',
}

CONDITIONAL_TYPES = {
    'require_elevator_if_floor_min',
    'require_renovation_if_old',
    'require_elevator_if_old',
    'relax_preference_if_commute_close',
    'relax_preference_if_evidence',
    'conditional_max_rent_if_commute_close',
    'relax_area_min_if_commute_close',
}
FALLBACK_TYPES = {
    'neighborhood_scope',
    'max_rent',
    'bedrooms_allowed',
    'relax_parking',
    'new_then_renovated_old',
}


def default_logic() -> dict:
    return deepcopy(LOGIC_DEFAULT)


def _restore_amenity(result, current, key):
    """Repair only a conditional's subject, preserving unrelated same-request edits."""
    result.constraints['required_amenities'] = [k for k in result.constraints['required_amenities'] if k != key]
    if key in current.constraints['required_amenities']:
        result.constraints['required_amenities'].append(key)


def validate_logic(logic: dict) -> None:
    if not isinstance(logic, dict):
        raise ValueError('منطق ترکیبی معتبر نیست.')
    for key, default in LOGIC_DEFAULT.items():
        logic.setdefault(key, deepcopy(default))
    if set(logic) != set(LOGIC_DEFAULT):
        raise ValueError('ساختار منطق ترکیبی معتبر نیست.')
    if not all(isinstance(logic[key], list) for key in LOGIC_DEFAULT):
        raise ValueError('منطق ترکیبی معتبر نیست.')

    for rule in logic['relative_priorities']:
        if not isinstance(rule, dict) or set(rule) != {'higher', 'lower'}:
            raise ValueError('اولویت نسبی معتبر نیست.')
        if not _valid_priority_token(rule['higher']) or not _valid_priority_token(rule['lower']) or rule['higher'] == rule['lower']:
            raise ValueError('اولویت نسبی معتبر نیست.')

    for rule in logic['conditionals']:
        if not isinstance(rule, dict) or rule.get('type') not in CONDITIONAL_TYPES:
            raise ValueError('شرط ترکیبی معتبر نیست.')
        t = rule['type']
        if t == 'require_elevator_if_floor_min':
            if type(rule.get('floor_min')) is not int or not -5 <= rule['floor_min'] <= 100:
                raise ValueError('شرط طبقه/آسانسور معتبر نیست.')
        elif t in ('require_renovation_if_old', 'require_elevator_if_old'):
            if type(rule.get('old_before')) is not int or not 1300 <= rule['old_before'] <= 1405:
                raise ValueError('شرط ساختمان قدیمی معتبر نیست.')
        elif t == 'relax_preference_if_commute_close':
            if rule.get('target') not in BASE_PRIORITY_PATTERNS or rule.get('to') not in ('ignored', 'low'):
                raise ValueError('شرط انعطاف اولویت معتبر نیست.')
            if not _valid_km(rule.get('max_km')):
                raise ValueError('فاصله شرطی معتبر نیست.')
            if 'preferred_count' in rule or 'close_count' in rule:
                if rule.get('target') != 'parking' or any(type(rule.get(k)) is not int or not 1 <= rule[k] <= 5 for k in ('preferred_count','close_count')) or rule['close_count'] > rule['preferred_count']:
                    raise ValueError('ترجیح تعداد پارکینگ معتبر نیست.')
        elif t == 'relax_preference_if_evidence':
            if rule.get('target') not in BASE_PRIORITY_PATTERNS or rule.get('evidence') not in EVIDENCE_PRIORITY_PATTERNS or rule.get('to') not in ('ignored', 'low'):
                raise ValueError('شرط مبتنی بر شواهد معتبر نیست.')
        elif t == 'conditional_max_rent_if_commute_close':
            if not _valid_money(rule.get('base_max')) or not _valid_money(rule.get('relaxed_max')) or rule['relaxed_max'] < rule['base_max']:
                raise ValueError('سقف اجاره شرطی معتبر نیست.')
            if not _valid_km(rule.get('max_km')):
                raise ValueError('فاصله شرطی معتبر نیست.')
        elif t == 'relax_area_min_if_commute_close':
            if type(rule.get('base_min')) is not int or not 1 <= rule['base_min'] <= 2000:
                raise ValueError('حداقل متراژ شرطی معتبر نیست.')
            if not _valid_km(rule.get('max_km')):
                raise ValueError('فاصله شرطی معتبر نیست.')

    for rule in logic['fallbacks']:
        if not isinstance(rule, dict) or rule.get('type') not in FALLBACK_TYPES:
            raise ValueError('مرحله جایگزین معتبر نیست.')
        if type(rule.get('trigger_min_results', 1)) is not int or not 1 <= rule.get('trigger_min_results', 1) <= 20:
            raise ValueError('آستانه مرحله جایگزین معتبر نیست.')
        t = rule['type']
        if t == 'neighborhood_scope' and rule.get('to') != 'nearby':
            raise ValueError('مرحله جایگزین محله معتبر نیست.')
        if t == 'max_rent' and not _valid_money(rule.get('to')):
            raise ValueError('مرحله جایگزین اجاره معتبر نیست.')
        if t == 'bedrooms_allowed':
            values = rule.get('values')
            if not isinstance(values, list) or not values or any(type(v) is not int or not 1 <= v <= 5 for v in values):
                raise ValueError('مرحله جایگزین اتاق معتبر نیست.')
        if t == 'new_then_renovated_old':
            if type(rule.get('new_year', NEW_BUILD_YEAR)) is not int:
                raise ValueError('مرحله جایگزین سن بنا معتبر نیست.')


def _valid_priority_token(token: str) -> bool:
    if not isinstance(token, str) or ':' not in token:
        return False
    group, key = token.split(':', 1)
    return (group == 'base' and key in BASE_PRIORITY_PATTERNS) or (group == 'evidence' and key in EVIDENCE_PRIORITY_PATTERNS)


def _valid_money(value) -> bool:
    return type(value) is int and 0 <= value <= 100_000_000_000


def _valid_km(value) -> bool:
    return isinstance(value, (int, float)) and 0 < value <= 50


def _token_for_phrase(text: str) -> str | None:
    text = normalize_persian(text)
    # Prefer specific evidence concepts before broad words like "نزدیک".
    for key, pattern in EVIDENCE_PRIORITY_PATTERNS.items():
        if re.search(pattern, text, re.I):
            return 'evidence:' + key
    for key, pattern in BASE_PRIORITY_PATTERNS.items():
        if re.search(pattern, text, re.I):
            return 'base:' + key
    return None


def token_label(token: str) -> str:
    group, key = token.split(':', 1)
    return (BASE_LABELS if group == 'base' else EVIDENCE_LABELS).get(key, key)


def _set_priority_token(intent, token: str, priority: str) -> None:
    group, key = token.split(':', 1)
    if group == 'base' and key in intent.preferences:
        intent.preferences[key] = priority
    elif group == 'evidence' and key in intent.evidence_preferences:
        intent.evidence_preferences[key] = priority


def _get_priority_token(intent, token: str) -> str:
    group, key = token.split(':', 1)
    return intent.preferences[key] if group == 'base' else intent.evidence_preferences[key]


def _add_unique(items: list, rule: dict) -> None:
    # Repeating a controlled conditional replaces its threshold rather than
    # conjoining stale and new versions of the same user instruction.
    conditional_types = {'require_elevator_if_floor_min', 'require_elevator_if_old', 'require_renovation_if_old', 'relax_preference_if_commute_close', 'relax_preference_if_evidence', 'relax_area_min_if_commute_close', 'conditional_max_rent_if_commute_close'}
    if rule.get('type') in conditional_types:
        items[:] = [old for old in items if not (old.get('type') == rule['type'] and old.get('target') == rule.get('target'))]
    if rule not in items:
        items.append(rule)


def _fallback_threshold(text: str) -> int:
    return 3 if re.search(r'کم\s*بود|گزینه.{0,8}کم|نتیجه.{0,8}کم', text) else 1


def _money_amounts(text: str, noun_pattern: str) -> list[int]:
    text = normalize_persian(text)
    pattern = rf'(\d+(?:\.\d+)?)\s*(میلیون|میلیارد)\s*(?:تومان\s*)?(?:{noun_pattern})|(?:{noun_pattern})[^\d]{{0,20}}(\d+(?:\.\d+)?)\s*(میلیون|میلیارد)'
    values = []
    for m in re.finditer(pattern, text):
        raw = m.group(1) or m.group(3)
        unit = m.group(2) or m.group(4)
        value = int(float(raw) * (1_000_000 if unit == 'میلیون' else 1_000_000_000))
        if value not in values:
            values.append(value)
    return values


def _renovated(listing) -> bool:
    return getattr(listing, 'renovated', None) is True or getattr(listing, 'renovation_claim', None) is True


def _commute_close(listing, intent, max_km: float) -> bool:
    workplace = getattr(intent, 'work_location', 'none')
    if workplace == 'none':
        return False
    value = workplace_distance(listing, workplace)
    if value is None and getattr(listing, 'data_source', '') != 'real':
        value = getattr(listing, 'distances', {}).get(workplace, getattr(listing, 'distance_to_work_km', None))
    return value is not None and value <= max_km


def _evidence_yes(listing, token: str) -> bool:
    try:
        return evidence_feature_state(extract_listing_evidence(listing), token) == YES
    except KeyError:
        return False


def clear_related_logic(intent, paths):
    """Explicit manual edits invalidate only relationships touching those criteria."""
    tokens={('base:' if p.startswith('preferences.') else 'evidence:')+p.split('.')[1] for p in paths if p.startswith(('preferences.','evidence_preferences.'))}
    aliases={'constraints.area':'area','constraints.floor':'floor','constraints.construction_year_min':'building_age','constraints.renovation_required':'building_age','constraints.neighborhoods':'neighborhood','constraints.neighborhood_mode':'neighborhood','constraints.max_rent':'rent','constraints.bedrooms':'bedrooms','context.workplace':'commute'}
    touched={aliases[p] for p in paths if p in aliases}
    touched.update(t.split(':')[1] for t in tokens if t.startswith('base:'))
    if any(p.startswith('constraints.parking_') for p in paths):touched.add('parking')
    logic=intent.logic
    logic['relative_priorities']=[r for r in logic['relative_priorities'] if r['higher'] not in tokens and r['lower'] not in tokens]
    def keep(r):
        t=r['type']
        if t=='require_elevator_if_floor_min':return not touched & {'floor','elevator'}
        if t=='require_elevator_if_old':return not touched & {'building_age','elevator'}
        if t=='require_renovation_if_old':return 'building_age' not in touched
        if t=='conditional_max_rent_if_commute_close':return not touched & {'rent','commute'}
        if t=='relax_area_min_if_commute_close':return not touched & {'area','commute'}
        if t.startswith('relax_preference'):return r.get('target') not in touched and not (t=='relax_preference_if_commute_close' and 'commute' in touched) and 'evidence:'+r.get('evidence','') not in tokens
        return True
    logic['conditionals']=[r for r in logic['conditionals'] if keep(r)]
    fallback_fields={'neighborhood_scope':'neighborhood','max_rent':'rent','bedrooms_allowed':'bedrooms','relax_parking':'parking','new_then_renovated_old':'building_age'}
    logic['fallbacks']=[r for r in logic['fallbacks'] if fallback_fields[r['type']] not in touched]


def apply_compound_language(text: str, current, result, neighborhoods=()):
    """Project compound meaning onto ``result`` while preserving current PATCH state.

    The ordinary parser runs first.  This pass repairs phrases that *must not* be
    flattened (e.g. "floor 4+ only if elevator") and records explicit logic.
    """
    text = normalize_persian(text)
    logic = deepcopy(getattr(result, 'logic', default_logic()))

    if re.search(r'(?:منطق|استثنا|مرحله\s*جایگزین|شرط\s*قبلی).{0,20}(?:حذف|بی\s*خیال|بیخیال)', text):
        logic = default_logic()

    # Latest explicit action wins: when a criterion is directly redefined without a
    # compound phrase, remove stale rules involving that same criterion only.
    relative_expression = bool(re.search(r'مهم\s*تر|رو\s+به\s+.+?ترجیح\s*می\s*دم|اولویت.+?بیشتر\s+از', text))
    if not relative_expression:
        mentioned = set()
        for key, pattern in BASE_PRIORITY_PATTERNS.items():
            if re.search(pattern, text, re.I): mentioned.add('base:' + key)
        for key, pattern in EVIDENCE_PRIORITY_PATTERNS.items():
            if re.search(pattern, text, re.I): mentioned.add('evidence:' + key)
        if mentioned:
            logic['relative_priorities'] = [r for r in logic['relative_priorities'] if r['higher'] not in mentioned and r['lower'] not in mentioned]

    defines_floor_conditional = bool(re.search(r'طبقه.{0,35}(?:اگر|اگه|به\s*شرط|فقط\s*با).{0,30}آسانسور|(?:اگر|اگه).{0,20}آسانسور.{0,35}(?:طبقه|بالاتر)', text))
    defines_old_condition = bool(re.search(r'(?:اگر|اگه).{0,22}قدیمی|قدیمی.{0,30}(?:اگر|اگه|به\s*شرط)|(?:نوساز|جدید).{0,30}(?:ولی|اما).{0,25}قدیمی', text))
    defines_parking_condition = bool(re.search(r'پارکینگ.{0,35}(?:اگر|اگه)|(?:اگر|اگه).{0,35}پارکینگ', text))
    defines_rent_condition = bool(re.search(r'(?:اجاره|کرایه).{0,50}(?:اگر|اگه)|(?:اگر|اگه).{0,50}(?:اجاره|کرایه)', text))
    fallback_signal = bool(re.search(r'(?:اگر|اگه).{0,30}(?:نبود|پیدا\s*نشد|کم\s*بود)', text))

    if re.search(r'طبقه', text) and not defines_floor_conditional:
        logic['conditionals'] = [r for r in logic['conditionals'] if r['type'] != 'require_elevator_if_floor_min']
    if re.search(r'آسانسور', text) and not defines_floor_conditional and not defines_old_condition:
        logic['conditionals'] = [r for r in logic['conditionals'] if r['type'] not in ('require_elevator_if_floor_min', 'require_elevator_if_old')]
    if re.search(r'نوساز|قدیمی|سن\s*بنا|سال\s*ساخت|بازسازی|نوسازی', text) and not defines_old_condition:
        logic['conditionals'] = [r for r in logic['conditionals'] if r['type'] not in ('require_renovation_if_old','require_elevator_if_old')]
    if re.search(r'پارکینگ|جای\s*پارک', text) and not defines_parking_condition:
        logic['conditionals'] = [r for r in logic['conditionals'] if not (r['type'] in ('relax_preference_if_commute_close','relax_preference_if_evidence') and r.get('target') == 'parking')]
    if re.search(r'متراژ|مساحت', text) and not re.search(r'اگر|اگه', text):
        logic['conditionals'] = [r for r in logic['conditionals'] if not (r['type'] == 'relax_area_min_if_commute_close' or (r['type'] == 'relax_preference_if_commute_close' and r.get('target') == 'area'))]
    if re.search(r'اجاره|کرایه', text) and not defines_rent_condition:
        logic['conditionals'] = [r for r in logic['conditionals'] if r['type'] != 'conditional_max_rent_if_commute_close']
    if not fallback_signal:
        from .patches import location_mentions
        residence,_ = location_mentions(text,current,neighborhoods)
        if residence or re.search(r'(?:محله|محدوده).{0,18}(?:مهم\s*نیست|فرقی\s*ندار|بی\s*خیال)',text): logic['fallbacks'] = [r for r in logic['fallbacks'] if r['type'] != 'neighborhood_scope']
        if re.search(r'اجاره|کرایه', text): logic['fallbacks'] = [r for r in logic['fallbacks'] if r['type'] != 'max_rent']
        if re.search(r'خواب|اتاق\s*خواب', text): logic['fallbacks'] = [r for r in logic['fallbacks'] if r['type'] != 'bedrooms_allowed']
        if re.search(r'پارکینگ|جای\s*پارک', text): logic['fallbacks'] = [r for r in logic['fallbacks'] if r['type'] != 'relax_parking']
        if re.search(r'نوساز|قدیمی|بازسازی|سن\s*بنا', text): logic['fallbacks'] = [r for r in logic['fallbacks'] if r['type'] != 'new_then_renovated_old']

    # ---------- relative priority ----------
    relative_patterns = (
        r'(.+?)\s+از\s+(.+?)\s+مهم\s*تر(?:ه|\s*است)?',
        r'(.+?)\s+رو\s+به\s+(.+?)\s+ترجیح\s*می\s*دم',
        r'اولویت\s+(.+?)\s+بیشتر\s+از\s+(.+?)(?:ه|\s*است|$)',
    )
    for pattern in relative_patterns:
        for m in re.finditer(pattern, text):
            # A previous clause may precede the relative statement ("view is nice, but
            # quietness is more important than view").  Only the last discourse clause
            # before «از» names the higher criterion.
            higher_phrase = re.split(r'(?:ولی|اما|،|؛)', m.group(1))[-1].strip()
            lower_phrase = re.split(r'(?:ولی|اما|،|؛)', m.group(2))[0].strip()
            higher, lower = _token_for_phrase(higher_phrase), _token_for_phrase(lower_phrase)
            if higher and lower and higher != lower:
                _set_priority_token(result, higher, 'very_high')
                # A lower criterion remains a preference rather than being silently deleted.
                _set_priority_token(result, lower, 'low')
                _add_unique(logic['relative_priorities'], {'higher': higher, 'lower': lower})

    # Superlative phrasing has no concrete lower token: "commute is more important than everything".
    supreme = re.search(r'(.+?)\s+از\s+همه(?:\s*چی|\s*چیز)?\s+مهم\s*تر(?:ه|\s*است)?', text)
    if supreme:
        # Scope the subject to the final discourse clause.  Without this, a query
        # such as «پارکینگ مهم نیست؛ رفت و آمد از همه چیز مهم تره» can bind the
        # superlative to the earlier parking token because parking appears first in
        # the combined regex search order.
        subject = re.split(r'(?:ولی|اما|،|؛)', supreme.group(1))[-1].strip()
        token = _token_for_phrase(subject)
        if token:
            _set_priority_token(result, token, 'very_high')

    # "X is the least important" has no counterpart in the generic relative regex.
    least = re.search(r'(.+?)\s+از\s+همه(?:\s*چی|\s*چیز)?\s+کم\s*اهمیت\s*تر(?:ه|\s*است)?', text)
    if least:
        subject = re.split(r'(?:ولی|اما|،|؛)', least.group(1))[-1].strip()
        token = _token_for_phrase(subject)
        if token:
            _set_priority_token(result, token, 'low')

    # ---------- conditional floor/elevator ----------
    floor_token = rf'(?:{SMALL_NUMBER_TOKEN}|اول|دوم|سوم|چهارم|پنجم|ششم|هفتم|هشتم|نهم|دهم)'
    m = re.search(rf'طبقه\s*({floor_token})\s*(?:به\s*بالا|یا\s*بالاتر).{{0,24}}(?:فقط\s*)?(?:اگر|اگه|به\s*شرطی\s*که|با).{{0,24}}آسانسور', text)
    if m:
        value = number_value(m.group(1))
        if value is not None:
            # The floor wording describes the condition, not a global minimum floor.
            result.constraints['floor'] = deepcopy(current.constraints['floor'])
            _restore_amenity(result, current, 'elevator')
            result.preferences['elevator'] = current.preferences['elevator']
            _add_unique(logic['conditionals'], {'type': 'require_elevator_if_floor_min', 'floor_min': value})

    # Equivalent natural order: "if it is floor four or higher, it must have an elevator".
    m_alt = re.search(rf'(?:اگر|اگه)\s*(?:طبقه\s*)?({floor_token})\s*(?:یا\s*بالاتر|به\s*بالا|به\s*بالاتر).{{0,28}}(?:حتما|باید|لازم).{{0,14}}آسانسور', text)
    if m_alt:
        value = number_value(m_alt.group(1))
        if value is not None:
            result.constraints['floor'] = deepcopy(current.constraints['floor'])
            _restore_amenity(result, current, 'elevator')
            result.preferences['elevator'] = current.preferences['elevator']
            _add_unique(logic['conditionals'], {'type': 'require_elevator_if_floor_min', 'floor_min': value})

    m = re.search(r'(?:اگر|اگه)\s*آسانسور\s*(?:نداره|نباشه|نبود).{0,35}(?:حداکثر\s*)?(?:طبقه\s*)?(' + floor_token + r')(?:\s*باشه)?', text)
    if not m:
        m = re.search(r'(?:اگر|اگه).{0,18}آسانسور.{0,10}(?:نداره|نباشه|نبود).{0,28}بالاتر\s*از\s*(' + floor_token + r').{0,12}(?:نباش|نمی\s*خوام)', text)
    if m:
        value = number_value(m.group(1))
        if value is not None:
            result.constraints['floor'] = deepcopy(current.constraints['floor'])
            _add_unique(logic['conditionals'], {'type': 'require_elevator_if_floor_min', 'floor_min': value + 1})

    # Compact equivalent without an explicit "if": "without elevator, max floor two".
    m_no_elevator = re.search(r'بدون\s*آسانسور.{0,25}(?:حداکثر\s*)?(?:طبقه\s*)?(' + floor_token + r')|(?:حداکثر\s*)?(?:طبقه\s*)?(' + floor_token + r').{0,20}بدون\s*آسانسور', text)
    if m_no_elevator:
        raw = m_no_elevator.group(1) or m_no_elevator.group(2)
        value = number_value(raw)
        if value is not None:
            result.constraints['floor'] = deepcopy(current.constraints['floor'])
            _add_unique(logic['conditionals'], {'type': 'require_elevator_if_floor_min', 'floor_min': value + 1})

    # ---------- old building exceptions ----------
    old_and_elevator = re.search(r'(?:اگر|اگه).{0,18}قدیمی.{0,28}(?:حتما|باید|لازم).{0,12}آسانسور|(?:نوساز|جدید).{0,30}(?:ولی|اما).{0,30}قدیمی.{0,40}با\s*آسانسور.{0,15}(?:قبول|اوکی)', text)
    if old_and_elevator:
        _restore_amenity(result, current, 'elevator')
        result.preferences['elevator'] = current.preferences['elevator']
        _add_unique(logic['conditionals'], {'type': 'require_elevator_if_old', 'old_before': NEW_BUILD_YEAR})

    # "new preferred, old okay only if renovated" / "old okay if renovated".
    if re.search(r'(?:قدیمی|سن\s*بنا).{0,30}(?:اگر|اگه|به\s*شرط).{0,24}(?:بازسازی|نوسازی)|(?:نوساز|جدید).{0,30}(?:ولی|اما).{0,25}قدیمی.{0,25}بازسازی|(?:اگر|اگه).{0,12}قدیمی.{0,25}بازسازی', text):
        # The older v0.9-B parser intentionally did not globalize renovation; ensure it stays conditional.
        result.constraints['renovation_required'] = current.constraints['renovation_required']
        if result.preferences['building_age'] in ('ignored', 'low'):
            result.preferences['building_age'] = 'high'
        _add_unique(logic['conditionals'], {'type': 'require_renovation_if_old', 'old_before': NEW_BUILD_YEAR})

    # Numeric parking preference with an explicitly smaller acceptable commute exception.
    count_preference = re.search(rf'({SMALL_NUMBER_TOKEN})\s*(?:تا\s*)?پارکینگ[^.؛،]{{0,18}}ترجیح[^.؛]{{0,28}}(?:اگر|اگه)[^.؛]{{0,28}}نزدیک\s*محل\s*کار[^.؛]{{0,22}}({SMALL_NUMBER_TOKEN}|یکی)\s*هم\s*قبول', text)
    if count_preference:
        preferred = number_value(count_preference[1])
        close = 1 if count_preference[2] == 'یکی' else number_value(count_preference[2])
        if preferred and close and 1 <= close <= preferred <= 5:
            result.constraints['parking_count_min'] = current.constraints['parking_count_min']
            _restore_amenity(result, current, 'parking')
            result.preferences['parking'] = 'high'
            _add_unique(logic['conditionals'], {'type':'relax_preference_if_commute_close','target':'parking','max_km':DEFAULT_CLOSE_COMMUTE_KM,'to':'low','preferred_count':preferred,'close_count':close})

    # ---------- conditional preference relaxation ----------
    parking_clause = re.search(r'پارکینگ.{0,25}(?:مهم\s*نیست|لازم\s*نیست|می\s*تونم.{0,8}بی\s*خیال).{0,35}(?:اگر|اگه).{0,45}(نزدیک\s*محل\s*کار|رفت\s*و\s*آمد.{0,10}(?:کوتاه|خوب)|مترو.{0,12}(?:نزدیک|دم\s*دست))', text)
    if not parking_clause:
        # Inverse wording: "a home without parking is acceptable only if it is very close to work".
        parking_clause = re.search(r'(?:اگر|اگه)?\s*پارکینگ\s*(?:نداره|نباشه|نداشت).{0,28}(?:فقط\s*)?(?:وقتی|اگر|اگه|به\s*شرط).{0,35}(نزدیک\s*محل\s*کار|رفت\s*و\s*آمد.{0,10}(?:کوتاه|خوب)|مترو.{0,12}(?:نزدیک|دم\s*دست))', text)
    if parking_clause:
        # Outside the condition, preserve the previous parking importance.  For a fresh
        # query with no prior signal, "not important IF ..." implies it matters otherwise.
        prior = current.preferences['parking']
        result.preferences['parking'] = prior if PRIORITY_ORDER[prior] >= PRIORITY_ORDER['medium'] else 'high'
        # Flat parsing may have removed a previously-hard parking requirement because it
        # saw «مهم نیست».  Restore the base requirement; the conditional matcher below
        # relaxes it only for listings that satisfy the IF clause.
        _restore_amenity(result, current, 'parking')
        if 'مترو' in parking_clause.group(1):
            _add_unique(logic['conditionals'], {'type': 'relax_preference_if_evidence', 'target': 'parking', 'evidence': 'near_metro', 'to': 'ignored'})
        else:
            if current.context.get('workplace') != 'none':
                result.preferences['commute'] = max(result.preferences['commute'], 'high', key=lambda p: PRIORITY_ORDER[p])
            _add_unique(logic['conditionals'], {'type': 'relax_preference_if_commute_close', 'target': 'parking', 'max_km': DEFAULT_CLOSE_COMMUTE_KM, 'to': 'ignored'})

    # Generic soft relaxation: "A is not important if commute is very good".
    generic_relax = re.search(r'(.{1,32}?)(?:مهم\s*نیست|کم\s*اهمیت(?:ه|\s*است)?|لازم\s*نیست).{0,24}(?:اگر|اگه).{0,38}(نزدیک\s*محل\s*کار|رفت\s*و\s*آمد.{0,12}(?:کوتاه|خوب|بهتر))', text)
    if generic_relax:
        target = _token_for_phrase(generic_relax.group(1))
        if target and target.startswith('base:'):
            key = target.split(':', 1)[1]
            prior = current.preferences.get(key, 'ignored')
            result.preferences[key] = prior if PRIORITY_ORDER[prior] >= PRIORITY_ORDER['medium'] else 'high'
            if current.context.get('workplace') != 'none':
                result.preferences['commute'] = max(result.preferences['commute'], 'high', key=lambda p: PRIORITY_ORDER[p])
            _add_unique(logic['conditionals'], {'type': 'relax_preference_if_commute_close', 'target': key, 'max_km': DEFAULT_CLOSE_COMMUTE_KM, 'to': 'ignored'})

    # Hard minimum area can also be conditionally relaxed in a refinement.  We only
    # do this when a concrete previous minimum exists; we never invent a threshold.
    if current.constraints.get('area', {}).get('min') is not None and re.search(r'متراژ\s*(?:کمتر|پایین\s*تر).{0,20}(?:اوکی|قبول|اشکال\s*نداره).{0,24}(?:اگر|اگه).{0,35}(?:رفت\s*و\s*آمد|نزدیک\s*محل\s*کار)', text):
        result.constraints['area'] = deepcopy(current.constraints['area'])
        _add_unique(logic['conditionals'], {'type': 'relax_area_min_if_commute_close', 'base_min': current.constraints['area']['min'], 'max_km': DEFAULT_CLOSE_COMMUTE_KM})

    # ---------- conditional rent cap ----------
    # Patch form: existing cap stays strict, a larger cap is allowed only when very close.
    if re.search(r'(?:فقط\s*)?(?:اگر|اگه).{0,35}(?:خیلی\s*)?نزدیک\s*محل\s*کار', text) and re.search(r'اجاره|کرایه', text):
        amounts = _money_amounts(text, r'اجاره|کرایه')
        base_cap = current.constraints.get('max_rent')
        relaxed = max(amounts) if amounts else result.constraints.get('max_rent')
        if base_cap is not None and relaxed is not None and relaxed > base_cap:
            result.constraints['max_rent'] = base_cap
            result.targets['rent'] = current.targets['rent']
            _add_unique(logic['conditionals'], {
                'type': 'conditional_max_rent_if_commute_close',
                'base_max': base_cap, 'relaxed_max': relaxed, 'max_km': DEFAULT_CLOSE_COMMUTE_KM,
            })

    # ---------- progressive fallback: location ----------
    names = sorted(set(neighborhoods), key=len, reverse=True)
    if fallback_signal:
        for name in names:
            n = normalize_persian(name)
            if n in text and re.search(r'(?:اول|فقط|خود).{0,14}' + re.escape(n), text) and re.search(r'اطرافش|نزدیکش|(?:اطراف|نزدیکای|نزدیک).{0,12}' + re.escape(n) + r'|' + re.escape(n) + r'.{0,15}اطراف', text):
                result.constraints['neighborhoods'] = [name]
                result.constraints['neighborhood_mode'] = 'exact'
                _add_unique(logic['fallbacks'], {'type': 'neighborhood_scope', 'to': 'nearby', 'trigger_min_results': _fallback_threshold(text)})
                break
        if not any(r['type'] == 'neighborhood_scope' for r in logic['fallbacks']) and current.constraints.get('neighborhoods') and re.search(r'(?:همون|همان).{0,12}(?:محله|محدوده)|اطرافش|نزدیکش', text):
            result.constraints['neighborhoods'] = deepcopy(current.constraints['neighborhoods'])
            result.constraints['neighborhood_mode'] = 'exact'
            _add_unique(logic['fallbacks'], {'type': 'neighborhood_scope', 'to': 'nearby', 'trigger_min_results': _fallback_threshold(text)})

        # Rent fallback: first cap, then larger cap.
        amounts = _money_amounts(text, r'اجاره|کرایه')
        all_amounts = []
        if not re.search(r'ودیعه|رهن|پول\s*پیش', text):
            for raw, unit in re.findall(r'(\d+(?:\.\d+)?)\s*(میلیون|میلیارد)', text):
                value = int(float(raw) * (1_000_000 if unit == 'میلیون' else 1_000_000_000))
                if value not in all_amounts:
                    all_amounts.append(value)
        # Persian users often omit «اجاره» in stage two, or omit the noun entirely in
        # a follow-up because the current search already establishes the field.
        if len(amounts) < 2 and (re.search(r'اجاره|کرایه', text) or len(all_amounts) >= 2):
            for value in all_amounts:
                if value not in amounts: amounts.append(value)
        if all_amounts and re.search(r'اجاره|کرایه', text):
            # Stage two may inherit the explicitly stated million/billion unit.
            tail = re.split(r'اگر|اگه', text, maxsplit=1)[-1]
            for raw in re.findall(r'تا\s*(\d+)(?![\d]).{0,5}(?:هم|اوکی)', tail):
                value = int(raw) * (1_000_000_000 if 'میلیارد' in text else 1_000_000)
                if value not in amounts: amounts.append(value)
        current_cap = current.constraints.get('max_rent')
        if current_cap is not None and all_amounts:
            for value in all_amounts:
                if value not in amounts: amounts.append(value)
            if current_cap not in amounts: amounts.insert(0, current_cap)
            else:
                amounts = [current_cap] + [v for v in amounts if v != current_cap]
        if len(amounts) >= 2:
            base, relaxed = amounts[0], max(amounts[1:])
            if relaxed > base:
                result.targets['rent'] = base
                result.constraints['max_rent'] = base
                _add_unique(logic['fallbacks'], {'type': 'max_rent', 'to': relaxed, 'trigger_min_results': _fallback_threshold(text)})

        # Bedroom fallback: "first 2BR, if few/no results include 3BR".
        bed_values = []
        for m in re.finditer(rf'({SMALL_NUMBER_TOKEN})\s*(?:خواب|خوابه|اتاق\s*خواب)', text):
            value = number_value(m.group(1))
            if value is not None and 1 <= value <= 5 and value not in bed_values:
                bed_values.append(value)
        if len(bed_values) >= 2 and re.search(r'اول.{0,30}(?:خواب|خوابه)', text):
            result.constraints['bedrooms'] = {'mode': 'exact', 'value': bed_values[0]}
            _add_unique(logic['fallbacks'], {'type': 'bedrooms_allowed', 'values': sorted(set(bed_values[:2])), 'trigger_min_results': _fallback_threshold(text)})
        elif len(bed_values) >= 1 and current.constraints['bedrooms']['mode'] in ('exact','allowed'):
            prior_values = current.constraints['bedrooms']['value'] if current.constraints['bedrooms']['mode'] == 'allowed' else [current.constraints['bedrooms']['value']]
            values = sorted(set([*prior_values, *bed_values]))
            if values != sorted(set(prior_values)):
                result.constraints['bedrooms'] = deepcopy(current.constraints['bedrooms'])
                _add_unique(logic['fallbacks'], {'type': 'bedrooms_allowed', 'values': values, 'trigger_min_results': _fallback_threshold(text)})

        if re.search(r'اول.{0,30}پارکینگ.{0,35}(?:اگر|اگه).{0,25}(?:بدون\s*پارکینگ|پارکینگ\s*لازم\s*نیست)', text):
            if 'parking' not in result.constraints['required_amenities']:
                result.constraints['required_amenities'].append('parking')
            result.preferences['parking'] = 'very_high'
            _add_unique(logic['fallbacks'], {'type': 'relax_parking', 'trigger_min_results': _fallback_threshold(text)})

        if re.search(r'اول.{0,15}(?:نوساز|جدید).{0,35}(?:اگر|اگه).{0,25}(?:قدیمی).{0,25}(?:بازسازی|نوسازی)', text):
            result.constraints['construction_year_min'] = NEW_BUILD_YEAR
            result.constraints['renovation_required'] = False
            _add_unique(logic['fallbacks'], {'type': 'new_then_renovated_old', 'new_year': NEW_BUILD_YEAR, 'trigger_min_results': _fallback_threshold(text)})

    result.logic = logic
    validate_logic(result.logic)
    return result


def area_min_matches(listing, intent) -> bool:
    """Evaluate the canonical area minimum with any explicit conditional relaxation.

    A minimum area remains hard by default.  A rule may relax it only for listings
    that satisfy the user's stated commute condition.
    """
    minimum = intent.constraints.get('area', {}).get('min')
    if minimum is None or getattr(listing, 'area_m2', 0) >= minimum:
        return True
    for rule in intent.logic.get('conditionals', []):
        if rule['type'] == 'relax_area_min_if_commute_close' and rule['base_min'] == minimum and _commute_close(listing, intent, rule['max_km']):
            return True
    return False


def conditional_eligibility(listing, intent) -> bool:
    """Evaluate only the additional v0.9-D conditional rules."""
    for rule in getattr(intent, 'logic', LOGIC_DEFAULT).get('conditionals', []):
        t = rule['type']
        if t == 'require_elevator_if_floor_min':
            floor = getattr(listing, 'floor', None)
            if floor is not None and floor >= rule['floor_min'] and getattr(listing, 'elevator', None) is not True:
                return False
        elif t == 'require_elevator_if_old':
            year = getattr(listing, 'construction_year', None)
            if year is not None and year < rule['old_before'] and getattr(listing, 'elevator', None) is not True:
                return False
        elif t == 'require_renovation_if_old':
            year = getattr(listing, 'construction_year', None)
            if year is not None and year < rule['old_before'] and not _renovated(listing):
                return False
        elif t == 'conditional_max_rent_if_commute_close':
            rent = getattr(listing, 'monthly_rent', 0)
            if rent > rule['base_max']:
                if rent > rule['relaxed_max'] or not _commute_close(listing, intent, rule['max_km']):
                    return False
    return True


def parking_relaxation_applies(listing, intent) -> bool:
    for rule in intent.logic.get('conditionals', []):
        if rule.get('target') != 'parking':
            continue
        if 'preferred_count' in rule:
            continue  # A soft count preference cannot waive an independent hard requirement.
        if rule['type'] == 'relax_preference_if_commute_close' and _commute_close(listing, intent, rule['max_km']):
            return True
        if rule['type'] == 'relax_preference_if_evidence' and _evidence_yes(listing, rule['evidence']):
            return True
    return False


def effective_evidence_constraints(listing, intent) -> dict:
    constraints = intent.constraints
    if parking_relaxation_applies(listing, intent):
        constraints = dict(constraints)
        constraints.update(parking_count_min=None, parking_non_tandem_required=False, parking_dedicated_required=False)
    return constraints


def amenity_requirement_matches(listing, intent) -> bool:
    """Hard amenity requirements with explicit conditional relaxations."""
    for amenity in intent.constraints['required_amenities']:
        if getattr(listing, amenity, None) is True:
            continue
        relaxed = False
        if amenity == 'parking':
            for rule in intent.logic.get('conditionals', []):
                if rule['type'] == 'relax_preference_if_commute_close' and rule['target'] == 'parking' and 'preferred_count' not in rule and _commute_close(listing, intent, rule['max_km']):
                    relaxed = True
                if rule['type'] == 'relax_preference_if_evidence' and rule['target'] == 'parking' and _evidence_yes(listing, rule['evidence']):
                    relaxed = True
        if not relaxed:
            return False
    return True


def budget_cap_matches(listing, intent) -> bool:
    c = intent.constraints
    if c['max_deposit'] is not None and listing.deposit > c['max_deposit']:
        return False
    # A conditional rent rule replaces the ordinary max-rent check.
    rent_rules = [r for r in intent.logic.get('conditionals', []) if r['type'] == 'conditional_max_rent_if_commute_close']
    if rent_rules:
        # conditional_eligibility() performs the detailed rule check.
        return True
    return c['max_rent'] is None or listing.monthly_rent <= c['max_rent']


def effective_priorities(listing, intent):
    """Return per-listing priority maps after conditional relaxations."""
    base = dict(intent.preferences)
    evidence = dict(intent.evidence_preferences)
    for rule in intent.logic.get('conditionals', []):
        applies = False
        if rule['type'] == 'relax_preference_if_commute_close':
            applies = _commute_close(listing, intent, rule['max_km'])
        elif rule['type'] == 'relax_preference_if_evidence':
            applies = _evidence_yes(listing, rule['evidence'])
        if applies:
            base[rule['target']] = rule['to']
            if rule['target'] == 'parking':
                evidence.update(parking_non_tandem='ignored', parking_dedicated='ignored')
    return base, evidence


def fit_overrides(listing, intent, fits: dict) -> dict:
    """Controlled scoring exceptions: an accepted exception should not look like failure."""
    fits = dict(fits)
    for rule in intent.logic.get('conditionals', []):
        if 'preferred_count' in rule:
            count = extract_listing_evidence(listing).parking_count
            target = rule['close_count'] if _commute_close(listing, intent, rule['max_km']) else rule['preferred_count']
            fits['parking'] = min(count / target, 1) if count is not None else 0
        if rule['type'] == 'require_renovation_if_old':
            year = getattr(listing, 'construction_year', None)
            if year is not None and year < rule['old_before'] and _renovated(listing):
                # New remains preferred (1.0); renovated-old is explicitly acceptable.
                fits['building_age'] = max(fits.get('building_age') or 0, 0.7)
    return fits


def conditional_notes(listing, intent) -> tuple[list[str], list[str]]:
    reasons, tradeoffs = [], []
    for rule in intent.logic.get('conditionals', []):
        t = rule['type']
        if t == 'require_elevator_if_floor_min':
            floor = getattr(listing, 'floor', None)
            if floor is None:
                tradeoffs.append('طبقه آگهی مشخص نیست؛ شرط آسانسور برای طبقات بالا نیاز به بررسی دارد')
            elif floor >= rule['floor_min'] and getattr(listing, 'elevator', None) is True:
                reasons.append('در این طبقه، شرط آسانسور تو رعایت شده')
        elif t == 'require_elevator_if_old':
            year = getattr(listing, 'construction_year', None)
            if year is None:
                tradeoffs.append('سال ساخت مشخص نیست؛ شرط آسانسور برای ساختمان قدیمی نیاز به بررسی دارد')
            elif year < rule['old_before'] and getattr(listing, 'elevator', None) is True:
                reasons.append('ساختمان قدیمی‌تر است و طبق شرط تو آسانسور دارد')
        elif t == 'require_renovation_if_old':
            year = getattr(listing, 'construction_year', None)
            if year is None:
                tradeoffs.append('سال ساخت مشخص نیست؛ استثنای بازسازی نیاز به بررسی دارد')
            elif year < rule['old_before'] and _renovated(listing):
                reasons.append('قدیمی‌تر است اما بازسازی‌شده؛ مطابق استثنای تو')
        elif t == 'relax_preference_if_commute_close' and _commute_close(listing, intent, rule['max_km']):
            reasons.append('به‌خاطر نزدیکی به محل کار، ' + BASE_LABELS[rule['target']] + ' طبق شرط تو وزن کمتری دارد')
        elif t == 'relax_preference_if_evidence' and _evidence_yes(listing, rule['evidence']):
            reasons.append(EVIDENCE_LABELS[rule['evidence']] + ' باعث شده ' + BASE_LABELS[rule['target']] + ' طبق شرط تو کم‌اهمیت شود')
        elif t == 'conditional_max_rent_if_commute_close' and listing.monthly_rent > rule['base_max'] and _commute_close(listing, intent, rule['max_km']):
            reasons.append('اجاره بالاتر فقط به‌دلیل نزدیکی زیاد به محل کار پذیرفته شده')
        elif t == 'relax_area_min_if_commute_close' and getattr(listing, 'area_m2', 0) < rule['base_min'] and _commute_close(listing, intent, rule['max_km']):
            reasons.append('متراژ کمتر فقط به‌دلیل رفت‌وآمد خیلی بهتر طبق شرط تو پذیرفته شده')
    return reasons, tradeoffs


def logic_labels(intent) -> list[str]:
    labels = []
    for rule in intent.logic.get('relative_priorities', []):
        labels.append(token_label(rule['higher']) + ' مهم‌تر از ' + token_label(rule['lower']))
    for rule in intent.logic.get('conditionals', []):
        t = rule['type']
        if t == 'require_elevator_if_floor_min':
            labels.append(f'طبقه {rule["floor_min"]}+ فقط با آسانسور')
        elif t == 'require_elevator_if_old':
            labels.append('ساختمان قدیمی فقط با آسانسور')
        elif t == 'require_renovation_if_old':
            labels.append('خانه قدیمی فقط اگر بازسازی‌شده باشد')
        elif t == 'relax_preference_if_commute_close':
            labels.append(f'{rule["preferred_count"]} پارکینگ ترجیحی؛ نزدیک محل کار {rule["close_count"]} هم پذیرفته است' if 'preferred_count' in rule else BASE_LABELS[rule['target']] + ' در صورت نزدیکی به محل کار کم‌اهمیت می‌شود')
        elif t == 'relax_preference_if_evidence':
            labels.append(BASE_LABELS[rule['target']] + ' در صورت ' + EVIDENCE_LABELS[rule['evidence']] + ' کم‌اهمیت می‌شود')
        elif t == 'conditional_max_rent_if_commute_close':
            labels.append('اجاره بالاتر فقط برای گزینه خیلی نزدیک به محل کار')
        elif t == 'relax_area_min_if_commute_close':
            labels.append('متراژ کمتر فقط برای گزینه خیلی نزدیک به محل کار')
    for rule in intent.logic.get('fallbacks', []):
        t = rule['type']
        suffix = 'اگر نتیجه کافی نبود'
        if t == 'neighborhood_scope': labels.append('اول محله دقیق؛ سپس اطراف ' + suffix)
        elif t == 'max_rent': labels.append('افزایش سقف اجاره در مرحله دوم ' + suffix)
        elif t == 'bedrooms_allowed': labels.append('گسترش تعداد خواب در مرحله دوم ' + suffix)
        elif t == 'relax_parking': labels.append('حذف الزام پارکینگ در مرحله دوم ' + suffix)
        elif t == 'new_then_renovated_old': labels.append('اول نوساز؛ سپس قدیمیِ بازسازی‌شده ' + suffix)
    return labels


def apply_fallback_rule(intent, rule: dict):
    """Return a new SearchIntent-like object with one fallback stage applied."""
    stage = intent.copy()
    t = rule['type']
    if t == 'neighborhood_scope':
        stage.constraints['neighborhood_mode'] = 'nearby'
    elif t == 'max_rent':
        stage.constraints['max_rent'] = rule['to']
        stage.targets['rent'] = rule['to']
    elif t == 'bedrooms_allowed':
        stage.constraints['bedrooms'] = {'mode': 'allowed', 'value': sorted(set(rule['values']))}
    elif t == 'relax_parking':
        stage.constraints['required_amenities'] = [x for x in stage.constraints['required_amenities'] if x != 'parking']
        stage.preferences['parking'] = 'low'
        stage.constraints.update(parking_count_min=None, parking_non_tandem_required=False, parking_dedicated_required=False)
        stage.evidence_preferences.update(parking_non_tandem='ignored', parking_dedicated='ignored')
    elif t == 'new_then_renovated_old':
        stage.constraints['construction_year_min'] = None
        _add_unique(stage.logic['conditionals'], {'type': 'require_renovation_if_old', 'old_before': rule.get('new_year', NEW_BUILD_YEAR)})
    stage.__post_init__()
    return stage


def fallback_label(rule: dict) -> str:
    return {
        'neighborhood_scope': 'محدوده جستجو از خود محله به اطراف آن گسترش یافت',
        'max_rent': 'سقف اجاره طبق مرحله جایگزین افزایش یافت',
        'bedrooms_allowed': 'تعداد خواب طبق مرحله جایگزین گسترده شد',
        'relax_parking': 'الزام پارکینگ در مرحله جایگزین برداشته شد',
        'new_then_renovated_old': 'خانه‌های قدیمیِ بازسازی‌شده به مرحله جایگزین اضافه شدند',
    }[rule['type']]
