from dataclasses import asdict, dataclass, field
from functools import lru_cache
import re
from .location_registry import workplace_choices, normalize_location_text
from .language import (
    bedroom_constraint, extract_money, is_negated, is_required,
    normalize_persian, priority_hint, split_clauses,
)

PRIORITIES = {'ignored': 0, 'low': 0.4, 'medium': 1.5, 'high': 3, 'very_high': 6}
LABELS = {'ignored': 'مهم نیست', 'low': 'کم‌اهمیت', 'medium': 'ترجیحی', 'high': 'مهم', 'very_high': 'خیلی مهم'}
FEATURES = {'natural_light': 'نورگیری', 'parking': 'پارکینگ', 'elevator': 'آسانسور', 'storage': 'انباری', 'quietness': 'آرامش محله', 'building_age': 'نوساز بودن', 'area': 'متراژ'}
SCENARIOS = {
    'a': ('دو نفر، نور و مسیر', 'من و همسرم حوالی ونک کار می‌کنیم. دوخوابه می‌خوایم، نور خوب خیلی مهمه، پارکینگ ترجیحاً داشته باشه. حدود ۸۰۰ میلیون ودیعه و ۲۵ میلیون اجاره می‌تونیم بدیم.'),
    'b': ('یک نفر، رفت‌وآمد کوتاه', 'تنها زندگی می‌کنم، محل کارم حوالی میدان ولیعصره. مسیر رفت‌وآمد برام از متراژ مهم‌تره. آسانسور مهمه ولی ماشین ندارم و پارکینگ لازم نیست. اجاره بیشتر از ۲۰ میلیون نشه.'),
    'c': ('خانواده، آرامش و امکانات', 'برای خانواده سه نفره خونه دو یا سه خوابه می‌خوایم. محله آروم و خونه نسبتاً نوساز باشه. انباری و پارکینگ مهمه. کمی بالاتر رفتن از بودجه برای گزینه خیلی بهتر قابل قبوله.'),
}


@dataclass
class IntentProfile:
    bedrooms_min: int = 0
    bedrooms_hard: bool = True
    deposit_target: int | None = None
    rent_target: int | None = None
    budget_flexibility: str = 'medium'
    budget_priority: str = 'high'
    rent_hard: bool = False
    elevator_required: bool = False
    work_location: str = 'none'
    location_priority: str = 'ignored'
    preferences: dict = field(default_factory=lambda: {key: 'low' for key in FEATURES})

    def __post_init__(self):
        if type(self.bedrooms_min) is not int or not 0 <= self.bedrooms_min <= 5:
            raise ValueError('تعداد اتاق باید بین صفر و پنج باشد.')
        for value in (self.deposit_target, self.rent_target):
            if value is not None and (type(value) is not int or not 0 <= value <= 100_000_000_000):
                raise ValueError('بودجه باید عددی مثبت و معتبر باشد.')
        if self.budget_flexibility not in ('none', 'medium', 'flexible') or self.work_location not in {key for key,label in workplace_choices()}:
            raise ValueError('بودجه یا محدوده محل کار معتبر نیست.')
        if self.location_priority not in PRIORITIES or self.budget_priority not in PRIORITIES or set(self.preferences) != set(FEATURES) or any(v not in PRIORITIES for v in self.preferences.values()):
            raise ValueError('اولویت‌ها معتبر نیستند.')
        if any(type(v) is not bool for v in (self.bedrooms_hard, self.rent_hard, self.elevator_required)):
            raise ValueError('محدودیت‌ها معتبر نیستند.')

    def to_dict(self):
        return asdict(self)


@lru_cache(maxsize=4096)
def normalize(text):
    return normalize_location_text(normalize_persian(text))


# Controlled phrase families. Negation is scoped to a clause, not the whole query.
ALIASES = {
    'parking': r'پارکینگ|جای\s*پارک',
    'natural_light': r'نور(?:گیری|گیر(?:ه)?)?|روشن|آفتاب\s*گیر|تاریک|دلگیر|پنجره\s*(?:بزرگ|قدی)|نور\s*طبیعی',
    'quietness': r'آروم|آرام(?:ش)?|ساکت|دنج|شلوغ|خلوت|بی\s*سروصدا|کم\s*تردد|کوچه\s*خلوت',
    'building_age': r'نوساز|نو\s*ساز|تازه\s*ساز|جدید|قدیمی(?:\s*بودن)?|سن\s*بنا|سال\s*ساخت|بازسازی',
    'elevator': r'آسانسور',
    'storage': r'انباری|انبار',
    'area': r'متراژ|مساحت|\b\d+\s*متر\b|جادار|جمع\s*و\s*جور',
    'location': r'رفت\s*و\s*آمد|مسیر|نزدیکی|فاصله\s*تا\s*محل\s*کار|نزدیک(?:\s*بودن)?',
    'budget': r'بودجه|هزینه|قیمت',
}
NEGATION = r'(?:اصلا\s*)?مهم\s*نیست|لازم\s*نیست|ضروری\s*نیست|نمی\s*خوام|اهمیت(?:ی)?\s*ندار[ده]|لازم\s*ندارم|فرقی\s*ندار[ده]|بی\s*خیال|بیخیال'
SUPERLATIVE = r'خیلی\s*مهم|مهم\s*ترین|اولویت\s*اول|از\s*همه(?:\s*چیز)?\s*مهم\s*تر|حتما|واجب'


def set_priority(profile, key, value):
    if key == 'location':
        profile.location_priority = value
    elif key == 'budget':
        profile.budget_priority = value
    else:
        profile.preferences[key] = value


def phrase_key(text):
    return next((key for key, pattern in ALIASES.items() if re.search(pattern, text)), None)


def heuristic_parse(text, base=None):
    profile = IntentProfile(**base.to_dict()) if base else IntentProfile()
    text = normalize(text)

    bed = bedroom_constraint(text)
    if bed and bed['mode'] != 'any':
        value = min(bed['value']) if isinstance(bed['value'], list) else bed['value']
        profile.bedrooms_min = value or 0
        profile.bedrooms_hard = True
    elif bed and bed['mode'] == 'any':
        profile.bedrooms_min = 0
        profile.bedrooms_hard = False

    deposit = extract_money(text, ('ودیعه', 'رهن', 'پول پیش', 'پیش'))
    rent = extract_money(text, ('اجاره', 'کرایه', 'اجاره ماهانه'))
    if deposit is not None:
        profile.deposit_target = deposit
    if rent is not None:
        profile.rent_target = rent
    if re.search(r'(?:بیشتر|بالاتر).{0,20}(?:نشه|نباشه)|سقف\s*اجاره|حداکثر\s*اجاره', text):
        profile.rent_hard = True

    for clause in split_clauses(text):
        relative = re.search(r'(.+?)\s+از\s+(.+?)\s+مهم\s*تر(?:ه|\s*است)?', clause)
        if relative:
            higher, lower = phrase_key(relative[1]), phrase_key(relative[2])
            if higher:
                set_priority(profile, higher, 'very_high')
                if lower and lower != higher:
                    set_priority(profile, lower, 'low')
                continue
        parts = re.split(r'\s+و\s+(?=پارکینگ|جای\s*پارک|آسانسور|انباری|انبار|نور|متراژ|بودجه)', clause)
        for part in parts:
            for key, pattern in ALIASES.items():
                if not re.search(pattern, part):
                    continue
                # Transit proximity (e.g. «نزدیک مترو») is an ad-text access
                # preference, not automatically a workplace/commute preference.
                if key == 'location' and re.search(r'مترو|BRT|ایستگاه|بزرگراه|اتوبان', part) and not re.search(r'محل\s*کار|رفت\s*و\s*آمد|مسیر\s*کار', part):
                    continue
                priority = priority_hint(part)
                # Negative wording such as "تاریک نباشه" is a positive light requirement,
                # not an instruction to ignore the light criterion.
                if key == 'natural_light' and re.search(r'(?:تاریک|دلگیر).*(?:نباش|نمی\s*خوام)', part):
                    priority = 'high'
                if key == 'quietness' and re.search(r'(?:شلوغ|پرتردد|خیابان\s*اصلی).*(?:نباش|نمی\s*خوام)', part):
                    priority = 'high'
                if key == 'building_age' and re.search(r'قدیمی.*(?:نباش|نمی\s*خوام)', part):
                    priority = 'high'
                if key == 'location' and re.search(r'مهم\s*تر|اولویت\s*اول', part):
                    priority = 'very_high'
                set_priority(profile, key, priority)
                if key == 'elevator':
                    if is_required(part):
                        profile.elevator_required = True
                    elif is_negated(part):
                        profile.elevator_required = False

    if 'ماشین ندارم' in text or re.search(r'بدون\s*پارکینگ.*(?:اوکی|مشکل)', text):
        profile.preferences['parking'] = 'low'

    # Work context is intentionally conservative: a named neighborhood alone is not a workplace.
    if 'ولیعصر' in text and re.search(r'محل\s*کار|دفتر|شرکت|اداره|کار\s*می|برای\s*کار', text):
        profile.work_location = 'valiasr'
        if profile.location_priority == 'ignored':
            profile.location_priority = 'high'
    elif 'ونک' in text and re.search(r'محل\s*کار|دفتر|شرکت|اداره|کار\s*می|برای\s*کار', text):
        profile.work_location = 'vanak'
        if profile.location_priority == 'ignored':
            profile.location_priority = 'high'

    if re.search(r'بودجه.{0,30}(?:منعطف|انعطاف|بالاتر)|(?:کمی|یه\s*کم|یه\s*ذره).{0,20}(?:بیشتر|بالاتر).{0,20}(?:اوکی|مشکل|می\s*دم)', text):
        profile.budget_flexibility = 'flexible'
    elif re.search(r'بالاتر\s*از\s*بودجه\s*نمی\s*رم|بودجه.{0,20}(?:ثابت|قطعی|انعطاف\s*ندار)', text):
        profile.budget_flexibility = 'none'

    profile.__post_init__()
    return profile


def intent_changes(before, after):
    changes = []
    for key, label in {**FEATURES, 'location': 'رفت‌وآمد', 'budget': 'اهمیت بودجه'}.items():
        old = before.location_priority if key == 'location' else before.budget_priority if key == 'budget' else before.preferences[key]
        new = after.location_priority if key == 'location' else after.budget_priority if key == 'budget' else after.preferences[key]
        if old != new:
            changes.append({'label': label, 'before': LABELS[old], 'after': LABELS[new]})
    for key, label in {'bedrooms_min': 'حداقل اتاق', 'deposit_target': 'ودیعه هدف', 'rent_target': 'اجاره هدف', 'work_location': 'محل کار', 'budget_flexibility': 'انعطاف بودجه', 'rent_hard': 'سقف قطعی اجاره', 'elevator_required': 'آسانسور ضروری'}.items():
        if getattr(before, key) != getattr(after, key):
            changes.append({'label': label, 'before': getattr(before, key), 'after': getattr(after, key), 'field': key})
    return changes
