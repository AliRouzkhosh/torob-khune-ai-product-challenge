"""Synthetic adjacency plus approximate straight-line geography for imported records."""
from math import radians, sin, cos, asin, sqrt
from .location_registry import REGISTRY, location_key, display_location, source_labels

# Fixed approximate square/center anchors for the hiring demo, never routing endpoints.
WORKPLACE_ANCHORS = {'vanak': (35.7575, 51.4099), 'valiasr': (35.7117, 51.4072)}
NEIGHBORHOOD_ANCHORS = {'ونک': WORKPLACE_ANCHORS['vanak'], 'ولیعصر': WORKPLACE_ANCHORS['valiasr']}
# New workplace context uses existing listing-coordinate medians, never inferred routes.
REGISTRY_WORKPLACE_ANCHORS={**WORKPLACE_ANCHORS,**{r['key']:tuple(r['anchor']) for r in REGISTRY if r['anchor'] and r['classification'] in ('mapped','Persian')}}
NEIGHBORHOOD_ANCHORS.update({r['display_fa']:tuple(r['anchor']) for r in REGISTRY if r['anchor'] and r['classification'] in ('mapped','Persian')})
NEARBY_RADIUS_KM = 4.0


def haversine(lat1, lon1, lat2, lon2):
    """Kilometers on a spherical Earth; coordinate uncertainty is retained separately."""
    a, b = radians(lat2-lat1), radians(lon2-lon1)
    h = sin(a/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(b/2)**2
    return 6371.0088 * 2 * asin(sqrt(min(1, max(0, h))))


def point_distance(listing, anchor):
    if listing.latitude is None or listing.longitude is None or anchor is None: return None
    return haversine(listing.latitude, listing.longitude, *anchor)


def workplace_distance(listing, workplace):
    return point_distance(listing, REGISTRY_WORKPLACE_ANCHORS.get(workplace))


def location_matches(listing, intent):
    if any(location_key(listing.neighborhood)==location_key(n) for n in intent.constraints.get('excluded_neighborhoods',[])):return False
    targets = intent.constraints['neighborhoods']
    if not targets or intent.constraints['neighborhood_mode']=='preferred' or any(location_key(listing.neighborhood)==location_key(t) for t in targets): return True
    if intent.constraints['neighborhood_mode'] == 'exact': return False
    if listing.data_source == 'real':
        for target in targets:
            distance = point_distance(listing, NEIGHBORHOOD_ANCHORS.get(target))
            if distance is not None:
                if distance <= NEARBY_RADIUS_KM: return True
            elif proximity(listing.neighborhood, target): return True
        return False
    return listing.neighborhood in candidate_neighborhoods(intent)

# Fits the current 12 fixture neighborhoods. Scores are deterministic proximity tiers.
NEARBY = {
    'ونک': {'شیخ بهایی': .85, 'ملاصدرا': .85, 'یوسف‌آباد': .65, 'عباس‌آباد': .65},
    'ولیعصر': {'فاطمی': .85, 'یوسف‌آباد': .65, 'امیرآباد': .65, 'عباس‌آباد': .65},
    'یوسف‌آباد': {'ونک': .65, 'فاطمی': .85, 'امیرآباد': .85, 'عباس‌آباد': .65},
}

def proximity(neighborhood, target):
    neighborhood, target = display_location(neighborhood), display_location(target)
    if neighborhood == target: return 1.0
    return NEARBY.get(target, {}).get(neighborhood, NEARBY.get(neighborhood, {}).get(target, 0))

def candidate_neighborhoods(intent):
    targets = intent.constraints['neighborhoods']
    if intent.constraints['neighborhood_mode'] == 'exact': return source_labels(targets)
    return sorted(set(targets) | {name for target in targets for name in NEARBY.get(target, {})} | {name for name in NEARBY if any(proximity(name,t) for t in targets)})

def residential_fit(listing, intent):
    targets = intent.constraints['neighborhoods']
    if listing.data_source != 'real':
        return max((proximity(listing.neighborhood, target) for target in targets), default=0)
    fits = []
    for target in targets:
        if location_key(listing.neighborhood) == location_key(target): fits.append(1.0); continue
        distance = point_distance(listing, NEIGHBORHOOD_ANCHORS.get(target))
        fits.append(max(0, 1-distance/NEARBY_RADIUS_KM)*.9 if distance is not None else proximity(listing.neighborhood,target))
    return max(fits, default=0)
