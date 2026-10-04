from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.http import Http404
from django.views.decorators.cache import never_cache
from django.utils.cache import patch_vary_headers
from django.core.exceptions import ValidationError
from .ai import get_ai_service
from .intent import IntentProfile, SCENARIOS, FEATURES, LABELS, PRIORITIES, normalize
from .ranking import RankedListing, rank_listings, score_listing, money, fa, consumer_labels, plain_ranking_reasons
from .selectors import listings, image_url, filter_listings, neighborhood_names
from .forms import PrecisionFilters
from .advanced import AdvancedFilters, ui_context, remove_logic, reset_filters
from .location_registry import workplace_label, workplace_choices, location_key
from .contact import demo_bale_url
from .patches import recognized_text
from .query import QueryOperation, classify_query, resolve_references
from .conflicts import IntentConflict, check_request
from .calendar import new_build_min_year
from .search import SearchIntent, apply_filters, filter_initial, remove_constraint, chips, active_filter_chips, changes, recovery_options, AMENITIES



def render_results(request, context):
    context['results_region'] = True
    partial = request.headers.get('X-Results-Partial') == '1'
    response = render(request, 'finder/_results_response.html' if partial else 'finder/results.html', context)
    patch_vary_headers(response, ['X-Results-Partial'])
    response['Cache-Control'] = 'private, no-store'
    return response


def brand(request):
    selected = list(listings().filter(id__in=request.session.get('comparison', [])))
    current = request.resolver_match.url_name if request.resolver_match else ''
    order = {'home': 1, 'intent': 2, 'results': 3, 'compare': 4}.get(current, 0)
    stages = [{'number': i, 'label': label, 'route': route, 'active': i == order, 'complete': i < order, 'link': i < order or i == order} for i, (label, route) in enumerate([('خواسته‌ها', 'home'), ('اولویت‌ها', 'intent'), ('خانه‌ها', 'results'), ('مقایسه', 'compare')], 1)]
    saved_ids = request.session.get('saved_listing_ids', [])
    current_search = profile(request)
    for item in selected: item.saved = item.id in saved_ids
    return {'data_mode': settings.DATA_MODE, 'brand_name': settings.BRAND_NAME, 'comparison_homes': selected, 'comparison_count': len(selected), 'comparison_tray_visible': bool(selected) and current in ('results','saved','detail','browse'), 'saved_count': listings().filter(pk__in=saved_ids).count(), 'current_page': current, 'current_detail_pk': request.resolver_match.kwargs.get('pk') if current == 'detail' else None, 'flow_stages': stages, 'github_url': getattr(settings, 'GITHUB_URL', ''), 'current_search': current_search, 'search_workplace': workplace_label(current_search.work_location) if current_search and current_search.work_location!='none' else '', 'save_feedback': request.session.pop('save_feedback', ''), 'search_notice': request.session.get('search_notice', ''), 'pending_reference': request.session.get('pending_query'), 'reference_choices': [name for key,name in workplace_choices() if key!='none'] if request.session.get('pending_query', {}).get('reference') == 'workplace' else neighborhood_names()}


def profile(request):
    if 'intent' not in request.session: return None
    value = request.session['intent']
    if 'constraints' in value: return SearchIntent(**value)
    intent = SearchIntent.from_profile(IntentProfile(**value), legacy=True)
    old_filters = request.session.pop('precision_filters', None)
    if old_filters:
        values = filter_initial(intent)
        values.update(old_filters)
        intent = apply_filters(intent, values)
    save_profile(request, intent)
    return intent


def save_profile(request, intent):
    request.session['intent'] = intent.to_dict()


def home(request):
    intent=neutral_intent()
    invalid=None
    if request.method=='POST':
        response,invalid=advanced_action(request,intent,'intent')
        if response:
            for key in ('query','refinement_diff','rank_changes','promotions','last_update','search_notice','precision_filters'):
                request.session.pop(key,None)
            request.session['last_query_operation']=QueryOperation.NEW_SEARCH.value
            return response
    return render(request, 'finder/home.html', {**ui_context(intent,invalid or AdvancedFilters(intent=intent,neighborhoods=neighborhood_names())), 'scenarios': HOME_EXAMPLES, 'intent':intent, 'step': 'search'})


HOME_EXAMPLES={
    'simple':('نور و محله','دوخوابه حوالی ونک می‌خوام، نور خوب و پارکینگ مهمه'),
    'parking':('پارکینگ با شواهد آگهی','دوخوابه می‌خوام، حداقل دو پارکینگ غیرمزاحم لازم دارم'),
    'conditional':('انعطاف با شرط','نوساز ترجیح می‌دم؛ ولی قدیمیِ بازسازی‌شده با آسانسور هم قبوله'),
}


def advanced_action(request,intent,destination):
    action=request.POST.get('action')
    if action=='advanced' and request.POST.get('rule'):action='remove_logic'
    if action not in ('advanced','reset_filters','remove_logic'):return None,None
    form=AdvancedFilters(request.POST,intent=intent,neighborhoods=neighborhood_names())
    try:
        updated=reset_filters() if action=='reset_filters' else remove_logic(intent,request.POST.get('rule','')) if action=='remove_logic' else form.apply()
        record_change(request,intent,updated)
        request.session.pop('pending_query',None)
        return redirect(destination),None
    except (ValueError,TypeError):
        if not form.errors:form.add_error(None,'این تغییر معتبر نیست.')
        return None,form


def apply_natural_query(request, text, destination, force_new=False, operation=None, context=None):
    """One entry point for home, Browse and result submissions."""
    text = normalize(text)
    if not text or len(text) > 2000: raise ValueError('خواسته‌ات را کوتاه و روشن بنویس.')
    neighborhoods = neighborhood_names()
    current = profile(request)
    operation = operation or classify_query(text, current, force_new=force_new, neighborhoods=neighborhoods)
    base = context or (current if operation == QueryOperation.PATCH else SearchIntent())
    try:
        check_request(text)
    except IntentConflict as conflict:
        request.session['pending_query']={'text':text,'reference':'conflict','conflicts':conflict.conflicts,'operation':operation.value,'destination':destination}
        return redirect('results' if current and destination=='results' else 'home')
    resolution = resolve_references(text, base, neighborhoods=neighborhoods)
    if resolution.needs_clarification:
        request.session['pending_query'] = {'text': text, 'reference': resolution.needs_clarification,
                                           'operation': operation.value, 'destination': destination}
        return redirect('results' if current and destination == 'results' else 'home')
    service = get_ai_service()
    if operation == QueryOperation.NEW_SEARCH:
        updated = service.parse_full_intent(resolution.text, neighborhoods)
        if context: updated.context = context.context.copy()
        save_profile(request, updated)
        request.session['query'] = text
        for key in ('refinement_diff', 'rank_changes', 'promotions', 'last_update', 'precision_filters'):
            request.session.pop(key, None)
        request.session['search_notice'] = 'جستجوی جدید از درخواستت ساخته شد.'
    else:
        updated = service.parse_intent_patch(resolution.text, base, neighborhoods).merge(base)
        record_change(request, current, updated)
        request.session['last_update'] = text
        request.session.pop('search_notice', None)
    request.session.pop('pending_query', None)
    request.session['last_query_operation'] = operation.value
    request.session['listing_context'] = 'results'
    return redirect(destination)


def start_smart_search(request, text, operation=None):
    return apply_natural_query(request, text, 'intent', operation=operation)


def clarify_query(request):
    pending = request.session.get('pending_query')
    if not pending: return redirect('home')
    if request.POST.get('cancel'):
        request.session.pop('pending_query', None)
        return redirect('results' if profile(request) else 'home')
    place = request.POST.get('reference_place', '')
    choices = [name for key,name in workplace_choices() if key!='none'] if pending['reference'] == 'workplace' else neighborhood_names()
    if place not in choices: return redirect('results' if profile(request) else 'home')
    operation = QueryOperation(pending['operation'])
    base = profile(request) if operation == QueryOperation.PATCH else SearchIntent()
    if pending['reference'] == 'workplace': base.context['workplace'] = location_key(place)
    else: base.constraints['neighborhoods'] = [place]
    return apply_natural_query(request, pending['text'], pending['destination'], operation=operation, context=base)


def new_search(request):
    # A start-over action clears search context, never saved/comparison/theme utilities.
    for key in ('intent', 'query', 'precision_filters', 'refinement_diff', 'rank_changes', 'promotions', 'last_update', 'listing_context', 'pending_query', 'search_notice', 'last_query_operation'):
        request.session.pop(key, None)
    return redirect('home')


def neutral_intent():
    intent = SearchIntent()
    intent.preferences = {key: 'ignored' for key in intent.preferences}
    return intent


def browse_item(request, listing):
    facts = [AMENITIES[key] + ' دارد' for key in ('parking', 'elevator', 'storage') if getattr(listing, key)]
    if any(e.get('factor') == 'natural_light' for e in listing.evidence):
        facts.append('آگهی روی نورگیری تأکید دارد')
    return RankedListing(listing=listing, score=0, breakdown=[], reasons=facts[:2],
        tradeoffs=listing.data_conflicts[:1], distance=0, rank=None,
        image=image_url(listing), selected=listing.id in request.session.get('comparison', []),
        saved=listing.id in request.session.get('saved_listing_ids', []),
        label='نوساز' if listing.construction_year is not None and listing.construction_year >= new_build_min_year() else '')


def browse(request):
    # Separate explicit browse constraints; never read/write personalized session['intent'].
    if request.method == 'GET' and not request.GET.get('continue') and not request.GET.get('sort'):
        request.session.pop('browse_intent', None)
        request.session.pop('browse_query', None)
    intent = SearchIntent(**request.session['browse_intent']) if 'browse_intent' in request.session else neutral_intent()
    neighborhoods = neighborhood_names()
    form = PrecisionFilters(request.POST if request.POST.get('action') == 'filter' else None, initial=filter_initial(intent), neighborhoods=neighborhoods)
    error = ''
    if request.method == 'POST':
        action = request.POST.get('action')
        if action in ('advanced','reset_filters','remove_logic'):
            advanced=AdvancedFilters(request.POST,intent=intent,neighborhoods=neighborhoods)
            try:
                intent=reset_filters() if action=='reset_filters' else remove_logic(intent,request.POST.get('rule','')) if action=='remove_logic' or request.POST.get('rule') else advanced.apply()
            except (ValueError,TypeError):error='مقدار فیلتر معتبر نیست.'
        elif action == 'filter':
            if form.is_valid(): intent = apply_filters(intent, form.cleaned_data)
            else: error = 'مقدار فیلتر معتبر نیست.'
        elif action == 'remove':
            if request.POST.get('key') in {r['key'] for r in active_filter_chips(intent)}: intent = remove_constraint(intent, request.POST['key'])
        elif action == 'clear':
            intent = neutral_intent()
            request.session.pop('browse_query', None)
        elif action == 'search':
            text = request.POST.get('q', '').strip()
            operation = classify_query(text, profile(request), neighborhoods=neighborhoods)
            if recognized_text(text, neighborhoods):
                try: return start_smart_search(request, text, operation)
                except (ValueError, TypeError): error = 'خواسته یا مبلغ بودجه معتبر نیست؛ آن را کوتاه و روشن بنویس.'
            else: request.session['browse_query'] = text[:200]
        request.session['browse_intent'] = intent.to_dict()
        if not error: return redirect('/browse/?continue=1')
    request.session['listing_context'] = 'browse'
    query = request.session.get('browse_query', '')
    candidates = list(filter_listings(listings(), intent))
    # Literal normalized listing-text search; no intent inference or preference weights.
    if query:
        tokens = normalize(query).split()
        candidates = [l for l in candidates if all(t in normalize(f'{l.title} {l.neighborhood} {l.description} {l.area_m2}') for t in tokens)]
    mode = request.GET.get('sort', 'default')
    if mode == 'cost': candidates.sort(key=lambda l: (l.monthly_rent, l.deposit, l.id))
    elif mode == 'new': candidates.sort(key=lambda l: (-(l.construction_year or 0), l.id))
    else: mode = 'default'
    return render_results(request, {'browse_mode': True, 'items': [browse_item(request,l) for l in candidates[:settings.RESULT_DISPLAY_LIMIT]], 'display_limit': settings.RESULT_DISPLAY_LIMIT,
        **ui_context(intent,advanced if error and request.POST.get('action')=='advanced' else AdvancedFilters(intent=intent,neighborhoods=neighborhoods)),
        'intent': intent, 'filter_form': form, 'active_chips': chips(intent), 'eligible_count': len(candidates),
        'total': listings().count(), 'sort': mode, 'browse_query': query, 'error': error})


def display_intent(request):
    return profile(request) if request.session.get('listing_context') != 'browse' else None


def review_context(request, intent, error=''):
    important, preferred = [], []
    for key in FEATURES:
        value = intent.preferences[key]
        if value in ('high', 'very_high', 'medium'):
            (important if value in ('high', 'very_high') else preferred).append(FEATURES[key])
    for label, value in intent.evidence_preference_groups:
        if value in ('high', 'very_high', 'medium'):
            (important if value in ('high', 'very_high') else preferred).append(label + ' (بر اساس متن آگهی)')
    necessary = ['تهران'] + ([intent.bedroom_label] if intent.bedrooms_hard else [])
    if intent.constraints['neighborhoods']: necessary.append(intent.residential_label)
    necessary.extend(AMENITIES[k] + ' ضروری' for k in intent.constraints['required_amenities'])
    necessary.extend(intent.structured_constraint_labels)
    budget = [label + ' ' + money(value) + ' تومان' for value, label in [(intent.deposit_target, 'ودیعه'), (intent.rent_target, 'اجاره')] if value is not None]
    budget.append({'none': 'بدون افزایش بودجه', 'medium': 'تا ۲۰٪ انعطاف', 'flexible': 'تا ۴۰٪ انعطاف'}[intent.budget_flexibility])
    if intent.rent_hard:
        budget.append('سقف اجاره قطعی')
    return {**ui_context(intent,AdvancedFilters(intent=intent,neighborhoods=neighborhood_names())), 'intent': intent, 'query': request.session.get('query', ''), 'error': error,
            'summary_groups': [('ضروری', necessary), ('بودجه', budget), ('خیلی مهم', important), ('ترجیحی', preferred)],
            'preferences': [(key, label, intent.preferences[key]) for key, label in FEATURES.items() if key not in ('parking', 'natural_light')],
            'bedroom_value': filter_initial(intent)['bedrooms'], 'bedroom_choices': PrecisionFilters(initial=filter_initial(intent)).fields['bedrooms'].choices,
            'inline_priorities': [('natural_light', 'نور', intent.preferences['natural_light']), ('location_priority', 'رفت‌وآمد', intent.location_priority), ('parking', 'پارکینگ', intent.preferences['parking'])],
            'priorities': LABELS.items(), 'deposit_m': intent.deposit_target // 1_000_000 if intent.deposit_target is not None else '',
            'rent_m': intent.rent_target // 1_000_000 if intent.rent_target is not None else '', 'step': 'intent'}


def intent_review(request):
    intent = profile(request)
    if intent and request.method=='POST':
        response,advanced_form=advanced_action(request,intent,'intent')
        if response:return response
        if advanced_form:return render(request,'finder/intent.html',{**review_context(request,intent),**ui_context(intent,advanced_form)},status=400)
    if request.method == 'POST':
        if request.POST.get('action') == 'clarify': return clarify_query(request)
        if request.POST.get('action') == 'confirm':
            if intent is None:
                return redirect('home')
            try:
                parsed = IntentProfile(
                    bedrooms_min=int(request.POST.get('bedrooms_min', 0)), bedrooms_hard='bedrooms_hard' in request.POST,
                    deposit_target=int(normalize(request.POST['deposit'])) * 1_000_000 if request.POST.get('deposit') else None,
                    rent_target=int(normalize(request.POST['rent'])) * 1_000_000 if request.POST.get('rent') else None,
                    budget_flexibility=request.POST.get('budget_flexibility', 'medium'), rent_hard='rent_hard' in request.POST,
                    budget_priority=request.POST.get('budget_priority', intent.budget_priority),
                    elevator_required='elevator_required' in request.POST,
                    work_location=request.POST.get('work_location', 'none'), location_priority=request.POST.get('location_priority', 'high'),
                    preferences={key: request.POST.get(key, 'low') for key in FEATURES})
                PrecisionFilters(request.POST, initial=filter_initial(intent)).fields['bedrooms'].clean(request.POST.get('bedrooms', filter_initial(intent)['bedrooms']))
            except (ValueError, TypeError, ValidationError):
                context = review_context(request, intent, 'مقادیر واردشده معتبر نیستند. بودجه و تعداد اتاق را بررسی کن.')
                context['deposit_m'] = request.POST.get('deposit', '')
                context['rent_m'] = request.POST.get('rent', '')
                return render(request, 'finder/intent.html', context, status=400)
            updated = intent.copy()
            updated.preferences.update(parsed.preferences, commute=parsed.location_priority, budget=parsed.budget_priority)
            updated.context['workplace'] = parsed.work_location
            updated.constraints['required_amenities'] = [k for k in updated.constraints['required_amenities'] if k not in updated.preferences or updated.preferences[k] in ('high', 'very_high')]
            bed = request.POST.get('bedrooms', filter_initial(intent)['bedrooms'])
            values = filter_initial(intent)
            values['bedrooms'] = bed
            updated = apply_filters(updated, values)
            for target, value, cap in [('deposit', parsed.deposit_target, 'max_deposit'), ('rent', parsed.rent_target, 'max_rent')]:
                if value != intent.targets[target] or parsed.budget_flexibility != intent.budget_flexibility or (target == 'rent' and parsed.rent_hard != intent.rent_hard):
                    updated.targets[target] = value
                    updated.constraints[cap] = int(value * (1 if target == 'rent' and parsed.rent_hard else {'none': 1, 'medium': 1.2, 'flexible': 1.4}[parsed.budget_flexibility])) if value is not None else None
            updated.targets['flexibility'] = parsed.budget_flexibility
            required = request.POST.getlist('required_amenities')
            if 'required_amenities_present' in request.POST:
                for key in required:
                    if key not in intent.constraints['required_amenities'] and key in updated.preferences:
                        updated.preferences[key] = max(updated.preferences[key], 'high', key=lambda p: PRIORITIES[p])
                updated.constraints['required_amenities'] = [k for k in required if k not in updated.preferences or updated.preferences[k] in ('high', 'very_high')]
            elif parsed.elevator_required and 'elevator' not in updated.constraints['required_amenities']:
                updated.constraints['required_amenities'].append('elevator')
            for key in updated.constraints['required_amenities']:
                if key in updated.preferences and updated.preferences[key] in ('ignored', 'low', 'medium'): updated.preferences[key] = 'high'
            updated.metadata['source'] = 'review'
            updated.metadata['manual'] = [k for k in updated.metadata['manual'] if not k.startswith('amenity:') or k[8:] in updated.constraints['required_amenities']]
            from .compound import clear_related_logic
            paths={group+'.'+key for group in ('constraints','preferences','context','targets') for key in getattr(intent,group) if getattr(intent,group)[key]!=getattr(updated,group)[key]}
            clear_related_logic(updated,paths)
            try: updated.__post_init__()
            except ValueError:
                return render(request, 'finder/intent.html', review_context(request, intent, 'مقادیر واردشده معتبر نیستند.'), status=400)
            save_profile(request, updated)
            request.session.pop('promotions', None)
            request.session.pop('refinement_diff', None)
            request.session.pop('rank_changes', None)
            request.session.pop('last_update', None)
            return redirect('results')
        examples={**SCENARIOS,**HOME_EXAMPLES}
        query = examples[request.POST['scenario']][1] if request.POST.get('scenario') in examples else request.POST.get('query', '').strip()
        if not query or len(query) > 2000:
            return render(request, 'finder/home.html', {'scenarios': HOME_EXAMPLES, 'error': 'خواسته‌ات را در یک تا چند جمله بنویس (حداکثر ۲۰۰۰ حرف).', 'query': query, 'step': 'search'}, status=400)
        try:
            return start_smart_search(request, query)
        except (ValueError, TypeError):
            return render(request, 'finder/home.html', {'scenarios': HOME_EXAMPLES, 'error': 'خواسته یا مبلغ بودجه معتبر نیست؛ آن را کوتاه و روشن بنویس.', 'query': query, 'step': 'search'}, status=400)
    if intent is None:
        return redirect('home')
    return render(request, 'finder/intent.html', review_context(request, intent))


def decorated_results(request, intent, candidates=None):
    results = rank_listings(listings() if candidates is None else candidates, intent)
    consumer_labels(results, intent)
    selected = request.session.get('comparison', [])
    promotions = request.session.get('promotions', {})
    for item in results:
        item.image, item.selected = image_url(item.listing), item.listing.id in selected
        item.saved = item.listing.id in request.session.get('saved_listing_ids', [])
        item.promotion = promotions.get(str(item.listing.id), '')
        change = request.session.get('rank_changes', {}).get(str(item.listing.id), 0)
        item.rank_change = fa(abs(change)) + (' جایگاه بالاتر' if change > 0 else ' جایگاه پایین‌تر') if change else ''
    return results


def record_change(request, before, after):
    previous = {r.listing.id: r.rank for r in rank_listings(listings(), before)}
    ranked = rank_listings(listings(), after)
    moved = {str(r.listing.id): previous[r.listing.id] - r.rank for r in ranked if r.listing.id in previous and r.rank != previous[r.listing.id]}
    request.session['rank_changes'] = moved
    request.session['refinement_diff'] = {'changes': changes(before, after), 'moved': len(moved), 'source': after.metadata['source']}
    request.session['promotions'] = {str(r.listing.id): 'این گزینه بعد از تغییر اولویت بالاتر آمد چون به محل کار نزدیک‌تر است و نداشتن پارکینگ دیگر اهمیت کمی دارد.' for r in ranked if moved.get(str(r.listing.id), 0) > 0 and after.location_priority == 'very_high' and after.preferences['parking'] in ('low', 'ignored') and r.listing.parking is False}
    save_profile(request, after)


def results(request):
    request.session['listing_context'] = 'results'
    intent = profile(request)
    if intent is None:
        return redirect('home')
    error = ''
    neighborhoods = neighborhood_names()
    advanced_form=AdvancedFilters(intent=intent,neighborhoods=neighborhoods)
    if request.method=='GET' and request.session.get('pending_query',{}).get('reference')=='conflict':
        return render_results(request,{**ui_context(intent,advanced_form),'intent':intent,'conflict_pending':True,'step':'results'})
    advanced_failed=False
    if request.method=='POST':
        response,invalid=advanced_action(request,intent,'results')
        if response:return response
        if invalid:advanced_form=invalid;advanced_failed=True;error='مقدار فیلتر معتبر نیست؛ خواسته قبلی حفظ شد.'
    initial = filter_initial(intent)
    filter_data = request.POST if request.POST.get('action') == 'filter' else request.GET if request.GET.get('action') == 'filter' else None
    filter_form = PrecisionFilters(filter_data, initial=initial, neighborhoods=neighborhoods)
    if filter_data is not None:
        if filter_form.is_valid():
            record_change(request, intent, apply_filters(intent, filter_form.cleaned_data))
            return redirect('results')
        else:
            error = 'مقدار فیلتر معتبر نیست؛ فیلتر قبلی همچنان اعمال می‌شود.'
    if request.method == 'POST' and filter_data is None and not advanced_failed:
        action = request.POST.get('action')
        if action == 'dismiss':
            request.session.pop('search_notice', None)
            request.session.pop('refinement_diff', None)
            request.session.pop('rank_changes', None)
            request.session.pop('promotions', None)
            return redirect('results')
        if action in ('remove', 'clear', 'recover'):
            updated = intent.copy()
            try:
                if action == 'clear':
                    for key in intent.metadata['manual']: updated = remove_constraint(updated, key)
                elif action == 'recover' and request.POST.get('key', '').startswith(('raise:', 'accept:')):
                    options = recovery_options(intent, list(listings()), rank_listings)
                    option = next(o for o in options if o['action'] == request.POST['key'])
                    updated.constraints[option['action'].split(':',1)[1]] = option['value']
                    updated.metadata['source'] = 'recovery'
                else:
                    key = request.POST.get('key', '')
                    if action == 'remove' and key not in {r['key'] for r in active_filter_chips(intent)}: raise ValueError()
                    updated = remove_constraint(intent, key, 'recovery' if action == 'recover' else 'filter')
                record_change(request, intent, updated)
            except (ValueError, StopIteration):
                request.session['comparison_error'] = 'این تغییر معتبر نیست.'
            return redirect('results')
        update = request.POST.get('update', '').strip()
        if not update or len(update) > 2000:
            error = 'تغییر اولویت را کوتاه و روشن بنویس.'
        else:
            try:
                return apply_natural_query(request, update, 'results', force_new=request.POST.get('operation') == 'NEW_SEARCH')
            except (ValueError, TypeError):
                request.session['comparison_error'] = 'عدد بودجه معتبر نیست؛ مبلغ را به میلیون یا میلیارد تومان بنویس.'
                return redirect('results')
    if request.session.get('pending_query',{}).get('reference')=='conflict':
        return render_results(request,{**ui_context(intent,advanced_form),'intent':intent,'conflict_pending':True,'step':'results'})
    ranked = decorated_results(request, intent, filter_listings(listings(), intent))
    mode = request.GET.get('sort', 'match')
    if mode == 'cost':
        ranked.sort(key=lambda r: (r.listing.monthly_rent, r.listing.deposit, r.listing.id))
    elif mode == 'near':
        from .locations import residential_fit
        ranked.sort(key=lambda r: (-residential_fit(r.listing,intent),r.listing.id) if intent.constraints['neighborhoods'] and intent.work_location=='none' else (r.distance if r.distance is not None else float('inf'),r.listing.id))
    else:
        mode = 'match'
    return render_results(request, {
        **ui_context(intent,advanced_form),
        'items': ranked[:settings.RESULT_DISPLAY_LIMIT], 'display_limit': settings.RESULT_DISPLAY_LIMIT, 'total': listings().count(), 'eligible_count': len(ranked), 'intent': intent,
        'priorities': LABELS, 'location_label': workplace_label(intent.work_location),
        'parking_label': LABELS[intent.preferences['parking']], 'commute_label': LABELS[intent.location_priority],
        'light_label': LABELS[intent.preferences['natural_light']], 'selected_count': listings().filter(pk__in=request.session.get('comparison', [])).count(),
        'sort': mode, 'error': error or request.session.pop('comparison_error', ''), 'step': 'results',
        'last_update': request.session.get('last_update', ''), 'refinement': request.session.get('refinement_diff'),
        'filter_form': filter_form, 'active_chips': chips(intent), 'required_amenities': [(key, AMENITIES[key]) for key in intent.constraints['required_amenities']],
        'important_constraints': (([intent.bedroom_label] if intent.bedrooms_hard else []) + intent.structured_constraint_labels + intent.logic_labels),
        'fallback_notice': (ranked[0].fallback_notes if ranked and ranked[0].fallback_stage else []), 'recoveries': recovery_options(intent, list(listings()), rank_listings) if not ranked else []})


@require_POST
def compare_toggle(request):
    if request.POST.get('action') == 'clear':
        from .comparison import clear_comparison
        clear_comparison(request.session)
        destination = request.POST.get('return', 'results')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            from django.http import JsonResponse
            from django.template.loader import render_to_string
            context = brand(request)
            page = destination if destination in ('results', 'browse', 'saved', 'detail', 'compare') else 'results'
            context.update(current_page=page, comparison_tray_visible=False)
            return JsonResponse({'cleared': True, 'selected': False, 'count': 0, 'error': '',
                'utilities': render_to_string('finder/_utility_update.html', context, request=request)})
        if destination == 'detail':
            try:
                pk = int(request.POST.get('return_pk', 0))
            except (ValueError, TypeError):
                pk = 0
            if listings().filter(pk=pk).exists():
                return redirect('detail', pk=pk)
        return redirect('/browse/?continue=1') if destination == 'browse' else redirect(destination if destination in ('compare', 'saved', 'home') else 'results')
    try:
        listing_id = int(request.POST.get('listing', 0))
    except (ValueError, TypeError):
        raise Http404('خانه پیدا نشد')
    listing = get_object_or_404(listings(), pk=listing_id)
    selected = request.session.get('comparison', []).copy()
    if listing.id in selected:
        selected.remove(listing.id)
    elif listings().filter(pk__in=selected).count() < 3:
        selected.append(listing.id)
    else:
        request.session['comparison_error'] = 'حداکثر سه خانه را مقایسه کن؛ ابتدا یکی را از انتخاب خارج کن.'
    request.session['comparison'] = selected
    destination = request.POST.get('return', 'results')
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        from django.http import JsonResponse
        from django.template.loader import render_to_string
        page = destination if destination in ('results', 'browse', 'saved', 'detail', 'compare') else 'results'
        context = brand(request)
        context.update(current_page=page, comparison_tray_visible=bool(context['comparison_homes']) and page in ('results','saved','detail','browse'), current_detail_pk=request.POST.get('return_pk') or listing.id if page == 'detail' else None)
        error = request.session.pop('comparison_error', '')
        return JsonResponse({'selected': listing.id in selected, 'count': len(context['comparison_homes']), 'id': str(listing.id), 'error': error,
            'utilities': render_to_string('finder/_utility_update.html', context, request=request)})
    if destination == 'detail':
        try:
            return_pk = int(request.POST.get('return_pk', listing.id))
        except (ValueError, TypeError):
            return_pk = listing.id
        return redirect('detail', pk=return_pk if listings().filter(pk=return_pk).exists() else listing.id)
    return redirect('/browse/?continue=1') if destination == 'browse' else redirect(destination if destination in ('compare', 'saved', 'home') else 'results')


def compare(request):
    personalized = display_intent(request)
    intent = personalized or neutral_intent()
    items = [r for r in decorated_results(request, intent) if r.selected]
    # Include selected homes even if a later preference change excludes them.
    included = {r.listing.id for r in items}
    for listing in listings().filter(id__in=request.session.get('comparison', [])):
        if listing.id not in included:
            row = score_listing(listing, intent)
            row.rank = None
            row.image = image_url(listing)
            row.saved = listing.id in request.session.get('saved_listing_ids', [])
            items.append(row)
    if not personalized:
        items = [browse_item(request,l) for l in listings().filter(pk__in=request.session.get('comparison', []))]
    rows = []
    fields = [('ودیعه', lambda r: money(r.listing.deposit) + ' تومان'), ('اجاره ماهانه', lambda r: money(r.listing.monthly_rent) + ' تومان'),
             ('متراژ', lambda r: fa(r.listing.area_m2) + ' متر'), ('اتاق خواب', lambda r: fa(r.listing.bedrooms)),
             ('سال ساخت / عمر تقریبی', lambda r: fa(r.listing.construction_year) + ' / ' + fa(max(0, 1405 - r.listing.construction_year)) + ' سال' if r.listing.construction_year is not None else 'تعیین نشده'),
             *[(label, lambda r, key=key: 'نامشخص' if getattr(r.listing,key) is None else 'دارد' if getattr(r.listing, key) else 'ندارد') for key, label in [('parking', 'پارکینگ'), ('elevator', 'آسانسور'), ('storage', 'انباری')]],
             ('فاصله تقریبی تا محل کار', lambda r: (fa(r.distance) + ' کیلومتر' if r.distance is not None else 'مختصات نامشخص') if intent.work_location != 'none' else 'محل کار تعیین نشده'),
             ('شواهد نورگیری در آگهی', lambda r: next((e['text'] for e in r.listing.evidence if e.get('factor') == 'natural_light'), 'شواهد کافی نداریم')),
             ('مهم‌ترین ملاحظه', lambda r: r.tradeoffs[0] if r.tradeoffs else '—')]
    for label, value in fields:
        values = [value(r) for r in items]
        different = len(set(values)) > 1
        cells = []
        for i, text in enumerate(values):
            highlight = different and ((label in ('پارکینگ', 'آسانسور', 'انباری') and text == 'دارد') or (label == 'فاصله تقریبی تا محل کار' and intent.work_location != 'none' and items[i].distance is not None and items[i].distance == min((r.distance for r in items if r.distance is not None), default=None)))
            if highlight:
                text = '✓ دارد' if text == 'دارد' else text + '، نزدیک‌تر'
            cells.append({'text': text, 'highlight': highlight})
        rows.append({'label': label, 'cells': cells, 'different': different})
    decisions = []
    if personalized and len(items) >= 2:
        for title, keys in [('اگر نزدیکی به محدوده مهم‌تر است' if intent.constraints['neighborhoods'] and intent.work_location=='none' else 'اگر رفت‌وآمد مهم‌تر است', ['location']), ('اگر نور و پارکینگ مهم‌ترند', ['natural_light', 'parking'])]:
            scored = [(sum(row['points'] for row in item.breakdown if row['key'] in keys), item) for item in items]
            scored.sort(key=lambda pair: -pair[0])
            if scored[0][0] > scored[1][0] and scored[0][1].rank is not None:
                decisions.append({'title': title, 'home': scored[0][1].listing, 'evidence': 'سهم بالاتر این معیارها در امتیاز فعلی؛ ادعاهای کیفیت از متن آگهی‌اند.'})
    why = ''
    if personalized and len(items) >= 2:
        other_points = {r['key']: r['points'] for r in items[1].breakdown}
        advantages = sorted([r for r in items[0].breakdown if r['points'] > other_points[r['key']]], key=lambda r: -(r['points'] - other_points[r['key']]))[:2]
        if advantages:
            why = 'در مقایسه با «' + items[1].listing.title + '»، سهم بهترِ ' + ' و '.join(r['label'] for r in advantages) + ' در امتیاز، این خانه را بالاتر قرار داده است.'
        else:
            why = 'امتیاز این دو خانه برابر است؛ ترتیب ثابت شناسه آگهی، تساوی را می‌شکند.'
    return render(request, 'finder/_compare_region.html' if request.headers.get('X-Compare-Partial') == '1' else 'finder/compare.html', {'items': items, 'rows': rows, 'why': why, 'decisions': decisions, 'personalized': bool(personalized), 'back_route': 'results' if personalized else 'browse', 'intent': intent, 'step': 'compare' if personalized else None, 'error': request.session.pop('comparison_error', '')})


@never_cache
def detail(request, pk, demo_contact=None, contact_action=None):
    listing = get_object_or_404(listings(), pk=pk)
    intent = display_intent(request)
    item = score_listing(listing, intent) if intent else browse_item(request, listing)
    item.image = image_url(listing)
    item.selected = pk in request.session.get('comparison', [])
    item.saved = pk in request.session.get('saved_listing_ids', [])
    return render(request, 'finder/detail.html', {'item': item, 'demo_contact': demo_contact, 'contact_action': contact_action, 'bale_configured': bool(demo_bale_url()) if request.user.is_authenticated else False, 'plain_reasons': plain_ranking_reasons(item, intent) if intent else [], 'personalized': bool(intent), 'back_route': 'results' if intent else 'browse', 'matches_constraints': bool(rank_listings([listing], intent)) if intent else True})


@require_POST
def save_toggle(request):
    try: listing_id = int(request.POST.get('listing', 0))
    except (ValueError, TypeError): listing_id = 0
    listing = listings().filter(pk=listing_id).first()
    saved_ids = list(dict.fromkeys(request.session.get('saved_listing_ids', [])))
    if listing:
        if listing_id in saved_ids: saved_ids.remove(listing_id)
        else: saved_ids.append(listing_id)
        request.session['saved_listing_ids'] = saved_ids
        request.session['save_feedback'] = 'خانه ذخیره شد' if listing_id in saved_ids else 'از ذخیره‌ها حذف شد'
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        request.session.pop('save_feedback', None)
        from django.http import JsonResponse
        return JsonResponse({'saved': bool(listing and listing_id in saved_ids), 'count': listings().filter(pk__in=saved_ids).count(), 'id': str(listing_id) if listing and listing.data_source == 'real' else listing_id}, status=200 if listing else 404)
    destination = request.POST.get('return', 'results')
    if destination == 'browse': return redirect('/browse/?continue=1')
    return redirect('detail', pk=listing_id) if destination == 'detail' and listing else redirect(destination if destination in ('saved', 'compare', 'home', 'browse') else 'results')


def saved(request):
    intent = display_intent(request)
    items = []
    for listing in listings().filter(pk__in=request.session.get('saved_listing_ids', [])):
        item = score_listing(listing, intent) if intent else browse_item(request, listing)
        item.image, item.saved = image_url(listing), True
        item.selected = listing.id in request.session.get('comparison', [])
        items.append(item)
    return render(request, 'finder/saved.html', {'items': items})


def about(request):
    return render(request, 'finder/about.html')
