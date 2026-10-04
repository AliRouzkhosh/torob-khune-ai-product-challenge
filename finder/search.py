"""One validated search state. Metadata records provenance, never competing values."""
from copy import deepcopy
from dataclasses import dataclass, field
import re
from .intent import IntentProfile, FEATURES, PRIORITIES, LABELS, ALIASES, normalize, intent_changes
from .ranking import fa, money
from .evidence_features import EVIDENCE_FEATURES, EVIDENCE_FEATURE_LABELS, required_evidence_tokens
from .compound import default_logic, validate_logic, logic_labels as compound_logic_labels
from .location_registry import workplace_label

AMENITIES = {'parking': 'پارکینگ', 'elevator': 'آسانسور', 'storage': 'انباری', 'balcony': 'بالکن'}
MANUAL_FIELDS = {'bedrooms', 'max_deposit', 'max_rent', 'neighborhoods', 'area', 'floor', 'construction_year_min', 'renovation_required', *('amenity:' + k for k in AMENITIES)}


@dataclass
class SearchIntent:
    """Canonical validated search state; every input channel edits this contract."""
    constraints: dict = field(default_factory=lambda: {
        'bedrooms': {'mode': 'any', 'value': None},
        'max_deposit': None, 'max_rent': None,
        'neighborhoods': [], 'neighborhood_mode': 'exact',
        'required_amenities': [],
        'area': {'min': None, 'max': None},
        'floor': {'mode': 'any', 'value': None, 'excluded': []},
        'construction_year_min': None,
        'renovation_required': False,
        # v0.9-C: requirements inferred from seller/ad text. Unknown evidence never
        # satisfies these hard constraints.
        'pet_policy': 'any',
        'parking_count_min': None,
        'parking_non_tandem_required': False,
        'parking_dedicated_required': False,
        'furnishing': 'any',
        'hvac_required': [],
        'building_density': 'any',
        'security_required': [],
        'transport_required': [],
        'view_privacy_required': [],
        'accessibility_required': [],
    })
    preferences: dict = field(default_factory=lambda: {**{k: 'low' for k in FEATURES}, 'commute': 'ignored', 'budget': 'high'})
    evidence_preferences: dict = field(default_factory=lambda: {key: 'ignored' for key in EVIDENCE_FEATURES})
    context: dict = field(default_factory=lambda: {'workplace': 'none'})
    targets: dict = field(default_factory=lambda: {'deposit': None, 'rent': None, 'flexibility': 'medium'})
    metadata: dict = field(default_factory=lambda: {'manual': [], 'source': 'prompt'})
    # v0.9-D: relationships between criteria.  Kept separate from flat constraints so
    # conditional requirements and fallback plans are never silently globalized.
    logic: dict = field(default_factory=default_logic)

    def __post_init__(self):
        # Session-schema migration: older v0.4-v0.9A states gain the new structured
        # constraints on read without losing any existing search state.
        self.constraints.setdefault('neighborhood_mode', 'exact')
        self.constraints.setdefault('full_deposit', False)
        self.constraints.setdefault('convertible', False)
        self.constraints.setdefault('excluded_neighborhoods', [])
        self.constraints.setdefault('area', {'min': None, 'max': None})
        self.constraints.setdefault('floor', {'mode': 'any', 'value': None, 'excluded': []})
        self.constraints.setdefault('construction_year_min', None)
        self.constraints.setdefault('renovation_required', False)
        self.constraints.setdefault('pet_policy', 'any')
        self.constraints.setdefault('parking_count_min', None)
        self.constraints.setdefault('parking_non_tandem_required', False)
        self.constraints.setdefault('parking_dedicated_required', False)
        self.constraints.setdefault('furnishing', 'any')
        self.constraints.setdefault('hvac_required', [])
        self.constraints.setdefault('building_density', 'any')
        self.constraints.setdefault('security_required', [])
        self.constraints.setdefault('transport_required', [])
        self.constraints.setdefault('view_privacy_required', [])
        self.constraints.setdefault('accessibility_required', [])
        # v0.9-C session migration: a v0.9-B state does not have this group.
        for key in EVIDENCE_FEATURES:
            self.evidence_preferences.setdefault(key, 'ignored')
        # v0.9-D session migration: v0.9-C session dictionaries have no logic group.
        validate_logic(self.logic)
        if self.constraints['neighborhood_mode'] not in ('exact', 'nearby', 'preferred'): raise ValueError('محدوده محله معتبر نیست.')
        if any(type(self.constraints[k]) is not bool for k in ('full_deposit','convertible')): raise ValueError('شرط بودجه معتبر نیست.')
        expected_constraints = {'bedrooms', 'max_deposit', 'max_rent', 'neighborhoods', 'neighborhood_mode', 'required_amenities', 'area', 'floor', 'construction_year_min', 'renovation_required', 'pet_policy', 'parking_count_min', 'parking_non_tandem_required', 'parking_dedicated_required', 'furnishing', 'hvac_required', 'building_density', 'security_required', 'transport_required', 'view_privacy_required', 'accessibility_required'}
        expected_constraints.update(('full_deposit','convertible','excluded_neighborhoods'))
        if set(self.constraints) != expected_constraints or set(self.context) != {'workplace'} or set(self.targets) != {'deposit', 'rent', 'flexibility'}:
            raise ValueError('ساختار خواسته‌ها معتبر نیست.')
        bed = self.constraints['bedrooms']
        if set(bed) != {'mode', 'value'} or bed['mode'] not in ('any', 'exact', 'min', 'max', 'allowed') or (bed['mode'] == 'any' and bed['value'] is not None) or (bed['mode'] not in ('any', 'allowed') and (type(bed['value']) is not int or not 1 <= bed['value'] <= 5)):
            raise ValueError('تعداد اتاق معتبر نیست.')
        if bed['mode'] == 'allowed' and (not isinstance(bed['value'], list) or not bed['value'] or any(type(v) is not int or not 1 <= v <= 5 for v in bed['value'])): raise ValueError('اتاق‌های مجاز معتبر نیست.')
        area = self.constraints['area']
        if set(area) != {'min', 'max'}: raise ValueError('محدوده متراژ معتبر نیست.')
        for value in area.values():
            if value is not None and (type(value) is not int or not 10 <= value <= 1500): raise ValueError('محدوده متراژ معتبر نیست.')
        if area['min'] is not None and area['max'] is not None and area['min'] > area['max']: raise ValueError('محدوده متراژ معتبر نیست.')
        floor = self.constraints['floor']
        if set(floor) != {'mode', 'value', 'excluded'} or floor['mode'] not in ('any', 'exact', 'min', 'max', 'allowed'): raise ValueError('طبقه معتبر نیست.')
        if floor['mode'] == 'any' and floor['value'] is not None: raise ValueError('طبقه معتبر نیست.')
        if floor['mode'] == 'allowed':
            if not isinstance(floor['value'], list) or not floor['value'] or any(type(v) is not int or not -5 <= v <= 100 for v in floor['value']): raise ValueError('طبقه معتبر نیست.')
        elif floor['mode'] != 'any' and (type(floor['value']) is not int or not -5 <= floor['value'] <= 100): raise ValueError('طبقه معتبر نیست.')
        if not isinstance(floor['excluded'], list) or not set(floor['excluded']) <= {'ground', 'basement'}: raise ValueError('طبقه‌های حذف‌شده معتبر نیستند.')
        year = self.constraints['construction_year_min']
        from .calendar import current_jalali_year
        if year is not None and (type(year) is not int or not 1300 <= year <= current_jalali_year()): raise ValueError('سال ساخت معتبر نیست.')
        if type(self.constraints['renovation_required']) is not bool: raise ValueError('شرط بازسازی معتبر نیست.')
        if self.constraints['pet_policy'] not in ('any', 'allowed'): raise ValueError('شرط حیوان خانگی معتبر نیست.')
        parking_count = self.constraints['parking_count_min']
        if parking_count is not None and (type(parking_count) is not int or not 1 <= parking_count <= 5): raise ValueError('تعداد پارکینگ معتبر نیست.')
        if type(self.constraints['parking_non_tandem_required']) is not bool or type(self.constraints['parking_dedicated_required']) is not bool: raise ValueError('نوع پارکینگ معتبر نیست.')
        if self.constraints['furnishing'] not in ('any', 'furnished', 'unfurnished'): raise ValueError('وضعیت مبله معتبر نیست.')
        if self.constraints['building_density'] not in ('any', 'single_unit', 'low_density'): raise ValueError('تراکم ساختمان معتبر نیست.')
        evidence_lists = {
            'hvac_required': {'package_heating','radiator','split_ac','water_cooler','fan_coil','chiller'},
            'security_required': {'security_24h','cctv','concierge','lobby'},
            'transport_required': {'near_metro','near_brt','good_road_access'},
            'view_privacy_required': {'open_view','privacy','mountain_view','city_view'},
            'accessibility_required': {'step_free','wheelchair','ramp','elevator_from_parking'},
        }
        for key, allowed in evidence_lists.items():
            value = self.constraints[key]
            if not isinstance(value, list) or not set(value) <= allowed: raise ValueError('شرط مبتنی بر متن آگهی معتبر نیست.')
        if set(self.evidence_preferences) != set(EVIDENCE_FEATURES) or any(value not in PRIORITIES for value in self.evidence_preferences.values()):
            raise ValueError('اولویت‌های مبتنی بر متن آگهی معتبر نیستند.')
        for key in ('max_deposit', 'max_rent'):
            value = self.constraints[key]
            if value is not None and (type(value) is not int or not 0 <= value <= 100_000_000_000):
                raise ValueError('سقف بودجه معتبر نیست.')
        if not isinstance(self.constraints['neighborhoods'], list) or any(not isinstance(x, str) or len(x) > 80 for x in self.constraints['neighborhoods']):
            raise ValueError('محله معتبر نیست.')
        if not isinstance(self.constraints['excluded_neighborhoods'],list) or any(not isinstance(x,str) or len(x)>80 for x in self.constraints['excluded_neighborhoods']):raise ValueError('محله حذف‌شده معتبر نیست.')
        if not isinstance(self.constraints['required_amenities'], list) or not set(self.constraints['required_amenities']) <= set(AMENITIES):
            raise ValueError('امکانات معتبر نیست.')
        if set(self.preferences) != {*FEATURES, 'commute', 'budget'} or any(x not in PRIORITIES for x in self.preferences.values()):
            raise ValueError('اولویت معتبر نیست.')
        if set(self.metadata) != {'manual', 'source'} or not isinstance(self.metadata['manual'], list) or not set(self.metadata['manual']) <= MANUAL_FIELDS or self.metadata['source'] not in ('prompt', 'filter', 'refinement', 'review', 'recovery'):
            raise ValueError('منبع تغییر معتبر نیست.')
        self.as_profile().__post_init__()
        for key in self.constraints['required_amenities']:
            if key in self.preferences and self.preferences[key] in ('low', 'ignored', 'medium'):
                raise ValueError('امکان ضروری باید اولویت مهم داشته باشد.')

    def to_dict(self):
        return deepcopy({k: getattr(self, k) for k in ('constraints', 'preferences', 'evidence_preferences', 'context', 'targets', 'metadata', 'logic')})

    def copy(self):
        return SearchIntent(**self.to_dict())

    @property
    def bedrooms_min(self):
        bed = self.constraints['bedrooms']
        value = bed['value']
        if bed['mode'] == 'max' or bed['mode'] == 'any': return 0
        return min(value) if isinstance(value, list) else value or 0
    @property
    def bedrooms_hard(self): return self.constraints['bedrooms']['mode'] != 'any'
    @property
    def deposit_target(self): return self.targets['deposit']
    @property
    def rent_target(self): return self.targets['rent']
    @property
    def budget_flexibility(self): return self.targets['flexibility']
    @property
    def budget_priority(self): return self.preferences['budget']
    @property
    def location_priority(self): return self.preferences['commute']
    @property
    def work_location(self): return self.context['workplace']
    @property
    def elevator_required(self): return 'elevator' in self.constraints['required_amenities']
    @property
    def rent_hard(self): return self.constraints['max_rent'] is not None and self.constraints['max_rent'] == self.rent_target
    @property
    def bedroom_label(self):
        bed = self.constraints['bedrooms']
        if bed['mode'] == 'allowed': return ' یا '.join(fa(v) for v in bed['value']) + ' خواب'
        if bed['mode'] == 'any': return 'فرقی ندارد'
        prefix = 'حداقل ' if bed['mode'] == 'min' else 'حداکثر ' if bed['mode'] == 'max' else ''
        return prefix + fa(bed['value']) + ' خواب'

    @property
    def area_label(self):
        area = self.constraints['area']
        if area['min'] is not None and area['max'] is not None: return f'{fa(area["min"])} تا {fa(area["max"])} متر'
        if area['min'] is not None: return f'حداقل {fa(area["min"])} متر'
        if area['max'] is not None: return f'حداکثر {fa(area["max"])} متر'
        return ''

    @property
    def floor_label(self):
        floor = self.constraints['floor']
        parts = []
        if floor['mode'] == 'allowed': parts.append('طبقه ' + ' یا '.join(fa(v) for v in floor['value']))
        elif floor['mode'] == 'exact': parts.append('طبقه ' + fa(floor['value']))
        elif floor['mode'] == 'min': parts.append('طبقه ' + fa(floor['value']) + ' به بالا')
        elif floor['mode'] == 'max': parts.append('حداکثر طبقه ' + fa(floor['value']))
        if 'ground' in floor['excluded']: parts.append('بدون همکف')
        if 'basement' in floor['excluded']: parts.append('بدون زیرزمین')
        return ' · '.join(parts)

    @property
    def structured_constraint_labels(self):
        labels = []
        from .location_registry import display_location
        labels.extend('به‌جز محله '+display_location(n) for n in self.constraints['excluded_neighborhoods'])
        if self.area_label: labels.append(self.area_label)
        if self.floor_label: labels.append(self.floor_label)
        if self.constraints['construction_year_min'] is not None:
            labels.append('ساخت ' + fa(self.constraints['construction_year_min']) + ' به بعد')
        if self.constraints['renovation_required']:
            labels.append('بازسازی‌شده ضروری')
        if self.constraints['pet_policy'] == 'allowed': labels.append('حیوان خانگی مجاز · نیازمند ذکر در آگهی')
        if self.constraints['parking_count_min'] is not None: labels.append('حداقل ' + fa(self.constraints['parking_count_min']) + ' پارکینگ')
        if self.constraints['parking_non_tandem_required']: labels.append('پارکینگ غیرمزاحم ضروری')
        if self.constraints['parking_dedicated_required']: labels.append('پارکینگ اختصاصی ضروری')
        if self.constraints['furnishing'] == 'furnished': labels.append('مبله ضروری')
        elif self.constraints['furnishing'] == 'unfurnished': labels.append('غیرمبله ضروری')
        labels.extend(EVIDENCE_FEATURE_LABELS[key] + ' ضروری' for key in self.constraints['hvac_required'])
        if self.constraints['building_density'] != 'any': labels.append(EVIDENCE_FEATURE_LABELS[self.constraints['building_density']] + ' ضروری')
        for group in ('security_required','transport_required','view_privacy_required','accessibility_required'):
            labels.extend(EVIDENCE_FEATURE_LABELS[key] + ' ضروری' for key in self.constraints[group])
        return labels

    @property
    def evidence_preference_labels(self):
        hard = required_evidence_tokens(self.constraints)
        return [EVIDENCE_FEATURE_LABELS[key] for key, priority in self.evidence_preferences.items() if priority in ('medium','high','very_high') and key not in hard]

    @property
    def evidence_preference_groups(self):
        hard = required_evidence_tokens(self.constraints)
        return [(EVIDENCE_FEATURE_LABELS[key], priority) for key, priority in self.evidence_preferences.items() if priority in ('medium','high','very_high') and key not in hard]

    @property
    def logic_labels(self):
        return compound_logic_labels(self)

    @property
    def desired_location(self):
        # Read-only projection: canonical neighborhoods + scope are stored once.
        return {'neighborhood': next(iter(self.constraints['neighborhoods']), None), 'mode': self.constraints['neighborhood_mode']}

    @property
    def residential_label(self):
        from .location_registry import display_location
        return '، '.join(display_location(n) for n in self.constraints['neighborhoods']) + {'exact':'','nearby':' و اطراف','preferred':' (ترجیحی)'}[self.constraints['neighborhood_mode']] if self.constraints['neighborhoods'] else 'همه محله‌ها'

    @property
    def summary_line(self):
        place = self.residential_label if self.constraints['neighborhoods'] else ('نزدیک محل کار' if self.work_location != 'none' and self.location_priority in ('high','very_high') else '')
        return self.bedroom_label + (' · ' + place if place else '')

    def as_profile(self):
        return IntentProfile(bedrooms_min=self.bedrooms_min, bedrooms_hard=self.bedrooms_hard, deposit_target=self.deposit_target, rent_target=self.rent_target, budget_flexibility=self.budget_flexibility, budget_priority=self.budget_priority, rent_hard=self.rent_hard, elevator_required=self.elevator_required, work_location=self.work_location, location_priority=self.location_priority, preferences={k: self.preferences[k] for k in FEATURES})

    @classmethod
    def from_profile(cls, profile, text='', legacy=False):
        intent = cls()
        intent.preferences.update(profile.preferences, commute=profile.location_priority, budget=profile.budget_priority)
        intent.context['workplace'] = profile.work_location
        intent.targets.update(deposit=profile.deposit_target, rent=profile.rent_target, flexibility=profile.budget_flexibility)
        if profile.bedrooms_min and profile.bedrooms_hard:
            mode = 'min' if legacy or re.search(r'حداقل|دو\s*یا\s*سه', normalize(text)) else 'exact'
            intent.constraints['bedrooms'] = {'mode': mode, 'value': profile.bedrooms_min}
        for field, target in [('max_deposit', profile.deposit_target), ('max_rent', profile.rent_target)]:
            intent.constraints[field] = int(target * (1 if field == 'max_rent' and profile.rent_hard else {'none': 1, 'medium': 1.2, 'flexible': 1.4}[profile.budget_flexibility])) if target is not None else None
        if profile.elevator_required:
            intent.constraints['required_amenities'] = ['elevator']
            intent.preferences['elevator'] = 'high'
        intent.__post_init__()
        return intent


def _legacy_merge_inference(current, parsed, text, neighborhoods=()):
    """Provider output is projected only onto mentioned, controlled fields."""
    result = current.copy()
    text = normalize(text)
    for key, pattern in ALIASES.items():
        if re.search(pattern, text) or (key == 'parking' and 'ماشین ندارم' in text):
            name = 'commute' if key == 'location' else key
            value = parsed.location_priority if key == 'location' else parsed.budget_priority if key == 'budget' else parsed.preferences[key]
            result.preferences[name] = value
            if key in AMENITIES:
                required = result.constraints['required_amenities']
                if value in ('ignored', 'low') and key in required:
                    required.remove(key)
                elif any(re.search(pattern, clause) and re.search(r'حتما|ضروری|الزامی|لازم\s*دارم', clause) for clause in re.split(r'[؛،,.!?؟]', text)) and value in ('high', 'very_high') and key not in required:
                    required.append(key)
                forget_manual(result, 'amenity:' + key)
    if re.search(r'(?:یک|دو|سه|چهار|[1-5])\s*(?:یا سه\s*)?خواب|(?:خواب\w*|اتاق(?:\s*خواب)?).*(?:فرقی ندار|مهم نیست|بی\s*خیال)', text):
        # Bedroom removal phrases such as «دوخوابه بودن دیگه مهم نیست» must
        # clear the constraint before validation.  The legacy DTO reports
        # bedrooms_min=0 here, so treating the leading «دوخوابه» as exact would
        # construct an invalid exact-0 SearchIntent.
        any_bed = bool(re.search(r'(?:خواب\w*|اتاق(?:\s*خواب)?).*(?:فرقی ندار|مهم نیست|بی\s*خیال)|بی\s*خیال.*(?:خواب|اتاق)', text))
        value = parsed.bedrooms_min
        if re.search(r'چهار\s*خواب|4\s*خواب', text): value = 4
        result.constraints['bedrooms'] = {'mode': 'any', 'value': None} if any_bed else {'mode': 'min' if 'حداقل' in text or 'دو یا سه' in text else 'exact', 'value': value}
        forget_manual(result, 'bedrooms')
    from .language import extract_money
    for word, target, cap in [('ودیعه', 'deposit', 'max_deposit'), ('اجاره', 'rent', 'max_rent')]:
        explicit_value = extract_money(text, (word,))
        if explicit_value is not None:
            value = explicit_value
            result.targets[target] = value
            hard = bool(re.search(r'بیشتر.*نشه|سقف|حداکثر|تا\s*\d+', text))
            result.constraints[cap] = int(value * (1 if hard else {'none': 1, 'medium': 1.2, 'flexible': 1.4}[result.budget_flexibility])) if value is not None else None
            forget_manual(result, cap)
        if word in text and re.search(r'محدودیت.*ندار|سقف.*ندار', text):
            result.constraints[cap] = None
            forget_manual(result, cap)
    if 'بودجه' in text and 'بالاتر' in text:
        result.targets['flexibility'] = parsed.budget_flexibility
        for target, cap in [('deposit', 'max_deposit'), ('rent', 'max_rent')]:
            if result.targets[target] is not None:
                result.constraints[cap] = int(result.targets[target] * 1.4)
                forget_manual(result, cap)
    if ('ونک' in text or 'ولیعصر' in text) and re.search(r'محل\s*کار|کار\s*می|نزدیک|حوالی|اطراف', text):
        result.context['workplace'] = parsed.work_location
    if 'محله' in text or re.search(r'فقط|محدوده', text):
        named = [name for name in neighborhoods if normalize(name) in text]
        if named:
            result.constraints['neighborhoods'] = named
            forget_manual(result, 'neighborhoods')
        elif re.search(r'محله.*(?:فرقی ندارد|مهم نیست|محدودیت ندارد)', text):
            result.constraints['neighborhoods'] = []
            forget_manual(result, 'neighborhoods')
    result.metadata['source'] = 'refinement'
    result.__post_init__()
    return result


def forget_manual(intent, key):
    intent.metadata['manual'] = [x for x in intent.metadata['manual'] if x != key]


def filter_initial(intent):
    bed = intent.constraints['bedrooms']
    return {'bedrooms': '' if bed['mode'] == 'any' else ('allowed' + ','.join(map(str,bed['value'])) if bed['mode'] == 'allowed' else ('min' if bed['mode'] == 'min' else 'max') + str(bed['value']) if bed['mode'] in ('min','max') else str(bed['value'])), 'neighborhood': next(iter(intent.constraints['neighborhoods']), ''), 'neighborhood_scope': intent.constraints['neighborhood_mode'], 'max_deposit': intent.constraints['max_deposit'] // 1_000_000 if intent.constraints['max_deposit'] is not None else None, 'max_rent': intent.constraints['max_rent'] // 1_000_000 if intent.constraints['max_rent'] is not None else None, 'amenities': intent.constraints['required_amenities']}


def apply_filters(current, values):
    result = current.copy()
    initial = filter_initial(current)
    manual = set(result.metadata['manual'])
    for key in ('bedrooms', 'neighborhood', 'max_deposit', 'max_rent', 'amenities'):
        if values[key] == initial[key]: continue
        if key == 'bedrooms':
            value = values[key]
            result.constraints[key] = {'mode': 'any', 'value': None} if not value else {'mode': 'allowed', 'value': [int(v) for v in value[7:].split(',')]} if value.startswith('allowed') else {'mode': 'min' if value.startswith('min') else 'max' if value.startswith('max') else 'exact', 'value': int(value.removeprefix('min').removeprefix('max'))}
            manual.add(key) if value else manual.discard(key)
        elif key == 'neighborhood':
            result.constraints['neighborhoods'] = [values[key]] if values[key] else []
            manual.add('neighborhoods') if values[key] else manual.discard('neighborhoods')
        elif key == 'amenities':
            for amenity in AMENITIES:
                if (amenity in values[key]) != (amenity in initial[key]):
                    marker = 'amenity:' + amenity
                    if amenity in values[key]:
                        manual.add(marker)
                        if amenity in result.preferences:
                            result.preferences[amenity] = max(result.preferences[amenity], 'high', key=lambda p: PRIORITIES[p])
                    else:
                        manual.discard(marker)
                        if amenity in result.preferences: result.preferences[amenity] = 'low'
            result.constraints['required_amenities'] = list(values[key])
        else:
            result.constraints[key] = values[key] * 1_000_000 if values[key] is not None else None
            if values[key] is not None:
                result.targets['deposit' if key == 'max_deposit' else 'rent'] = result.constraints[key]
                manual.add(key)
            else: manual.discard(key)
    scope = values.get('neighborhood_scope') or ('exact' if values['neighborhood'] != initial['neighborhood'] else initial['neighborhood_scope'])
    if scope != initial['neighborhood_scope']:
        result.constraints['neighborhood_mode'] = scope
        if result.constraints['neighborhoods']: manual.add('neighborhoods')
    if not result.constraints['neighborhoods']: result.constraints['neighborhood_mode'] = 'exact'
    result.metadata = {'manual': sorted(manual), 'source': 'filter'}
    from .compound import clear_related_logic
    paths={group+'.'+key for group in ('constraints','preferences','context','targets') for key in getattr(current,group) if getattr(current,group)[key]!=getattr(result,group)[key]}
    clear_related_logic(result,paths)
    result.__post_init__()
    return result


def remove_constraint(current, key, source='filter'):
    result = current.copy()
    if key == 'all_hard':
        defaults = SearchIntent()
        result.constraints = defaults.constraints
        result.logic = defaults.logic
        result.metadata['manual'] = []
    elif key == 'bedrooms': result.constraints[key] = {'mode': 'any', 'value': None}
    elif key in ('max_deposit', 'max_rent'): result.constraints[key] = None
    elif key == 'area': result.constraints[key] = {'min': None, 'max': None}
    elif key == 'floor': result.constraints[key] = {'mode': 'any', 'value': None, 'excluded': []}
    elif key == 'construction_year_min': result.constraints[key] = None
    elif key == 'renovation_required': result.constraints[key] = False
    elif key in ('full_deposit','convertible'):result.constraints[key]=False
    elif key == 'excluded_neighborhoods':result.constraints[key]=[]
    elif key.startswith('preference:') and key[11:] in result.preferences:result.preferences[key[11:]]='ignored'
    elif key.startswith('evidence:') and key[9:] in result.evidence_preferences:result.evidence_preferences[key[9:]]='ignored'
    elif key == 'workplace':result.context['workplace']='none'
    elif key == 'logic':result.logic=SearchIntent().logic
    elif key in ('pet_policy','furnishing','building_density'):
        result.constraints[key] = SearchIntent().constraints[key]
    elif key in ('parking_count_min',): result.constraints[key] = None
    elif key in ('parking_non_tandem_required','parking_dedicated_required'): result.constraints[key] = False
    elif key in ('hvac_required','security_required','transport_required','view_privacy_required','accessibility_required'): result.constraints[key] = []
    elif key == 'neighborhoods':
        result.constraints[key] = []
        result.constraints['neighborhood_mode'] = 'exact'
        result.constraints['excluded_neighborhoods'] = []
    elif key.startswith('amenity:'):
        result.constraints['required_amenities'] = [x for x in result.constraints['required_amenities'] if x != key[8:]]
    else: raise ValueError('محدودیت معتبر نیست.')
    forget_manual(result, key)
    result.metadata['source'] = source
    from .compound import clear_related_logic
    paths={group+'.'+field for group in ('constraints','preferences','context','evidence_preferences','targets') for field in getattr(current,group) if getattr(current,group)[field]!=getattr(result,group)[field]}
    if key.startswith('amenity:'):paths.add('preferences.'+key[8:])
    clear_related_logic(result,paths)
    result.__post_init__()
    return result


def chips(intent):
    labels = {
        'bedrooms': intent.bedroom_label,
        'max_deposit': 'ودیعه تا ' + money(intent.constraints['max_deposit']),
        'max_rent': 'اجاره تا ' + money(intent.constraints['max_rent']),
        'neighborhoods': intent.residential_label,
        'area': intent.area_label or 'متراژ بدون محدودیت',
        'floor': intent.floor_label or 'طبقه بدون محدودیت',
        'construction_year_min': ('ساخت ' + fa(intent.constraints['construction_year_min']) + ' به بعد') if intent.constraints['construction_year_min'] is not None else 'سال ساخت بدون محدودیت',
        'renovation_required': 'بازسازی‌شده ضروری',
        **{'amenity:' + key: name + ' ضروری' for key, name in AMENITIES.items()},
    }
    return [{'key': k, 'label': labels[k]} for k in intent.metadata['manual'] if k in labels]


def active_filter_chips(intent):
    """Count user-level obligations/preferences, not internal keys. Logic is one group."""
    c=intent.constraints; rows=[]
    def add(key,label):rows.append({'key':key,'label':label})
    if c['neighborhoods']:add('neighborhoods',intent.residential_label)
    elif c['excluded_neighborhoods']:add('excluded_neighborhoods','به‌جز '+ '، '.join(c['excluded_neighborhoods']))
    for key,label in [('max_rent','اجاره'),('max_deposit','ودیعه')]:
        if c[key] is not None:add(key,label+' تا '+money(c[key]))
    for key,label in [('full_deposit','رهن کامل'),('convertible','قابل تبدیل')]:
        if c[key]:add(key,label)
    if c['bedrooms']['mode']!='any':add('bedrooms',intent.bedroom_label)
    if any(v is not None for v in c['area'].values()):add('area',intent.area_label)
    if c['floor']['mode']!='any' or c['floor']['excluded']:add('floor',intent.floor_label)
    if c['construction_year_min'] is not None:add('construction_year_min','ساخت '+fa(c['construction_year_min'])+' به بعد')
    if c['renovation_required']:add('renovation_required','بازسازی‌شده')
    for key in c['required_amenities']:add('amenity:'+key,AMENITIES[key]+' ضروری')
    if c['parking_count_min'] is not None:add('parking_count_min','پارکینگ '+fa(c['parking_count_min'])+'+')
    for key,label in [('parking_non_tandem_required','غیرمزاحم'),('parking_dedicated_required','پارکینگ اختصاصی')]:
        if c[key]:add(key,label)
    if c['pet_policy']!='any':add('pet_policy','حیوان خانگی مجاز')
    for key,label in [('furnishing','مبله' if c['furnishing']=='furnished' else 'غیرمبله'),('building_density','تک‌واحدی' if c['building_density']=='single_unit' else 'کم‌واحد')]:
        if c[key]!='any':add(key,label)
    FEATURE_LABELS=EVIDENCE_FEATURE_LABELS
    for key in ('hvac_required','security_required','transport_required','view_privacy_required','accessibility_required'):
        if c[key]:add(key,'، '.join(FEATURE_LABELS[x] for x in c[key]))
    if intent.work_location!='none':add('workplace','محل کار: '+workplace_label(intent.work_location))
    for key,value in intent.preferences.items():
        if key=='budget' or key in c['required_amenities'] or value not in ('medium','high','very_high'):continue
        if key=='commute' and intent.work_location=='none':continue
        add('preference:'+key,({'commute':'رفت‌وآمد',**FEATURES}[key])+': '+LABELS[value])
    from .evidence_features import required_evidence_tokens
    hard=required_evidence_tokens(c)
    for key,value in intent.evidence_preferences.items():
        if value in ('medium','high','very_high') and key not in hard:add('evidence:'+key,FEATURE_LABELS[key]+': '+LABELS[value])
    count=sum(len(v) for v in intent.logic.values())
    if count:add('logic',fa(count)+' قانون انتخاب')
    return rows


def changes(before, after):
    rows = [r for r in intent_changes(before.as_profile(), after.as_profile()) if r.get('field') not in ('bedrooms_min', 'elevator_required', 'rent_hard')]
    for row in rows:
        key = row.get('field')
        if key in ('deposit_target', 'rent_target'): row['before'], row['after'] = money(row['before']), money(row['after'])
        if key == 'work_location': row['before'], row['after'] = [workplace_label(v) for v in (row['before'], row['after'])]
    for key, label in [('bedrooms', 'اتاق خواب'), ('max_deposit', 'سقف ودیعه'), ('max_rent', 'سقف اجاره'), ('neighborhoods', 'محله'), ('required_amenities', 'امکانات ضروری'), ('area', 'متراژ'), ('floor', 'طبقه'), ('construction_year_min', 'سال ساخت'), ('renovation_required', 'بازسازی'), ('pet_policy','حیوان خانگی'), ('parking_count_min','تعداد پارکینگ'), ('parking_non_tandem_required','پارکینگ غیرمزاحم'), ('parking_dedicated_required','پارکینگ اختصاصی'), ('furnishing','مبله بودن'), ('hvac_required','گرمایش و سرمایش'), ('building_density','تراکم ساختمان'), ('security_required','امنیت ساختمان'), ('transport_required','دسترسی حمل‌ونقل'), ('view_privacy_required','دید و حریم خصوصی'), ('accessibility_required','دسترسی‌پذیری')]:
        if before.constraints[key] == after.constraints[key]: continue
        if key == 'required_amenities':
            for amenity in AMENITIES:
                old, new = amenity in before.constraints[key], amenity in after.constraints[key]
                if old != new: rows.append({'label': AMENITIES[amenity], 'before': 'ضروری' if old else 'اختیاری', 'after': 'ضروری' if new else 'اختیاری'})
            continue
        def display(intent):
            value = intent.constraints[key]
            if key == 'bedrooms': return intent.bedroom_label
            if key.startswith('max_'): return money(value) if value is not None else 'بدون سقف'
            if key == 'neighborhoods': return '، '.join(value) or 'همه محله‌ها'
            if key == 'area': return intent.area_label or 'بدون محدودیت'
            if key == 'floor': return intent.floor_label or 'بدون محدودیت'
            if key == 'construction_year_min': return ('ساخت ' + fa(value) + ' به بعد') if value is not None else 'بدون محدودیت'
            if key == 'renovation_required': return 'ضروری' if value else 'اختیاری'
            if key == 'pet_policy': return 'مجاز و ذکرشده در آگهی' if value == 'allowed' else 'بدون الزام'
            if key == 'parking_count_min': return ('حداقل ' + fa(value)) if value is not None else 'بدون الزام'
            if key in ('parking_non_tandem_required','parking_dedicated_required'): return 'ضروری' if value else 'اختیاری'
            if key == 'furnishing': return {'any':'بدون الزام','furnished':'مبله','unfurnished':'غیرمبله'}[value]
            if key == 'building_density': return {'any':'بدون الزام','single_unit':'تک‌واحدی','low_density':'کم‌واحد'}[value]
            if key in ('hvac_required','security_required','transport_required','view_privacy_required','accessibility_required'):
                return '، '.join(EVIDENCE_FEATURE_LABELS[v] for v in value) or 'بدون الزام'
            return '، '.join(AMENITIES[v] for v in value) or 'بدون الزام'
        rows.append({'label': label, 'before': display(before), 'after': display(after)})
    for key in EVIDENCE_FEATURES:
        if before.evidence_preferences[key] != after.evidence_preferences[key]:
            rows.append({'label': EVIDENCE_FEATURE_LABELS[key], 'before': LABELS[before.evidence_preferences[key]], 'after': LABELS[after.evidence_preferences[key]]})
    # Compact display: requirement changes subsume an amenity's automatic priority raise.
    requirement_changes = {AMENITIES[k] for k in AMENITIES if (k in before.constraints['required_amenities']) != (k in after.constraints['required_amenities'])}
    target_changed = before.targets['rent'] != after.targets['rent'] or before.targets['deposit'] != after.targets['deposit']
    compact = []
    for row in rows:
        if row['label'] in requirement_changes and row.get('after') in LABELS.values(): continue
        if target_changed and row['label'] == 'اهمیت بودجه': continue
        target = {'rent_target':'rent','deposit_target':'deposit'}.get(row.get('field'))
        if target:
            cap = 'max_' + target
            if after.constraints[cap] == after.targets[target] and before.constraints[cap] != after.constraints[cap]: continue
        compact.append(row)
    rows = compact
    if before.constraints['neighborhood_mode'] != after.constraints['neighborhood_mode']:
        rows.append({'label': 'محدوده محله', 'before': before.residential_label, 'after': after.residential_label})
    if before.logic != after.logic:
        old = '؛ '.join(before.logic_labels) or 'بدون منطق ترکیبی'
        new = '؛ '.join(after.logic_labels) or 'بدون منطق ترکیبی'
        rows.append({'label': 'منطق ترکیبی', 'before': old, 'after': new})
    return rows


def recovery_options(intent, listings, ranker):
    """Offer only relaxations that actually return candidates, with exact counts."""
    options = []
    bed = intent.constraints['bedrooms']
    if bed['mode'] != 'any' and intent.bedrooms_min >= 3:
        relaxed = intent.copy()
        relaxed.constraints['bedrooms'] = {'mode':'allowed','value': sorted(set([2,*bed['value']])) if bed['mode']=='allowed' else [2,bed['value']]}
        count = len(ranker(listings,relaxed))
        if count: options.append({'action':'accept:bedrooms','label':'۲ خواب را هم قبول کن','count':count,'value':relaxed.constraints['bedrooms']})
    for key, label in [('neighborhoods', 'پاک کردن فیلتر محله'), *[('amenity:' + k, 'حذف الزام ' + AMENITIES[k]) for k in intent.constraints['required_amenities']], ('bedrooms', 'آزاد کردن تعداد اتاق')]:
        if key == 'neighborhoods' and not intent.constraints[key]: continue
        if key == 'bedrooms' and intent.constraints[key]['mode'] == 'any': continue
        relaxed = remove_constraint(intent, key, 'recovery')
        count = len(ranker(listings, relaxed))
        if count: options.append({'action': key, 'label': label, 'count': count})
    for key, label in [('area', 'آزاد کردن متراژ'), ('floor', 'آزاد کردن طبقه'), ('construction_year_min', 'آزاد کردن سال ساخت'), ('renovation_required', 'حذف الزام بازسازی')]:
        active = (key == 'area' and any(v is not None for v in intent.constraints[key].values())) or (key == 'floor' and (intent.constraints[key]['mode'] != 'any' or intent.constraints[key]['excluded'])) or (key == 'construction_year_min' and intent.constraints[key] is not None) or (key == 'renovation_required' and intent.constraints[key])
        if not active: continue
        relaxed = remove_constraint(intent, key, 'recovery')
        count = len(ranker(listings, relaxed))
        if count: options.append({'action': key, 'label': label, 'count': count})
    evidence_recoveries = [
        ('pet_policy','حذف الزام مجاز بودن حیوان خانگی'),
        ('parking_count_min','آزاد کردن تعداد پارکینگ'),
        ('parking_non_tandem_required','حذف الزام پارکینگ غیرمزاحم'),
        ('parking_dedicated_required','حذف الزام پارکینگ اختصاصی'),
        ('furnishing','آزاد کردن شرط مبله بودن'),
        ('hvac_required','آزاد کردن شرط گرمایش/سرمایش'),
        ('building_density','آزاد کردن شرط تراکم ساختمان'),
        ('security_required','آزاد کردن الزام امنیت ساختمان'),
        ('transport_required','آزاد کردن الزام دسترسی'),
        ('view_privacy_required','آزاد کردن شرط دید/حریم خصوصی'),
        ('accessibility_required','آزاد کردن شرط دسترسی‌پذیری'),
    ]
    defaults = SearchIntent().constraints
    for key, label in evidence_recoveries:
        if intent.constraints[key] == defaults[key]:
            continue
        relaxed = remove_constraint(intent, key, 'recovery')
        count = len(ranker(listings, relaxed))
        if count:
            options.append({'action': key, 'label': label, 'count': count})

    for key, field_name in [('max_rent', 'monthly_rent'), ('max_deposit', 'deposit')]:
        if intent.constraints[key] is None: continue
        relaxed = remove_constraint(intent, key, 'recovery')
        candidates = ranker(listings, relaxed)
        if candidates:
            value = min(getattr(r.listing, field_name) for r in candidates)
            options.append({'action': 'raise:' + key, 'label': 'افزایش ' + ('اجاره' if key == 'max_rent' else 'ودیعه') + ' تا ' + money(value), 'value': value, 'count': sum(getattr(r.listing, field_name) <= value for r in candidates)})
    if not options:
        count = len(ranker(listings, remove_constraint(intent, 'all_hard', 'recovery')))
        if count: options.append({'action': 'all_hard', 'label': 'انعطاف همه محدودیت‌ها', 'count': count})
    return options[:3]


def merge_inference(current, parsed, text, neighborhoods=()):
    from .ai import get_ai_service
    return get_ai_service().parse_intent_patch(text,current,neighborhoods).merge(current)
