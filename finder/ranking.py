"""Deterministic, inspectable ranking. All amounts are toman, not rial."""
from dataclasses import dataclass, field
from .intent import PRIORITIES, FEATURES, LABELS
from .location_registry import display_location, location_key
from .calendar import new_build_min_year
from .locations import residential_fit, location_matches, workplace_distance, point_distance, NEIGHBORHOOD_ANCHORS
from .evidence_features import (
    YES, NO, EVIDENCE_FEATURE_LABELS, extract_listing_evidence,
    evidence_feature_state, evidence_requirement_matches, required_evidence_tokens,
)
from .compound import (
    amenity_requirement_matches, budget_cap_matches, conditional_eligibility, area_min_matches,
    effective_priorities, fit_overrides, conditional_notes, apply_fallback_rule,
    fallback_label, effective_evidence_constraints,
)

FA = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')


def fa(value):
    return 'تعیین نشده' if value is None else str(value).translate(FA)


def money(value):
    if value is None:
        return 'تعیین نشده'
    return fa(f'{value / 1_000_000:g}') + ' میلیون'


def distance(listing, intent):
    if listing.data_source == 'real':
        value = workplace_distance(listing, intent.work_location)
        return round(value, 1) if value is not None else None
    return listing.distances.get(intent.work_location, listing.distance_to_work_km)


def _structured_constraint_match(listing, constraints, intent=None):
    if constraints.get('full_deposit') and listing.monthly_rent != 0: return False
    if constraints.get('convertible') and (listing.alternative_deposit is None or listing.alternative_rent is None): return False
    area = constraints['area']
    if area['min'] is not None and listing.area_m2 < area['min']:
        if intent is None or not area_min_matches(listing, intent): return False
    if area['max'] is not None and listing.area_m2 > area['max']: return False

    floor = constraints['floor']
    if floor['mode'] != 'any' or floor['excluded']:
        if listing.floor is None: return False
        if floor['mode'] == 'allowed' and listing.floor not in floor['value']: return False
        if floor['mode'] == 'exact' and listing.floor != floor['value']: return False
        if floor['mode'] == 'min' and listing.floor < floor['value']: return False
        if floor['mode'] == 'max' and listing.floor > floor['value']: return False
        if 'ground' in floor['excluded'] and listing.floor == 0: return False
        if 'basement' in floor['excluded'] and listing.floor < 0: return False

    if constraints['construction_year_min'] is not None:
        if listing.construction_year is None or listing.construction_year < constraints['construction_year_min']: return False
    if constraints['renovation_required'] and not (listing.renovated is True or listing.renovation_claim is True):
        return False
    return True


def eligible(listing, intent):
    if hasattr(intent, 'constraints'):
        c = intent.constraints
        bed = c['bedrooms']
        bedroom_ok = bed['mode'] == 'any' or (
            listing.bedrooms in bed['value'] if bed['mode'] == 'allowed' else
            listing.bedrooms == bed['value'] if bed['mode'] == 'exact' else
            listing.bedrooms >= bed['value'] if bed['mode'] == 'min' else
            listing.bedrooms <= bed['value']
        )
        return (
            bedroom_ok
            and _structured_constraint_match(listing, c, intent)
            and evidence_requirement_matches(listing, effective_evidence_constraints(listing, intent))
            and location_matches(listing, intent)
            and amenity_requirement_matches(listing, intent)
            and budget_cap_matches(listing, intent)
            and conditional_eligibility(listing, intent)
        )
    if intent.bedrooms_hard and listing.bedrooms < intent.bedrooms_min:
        return False
    if intent.elevator_required and not listing.elevator:
        return False
    limits = {'none': 1, 'medium': 1.2, 'flexible': 1.4}
    if intent.deposit_target is not None and listing.deposit > intent.deposit_target * limits[intent.budget_flexibility]:
        return False
    if intent.rent_target is not None and listing.monthly_rent > intent.rent_target * (1 if intent.rent_hard else limits[intent.budget_flexibility]):
        return False
    return True


@dataclass
class RankedListing:
    listing: object
    score: float
    breakdown: list
    reasons: list
    tradeoffs: list
    distance: float | None
    rank: int = 0
    promotion: str = ''
    image: str | None = None
    selected: bool = False
    label: str = ''
    rank_change: str = ''
    saved: bool = False
    fallback_stage: int = 0
    fallback_notes: list = field(default_factory=list)


def score_listing(listing, intent):
    costs = [(listing.deposit, intent.deposit_target), (listing.monthly_rent, intent.rent_target)]
    budget_fits = [max(0, 1 - max(0, actual / target - 1) * 3.5) if target else float(actual == 0) for actual, target in costs if target is not None]
    commute_distance = distance(listing, intent)
    fits = {'budget': sum(budget_fits) / len(budget_fits) if budget_fits else 0.5,
            'location': max(0, 1 - commute_distance / 8) if commute_distance is not None else None,
            'area': min(listing.area_m2 / (100 if intent.bedrooms_min >= 2 else 65), 1),
            'natural_light': listing.natural_light, 'quietness': listing.quietness,
            'building_age': max(0, min(1, (listing.construction_year - 1385) / 20)) if listing.construction_year is not None else None,
            **{key: float(getattr(listing, key)) if getattr(listing,key) is not None else None for key in ('parking', 'elevator', 'storage')}}
    if hasattr(intent, 'logic'):
        fits = fit_overrides(listing, intent, fits)
        effective_base, effective_evidence = effective_priorities(listing, intent)
    else:
        effective_base, effective_evidence = intent.preferences, getattr(intent, 'evidence_preferences', {})
    weights = {'budget': 4 * PRIORITIES[effective_base.get('budget', intent.budget_priority)] / 3 if budget_fits else 0, 'location': PRIORITIES[effective_base.get('commute', intent.location_priority)] if intent.work_location != 'none' else 0, **{key: PRIORITIES[effective_base[key]] for key in FEATURES}}
    # Reuse the location dimension, combining residential proximity and commute when both are explicit.
    residential = hasattr(intent, 'constraints') and bool(intent.constraints['neighborhoods'])
    if residential:
        commute_weight = weights['location']
        residential_weight = PRIORITIES['high']
        fits['location'] = ((fits['location'] if fits['location'] is not None else .5) * commute_weight + residential_fit(listing,intent) * residential_weight) / (commute_weight + residential_weight)
        weights['location'] = commute_weight + residential_weight
    breakdown = [{'key': key, 'label': {'budget': 'بودجه', 'location': 'محدوده خانه و رفت‌وآمد' if residential else 'نزدیکی به محل کار', **FEATURES}[key], 'fit': round(value, 3) if value is not None else None, 'weight': weights[key], 'points': round((value if value is not None else 0 if key == 'building_age' else .5) * weights[key], 3)} for key, value in fits.items()]
    # v0.9-C soft evidence preferences: confirmed seller/ad wording can improve
    # ranking; UNKNOWN receives no bonus and is not converted into a false fact.
    listing_evidence = extract_listing_evidence(listing)
    if hasattr(intent, 'evidence_preferences'):
        hard_evidence_tokens = required_evidence_tokens(intent.constraints) if hasattr(intent, 'constraints') else set()
        for key, priority in effective_evidence.items():
            if priority in ('ignored', 'low') or key in hard_evidence_tokens:
                continue
            state = evidence_feature_state(listing_evidence, key)
            weight = PRIORITIES[priority] * 0.8
            breakdown.append({
                'key': 'evidence:' + key,
                'label': EVIDENCE_FEATURE_LABELS[key],
                'fit': 1 if state == YES else 0 if state == NO else None,
                'weight': weight,
                'points': round(weight if state == YES else 0, 3),
                'evidence_state': state,
            })
    # Subjective/conflicting claims reduce trust independently of preference weights.
    penalty = 0.6 * len(listing.data_conflicts) + (0.35 if not listing.evidence else 0)
    breakdown.append({'key': 'penalty', 'label': 'کسر امتیاز ابهام آگهی', 'fit': None, 'weight': None, 'points': -penalty})
    reasons, tradeoffs = explanations(listing, intent)
    return RankedListing(listing, round(sum(row['points'] for row in breakdown), 6), breakdown, reasons, tradeoffs, distance(listing, intent))


def explanations(listing, intent):
    reasons, tradeoffs = [], []
    effective_base = intent.preferences
    if hasattr(intent, 'logic'):
        effective_base, _ = effective_priorities(listing, intent)
        logic_reasons, logic_tradeoffs = conditional_notes(listing, intent)
        reasons.extend(logic_reasons)
        tradeoffs.extend(logic_tradeoffs)
    if hasattr(intent, 'constraints') and intent.constraints['neighborhoods']:
        target = display_location(intent.desired_location['neighborhood'])
        if any(location_key(listing.neighborhood)==location_key(n) for n in intent.constraints['neighborhoods']): reasons.append('داخل محله ' + display_location(listing.neighborhood))
        else:
            nearby_distance = point_distance(listing, NEIGHBORHOOD_ANCHORS.get(target)) if listing.data_source == 'real' else None
            reasons.append(f'حدود {fa(f"{nearby_distance:.1f}")} کیلومتر فاصله مستقیم تا محدوده {target}' if nearby_distance is not None else 'در محدوده نزدیک به ' + target + (' (همجواری تنظیم‌شده)' if listing.data_source == 'real' else ' (همجواری نمایشی)'))
    if hasattr(intent, 'constraints'):
        area = intent.constraints['area']
        if area['min'] is not None or area['max'] is not None:
            reasons.append(f'{fa(listing.area_m2)} متر؛ در محدوده متراژ درخواستی')
        floor = intent.constraints['floor']
        if floor['mode'] != 'any' or floor['excluded']:
            reasons.append('طبقه ' + fa(listing.floor) + ' با شرط طبقه سازگار است')
        if intent.constraints['construction_year_min'] is not None and listing.construction_year is not None:
            reasons.append('ساخت ' + fa(listing.construction_year) + '؛ مطابق محدودیت سال ساخت')
        if intent.constraints['renovation_required']:
            if listing.renovated is True:
                reasons.append('بازسازی‌شده است')
            elif listing.renovation_claim is True:
                reasons.append('متن آگهی به بازسازی اشاره می‌کند')
    if hasattr(intent, 'constraints'):
        evidence = extract_listing_evidence(listing)
        hard_labels = []
        c = intent.constraints
        if c.get('pet_policy') == 'allowed': hard_labels.append('حیوان خانگی مجاز')
        if c.get('parking_count_min') is not None: hard_labels.append('حداقل ' + fa(c['parking_count_min']) + ' پارکینگ')
        if c.get('parking_non_tandem_required'): hard_labels.append('پارکینگ غیرمزاحم')
        if c.get('parking_dedicated_required'): hard_labels.append('پارکینگ اختصاصی')
        if c.get('furnishing') == 'furnished': hard_labels.append('مبله')
        elif c.get('furnishing') == 'unfurnished': hard_labels.append('غیرمبله')
        hard_labels.extend(EVIDENCE_FEATURE_LABELS[key] for key in c.get('hvac_required', ()))
        if c.get('building_density', 'any') != 'any': hard_labels.append(EVIDENCE_FEATURE_LABELS[c['building_density']])
        for group in ('security_required','transport_required','view_privacy_required','accessibility_required'):
            hard_labels.extend(EVIDENCE_FEATURE_LABELS[key] for key in c.get(group, ()))
        if hard_labels:
            reasons.append('متن آگهی این شرط را ذکر می‌کند: ' + '، '.join(hard_labels[:2]))

        if hasattr(intent, 'evidence_preferences'):
            hard_evidence_tokens = required_evidence_tokens(c)
            for key, priority in intent.evidence_preferences.items():
                if priority not in ('high','very_high','medium') or key in hard_evidence_tokens:
                    continue
                state = evidence_feature_state(evidence, key)
                label = EVIDENCE_FEATURE_LABELS[key]
                if state == YES:
                    reasons.append('در متن آگهی «' + label + '» ذکر شده')
                elif priority in ('high','very_high'):
                    tradeoffs.append(('آگهی این مورد را رد می‌کند: ' if state == NO else 'آگهی درباره این مورد اطلاعاتی نداده: ') + label)
                if len(reasons) >= 4 and len(tradeoffs) >= 2:
                    break
    if intent.work_location != 'none' and intent.location_priority not in ('ignored', 'low') and distance(listing,intent) is None:
        tradeoffs.append('مختصات آگهی مشخص نیست؛ فاصله تا محل کار قابل محاسبه نیست')
    if intent.work_location != 'none' and intent.location_priority not in ('ignored', 'low') and distance(listing,intent) is not None:
        if distance(listing, intent) <= 2:
            reasons.append(f'حدود {fa(f"{distance(listing, intent):g}")} کیلومتر تا محل کار')
        else:
            tradeoffs.append(f'{fa(f"{distance(listing, intent):g}")} کیلومتر تا محل کار')
    if effective_base['natural_light'] in ('high', 'very_high'):
        light_evidence = [e['text'] for e in listing.evidence if e.get('factor') == 'natural_light']
        if light_evidence and listing.natural_light is not None and listing.natural_light >= 0.75:
            reasons.append('متن آگهی: «' + light_evidence[0] + '»')
        else:
            tradeoffs.append('شواهد روشنی درباره نورگیری نداریم')
    for key in ('parking', 'elevator', 'storage'):
        if effective_base[key] not in ('ignored', 'low'):
            if getattr(listing,key) is None:
                tradeoffs.append('اطلاعات ' + FEATURES[key] + ' مشخص نیست')
                continue
            (reasons if getattr(listing, key) else tradeoffs).append(FEATURES[key] + (' دارد' if getattr(listing, key) else ' ندارد'))
    if effective_base['quietness'] in ('high', 'very_high'):
        if listing.quietness is not None and listing.quietness >= 0.8 and any(e.get('factor') == 'quietness' for e in listing.evidence):
            reasons.append('متن آگهی: «' + next(e['text'] for e in listing.evidence if e.get('factor') == 'quietness') + '»')
        else:
            tradeoffs.append('آرامش محله نیاز به بررسی حضوری دارد')
    if effective_base['building_age'] in ('high', 'very_high') and listing.construction_year is not None:
        is_new = listing.construction_year >= new_build_min_year()
        (reasons if is_new else tradeoffs).append('ساختمان نوساز است؛ حداکثر ۳ سال' if is_new else 'ساختمان قدیمی‌تر از ترجیح شماست')
    targets = [(listing.deposit, intent.deposit_target, 'ودیعه'), (listing.monthly_rent, intent.rent_target, 'اجاره')]
    for actual, target, label in targets:
        if target is not None and actual > target:
            tradeoffs.insert(0, f'{label} {money(actual - target)} تومان بالاتر از هدف شماست')
    if any(target is not None for _, target, _ in targets) and all(target is None or actual <= target for actual, target, _ in targets):
        reasons.append('در محدوده بودجه ترجیحی شماست')
    if listing.data_conflicts:
        tradeoffs.insert(0, 'اطلاعات آگهی تناقض دارد؛ پیش از تصمیم بررسی کنید')
    if not listing.evidence:
        tradeoffs.append('توضیحات آگهی برای ارزیابی کیفیت کافی نیست')
    if not reasons:
        reasons.append(f'{fa(listing.area_m2)} متر با {fa(listing.bedrooms)} اتاق خواب')
    if len(reasons) < 2:
        reasons.append('تعداد اتاق با خواسته‌ات سازگار است' if intent.bedrooms_min and listing.bedrooms >= intent.bedrooms_min else f'{fa(listing.area_m2)} متر فضای خانه')
    if not tradeoffs:
        tradeoffs.append('ادعاهای آگهی نیاز به بررسی حضوری دارند')
    return reasons[:4], tradeoffs[:2]


def _rank_once(listings, intent):
    results = [score_listing(item, intent) for item in listings if eligible(item, intent)]
    results.sort(key=lambda item: (-item.score, item.listing.id))
    for rank, item in enumerate(results, 1):
        item.rank = rank
        if intent.work_location != 'none' and intent.location_priority in ('high', 'very_high') and item.distance is not None and results[0].distance is not None and item.distance > results[0].distance + .1:
            text = f'{fa(f"{item.distance:g}")} کیلومتر تا محل کار؛ {fa(f"{item.distance - results[0].distance:g}")} کیلومتر بیشتر از پیشنهاد اول'
            for i, tradeoff in enumerate(item.tradeoffs):
                if 'تا محل کار' in tradeoff:
                    item.tradeoffs[i] = text
                    break
    return results


def rank_listings(listings, intent):
    """Apply eligibility and stable scoring, then only the requested fallback stages."""
    # Materialize once because fallback stages may inspect the same candidate pool more
    # than once.  The prototype is bounded to 3k rows and correctness matters more than
    # premature query micro-optimization here.
    pool = list(listings)
    results = _rank_once(pool, intent)
    if not hasattr(intent, 'logic') or not intent.logic.get('fallbacks'):
        return results

    stage_intent = intent
    applied = []
    for rule in intent.logic['fallbacks']:
        if len(results) >= rule.get('trigger_min_results', 1):
            break
        stage_intent = apply_fallback_rule(stage_intent, rule)
        results = _rank_once(pool, stage_intent)
        applied.append(rule)

    if applied:
        notes = [fallback_label(rule) for rule in applied]
        for item in results:
            item.fallback_stage = len(applied)
            item.fallback_notes = list(notes)
            # Keep the fallback visible in ordinary result-card explanations.
            item.reasons = notes[:1] + [r for r in item.reasons if r not in notes]
            item.reasons = item.reasons[:4]
    return results


def consumer_labels(results, intent):
    if not results:
        return
    cheapest = min(results, key=lambda r: (r.listing.monthly_rent, r.listing.deposit, r.listing.id))
    residential = hasattr(intent, 'constraints') and bool(intent.constraints['neighborhoods'])
    nearest = min(results, key=lambda r: (-residential_fit(r.listing,intent),r.listing.id) if residential and intent.work_location=='none' else (r.distance if r.distance is not None else float('inf'),r.listing.id))
    for item in results:
        item.label = 'پیشنهاد اول' if item.rank == 1 else 'نزدیک‌ترین گزینه مناسب' if item is nearest and ((intent.work_location != 'none' and item.distance is not None) or residential) else 'کم‌هزینه‌ترین گزینه مناسب' if item is cheapest else ''


def plain_ranking_reasons(item, intent):
    points = sorted([r for r in item.breakdown if r['key'] != 'penalty' and r['fit'] is not None and r['points'] > 0], key=lambda r: -r['points'])[:3]
    result = []
    effective_base = intent.preferences
    if hasattr(intent, 'logic'):
        effective_base, _ = effective_priorities(item.listing, intent)
        logic_reasons, _ = conditional_notes(item.listing, intent)
        result.extend(logic_reasons[:1])
    for row in points:
        if row['key'] == 'location' and hasattr(intent, 'constraints') and intent.constraints['neighborhoods']:
            result.append('قرار گرفتن در محدوده «' + intent.residential_label + '» در جای این خانه اثر داشته؛ فاصله‌ها تقریبی‌اند.')
            continue
        if row['key'].startswith('evidence:'):
            feature = row['key'].split(':', 1)[1]
            priority = intent.evidence_preferences[feature]
            result.append(f'{EVIDENCE_FEATURE_LABELS[feature]} را «{LABELS[priority]}» مشخص کرده‌ای؛ فقط ذکر صریح آن در متن آگهی امتیاز مثبت داده است.')
            continue
        priority = effective_base.get('budget', intent.budget_priority) if row['key'] == 'budget' else effective_base.get('commute', intent.location_priority) if row['key'] == 'location' else effective_base[row['key']]
        if row['key'] == 'budget' and row['fit'] == 1:
            result.append('ودیعه و اجاره در محدوده بودجه هدف تو هستند؛ این موضوع به نفع این خانه بوده.')
        elif row['key'] == 'location':
            result.append(f'فاصله حدود {fa(f"{item.distance:g}")} کیلومتری تا محل کار با اولویت «{LABELS[priority]}» در انتخاب اثر داشته.')
        else:
            result.append(f'{row["label"]} را «{LABELS[priority]}» مشخص کرده‌ای؛ تناسب این خانه با این معیار در جای آن اثر داشته.')
    if item.listing.parking is False and effective_base['parking'] in ('low', 'ignored'):
        result.append('نبود پارکینگ اثر کمی داشته چون پارکینگ را کم‌اهمیت کرده‌ای.')
    if item.listing.data_conflicts:
        result.append('تناقض اطلاعات آگهی، امتیاز را کاهش داده است.')
    return result
