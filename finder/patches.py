"""Sparse, validated changes. Application state supplies memory; providers do not."""
from copy import deepcopy
from dataclasses import dataclass, field
import re
from .intent import ALIASES, normalize, SCENARIOS
from .language import (
    area_constraint, bedroom_constraint, construction_year_min, extract_money,
    floor_constraint, is_required, renovation_requirement, evidence_language,
)
from .search import SearchIntent, _legacy_merge_inference, forget_manual
from .compound import apply_compound_language
from .location_registry import location_key,workplace_label


@dataclass
class IntentPatch:
    set: dict = field(default_factory=dict)
    unset: list = field(default_factory=list)
    source: str = 'refinement'

    def merge(self, current):
        """Copy the current state, reset explicit unsets, then validate sparse edits."""
        result = current.copy()
        defaults = SearchIntent().to_dict()
        allowed = {(group, key) for group in defaults for key in defaults[group]}
        if self.source not in ('prompt', 'refinement', 'filter', 'review', 'recovery'): raise ValueError('منبع تغییر معتبر نیست.')
        for path in [*self.set, *self.unset]:
            if tuple(path.split('.')) not in allowed: raise ValueError('فیلد تغییر معتبر نیست.')
        for path in self.unset:
            group, key = path.split('.')
            getattr(result, group)[key] = deepcopy(defaults[group][key])
        for path, value in self.set.items():
            group, key = path.split('.')
            getattr(result, group)[key] = deepcopy(value)
        result.metadata['source'] = self.source
        result.__post_init__()
        return result


def location_mentions(text, current, neighborhoods):
    """Separate residential request from work context, including inherited pronouns."""
    residential, workplace = None, None
    near = r'نزدیک|نزدیکای|حوالی|اطراف|دور و بر|محله های اطراف|نزدیکش'
    names = sorted(set(neighborhoods), key=len, reverse=True)
    occupied=[]
    for name in names:
        canonical = normalize(name)
        for match in re.finditer(r'(?<!\w)'+re.escape(canonical)+r'(?:ه)?(?!\w)', text):
            if any(match.start()<end and match.end()>start for start,end in occupied):continue
            left, right = text[max(0,match.start()-45):match.start()], text[match.end():match.end()+35]
            if canonical=='کن' and re.search(r'(?:پیدا|جستجو|شروع|اعمال|حذف|پاک|کم|زیاد|انتخاب|اضافه)\s*$',left):continue
            occupied.append((match.start(),match.end()))
            work = bool(re.match(r'(?:ه|\s)*(?:کار\s*می|کار\s*میک|کار\s*دار)', right) or (re.search(r'(?:محل\s*کار(?:م)?|سر\s*کار(?:م)?|دفترم|شرکتم|اداره\s*م|برای\s*کار\s*هر\s*روز\s*میرم)[^،؛.]*$', left) and not re.search(r'خونه|خانه|بگیر', right)))
            if work:
                workplace = location_key(name)
                continue
            if re.search(near, left[-20:] + right[:25]): residential = {'neighborhood': name, 'mode': 'nearby'}
            elif re.search(r'فقط|داخل|خود|حتما|محله|\bدر\b', left[-20:]) or text.strip() == canonical or re.search(r'خونه|خانه|باشه|باشد|خوب', right): residential = {'neighborhood': name, 'mode': 'exact'}
    if not residential and current.constraints['neighborhoods'] and re.search(r'نزدیکش|اطرافش|داخل.*نبود اشکال نداره', text):
        residential = {'neighborhood': current.desired_location['neighborhood'], 'mode':'nearby'}
    # Nearby relaxation wins over a preceding "inside ... wasn't necessary" clause.
    if residential and re.search(r'نزدیکش|اطرافش|اطراف.*هم خوب|هم نبود اشکال نداره',text): residential['mode'] = 'nearby'
    return residential, workplace


def parse_intent_patch(service, text, current, neighborhoods):
    from .conflicts import check_request
    check_request(text)
    from .query import resolve_references, UnresolvedReference
    raw_text = normalize(text)
    resolution = resolve_references(text, current, neighborhoods=neighborhoods)
    if resolution.needs_clarification: raise UnresolvedReference(resolution.needs_clarification)
    original = resolution.text
    clean = re.sub(r'\b(?:دیگه|فعلا|بودن|هم)\b', ' ', original)
    clean = normalize(clean)
    parsed = service.parse_intent(clean, base=current.as_profile())
    result = _legacy_merge_inference(current, parsed, clean, neighborhoods)
    # Older DTO inference cannot distinguish residence from workplace. Restore then project explicit mentions.
    result.context = deepcopy(current.context)
    result.constraints['neighborhoods'] = deepcopy(current.constraints['neighborhoods'])
    result.constraints['neighborhood_mode'] = current.constraints['neighborhood_mode']
    residential, workplace = location_mentions(original, current, neighborhoods)
    if workplace:
        result.context['workplace'] = workplace
        if result.preferences['commute'] == 'ignored': result.preferences['commute'] = 'high'
    if residential:
        result.constraints['neighborhoods'] = [residential['neighborhood']]
        result.constraints['neighborhood_mode'] = residential['mode']
        if current.work_location!='none' and re.search(r'خود\s*(?:محل\s*کار(?:م)?|'+re.escape(normalize(workplace_label(current.work_location)))+r')\s*نه',raw_text):
            result.constraints['excluded_neighborhoods']=[workplace_label(current.work_location)]
        elif re.search(r'خود|فقط|داخل',raw_text):result.constraints['excluded_neighborhoods']=[]
        forget_manual(result, 'neighborhoods')
        # Housing proximity does not imply commute preference.
        if not workplace and not re.search(r'رفت\s*و\s*آمد|محل کار|مسیر', original): result.preferences['commute'] = current.preferences['commute']
    if re.search(r'محله.*(?:مهم نیست|بیخیال|فرقی ندار)|بیخیال.*محله', clean):
        result.constraints['neighborhoods'] = []
        result.constraints['excluded_neighborhoods']=[]
        result.constraints['neighborhood_mode'] = 'exact'
        forget_manual(result, 'neighborhoods')

    # Structured bedroom language is parsed directly so colloquial forms and allowed sets
    # do not have to fit the legacy IntentProfile DTO.
    bed = bedroom_constraint(clean)
    if bed is not None:
        # In a PATCH, «یک خوابه هم اوکیه» means add an acceptable bedroom
        # count, not replace an existing exact choice.  Preserve this additive
        # conversational meaning while full searches still parse normally.
        additive_bed = bool(re.search(
            r'(?:خواب|خوابه|اتاق(?:\s*خواب)?).{0,12}(?:هم\s*)?(?:اوکی|قبول|خوبه|مناسبه)',
            original,
        ))
        prior_bed = current.constraints['bedrooms']
        if additive_bed and bed['mode'] in ('exact', 'allowed') and prior_bed['mode'] in ('exact', 'allowed'):
            old_values = prior_bed['value'] if prior_bed['mode'] == 'allowed' else [prior_bed['value']]
            new_values = bed['value'] if bed['mode'] == 'allowed' else [bed['value']]
            values = sorted({v for v in [*old_values, *new_values] if isinstance(v, int)})
            result.constraints['bedrooms'] = {'mode': 'allowed', 'value': values}
        else:
            result.constraints['bedrooms'] = bed
        forget_manual(result, 'bedrooms')

    # v0.9-B structured housing constraints. These map directly to fields present on
    # Listing, so they affect candidate eligibility rather than acting as decorative
    # keywords. Missing listing data never satisfies an active hard constraint.
    area = area_constraint(clean)
    if area is not None:
        result.constraints['area'] = area
        forget_manual(result, 'area')
        # A numeric bound is a hard constraint, not automatically a preference for
        # ever-larger homes. Preserve the previous area weight unless preference
        # language is explicit.
        if not re.search(r'(?:متراژ|مساحت).{0,14}(?:مهم|اولویت|ترجیح)|جادار|خونه\s*بزرگ', clean):
            result.preferences['area'] = current.preferences['area']
    elif re.search(r'(?:متراژ|مساحت).{0,18}(?:مهم نیست|فرقی ندار|بیخیال)|بیخیال.{0,14}(?:متراژ|مساحت)', clean):
        result.constraints['area'] = {'min': None, 'max': None}
        forget_manual(result, 'area')

    floor = floor_constraint(clean)
    if floor is not None:
        result.constraints['floor'] = floor
        forget_manual(result, 'floor')
    elif re.search(r'طبقه.{0,16}(?:مهم نیست|فرقی ندار|بیخیال)|بیخیال.{0,12}طبقه', clean):
        result.constraints['floor'] = {'mode': 'any', 'value': None, 'excluded': []}
        forget_manual(result, 'floor')

    year_min = construction_year_min(clean)
    if year_min is not None:
        result.constraints['construction_year_min'] = year_min
        forget_manual(result, 'construction_year_min')
        if not re.search(r'نوساز|تازه\s*ساز|جدید(?:تر)?|سن\s*بنا.{0,12}(?:مهم|پایین)|ترجیح', clean):
            result.preferences['building_age'] = current.preferences['building_age']
    elif re.search(r'(?:سن بنا|سال ساخت).{0,18}(?:مهم نیست|فرقی ندار|بیخیال)|بیخیال.{0,14}(?:سن بنا|سال ساخت)', clean):
        result.constraints['construction_year_min'] = None
        forget_manual(result, 'construction_year_min')
    elif any(re.search(r'نوساز',c) and re.search(r'ترجیح|بهتره',c) for c in re.split(r'[.؛،]|\s+(?:ولی|اما)\s+',clean)):
        result.constraints['construction_year_min'] = None
        forget_manual(result,'construction_year_min')

    renovation = renovation_requirement(clean)
    if renovation is not None:
        result.constraints['renovation_required'] = renovation
        forget_manual(result, 'renovation_required')
        # Asking for renovation does not mean "prefer newer construction".
        if not re.search(r'نوساز|تازه\s*ساز|جدید(?:تر)?|قدیمی|سن\s*بنا|سال\s*ساخت', clean):
            result.preferences['building_age'] = current.preferences['building_age']

    # v0.9-C evidence-aware language. User intent is stored canonically while
    # listing truth stays YES/NO/UNKNOWN in evidence_features.py. Soft wording only
    # affects evidence_preferences; explicit requirements become hard constraints.
    evidence_request = evidence_language(clean)
    evidence_defaults = SearchIntent().constraints
    list_constraints = {'hvac_required','security_required','transport_required','view_privacy_required','accessibility_required'}
    for key in evidence_request['unset_constraints']:
        if key in result.constraints:
            result.constraints[key] = deepcopy(evidence_defaults[key])
    # Feature-specific unsets should not erase sibling requirements in the same family.
    feature_groups = {
        'package_heating':'hvac_required','radiator':'hvac_required','split_ac':'hvac_required','water_cooler':'hvac_required','fan_coil':'hvac_required','chiller':'hvac_required',
        'security_24h':'security_required','cctv':'security_required','concierge':'security_required','lobby':'security_required',
        'near_metro':'transport_required','near_brt':'transport_required','good_road_access':'transport_required',
        'open_view':'view_privacy_required','privacy':'view_privacy_required','mountain_view':'view_privacy_required','city_view':'view_privacy_required',
        'step_free':'accessibility_required','wheelchair':'accessibility_required','ramp':'accessibility_required','elevator_from_parking':'accessibility_required',
    }
    for feature in evidence_request['unset_required_features']:
        group = feature_groups.get(feature)
        if group:
            result.constraints[group] = [value for value in result.constraints[group] if value != feature]
    for key, value in evidence_request['constraints'].items():
        if key in list_constraints:
            result.constraints[key] = sorted(set(result.constraints[key]) | set(value))
        else:
            result.constraints[key] = deepcopy(value)
    for feature in evidence_request['unset_preferences']:
        if feature in result.evidence_preferences:
            result.evidence_preferences[feature] = 'ignored'
    for feature, priority in evidence_request['preferences'].items():
        if feature in result.evidence_preferences:
            result.evidence_preferences[feature] = priority
    # Parking text constraints imply at least one structured parking place, but only
    # count/type evidence confirms the richer requirement.
    if result.constraints['parking_count_min'] is not None or result.constraints['parking_non_tandem_required'] or result.constraints['parking_dedicated_required']:
        if 'parking' not in result.constraints['required_amenities']:
            result.constraints['required_amenities'].append('parking')
        result.preferences['parking'] = max(result.preferences['parking'], 'high', key=lambda p: {'ignored':0,'low':1,'medium':2,'high':3,'very_high':4}[p])

    # Persian rental vocabulary: ودیعه/رهن/پول پیش and اجاره/کرایه all map to the
    # existing canonical targets.  Explicit سقف/حداکثر/بیشتر ... نشه makes the
    # amount a hard cap; otherwise existing flexibility semantics are preserved.
    for aliases, target, cap in [
        (('ودیعه','رهن','پول پیش','پیش'), 'deposit', 'max_deposit'),
        (('اجاره','کرایه','اجاره ماهانه'), 'rent', 'max_rent'),
    ]:
        value = extract_money(clean, aliases)
        if value is None:
            continue
        result.targets[target] = value
        alias_pattern = r'(?:' + '|'.join(re.escape(a) for a in aliases) + r')'
        hard = bool(re.search(r'(?:سقف|حداکثر).{0,20}' + alias_pattern + r'|' + alias_pattern + r'.{0,30}(?:بیشتر.{0,25}نش|حداکثر|سقف)|(?:تا\s*\d+.{0,15}' + alias_pattern + r')', clean))
        multiplier = 1 if hard else {'none':1,'medium':1.2,'flexible':1.4}[result.targets['flexibility']]
        result.constraints[cap] = int(value * multiplier)
        forget_manual(result, cap)
    if bed is None and re.search(r'(?:خواب\w*|اتاق).*?(?:مهم نیست|فرقی ندار|بیخیال)|بیخیال.*(?:خواب|اتاق)', clean):
        result.constraints['bedrooms'] = {'mode':'any','value':None}
        forget_manual(result,'bedrooms')
    elif bed is None and re.search(r'یک\s*(?:یا دو|خواب.*اوکی)|1\s*خواب.*اوکی', clean):
        old = current.constraints['bedrooms']
        values = old['value'] if old['mode']=='allowed' else [old['value']] if old['mode']=='exact' else []
        result.constraints['bedrooms'] = {'mode':'allowed','value': sorted(set([1,2] if 'یا دو' in clean else [1,*values]))}
        forget_manual(result,'bedrooms')
    elif bed is None and re.search(r'دو\s*یا\s*سه\s*خواب', clean):
        result.constraints['bedrooms'] = {'mode':'allowed','value':[2,3]}
    for key in ('parking','elevator','storage'):
        for clause in re.split(r'[؛،,.!?؟]|\s+(?:ولی|اما)\s+|\s+و\s+(?=پارکینگ|آسانسور|انباری|تا)',clean):
            if not re.search(ALIASES[key],clause): continue
            if re.search(r'مهم نیست|لازم نیست|بیخیال|حذف\s*کن|نمی\s*خوام|اهمیتی نداره',clause):
                result.preferences[key] = 'low'
                result.constraints['required_amenities'] = [k for k in result.constraints['required_amenities'] if k != key]
                if key == 'parking' and not re.search(r'اگر|اگه|نوع|کیفیت', clause):
                    result.constraints.update(parking_count_min=None, parking_non_tandem_required=False, parking_dedicated_required=False)
                    result.evidence_preferences.update(parking_non_tandem='ignored', parking_dedicated='ignored')
            elif is_required(clause):
                result.preferences[key] = 'very_high'
                if key not in result.constraints['required_amenities']: result.constraints['required_amenities'].append(key)
    for aliases, target, cap in [(r'ودیعه|رهن|پول\s*پیش', 'deposit', 'max_deposit'), (r'اجاره|کرایه', 'rent', 'max_rent')]:
        for clause in re.split(r'[؛،,.!?؟]|\s+(?:ولی|اما)\s+|\s+و\s+(?=تا|ودیعه|اجاره|کرایه|رهن)', clean):
            if re.search(aliases, clause) and re.search(r'بی\s*خیال|مهم\s*نیست|حذف\s*کن|محدودیت.{0,12}ندار', clause):
                result.constraints[cap] = None
                result.targets[target] = None
                forget_manual(result, cap)
    if re.search(r'بودجه.*(?:مهم نیست|بیخیال)|بیخیال.*بودجه',clean):
        for key in ('max_deposit','max_rent'): result.constraints[key] = None; forget_manual(result,key)
        result.targets.update(deposit=None,rent=None)
        result.preferences['budget'] = 'ignored'
    for clause in re.split(r'[؛،,.!?؟]|\s+(?:ولی|اما)\s+|\s+و\s+(?=نور|پارکینگ|آسانسور|انباری|بودجه)',clean):
        for key in ('natural_light','quietness','building_age','area'):
            if re.search(ALIASES[key],clause):
                if re.search(r'بیخیال|مهم نیست|اهمیتی نداره',clause): result.preferences[key] = 'low'
                elif 'کمتر مهم' in clause: result.preferences[key] = 'low'
                elif 'بیشتر مهم' in clause: result.preferences[key] = 'very_high'
    if re.search(r'(?:کمی|یه کم|یه ذره).{0,20}(?:بیشتر|بالاتر).{0,20}(?:مشکلی نیست|اوکی|می دم)|بودجه.{0,30}(?:بالاتر|منعطف|انعطاف)',clean):
        result.targets['flexibility']='flexible'
        for target,cap in [('deposit','max_deposit'),('rent','max_rent')]:
            if result.targets[target] is not None: result.constraints[cap]=int(result.targets[target]*1.4)

    # v0.9-D runs after flat parsing so conditional/fallback phrases can repair any
    # accidental globalization (e.g. floor 4+ is the IF side, not a global minimum).
    result = apply_compound_language(raw_text, current, result, neighborhoods)
    result.__post_init__()
    patch = IntentPatch()
    defaults=SearchIntent().to_dict()
    for group in ('constraints','preferences','evidence_preferences','context','targets','metadata','logic'):
        for key,value in getattr(result,group).items():
            if key == 'source' and group == 'metadata': continue
            if value != getattr(current,group)[key]:
                path=group+'.'+key
                if group=='constraints' and value == defaults[group][key]: patch.unset.append(path)
                else: patch.set[path]=deepcopy(value)
    return patch


def parse_full_intent(service, text, neighborhoods):
    # Keep the three curated personas; all other first queries start without unstated preferences.
    if any(normalize(query)==normalize(text) for _,query in SCENARIOS.values()):
        current=SearchIntent.from_profile(service.parse_intent(text),text)
    else:
        current=SearchIntent()
        current.preferences={key:'ignored' for key in current.preferences}
        current.preferences['budget']='high'  # Full-query default; patches never invent an unmentioned priority.
    patch=parse_intent_patch(service,text,current,neighborhoods)
    patch.source='prompt'
    return patch.merge(current)


def recognized_text(text, neighborhoods):
    from .query import WORK_REFERENCE, LOCATION_REFERENCE
    text=normalize(text)
    # A bare descriptive keyword is intentionally left as literal Browse search.
    # «بازسازی» alone is ambiguous (find ads containing the word vs. require a
    # renovated home); explicit language such as «بازسازی کامل لازم دارم» is
    # still handled by the smart-intent parser.
    if re.fullmatch(r'(?:بازسازی|نوسازی)', text):
        return False
    extra = r'خواب|اتاق\s*خواب|ودیعه|رهن|پول\s*پیش|اجاره|کرایه|ماشین\s*ندارم|طبقه|همکف|زیرزمین|مترو|BRT|حیوان\s*خانگی|حیوون\s*خونگی|پت|گربه|سگ|مبله|فرنیش|بازسازی|پارکینگ\s*(?:غیر\s*مزاحم|اختصاصی|سندی)|پکیج|کولر\s*(?:گازی|آبی)|اسپلیت|شوفاژ|فن\s*کویل|چیلر|تک\s*واحدی|کم\s*واحد|نگهبان|سرایدار|دوربین\s*مدار\s*بسته|ویو|مشرف|ویلچر|رمپ|بدون\s*پله'
    return bool(re.search(WORK_REFERENCE + '|' + LOCATION_REFERENCE,text) or any(re.search(pattern,text) for pattern in ALIASES.values()) or re.search(extra,text) or any(re.search(r'(?<!\w)'+re.escape(normalize(n))+r'(?:ه)?(?!\w)',text) for n in neighborhoods))
