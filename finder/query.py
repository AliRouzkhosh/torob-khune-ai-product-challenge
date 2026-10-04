"""Deterministic query operations and references; session state supplies context."""
from dataclasses import dataclass
from .location_registry import workplace_label
from enum import StrEnum
import re
from .intent import ALIASES, normalize


class QueryOperation(StrEnum):
    NEW_SEARCH = 'NEW_SEARCH'
    PATCH = 'PATCH'


WORK_REFERENCE = r'(?:همون\s+)?جایی که کار می\s*کنم|محل کار(?:م)?|دفترم|شرکتم|اداره\s*م'
LOCATION_REFERENCE = r'(?:همون|همان|اون|آن) (?:محله|محدوده)|اطرافش|نزدیکش|دورش|داخلش|خودش'
PATCH_SIGNALS = r'\b(?:حالا|این بار|ولی|اما|دیگه|هم|همچنان|همون|همان|اون|آن|حتما|ضمن اینکه)\b|اضافه کن|حذف کن|لازم نیست|مهم نیست|مهم\s*تر|کمتر مهم|بی\s*خیال|از این به بعد|همون قدر|همونقدر'

QUERY_DIMENSIONS = {
    'bedrooms': r'خواب|اتاق\s*خواب',
    'budget': r'ودیعه|رهن|پول\s*پیش|اجاره|کرایه|بودجه',
    'area': r'متراژ|مساحت|\b\d+\s*متر\b|جادار|جمع\s*و\s*جور',
    'floor': r'طبقه|همکف|زیرزمین',
    'building_age': r'نوساز|تازه\s*ساز|قدیمی|سن\s*بنا|بازسازی',
    'pets': r'حیوان\s*خانگی|حیوون\s*خونگی|پت|گربه|سگ',
    'furnishing': r'مبله|فرنیش|غیرمبله|بدون\s*وسایل',
    'transport': r'مترو|BRT|بزرگراه|اتوبان',
    'security': r'نگهبان|نگهبانی|سرایدار|لابی\s*من|دوربین\s*مداربسته',
    'parking_detail': r'پارکینگ\s*(?:غیر\s*مزاحم|اختصاصی|سندی)|(?:دو|سه|[2-3])\s*(?:تا\s*)?پارکینگ',
    'hvac': r'پکیج|رادیاتور|شوفاژ|کولر\s*(?:گازی|آبی)|اسپلیت|فن\s*کویل|چیلر',
    'density': r'تک\s*واحدی|کم\s*واحد|ساختمان\s*شلوغ',
    'view': r'ویو|دید\s*باز|مشرف|منظره',
    'accessibility': r'ویلچر|رمپ|بدون\s*پله|آسانسور.{0,20}پارکینگ',
}


def classify_query(text, current=None, *, force_new=False, neighborhoods=()):
    text = normalize(text)
    if force_new or current is None:
        return QueryOperation.NEW_SEARCH
    if re.search(PATCH_SIGNALS + '|' + WORK_REFERENCE + '|' + LOCATION_REFERENCE, text):
        return QueryOperation.PATCH
    dimensions = {key for key, pattern in ALIASES.items() if re.search(pattern, text)}
    dimensions.update(key for key, pattern in QUERY_DIMENSIONS.items() if re.search(pattern, text))
    if any(re.search(r'(?<!\w)'+re.escape(normalize(name))+r'(?:ه)?(?!\w)',text) for name in neighborhoods): dimensions.add('location')
    return QueryOperation.NEW_SEARCH if len(dimensions) >= 3 else QueryOperation.PATCH


@dataclass(frozen=True)
class ReferenceResolution:
    text: str
    needs_clarification: str | None = None


class UnresolvedReference(ValueError):
    def __init__(self, reference):
        self.needs_clarification = reference
        super().__init__(reference)


def resolve_references(text, current, *, neighborhoods=()):
    text = normalize(text)
    # Commute preference statements describe priorities, not a command to live there.
    work_command = re.search(WORK_REFERENCE, text) and re.search(r'داخل|خود|اطراف|نزدیک|حوالی|همان\s*محله|همون\s*محله|\bدر\b', text) and not re.search(r'اگر|اگه|به\s*شرط|بودن|مهم|ترجیح', text)
    declaration = any(re.search(r'(?:دفترم|شرکتم|اداره\s*م|محل\s*کارم)\s*(?:حوالی\s*)?'+re.escape(normalize(name))+r'(?:ه)?(?!\w)',text) for name in neighborhoods)
    if declaration and not re.search(r'خونه|خانه|باشد|باشه|داخل|\bدر\b',text):work_command=False
    if work_command:
        place = workplace_label(current.work_location) if current.work_location!='none' else None
        if not place: return ReferenceResolution(text, 'workplace')
        text = re.sub(WORK_REFERENCE, place, text)
        text = re.sub(r'(?:همان|همون)\s*محله\s*'+re.escape(normalize(place)), 'خود '+normalize(place), text)
        # A same-request negative exact reference anchors its nearby pronoun to work.
        if re.search(r'خود.{0,25}نه', text):
            text = text.replace('اطرافش', 'اطراف ' + normalize(place))
    if re.search(LOCATION_REFERENCE, text):
        place = current.desired_location['neighborhood'] if len(current.constraints['neighborhoods']) == 1 else None
        # An explicit residence in this request takes precedence over earlier context;
        # a separate workplace declaration cannot make its pronoun ambiguous.
        prefix = re.split(LOCATION_REFERENCE, text, maxsplit=1)[0]
        names = [name for name in neighborhoods if re.search(r'(?<!\w)'+re.escape(normalize(name))+r'(?:ه)?(?!\w)',prefix)]
        names=[name for name in names if not any(name!=longer and normalize(name) in normalize(longer) for longer in names)]
        from .patches import location_mentions
        homes=[name for name in names if location_mentions(prefix,current,(name,))[1] is None]
        if len(homes)==1:place=homes[0]
        if not place: return ReferenceResolution(text, 'desired_location')
        text = re.sub(r'(?:همون|همان|اون|آن) (?:محله|محدوده)', place, text)
        for token, prefix in [('اطرافش','اطراف'),('نزدیکش','نزدیک'),('دورش','اطراف'),('داخلش','داخل'),('خودش','خود')]:
            text = text.replace(token, prefix + ' ' + normalize(place))
    return ReferenceResolution(text)
