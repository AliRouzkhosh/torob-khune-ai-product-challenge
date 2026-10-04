"""Shared Persian-language normalization and deterministic phrase helpers.

This module deliberately has no Django dependency.  It is the runtime bridge between
KhaneYab's declarative search-language specification and the existing heuristic
parser.  The YAML language pack remains documentation/test data; production parsing
uses controlled helpers here so the app does not need PyYAML at request time.
"""
from __future__ import annotations

import re

DIGIT_TRANSLATION = str.maketrans(
    '۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩',
    '01234567890123456789',
)
CHAR_TRANSLATION = str.maketrans({
    'ي': 'ی', 'ى': 'ی', 'ك': 'ک', 'ۀ': 'ه', 'ة': 'ه',
})

# Deliberately conservative lexical canonicalization.  These variants are common in
# Persian search boxes and should not require every downstream regex to duplicate them.
LEXICAL_REPLACEMENTS = (
    (r'\bنمی\s*خوام\b|\bنمي\s*خوام\b|\bنمیخوام\b', 'نمی خوام'),
    (r'\bمی\s*خوام\b|\bمي\s*خوام\b|\bمیخوام\b|\bمیخام\b|\bميخام\b', 'می خوام'),
    (r'\bمی\s*خوایم\b|\bمیخوایم\b|\bمی\s*خواهیم\b|\bمیخواهیم\b', 'می خوایم'),
    (r'\bاسانسور\b|\bآسان\s*سور\b', 'آسانسور'),
    (r'\bبالکون\b', 'بالکن'),
    (r'\bتومن\b', 'تومان'),
    (r'\bملیون\b', 'میلیون'),
    (r'\bبی\s*(?:آر\s*تی|ار\s*تی|آرتی|ارتی)\b', 'BRT'),
    (r'\bدوروبر\b', 'دور و بر'),
    (r'\bخوشنقشه\b', 'خوش نقشه'),
    (r'\bتک\s*واحدی\b', 'تک واحدی'),
)

NUMBER_WORDS = {
    'صفر': 0, 'یک': 1, 'یه': 1, 'اول': 1,
    'دو': 2, 'دوم': 2,
    'سه': 3, 'سوم': 3,
    'چهار': 4, 'چهارم': 4,
    'پنج': 5, 'پنجم': 5,
    'شش': 6, 'ششم': 6,
    'هفت': 7, 'هفتم': 7,
    'هشت': 8, 'هشتم': 8,
    'نه': 9, 'نهم': 9,
    'ده': 10, 'دهم': 10,
}

SMALL_NUMBER_TOKEN = r'(?:[0-9]{1,3}(?![0-9])|یک|یه|دو|سه|چهار|پنج|شش|هفت|هشت|نه|ده)'
ORDINAL_NUMBER_TOKEN = r'(?:[0-9]{1,3}(?![0-9])|اول|دوم|سوم|چهارم|پنجم|ششم|هفتم|هشتم|نهم|دهم)'

REQUIRED_RE = re.compile(
    r'حتما|الزامی|اجباری|ضروری|واجب|لازم\s*دارم|لازمه|باید\s*داشته\s*باش|بدونش\s*نمی\s*خوام'
)
NEGATION_RE = re.compile(
    r'(?:اصلا\s*)?مهم\s*نیست|لازم\s*نیست|ضروری\s*نیست|نمی\s*خوام|'
    r'اهمیت(?:ی)?\s*ندار|لازم\s*ندارم|فرقی\s*ندار|بی\s*خیال|بیخیال'
)
PREFERENCE_RE = re.compile(r'ترجیح|بهتره|دوست\s*دارم|مزیت|امتیاز')
VERY_HIGH_RE = re.compile(r'خیلی\s*مهم|مهم\s*ترین|اولویت\s*اول|از\s*همه(?:\s*چیز)?\s*مهم\s*تر|حتما|واجب')


def normalize_persian(text: str) -> str:
    """Normalize Persian user input while preserving semantic wording.

    The function is idempotent and intentionally does not stem/tokenize Persian.
    """
    text = str(text or '').translate(DIGIT_TRANSLATION).translate(CHAR_TRANSLATION)
    text = re.sub(r'[\u064b-\u065f\u0640]', '', text).replace('\u200c', ' ')
    # Normalize punctuation spacing before lexical variants.
    text = re.sub(r'\s+', ' ', text).strip()
    for pattern, replacement in LEXICAL_REPLACEMENTS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def number_value(token: str | None) -> int | None:
    if token is None:
        return None
    token = normalize_persian(token)
    if token.isdigit():
        return int(token)
    return NUMBER_WORDS.get(token)


def extract_money(text: str, aliases: tuple[str, ...]) -> int | None:
    """Extract a million/billion Toman amount near one of ``aliases``.

    Supports both ``800 میلیون ودیعه`` and ``ودیعه تا 800 میلیون`` style input.
    """
    text = normalize_persian(text)
    alias = r'(?:' + '|'.join(re.escape(a) for a in aliases) + r')'
    amount = r'(\d+(?:\.\d+)?)\s*(میلیون|میلیارد)'
    patterns = (
        amount + r'\s*(?:تومان\s*)?' + alias,
        alias + r'(?:(?!ودیعه|اجاره|رهن|کرایه|پول\s*پیش)[^\d.،؛]){0,35}' + amount,
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        # amount/unit are groups 1/2 in both patterns because alias is non-capturing.
        value = float(match.group(1))
        return int(value * (1_000_000 if match.group(2) == 'میلیون' else 1_000_000_000))
    return None


def split_clauses(text: str) -> list[str]:
    """Split user text without destroying short coordinated amenity phrases."""
    text = normalize_persian(text)
    return [part.strip() for part in re.split(r'[؛،,.!?؟]|\s+(?:ولی|اما)\s+', text) if part.strip()]


def is_required(text: str) -> bool:
    return bool(REQUIRED_RE.search(normalize_persian(text)))


def is_negated(text: str) -> bool:
    return bool(NEGATION_RE.search(normalize_persian(text)))


def priority_hint(text: str, *, default: str = 'high') -> str:
    text = normalize_persian(text)
    if NEGATION_RE.search(text):
        return 'low'
    if VERY_HIGH_RE.search(text):
        return 'very_high'
    if PREFERENCE_RE.search(text):
        return 'medium'
    return default


def bedroom_constraint(text: str) -> dict | None:
    """Parse direct bedroom language into SearchIntent's current bed schema."""
    text = normalize_persian(text)
    if any(re.search(r'(?:تعداد\s*)?(?:خواب|اتاق(?:\s*خواب)?).{0,20}(?:مهم\s*نیست|فرقی\s*ندار|بی\s*خیال)|بی\s*خیال.{0,20}(?:خواب|اتاق)',c) for c in split_clauses(text)):
        return {'mode': 'any', 'value': None}

    # two/three alternatives, including colloquial hyphen/spacing after normalization.
    match = re.search(rf'({SMALL_NUMBER_TOKEN})\s*(?:یا|تا)\s*({SMALL_NUMBER_TOKEN})\s*(?:خواب|اتاق(?:\s*خواب)?|خوابه)', text)
    if match:
        values = sorted({number_value(match.group(1)), number_value(match.group(2))})
        values = [v for v in values if v is not None and 1 <= v <= 5]
        if values:
            return {'mode': 'allowed', 'value': values}

    match = re.search(rf'حداقل\s*({SMALL_NUMBER_TOKEN})\s*(?:خواب|اتاق(?:\s*خواب)?)', text)
    if not match:
        match = re.search(rf'({SMALL_NUMBER_TOKEN})\s*(?:خواب|اتاق(?:\s*خواب)?)\s*(?:به\s*بالا|یا\s*بیشتر)', text)
    if match:
        value = number_value(match.group(1))
        if value is not None and 1 <= value <= 5:
            return {'mode': 'min', 'value': value}

    match = re.search(rf'(?:حداکثر\s*)({SMALL_NUMBER_TOKEN})\s*(?:خواب|اتاق(?:\s*خواب)?)', text)
    if not match:
        match = re.search(rf'بیشتر\s*از\s*({SMALL_NUMBER_TOKEN})\s*(?:خواب|اتاق(?:\s*خواب)?).{{0,18}}(?:لازم\s*ندارم|نمی\s*خوام|نباش)', text)
    if match:
        value = number_value(match.group(1))
        if value is not None and 1 <= value <= 5:
            return {'mode': 'max', 'value': value}

    match = re.search(rf'({SMALL_NUMBER_TOKEN})\s*(?:خواب|خوابه|اتاق(?:\s*خواب)?)', text)
    if match:
        value = number_value(match.group(1))
        if value is not None and 1 <= value <= 5:
            return {'mode': 'exact', 'value': value}
    return None


REFERENCE_SOLAR_YEAR = 1405


def area_constraint(text: str) -> dict | None:
    """Parse explicit numeric area constraints in square metres."""
    text = normalize_persian(text)
    result = {'min': None, 'max': None}

    match = re.search(r'(?:بین\s*)?(\d{2,4})\s*(?:تا|الی|-)\s*(\d{2,4})\s*متر', text)
    if match:
        low, high = sorted((int(match.group(1)), int(match.group(2))))
        if 10 <= low <= high <= 1500:
            return {'min': low, 'max': high}

    min_patterns = (
        r'حداقل\s*(\d{2,4})\s*متر',
        r'(\d{2,4})\s*متر\s*(?:به\s*بالا|یا\s*بیشتر)',
        r'(?:کمتر|زیر)\s*از?\s*(\d{2,4})\s*متر.{0,14}(?:نباش|نمی\s*خوام)',
    )
    max_patterns = (
        r'حداکثر\s*(\d{2,4})\s*متر',
        r'بیشتر\s*از\s*(\d{2,4})\s*متر.{0,18}(?:لازم\s*ندارم|نباش|نمی\s*خوام)',
        r'(\d{2,4})\s*متر\s*(?:به\s*پایین|یا\s*کمتر)',
        r'تا\s*(\d{2,4})\s*متر(?:\s|$)',
    )
    for pattern in min_patterns:
        match = re.search(pattern, text)
        if match:
            value = int(match.group(1))
            if 10 <= value <= 1500:
                result['min'] = value
                break
    for pattern in max_patterns:
        match = re.search(pattern, text)
        if match:
            value = int(match.group(1))
            if 10 <= value <= 1500:
                result['max'] = value
                break
    if result['min'] is not None and result['max'] is not None and result['min'] > result['max']:
        return None
    return result if any(v is not None for v in result.values()) else None


def floor_constraint(text: str) -> dict | None:
    """Parse floor ranges/sets and ground/basement exclusions.

    Unknown listing floors do not satisfy an active hard floor constraint downstream.
    """
    text = normalize_persian(text)
    excluded = []
    if re.search(r'(?:همکف.{0,14}(?:نباش|نه|نمی\s*خوام)|نمی\s*خوام.{0,10}همکف)', text):
        excluded.append('ground')
    if re.search(r'(?:زیرزمین.{0,14}(?:نباش|نه|نمی\s*خوام)|نمی\s*خوام.{0,10}زیرزمین)', text):
        excluded.append('basement')

    token = rf'(?:{SMALL_NUMBER_TOKEN}|{ORDINAL_NUMBER_TOKEN})'
    match = re.search(rf'طبقه\s*({token})\s*(?:یا|و)\s*(?:طبقه\s*)?({token})', text)
    if match:
        values = sorted({number_value(match.group(1)), number_value(match.group(2))})
        values = [v for v in values if v is not None and -5 <= v <= 100]
        if values:
            return {'mode': 'allowed', 'value': values, 'excluded': excluded}

    match = re.search(rf'(?:طبقه\s*)?({token})\s*(?:یا|و)\s*(?:طبقه\s*)?({token})\s*(?:باشه|بهتره|خوبه)', text)
    if match and 'خواب' not in text:
        values = sorted({number_value(match.group(1)), number_value(match.group(2))})
        values = [v for v in values if v is not None and -5 <= v <= 100]
        if values:
            return {'mode': 'allowed', 'value': values, 'excluded': excluded}

    match = re.search(rf'طبقه\s*({token})\s*(?:به\s*بالا|یا\s*بالاتر)', text)
    if not match:
        match = re.search(rf'پایین\s*تر\s*از\s*طبقه\s*({token}).{{0,12}}(?:نباش|نمی\s*خوام)', text)
    if match:
        value = number_value(match.group(1))
        if value is not None:
            return {'mode': 'min', 'value': value, 'excluded': excluded}

    match = re.search(rf'حداکثر\s*طبقه\s*({token})', text)
    if not match:
        match = re.search(rf'بالاتر\s*از\s*طبقه\s*({token}).{{0,14}}(?:نباش|نمی\s*خوام)', text)
    if match:
        value = number_value(match.group(1))
        if value is not None:
            return {'mode': 'max', 'value': value, 'excluded': excluded}

    match = re.search(rf'طبقه(?:ی)?\s*({token})(?!\s*(?:یا|و)\s*(?:طبقه\s*)?{token})', text)
    if match:
        value = number_value(match.group(1))
        if value is not None:
            return {'mode': 'exact', 'value': value, 'excluded': excluded}

    if excluded:
        return {'mode': 'any', 'value': None, 'excluded': excluded}
    return None


def construction_year_min(text: str, *, reference_year: int | None = None) -> int | None:
    """Return the oldest acceptable Solar-Hijri construction year when explicit."""
    text = normalize_persian(text)
    from .calendar import current_jalali_year
    reference_year = current_jalali_year() if reference_year is None else reference_year
    age_clauses = [part for clause in split_clauses(text) for part in re.split(r'\s+و\s+(?=پارکینگ|آسانسور|انباری|نور|متراژ|ودیعه|اجاره|نوساز|ساختمان)',clause)]
    for clause in age_clauses:
        if re.search(r'\bنوساز\b', clause) and not re.search(r'ترجیح|بهتره|نسبتا|مهم|اگر|اگه|اول|قدیمی|بی\s*خیال|نمی\s*خوام|لازم\s*نیست|فرقی', clause):
            return reference_year - 3
    patterns = (
        r'(?:زیر|کمتر\s*از)\s*(\d{1,2})\s*سال(?:ه)?(?:\s*ساخت|\s*سن\s*بنا)?',
        r'سن\s*بنا.{0,12}(?:زیر|کمتر\s*از)\s*(\d{1,2})\s*سال',
        r'بیشتر\s*از\s*(\d{1,2})\s*سال(?:ه)?(?:\s*نباش|\s*نمی\s*خوام)',
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            age = int(match.group(1))
            if 0 <= age <= 100:
                return max(1300, reference_year - age)
    match = re.search(r'(?:سال\s*ساخت|ساخت)\s*(13\d{2}|14\d{2})\s*(?:به\s*بعد|یا\s*جدیدتر|به\s*بالا)', text)
    if match:
        year = int(match.group(1))
        if 1300 <= year <= reference_year:
            return year
    return None


def renovation_requirement(text: str) -> bool | None:
    """Parse an unconditional hard renovation requirement.

    Conditional wording such as "old is okay if renovated" is intentionally left for
    the later compound-rule engine instead of being flattened into a global rule.
    """
    text = normalize_persian(text)
    if re.search(r'بازسازی.{0,12}(?:مهم\s*نیست|لازم\s*نیست|فرقی\s*ندار|بی\s*خیال)', text):
        return False
    if re.search(r'(?:حتما|الزامی|اجباری|لازم).{0,20}(?:بازسازی|نوسازی)', text):
        return True
    if re.search(r'(?:بازسازی|نوسازی)\s*(?:کامل|فول)?.{0,10}(?:لازم|اجباری|الزامی|حتما)', text):
        return True
    if re.search(r'(?:فول|کامل)\s*بازسازی(?:\s*شده)?.{0,10}(?:باشه|می\s*خوام|لازم)?', text):
        return True
    if re.search(r'(?:بازسازی|نوسازی)\s*شده.{0,10}(?:می\s*خوام|لازم\s*دارم|حتما)', text):
        return True
    return None

# v0.9-C user-side vocabulary for criteria that are not structured in the Divar
# dataset.  Parsing and listing evidence stay separate: this function only describes
# what the user asked for; evidence_features.py decides what an ad actually supports.
_EVIDENCE_ITEM_PATTERNS = {
    'package_heating': r'پکیج',
    'radiator': r'رادیاتور|شوفاژ',
    'split_ac': r'کولر\s*گازی|اسپلیت',
    'water_cooler': r'کولر\s*آبی',
    'fan_coil': r'فن\s*کویل',
    'chiller': r'چیلر',
    'security_24h': r'نگهبان(?:ی)?\s*(?:24|شبانه\s*روزی)|نگهبانی\s*شبانه\s*روزی',
    'cctv': r'دوربین\s*مدار\s*بسته',
    'concierge': r'سرایدار(?:ی)?|لابی\s*من',
    'lobby': r'\bلابی\b',
    'near_metro': r'نزدیک(?:ی)?\s*(?:به\s*)?مترو|پیاده.{0,15}مترو|مترو\s*(?:دم\s*دست|نزدیک)',
    'near_brt': r'نزدیک(?:ی)?\s*(?:به\s*)?BRT|ایستگاه\s*BRT',
    'good_road_access': r'دسترسی.{0,18}(?:بزرگراه|اتوبان|همت|مدرس|چمران)|دسترسی\s*(?:عالی|خوب)',
    'open_view': r'ویو\s*باز|دید\s*باز|منظره\s*باز',
    'privacy': r'مشرف\s*نباش|بدون\s*مشرف|حریم\s*خصوصی',
    'mountain_view': r'ویو\s*(?:کوه|کوهستان)|منظره\s*(?:کوه|کوهستان)',
    'city_view': r'ویو\s*شهر|منظره\s*شهر',
    'step_free': r'ورودی\s*بدون\s*پله|بدون\s*پله\s*(?:باش|می\s*خوام)|پله\s*نخواد',
    'wheelchair': r'مناسب\s*ویلچر|دسترسی\s*ویلچر|ویلچر.{0,18}(?:راحت|وارد|مناسب)',
    'ramp': r'\bرمپ\b',
    'elevator_from_parking': r'آسانسور.{0,25}(?:از|تا)\s*پارکینگ|پارکینگ.{0,25}آسانسور.{0,12}(?:مستقیم|دسترسی)',
}


def _evidence_priority(clause: str) -> str:
    """Map ordinary preference language to existing priority levels."""
    clause = normalize_persian(clause)
    if re.search(r'خیلی\s*مهم|اولویت\s*اول|از\s*همه.{0,8}مهم\s*تر', clause):
        return 'very_high'
    if is_required(clause):
        return 'very_high'
    if re.search(r'ترجیح|بهتره|مزیت|امتیاز|اگه\s*باشه\s*خوبه', clause):
        return 'medium'
    return 'high'


def evidence_language(text: str) -> dict:
    """Parse v0.9-C evidence-based user requirements/preferences.

    Returns sparse data only for mentioned concepts::

        {
          'constraints': {...},
          'preferences': {feature_token: priority},
          'unset_preferences': {feature_token, ...},
          'unset_constraints': {constraint_key, ...},
        }

    Compound IF/THEN semantics intentionally remain out of scope until the dedicated
    conditional-rule batch.
    """
    text = normalize_persian(text)
    constraints: dict = {}
    preferences: dict[str, str] = {}
    unset_preferences: set[str] = set()
    unset_constraints: set[str] = set()
    unset_required_features: set[str] = set()

    clauses = split_clauses(text)

    # Pet ownership is a safety/feasibility requirement, not merely a ranking signal.
    pet_mentioned = re.search(r'حیوان\s*خانگی|حیوون\s*خونگی|\bپت\b|گربه|سگ', text)
    if pet_mentioned:
        if re.search(r'(?:حیوان\s*خانگی|پت).{0,18}(?:مهم\s*نیست|فرقی\s*ندار|بی\s*خیال)', text):
            unset_constraints.add('pet_policy')
            unset_preferences.add('pet_allowed')
        elif re.search(r'(?:حیوان\s*خانگی|حیوون\s*خونگی|پت|گربه|سگ)\s*دارم|مجاز\s*باش|ممنوع\s*نباش|باید.{0,12}(?:قبول|مجاز)', text):
            constraints['pet_policy'] = 'allowed'
            preferences['pet_allowed'] = 'very_high'
        elif re.search(r'ترجیح.{0,12}(?:حیوان\s*خانگی|پت).{0,12}مجاز', text):
            preferences['pet_allowed'] = 'medium'

    # Parking cardinality/type. A count is intrinsically a hard feasibility request.
    from .evidence_features import _parking_count_from_text
    parking_count = _parking_count_from_text(text, None)
    if parking_count is not None and 1 <= parking_count <= 5:
        clause = next((c for c in clauses if re.search(r'پارکینگ|جای\s*پارک', c)), text)
        if not re.search(r'ترجیح|بهتره', clause) or is_required(clause):
            constraints['parking_count_min'] = parking_count
    if re.search(r'پارکینگ.{0,22}(?:غیر\s*مزاحم|بدون\s*مزاحم|مزاحم\s*(?:نباش|نمی\s*خوام))|جای\s*پارک\s*غیر\s*مزاحم', text):
        constraints['parking_non_tandem_required'] = True
        preferences['parking_non_tandem'] = 'very_high'
    if re.search(r'پارکینگ\s*(?:اختصاصی|سندی)|جای\s*پارک\s*اختصاصی', text):
        clause = next((c for c in clauses if re.search(r'پارکینگ|جای\s*پارک', c)), text)
        if is_required(clause) or re.search(r'می\s*خوام|باشه', clause):
            constraints['parking_dedicated_required'] = True
        preferences['parking_dedicated'] = _evidence_priority(clause)
    if re.search(r'پارکینگ.{0,20}(?:کیفیت|نوع|مزاحم|اختصاصی).{0,20}(?:مهم\s*نیست|بی\s*خیال)', text):
        unset_constraints.update(('parking_non_tandem_required', 'parking_dedicated_required'))
        unset_preferences.update(('parking_non_tandem', 'parking_dedicated'))

    # Furnishing: plain "مبله باشه" is a concrete requirement; preference wording is soft.
    if re.search(r'غیر\s*مبله|بدون\s*وسایل|مبله\s*نمی\s*خوام', text):
        clause = next((c for c in clauses if re.search(r'غیر\s*مبله|بدون\s*وسایل|مبله\s*نمی\s*خوام', c)), text)
        if re.search(r'مهم\s*نیست|فرقی\s*ندار|بی\s*خیال', clause):
            unset_constraints.add('furnishing'); unset_preferences.update(('furnished', 'unfurnished'))
        elif re.search(r'ترجیح|بهتره|مزیت', clause):
            preferences['unfurnished'] = _evidence_priority(clause)
        else:
            constraints['furnishing'] = 'unfurnished'; preferences['unfurnished'] = _evidence_priority(clause)
    elif re.search(r'\bمبله\b|فول\s*فرنیش|\bفرنیش\b', text):
        clause = next((c for c in clauses if re.search(r'مبله|فرنیش', c)), text)
        if re.search(r'مهم\s*نیست|فرقی\s*ندار|بی\s*خیال', clause):
            unset_constraints.add('furnishing'); unset_preferences.update(('furnished', 'unfurnished'))
        elif re.search(r'ترجیح|بهتره|مزیت|امتیاز', clause):
            preferences['furnished'] = _evidence_priority(clause)
        else:
            constraints['furnishing'] = 'furnished'; preferences['furnished'] = _evidence_priority(clause)

    # HVAC/security/transport/view/accessibility items share the same evidence tokens.
    hard_lists = {
        'hvac_required': {'package_heating','radiator','split_ac','water_cooler','fan_coil','chiller'},
        'security_required': {'security_24h','cctv','concierge','lobby'},
        'transport_required': {'near_metro','near_brt','good_road_access'},
        'view_privacy_required': {'open_view','privacy','mountain_view','city_view'},
        'accessibility_required': {'step_free','wheelchair','ramp','elevator_from_parking'},
    }
    found_by_constraint = {key: [] for key in hard_lists}
    for feature, pattern in _EVIDENCE_ITEM_PATTERNS.items():
        for clause in clauses:
            if not re.search(pattern, clause, re.I):
                continue
            if re.search(r'مهم\s*نیست|لازم\s*نیست|فرقی\s*ندار|بی\s*خیال', clause):
                unset_preferences.add(feature)
                unset_required_features.add(feature)
                break
            priority = _evidence_priority(clause)
            preferences[feature] = priority
            for key, members in hard_lists.items():
                if feature in members:
                    # Accessibility and explicit negative-form privacy requests are
                    # feasibility constraints even without the word "حتماً".
                    naturally_hard = feature in {'step_free','wheelchair','ramp','elevator_from_parking','privacy'}
                    explicit_hard = is_required(clause) or bool(re.search(r'لازم|باید|حتما|اجباری|بدونش|داشته\s*باشه', clause))
                    if naturally_hard or explicit_hard:
                        found_by_constraint[key].append(feature)
                    break
            break
    for key, values in found_by_constraint.items():
        if values:
            constraints[key] = sorted(set(values))

    # Building density has a small ordered vocabulary rather than a feature list.
    density_clause = next((c for c in clauses if re.search(r'تک\s*واحدی|کم\s*واحد|ساختمون\s*شلوغ|ساختمان\s*شلوغ', c)), None)
    if density_clause:
        feature = 'single_unit' if re.search(r'تک\s*واحدی|هر\s*طبقه\s*(?:یک|1)\s*واحد', density_clause) else 'low_density'
        if re.search(r'مهم\s*نیست|فرقی\s*ندار|بی\s*خیال', density_clause):
            unset_constraints.add('building_density'); unset_preferences.update(('single_unit','low_density'))
        else:
            preferences[feature] = _evidence_priority(density_clause)
            if is_required(density_clause) or re.search(r'حتما|لازم|باید|می\s*خوام|باشه', density_clause):
                constraints['building_density'] = feature

    return {
        'constraints': constraints,
        'preferences': preferences,
        'unset_preferences': unset_preferences,
        'unset_constraints': unset_constraints,
        'unset_required_features': unset_required_features,
    }
