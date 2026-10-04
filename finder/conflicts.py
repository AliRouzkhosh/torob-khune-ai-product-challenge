"""Only clear simultaneous hard contradictions; never compare a PATCH to its past."""
import re
from .language import normalize_persian, number_value, SMALL_NUMBER_TOKEN, ORDINAL_NUMBER_TOKEN


class IntentConflict(ValueError):
    def __init__(self, conflicts):
        self.conflicts = conflicts
        super().__init__('؛ '.join(c['message'] for c in conflicts))


def request_conflicts(text):
    text = normalize_persian(text)
    # A conditional/fallback clause is not a simultaneous unconditional assertion.
    clauses = re.split(r'[.؛،!?؟]|\s+(?:ولی|اما)\s+', text)
    plain = ' ؛ '.join(c for c in clauses if not re.search(r'اگر|اگه|به\s*شرط|اول.*(?:نبود|کم\s*بود)|ترجیح|بهتره', c))
    token = rf'(?:{SMALL_NUMBER_TOKEN}|{ORDINAL_NUMBER_TOKEN})'
    conflicts = []
    def add(field, message):
        conflicts.append({'field': field, 'code': 'incompatible_hard_requirements', 'message': message})
    beds = {number_value(m.group(1)) for m in re.finditer(rf'(?:فقط|حتما|دقیقا)\s*({token})\s*(?:تا\s*)?خواب', plain)}
    if len(beds - {None}) > 1:
        add('bedrooms', 'تعداد خواب به چند مقدار متفاوت به‌صورت قطعی مشخص شده.')
    lows = [number_value(m.group(1)) for m in re.finditer(rf'حداقل\s*طبقه\s*({token})', plain)]
    highs = [number_value(m.group(1)) for m in re.finditer(rf'حداکثر\s*طبقه\s*({token})', plain)]
    if lows and highs and max(lows) > min(highs):
        add('floor', 'حداقل طبقه از حداکثر طبقه بیشتر است.')
    rent = {'min': [], 'max': []}
    subject=None
    for clause in re.split(r'\s+و\s+|؛', plain):
        # Carry the explicit rent subject into an adjacent "and minimum ..." clause.
        if re.search(r'ودیعه|رهن|پول\s*پیش',clause):subject='deposit'
        if re.search(r'اجاره|کرایه',clause):subject='rent'
        if subject!='rent':
            continue
        for bound, word in [('min', 'حداقل'), ('max', 'حداکثر')]:
            for m in re.finditer(word + r'\s*(\d+)\s*(میلیون|میلیارد)', clause):
                rent[bound].append(int(m[1]) * (1_000_000 if m[2] == 'میلیون' else 1_000_000_000))
    if rent['min'] and rent['max'] and max(rent['min']) > min(rent['max']):
        add('max_rent', 'حداقل اجاره از حداکثر اجاره بیشتر است.')
    if re.search(r'(?:حتما|فقط)\s*نوساز|نوساز\s*(?:حتما|الزامی)', plain) and re.search(r'(?:حتما|فقط)\s*قدیمی|قدیمی\s*(?:حتما|الزامی)', plain):
        add('construction_year_min', 'ساختمان هم نوساز و هم قدیمی به‌صورت قطعی درخواست شده.')
    return conflicts


def check_request(text):
    conflicts = request_conflicts(text)
    if conflicts:
        raise IntentConflict(conflicts)
