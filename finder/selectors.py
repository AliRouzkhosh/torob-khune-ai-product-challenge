from hashlib import sha256
from django.conf import settings
from django.db.models import Q
from django.templatetags.static import static
from .models import Listing
from .locations import candidate_neighborhoods, location_matches
from .evidence_features import evidence_requirement_matches, has_evidence_requirements
from .location_registry import display_location,source_labels


def listings():
    return Listing.objects.filter(data_source=settings.DATA_MODE).order_by('id')


def neighborhood_names():
    from .locations import NEIGHBORHOOD_ANCHORS
    return sorted({display_location(n) for n in listings().exclude(neighborhood='').values_list('neighborhood',flat=True).distinct()} | set(NEIGHBORHOOD_ANCHORS))


def filter_listings(queryset, intent):
    # v0.9-D conditional/fallback plans can deliberately relax a hard field per listing
    # or in a later stage.  Applying the first-stage SQL filter here would discard valid
    # alternatives before ranking can evaluate the rule.  The hiring-demo pool is only
    # ~3k rows, so compound searches intentionally defer eligibility to rank_listings().
    if getattr(intent, 'logic', {}).get('conditionals') or getattr(intent, 'logic', {}).get('fallbacks'):
        return queryset
    filters = intent.constraints
    if filters.get('excluded_neighborhoods'):queryset=queryset.exclude(neighborhood__in=source_labels(filters['excluded_neighborhoods']))
    if filters.get('full_deposit'): queryset=queryset.filter(monthly_rent=0)
    if filters.get('convertible'): queryset=queryset.exclude(alternative_deposit__isnull=True).exclude(alternative_rent__isnull=True)
    if filters['neighborhoods'] and filters['neighborhood_mode']!='preferred' and (settings.DATA_MODE == 'synthetic' or filters['neighborhood_mode'] == 'exact'):
        queryset = queryset.filter(neighborhood__in=candidate_neighborhoods(intent))
    bed = filters['bedrooms']
    if bed['mode'] != 'any':
        if bed['mode'] == 'allowed': queryset = queryset.filter(bedrooms__in=bed['value'])
        elif bed['mode'] == 'exact': queryset = queryset.filter(bedrooms=bed['value'])
        elif bed['mode'] == 'min': queryset = queryset.filter(bedrooms__gte=bed['value'])
        elif bed['mode'] == 'max': queryset = queryset.filter(bedrooms__lte=bed['value'])

    area = filters['area']
    if area['min'] is not None: queryset = queryset.filter(area_m2__gte=area['min'])
    if area['max'] is not None: queryset = queryset.filter(area_m2__lte=area['max'])

    floor = filters['floor']
    floor_active = floor['mode'] != 'any' or bool(floor['excluded'])
    if floor_active:
        queryset = queryset.exclude(floor__isnull=True)
        if floor['mode'] == 'allowed': queryset = queryset.filter(floor__in=floor['value'])
        elif floor['mode'] == 'exact': queryset = queryset.filter(floor=floor['value'])
        elif floor['mode'] == 'min': queryset = queryset.filter(floor__gte=floor['value'])
        elif floor['mode'] == 'max': queryset = queryset.filter(floor__lte=floor['value'])
        if 'ground' in floor['excluded']: queryset = queryset.exclude(floor=0)
        if 'basement' in floor['excluded']: queryset = queryset.exclude(floor__lt=0)

    if filters['construction_year_min'] is not None:
        queryset = queryset.filter(construction_year__gte=filters['construction_year_min'])
    if filters['renovation_required']:
        queryset = queryset.filter(Q(renovated=True) | Q(renovation_claim=True))

    for key, field in [('max_deposit', 'deposit'), ('max_rent', 'monthly_rent')]:
        if filters.get(key) is not None:
            queryset = queryset.filter(**{field + '__lte': filters[key]})
    for amenity in filters['required_amenities']:
        if amenity in ('parking', 'elevator', 'storage', 'balcony'):
            queryset = queryset.filter(**{amenity: True})
    if has_evidence_requirements(filters):
        # Description-derived criteria cannot be expressed portably as SQL regexes.
        # Structured filters run first; then the bounded prototype candidate set is
        # checked with the same conservative evidence matcher used by ranking.
        ids = [item.id for item in queryset if evidence_requirement_matches(item, filters)]
        queryset = queryset.filter(pk__in=ids)

    if filters['neighborhoods'] and filters['neighborhood_mode'] == 'nearby' and settings.DATA_MODE == 'real':
        # Other hard filters run in SQL first; geography evaluates only the bounded candidates.
        ids = [item.id for item in queryset.only('id','data_source','neighborhood','latitude','longitude') if location_matches(item,intent)]
        queryset = queryset.filter(pk__in=ids)
    return queryset


def get_demo_image(listing):
    """Illustrative photo only; stable within a characteristic pool, never listing evidence."""
    if listing.bedrooms <= 1 or listing.area_m2 < 70:
        pool = (4, 9)
    elif listing.renovated:
        pool = (3, 8)
    elif listing.balcony:
        pool = (1, 7)
    elif listing.construction_year and listing.construction_year >= 1398:
        pool = (6, 10)
    elif listing.bedrooms >= 2 and listing.area_m2 >= 100:
        pool = (5, 10)
    else:
        pool = (2, 3, 9)
    identity = str(listing.source_id or listing.pk)
    index = int.from_bytes(sha256(identity.encode('utf-8')).digest()[:8], 'big') % len(pool)
    return f'finder/images/homes/home-{pool[index]:02d}.webp'


def image_url(listing):
    path = get_demo_image(listing)
    return static(path) if (settings.BASE_DIR / 'finder/static' / path).is_file() else None
