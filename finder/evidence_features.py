"""Evidence-aware extraction for description-derived housing features.

The Divar release does not expose structured fields for every useful housing criterion.
This module extracts only conservative, auditable claims from listing title/description.
Every extractor can return unknown; absence of wording is never treated as a negative.

No Django dependency: helpers are reusable in selectors, ranking and tests.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
import re

from .language import normalize_persian, number_value

YES = 'yes'
NO = 'no'
UNKNOWN = 'unknown'


def _text(listing) -> str:
    return normalize_persian(f'{getattr(listing, "title", "")} {getattr(listing, "description", "")}')


def _state(text: str, positive: tuple[str, ...], negative: tuple[str, ...] = ()) -> str:
    # Explicit negative evidence wins over broad positive vocabulary.
    if any(re.search(pattern, text, re.I) for pattern in negative):
        return NO
    if any(re.search(pattern, text, re.I) for pattern in positive):
        return YES
    return UNKNOWN


PET_POSITIVE = (
    r'حیوان(?:ات)?\s*خانگی.{0,16}(?:مجاز|بلامانع|بلا\s*مانع)',
    r'پت\s*(?:مجاز|اوکی|بلامانع)',
    r'نگهداری\s*حیوان(?:ات)?\s*خانگی\s*(?:مجاز|بلامانع|مشکلی\s*ندار)',
    r'(?:داشتن|با)\s*حیوان(?:ات)?\s*خانگی.{0,18}(?:مشکلی\s*ندار|مانعی\s*ندار|بلامانع)',
    r'(?:بدون\s*مشکل\s*با.{0,20}(?:پت|حیوان(?:ات)?\s*خانگی)|مشکلی\s*با.{0,20}(?:پت|حیوان(?:ات)?\s*خانگی).{0,16}ندار)',
    r'(?:حیوان|حیوون)(?:ات)?\s*(?:ok|اوکی|بلامانع|بلا\s*مانع)',
    r'کسانی\s*که\s*حیوان(?:ات)?\s*خانگی.{0,30}(?:اجاره|پذیرفته)',
    r'حیوان(?:ات)?\s*خانگی.{0,12}(?:مشکلی\s*ندار|مانعی\s*ندار|بدون\s*اشکال)',
    r'(?:به|برای)\s*(?:مجرد|خانواده).{0,25}حیوان\s*خانگی\s*دار.{0,12}اجاره',
    r'با\s*(?:سگ|گربه|حیوان\s*خانگی|پت)\s*(?:مشکلی\s*نیست|اوکی)',
)
PET_NEGATIVE = (
    r'حیوان(?:ات)?\s*خانگی.{0,18}(?:مجاز|بلامانع)\s*نیست',
    r'بدون\s*حیوان\s*خانگی',
    r'حیوان(?:ات)?\s*خانگی.{0,18}(?:ممنوع|قبول\s*نمی\s*شود|پذیرفته\s*نمی\s*شود|نداشته\s*باش|نباش)',
    r'(?:بدون|فاقد)\s*حیوان(?:ات)?\s*خانگی',
    r'(?:از\s*)?پذیرفتن.{0,35}حیوان(?:ات)?\s*خانگی.{0,25}(?:معذور|امکان\s*ندار)',
    r'بدون\s*پت',
    r'(?:حیوان|پت)\s*نداشته\s*باش',
    r'پت\s*(?:ممنوع|قبول\s*نمی\s*شود|نباش)',
    r'(?:سگ|گربه)\s*(?:ممنوع|نباش)',
)


HVAC_PATTERNS = {
    'package_heating': (r'\b(?:پکیج|پکیچ)\b',),
    'radiator': (r'\bرادیاتور\b', r'\bو?شوفاژ\b'),
    'split_ac': (r'کولر\s*گازی', r'\b(?:اسپلیت|اسپیلت)\b'),
    'water_cooler': (r'کولر\s*[آا]بی',),
    'fan_coil': (r'فن\s*کویل',),
    'chiller': (r'\bچیلر\b',),
}

SECURITY_PATTERNS = {
    'security_24h': (r'نگهبان(?:ی)?\s*(?:24|شبانه\s*روزی)', r'نگهبانی\s*شبانه\s*روزی'),
    'cctv': (r'دوربین\s*(?:های\s*)?مدار\s*بسته',),
    'concierge': (r'\b(?:سرایدار|سریدار)(?:ی|مقیم)?\b', r'لابی\s*من',),
    'lobby': (r'\bلابی\b',),
}

TRANSPORT_PATTERNS = {
    'near_metro': (
        r'نزدیک\s*(?:به\s*)?مترو', r'دسترسی\s*(?:عالی\s*)?(?:به\s*)?مترو',
        r'مترو.{0,24}(?:دقیقه|پیاده|نزدیک)', r'(?:کمتر\s*از\s*)?[0-9]+\s*دقیقه.{0,12}مترو',
    ),
    'near_brt': (r'نزدیک\s*(?:به\s*)?BRT', r'دسترسی.{0,16}BRT', r'ایستگاه\s*BRT'),
    'good_road_access': (r'دسترسی.{0,24}(?:بزرگراه|اتوبان|همت|مدرس|چمران)', r'دسترسی\s*(?:عالی|مناسب).{0,12}(?:بزرگراه|اتوبان)'),
}

VIEW_PATTERNS = {
    'open_view': (r'ویو\s*باز(?!\s*سازی)', r'(?<![\w])دید\s*باز(?!دید|سازی)', r'منظره\s*باز'),
    'privacy': (r'بدون\s*مشرف', r'عدم\s*مشرف', r'مشرف\s*ندار'),
    'mountain_view': (r'ویو(?:ی)?\s*(?:(?:ابدی|شهر\s*و)\s*)?(?:به\s*)?(?:کوه|کوهستان)', r'منظره\s*(?:کوه|کوهستان)'),
    'city_view': (r'ویو\s*شهر(?!ک)', r'منظره\s*شهر(?!ک)'),
}

ACCESSIBILITY_PATTERNS = {
    'step_free': (r'ورودی\s*بدون\s*پله', r'بدون\s*پله\s*(?:تا\s*)?(?:واحد|ورودی)', r'همکف\s*بدون\s*پله'),
    'wheelchair': (r'مناسب\s*ویلچر', r'دسترسی\s*ویلچر', r'ویلچر.{0,20}(?:راحت|مناسب)'),
    'ramp': (r'رمپ.{0,20}(?:ویلچر|ورودی\s*واحد|ورودی\s*ساختمان)', r'(?:ورودی\s*ساختمان|ورودی\s*واحد).{0,20}رمپ'),
    'elevator_from_parking': (r'آسانسور.{0,25}(?:از|تا)\s*پارکینگ', r'پارکینگ\s*(?:به\s*)?آسانسور\s*(?:مستقیم|دسترسی\s*مستقیم)'),
}

FURNISHED_POSITIVE = (r'\bمبله\b', r'فول\s*فرنیش', r'\bفرنیش(?:\s*شده)?\b')
FURNISHED_NEGATIVE = (r'مبله\s*نیست', r'غیر\s*مبله', r'بدون\s*وسایل(?:\s*منزل)?', r'فاقد\s*وسایل')

SINGLE_UNIT_PATTERNS = (r'تک\s*واحد(?:ی)?\b', r'هر\s*طبقه\s*(?:فقط\s*)?(?:یک|1)\s*واحد')
LOW_DENSITY_PATTERNS = (r'کم\s*واحد', r'(?:ساختمان|برج)\s*کم\s*جمعیت', r'واحدهای\s*کم')

PARKING_NON_TANDEM_POSITIVE = (
    # Allow short descriptive wording between «پارکینگ» and «غیرمزاحم», e.g.
    # «2 پارکینگ سندی غیر مزاحم».  Stay inside the same punctuation-delimited
    # clause so unrelated later text cannot create a false positive.
    r'پارکینگ[^؛،,.!?؟]{0,35}(?:غیر\s*مزاحم|بدون\s*مزاحم)',
    r'پارکینگ\s*(?:(?:سندی|اختصاصی|هر\s*دو|و)\s*){0,3}مستقل',
    r'جای\s*پارک[^؛،,.!?؟]{0,28}(?:غیر\s*مزاحم|بدون\s*مزاحم)',
)
PARKING_NON_TANDEM_NEGATIVE = (r'پارکینگ[^؛،,.!?؟]{0,20}(?:غیر\s*مزاحم|مستقل)\s*نیست', r'پارکینگ\s*مزاحم(?!\s*نباش)',)
PARKING_DEDICATED_POSITIVE = (r'پارکینگ\s*(?:باکس\s*)?(?:اختصاصی|سندی)', r'جای\s*پارک\s*اختصاصی')


@dataclass(frozen=True)
class ListingEvidence:
    pet_policy: str = UNKNOWN
    parking_count: int | None = None
    parking_non_tandem: str = UNKNOWN
    parking_dedicated: str = UNKNOWN
    furnishing: str = 'unknown'  # furnished / unfurnished / unknown
    negative_features: frozenset[str] = field(default_factory=frozenset)
    hvac: frozenset[str] = field(default_factory=frozenset)
    building_density: frozenset[str] = field(default_factory=frozenset)
    security: frozenset[str] = field(default_factory=frozenset)
    transport: frozenset[str] = field(default_factory=frozenset)
    view_privacy: frozenset[str] = field(default_factory=frozenset)
    accessibility: frozenset[str] = field(default_factory=frozenset)


def _parking_count_from_text(text: str, structured_parking: bool | None) -> int | None:
    # Explicit count near parking wording. This intentionally does not infer from generic
    # words such as "فول امکانات".
    count_token = r'((?<![0-9])[0-9](?![0-9])|(?<![\w])یک|(?<![\w])یه|(?<![\w])دو|(?<![\w])سه|(?<![\w])چهار|(?<![\w])پنج)'
    patterns = (
        rf'{count_token}\s*(?:(?:تا|عدد)\s*)?(?:پارکینگ|جای\s*پارک)',
        # A bare number after parking may be the next field (age/rent/floor).
        rf'پارکینگ\s*{count_token}\s*(?:تایی|عددی|عدد|تا|سندی|اختصاصی)',
    )
    counts = []
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            before = text[max(0, match.start()-24):match.start()]
            if re.search(r'(?:طبقه|طبقه\s*ی|واحد|سال|پلاک)\s*$', before):
                continue
            value = number_value(match.group(1))
            if value is not None and 0 <= value <= 5:
                counts.append(value)
    if counts:
        return max(counts)
    if structured_parking is False:
        return 0
    if structured_parking is True:
        return 1  # only "at least one" is evidenced structurally
    return None


def parking_count_evidence(listing, text: str | None = None) -> int | None:
    text = _text(listing) if text is None else text
    return _parking_count_from_text(text, getattr(listing, 'parking', None))


@lru_cache(maxsize=10000)
def _extract_listing_evidence_cached(title: str, description: str, structured_parking: bool | None) -> ListingEvidence:
    text = normalize_persian(f'{title} {description}')
    furnishing = 'unknown'
    negatives = set()
    furnishing_text = re.sub(r'(?:لابی|آشپز\s*خانه|آشپزخانه|اشپز\s*خانه|نیمه|نیم|نمیه)\s*(?:مبله|فرنیش)', '', text)
    positive_furnishing = any(re.search(p, furnishing_text, re.I) for p in FURNISHED_POSITIVE)
    negative_furnishing = any(re.search(p, text, re.I) for p in FURNISHED_NEGATIVE)
    # Ads offering both furnishing modes need review rather than one fabricated mode.
    positive_furnishing = positive_furnishing and not re.search(r'غیر\s*مبله', furnishing_text)
    if negative_furnishing and re.search(r'(?<!غیر )مبله\s*(?:و|یا|هم).{0,12}غیر\s*مبله|هم.{0,12}مبله.{0,20}غیر\s*مبله', text):
        furnishing = 'unknown'
    elif negative_furnishing:
        furnishing = 'unfurnished'
    elif positive_furnishing:
        furnishing = 'furnished'

    def feature_set(mapping):
        found = set()
        for key, patterns in mapping.items():
            for pattern in patterns:
                for match in re.finditer(pattern, text, re.I):
                    before = text[max(0, match.start()-14):match.start()]
                    after = text[match.end():match.end()+18]
                    if re.search(r'(?:بدون|فاقد|نداشتن)\s*$', before) or re.match(r'\s*(?:ندارد|نداریم|نیست|موجود\s*نیست)', after):
                        negatives.add(key)
                    else:
                        found.add(key)
        return frozenset(found - negatives)

    hvac = feature_set(HVAC_PATTERNS)
    security = feature_set(SECURITY_PATTERNS)
    transport = feature_set(TRANSPORT_PATTERNS)
    view_privacy = feature_set(VIEW_PATTERNS)
    accessibility = feature_set(ACCESSIBILITY_PATTERNS)
    density = set(feature_set({'single_unit': SINGLE_UNIT_PATTERNS, 'low_density': LOW_DENSITY_PATTERNS}))
    if 'single_unit' in density:
        density.add('low_density')

    return ListingEvidence(
        pet_policy=_state(text, PET_POSITIVE, PET_NEGATIVE),
        parking_count=_parking_count_from_text(text, structured_parking),
        parking_non_tandem=_state(text, PARKING_NON_TANDEM_POSITIVE, PARKING_NON_TANDEM_NEGATIVE),
        parking_dedicated=_state(text, PARKING_DEDICATED_POSITIVE, (r'پارکینگ\s*(?:اختصاصی|سندی)\s*(?:نیست|ندارد)',)),
        furnishing=furnishing,
        negative_features=frozenset(negatives),
        hvac=hvac,
        building_density=frozenset(density),
        security=security,
        transport=transport,
        view_privacy=view_privacy,
        accessibility=accessibility,
    )


def extract_listing_evidence(listing) -> ListingEvidence:
    # Cache by normalized source wording + structured parking. The 3k-row prototype
    # reuses the same listings across filters/ranking, so this avoids repeated regex
    # scans while remaining deterministic and invalidating automatically if text changes.
    return _extract_listing_evidence_cached(str(getattr(listing, 'title', '') or ''), str(getattr(listing, 'description', '') or ''), getattr(listing, 'parking', None))


def evidence_requirement_matches(listing, constraints: dict) -> bool:
    """Return True only when every active text-evidence requirement is confirmed.

    Unknown evidence never confirms a hard requirement. This is the central v0.9-C
    safety rule and is intentionally stricter than preference scoring.
    """
    evidence = extract_listing_evidence(listing)
    if constraints.get('pet_policy') == 'allowed' and evidence.pet_policy != YES:
        return False
    count = constraints.get('parking_count_min')
    if count is not None and (evidence.parking_count is None or evidence.parking_count < count):
        return False
    if constraints.get('parking_non_tandem_required') and evidence.parking_non_tandem != YES:
        return False
    if constraints.get('parking_dedicated_required') and evidence.parking_dedicated != YES:
        return False
    furnishing = constraints.get('furnishing', 'any')
    if furnishing != 'any' and evidence.furnishing != furnishing:
        return False
    if not set(constraints.get('hvac_required', ())) <= evidence.hvac:
        return False
    density = constraints.get('building_density', 'any')
    if density != 'any' and density not in evidence.building_density:
        return False
    if not set(constraints.get('security_required', ())) <= evidence.security:
        return False
    if not set(constraints.get('transport_required', ())) <= evidence.transport:
        return False
    if not set(constraints.get('view_privacy_required', ())) <= evidence.view_privacy:
        return False
    if not set(constraints.get('accessibility_required', ())) <= evidence.accessibility:
        return False
    return True

EVIDENCE_FEATURE_LABELS = {
    'pet_allowed': 'حیوان خانگی مجاز',
    'parking_non_tandem': 'پارکینگ غیرمزاحم',
    'parking_dedicated': 'پارکینگ اختصاصی',
    'furnished': 'مبله',
    'unfurnished': 'غیرمبله',
    'package_heating': 'پکیج',
    'radiator': 'رادیاتور/شوفاژ',
    'split_ac': 'کولر گازی',
    'water_cooler': 'کولر آبی',
    'fan_coil': 'فن‌کویل',
    'chiller': 'چیلر',
    'single_unit': 'تک‌واحدی',
    'low_density': 'ساختمان کم‌واحد',
    'security_24h': 'نگهبانی ۲۴ ساعته',
    'cctv': 'دوربین مداربسته',
    'concierge': 'سرایدار/لابی‌من',
    'lobby': 'لابی',
    'near_metro': 'نزدیکی به مترو',
    'near_brt': 'نزدیکی به BRT',
    'good_road_access': 'دسترسی بزرگراهی',
    'open_view': 'دید باز',
    'privacy': 'بدون مشرف',
    'mountain_view': 'ویو کوه',
    'city_view': 'ویو شهر',
    'step_free': 'ورودی بدون پله',
    'wheelchair': 'دسترسی ویلچر',
    'ramp': 'رمپ',
    'elevator_from_parking': 'دسترسی آسانسور از پارکینگ',
}

EVIDENCE_FEATURES = frozenset(EVIDENCE_FEATURE_LABELS)


def evidence_feature_state(evidence: ListingEvidence, key: str) -> str:
    """Map a canonical preference token to YES/NO/UNKNOWN evidence."""
    if key in evidence.negative_features:
        return NO
    if key == 'pet_allowed':
        return evidence.pet_policy
    if key == 'parking_non_tandem':
        return evidence.parking_non_tandem
    if key == 'parking_dedicated':
        return evidence.parking_dedicated
    if key == 'furnished':
        return YES if evidence.furnishing == 'furnished' else NO if evidence.furnishing == 'unfurnished' else UNKNOWN
    if key == 'unfurnished':
        return YES if evidence.furnishing == 'unfurnished' else NO if evidence.furnishing == 'furnished' else UNKNOWN
    if key in HVAC_PATTERNS:
        return YES if key in evidence.hvac else UNKNOWN
    if key in ('single_unit', 'low_density'):
        return YES if key in evidence.building_density else UNKNOWN
    if key in SECURITY_PATTERNS:
        return YES if key in evidence.security else UNKNOWN
    if key in TRANSPORT_PATTERNS:
        return YES if key in evidence.transport else UNKNOWN
    if key in VIEW_PATTERNS:
        return YES if key in evidence.view_privacy else UNKNOWN
    if key in ACCESSIBILITY_PATTERNS:
        return YES if key in evidence.accessibility else UNKNOWN
    raise KeyError(key)


def has_evidence_requirements(constraints: dict) -> bool:
    return bool(
        constraints.get('pet_policy', 'any') != 'any'
        or constraints.get('parking_count_min') is not None
        or constraints.get('parking_non_tandem_required')
        or constraints.get('parking_dedicated_required')
        or constraints.get('furnishing', 'any') != 'any'
        or constraints.get('hvac_required')
        or constraints.get('building_density', 'any') != 'any'
        or constraints.get('security_required')
        or constraints.get('transport_required')
        or constraints.get('view_privacy_required')
        or constraints.get('accessibility_required')
    )


def required_evidence_tokens(constraints: dict) -> set[str]:
    tokens: set[str] = set()
    if constraints.get('pet_policy') == 'allowed': tokens.add('pet_allowed')
    if constraints.get('parking_non_tandem_required'): tokens.add('parking_non_tandem')
    if constraints.get('parking_dedicated_required'): tokens.add('parking_dedicated')
    furnishing = constraints.get('furnishing', 'any')
    if furnishing == 'furnished': tokens.add('furnished')
    elif furnishing == 'unfurnished': tokens.add('unfurnished')
    tokens.update(constraints.get('hvac_required', ()))
    density = constraints.get('building_density', 'any')
    if density != 'any': tokens.add(density)
    for group in ('security_required','transport_required','view_privacy_required','accessibility_required'):
        tokens.update(constraints.get(group, ()))
    return tokens
