"""Offline Divar normalization. No dataframe library or network calls in web requests."""
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re
from .intent import normalize

NEIGHBORHOODS = {
    'vanak': 'ونک', 'valiasr': 'ولیعصر', 'vali-asr': 'ولیعصر', 'میدان ولیعصر': 'ولیعصر',
    'yousef-abad': 'یوسف‌آباد', 'yousefabad': 'یوسف‌آباد', 'یوسف آباد': 'یوسف‌آباد',
    'abbas-abad': 'عباس‌آباد', 'abbasabad': 'عباس‌آباد', 'عباس آباد': 'عباس‌آباد',
    'amir-abad': 'امیرآباد', 'amirabad': 'امیرآباد', 'امیر آباد': 'امیرآباد',
    'mirdamad': 'میرداماد', 'jordan': 'جردن', 'molla-sadra': 'ملاصدرا', 'mollasadra': 'ملاصدرا',
    'sheikh-bahai': 'شیخ بهایی', 'sheykh-bahaei': 'شیخ بهایی',
    'behjat-abad': 'بهجت‌آباد', 'motahari': 'مطهری', 'tehran-university': 'دانشگاه تهران',
    'shadabad': 'شادآباد', 'hakimiyeh': 'حکیمیه', 'darrous': 'دروس', 'velenjak': 'ولنجک',
    'tavanir': 'توانیر', 'tehransar': 'تهرانسر',
    'fatemi': 'فاطمی', 'pasdaran': 'پاسداران', 'saadat-abad': 'سعادت‌آباد',
    'tehranpars': 'تهرانپارس', 'jannat-abad': 'جنت‌آباد', 'tohid': 'توحید', 'gholhak': 'قلهک',
}
WORDS = {'بدون اتاق': 0, 'بدون اتاق خواب': 0, 'بدون خواب': 0, 'صفر': 0, 'یک': 1, 'دو': 2, 'سه': 3, 'چهار': 4, 'پنج': 5}
SIGNALS = {
    'natural_light': r'نور\s*گیر\w*|آفتاب(?:\s*گیر)?|پنجره(?:\s*های)?\s*قدی|\bروشن\b|نور (?:طبیعی|عالی|خوب)',
    'quietness': r'دنج|آرام|آروم|ساکت|کوچه خلوت|کم\s*تردد',
    'layout_quality': r'بدون (?:فضای )?پرتی?|خوش\s*نقشه|نقشه عالی',
    'access_quality': r'دسترسی (?:عالی|مناسب)|نزدیک مترو|مترو|brt|حمل و نقل عمومی|خیابان اصلی',
    'renovation_claim': r'بازسازی(?:\s*شده)?|نقاشی شده|نوسازی',
}


def text(value):
    if value is None: return ''
    result = normalize(str(value))
    return '' if result.lower() in ('nan', 'none', 'null', 'na', 'n/a') else result


def number(value):
    raw = text(value).replace(',', '').replace('٬', '').replace('٫', '.')
    if not raw: return None
    try:
        result = Decimal(raw)
        return result if result.is_finite() else None
    except InvalidOperation: return None


def integer(value):
    result = number(value)
    return int(result) if result is not None and result == result.to_integral_value() else None


def bedrooms(value):
    raw = text(value)
    return WORDS.get(raw, integer(raw))


def boolean(value):
    raw = text(value).lower()
    if raw in ('true', '1', '1.0', 'yes', 'دارد', 'بله', 'موجود'): return True
    if raw in ('false', '0', '0.0', 'no', 'ندارد', 'خیر', 'بدون'): return False
    return None


def money(value, unit='toman'):
    raw = text(value)
    if not raw: return None
    explicit_rial = 'ریال' in raw
    explicit_toman = 'تومان' in raw
    scale = 1_000_000_000 if 'میلیارد' in raw else 1_000_000 if 'میلیون' in raw else 1
    raw = re.sub(r'میلیارد|میلیون|تومان|ریال', '', raw).strip()
    result = number(raw)
    if result is None or result < 0: return None
    result *= scale
    if explicit_rial or (unit == 'rial' and not explicit_toman): result /= 10
    return int(result) if result == result.to_integral_value() else None


def neighborhood(value):
    raw = text(value)
    return NEIGHBORHOODS.get(raw.lower(), raw)[:80]


def enrich(description):
    """Conservative positive claims. Missing/negated evidence stays unknown."""
    result = {key: None for key in SIGNALS}
    evidence = []
    for factor, pattern in SIGNALS.items():
        for clause in re.split(r'[؛،.!?؟\n]', str(description or '')):
            clause = text(clause)
            match = re.search(pattern, clause, re.I)
            if not match: continue
            # Do not turn negated or hypothetical seller language into positive evidence.
            if re.search(r'نیست|ندارد|ندار[دم]|نمی|بدون نور|نیاز.*بازسازی|قابل بازسازی|باید.*بازسازی', clause): continue
            result[factor] = True if factor == 'renovation_claim' else .85
            evidence.append({'factor': factor, 'text': clause if len(clause)<=240 else clause[max(0,match.start()-80):match.end()+100], 'source': 'listing_text'})
            break
    result['evidence'] = evidence
    return result


class SkipRecord(ValueError):
    pass


def normalize_record(row, money_unit='toman'):
    deposit, rent = money(row.get('credit_value'), money_unit), money(row.get('rent_value'), money_unit)
    # Explicit modes can establish zero; absent numbers alone never mean zero.
    if rent is None and text(row.get('rent_mode')) in ('رهن کامل', 'بدون اجاره'): rent = 0
    if deposit is None and text(row.get('credit_mode')) == 'بدون ودیعه': deposit = 0
    if deposit is None or rent is None or deposit + rent == 0: raise SkipRecord('missing_price')
    if (0 < deposit < 100_000 or 0 < rent < 10_000 or deposit > 100_000_000_000 or rent > 1_000_000_000): raise SkipRecord('implausible_price')
    area = integer(row.get('building_size'))
    if area is None or not 10 <= area <= 1500: raise SkipRecord('invalid_area')
    rooms = bedrooms(row.get('rooms_count'))
    if rooms is None or not 0 <= rooms <= 5: raise SkipRecord('invalid_bedrooms')
    title = text(row.get('title'))
    if not title: raise SkipRecord('missing_title')
    description = str(row.get('description') or '').strip()
    if text(description) == '': description = ''
    description_text = text(description)
    if re.search(r'دنبال.{0,100}(?:می\s*گردم|هستم)|متقاضی اجاره',description_text): raise SkipRecord('wanted_ad')
    if re.search(r'فقط جهت (?:تولیدی|دفتر|انبار)|آپارتمان تجاری|اپارتمان تجاری',title+' '+description_text): raise SkipRecord('commercial_description')
    title_letters = re.sub(r'[^آ-ی]', '', title)
    description_letters = re.sub(r'[^آ-ی]', '', description_text)
    if len(title_letters)>=8 and len(set(title_letters))<=3 and len(set(description_letters))<=3: raise SkipRecord('corrupt_text')
    year = integer(row.get('construction_year'))
    if year is not None and not 1300 <= year <= 1405: year = None
    floor = integer(row.get('floor'))
    if text(row.get('floor')) in ('همکف', 'ground'): floor = 0
    if floor is not None and not -5 <= floor <= 100: floor = None
    lat, lon = number(row.get('location_latitude')), number(row.get('location_longitude'))
    # City filter is Tehran: corrupted/out-of-city coordinates become unknown, not guessed.
    if lat is None or lon is None or not (35.4 <= lat <= 35.95 and 51.0 <= lon <= 51.8): lat = lon = None
    radius = number(row.get('location_radius'))
    if radius is not None and not 0 <= radius <= 10000: radius = None
    signals = enrich(description)
    conflicts = []
    title_areas = {int(value) for value in re.findall(r'(?<![0-9])([0-9]{2,4})\s*متر\b',title)}
    if len(title_areas)==1:
        stated_area = next(iter(title_areas))
        if abs(stated_area-area)>=10 and abs(stated_area-area)/area>=.1:
            conflicts.append('متراژ عنوان با متراژ ساختاری متفاوت است؛ پیش از تصمیم تأیید شود.')
    if deposit > 0 and rent >= 100_000_000 and rent > deposit*10:
        conflicts.append('نسبت اجاره به ودیعه غیرمعمول است؛ مبلغ‌ها باید از آگهی‌دهنده تأیید شوند.')
    if rooms >= 2 and re.search(r'(?:یک|1) (?:اتاق )?خواب.*(?:حذف|ادغام)|(?:حذف|ادغام).*?(?:یک|1) (?:اتاق )?خواب', text(description)):
        conflicts.append('تعداد اتاق ساختاری با ادعای حذف یا ادغام یک اتاق خواب نیاز به بررسی دارد.')
    result = dict(data_source='real', city='tehran', title=title[:150], description=description,
        neighborhood=neighborhood(row.get('neighborhood_slug')), deposit=deposit, monthly_rent=rent,
        alternative_deposit=None, alternative_rent=None, area_m2=area, bedrooms=rooms, floor=floor,
        construction_year=year, renovated=boolean(row.get('is_rebuilt')),
        parking=boolean(row.get('has_parking')), elevator=boolean(row.get('has_elevator')),
        storage=boolean(row.get('has_warehouse')), balcony=boolean(row.get('has_balcony')),
        latitude=float(lat) if lat is not None else None, longitude=float(lon) if lon is not None else None,
        location_radius_m=float(radius) if radius is not None else None,
        distance_to_work_km=None, distances={}, data_conflicts=conflicts, **signals)
    # The official release has no public ad token. Content identity remains stable across CSV/Parquet.
    supplied = text(row.get('source_id'))
    identity = supplied or hashlib.sha256(json.dumps(result, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    source_id = 'divar:' + hashlib.sha256(identity.encode()).hexdigest()
    digest = hashlib.sha256(source_id.encode()).hexdigest()
    result.update(source_id=source_id, id=1_000_000 + int(digest[:15], 16), image_name=f'home-{int(digest[:8],16)%10+1:02}.jpg',
        source_metadata={'dataset': 'divarofficial/real_estate_ads', 'raw_neighborhood': text(row.get('neighborhood_slug')),
                         'created_at_month': text(row.get('created_at_month')), 'money_unit': money_unit,
                         'alternative_prices': 'not_mapped_unverified_semantics'})
    return result
