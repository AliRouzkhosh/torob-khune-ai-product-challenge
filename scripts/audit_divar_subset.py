"""Read-only local audit artifact: 20 records, coverage and the three frozen scenarios."""
import json
import os
from pathlib import Path
import sys
from time import perf_counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ['DJANGO_SETTINGS_MODULE']='config.settings'
os.environ['DATA_MODE']='real'
import django
django.setup()
from finder.models import Listing
from finder.selectors import listings, filter_listings, neighborhood_names
from finder.ai import get_ai_service
from finder.intent import SCENARIOS
from finder.ranking import rank_listings


def main():
    rows=list(listings())
    if not rows: raise SystemExit('No real records imported; an audit cannot be fabricated.')
    chosen={r.id:r for r in rows[:10]}
    groups=[sorted(rows,key=lambda r:-r.deposit),sorted(rows,key=lambda r:-r.monthly_rent),
            [r for r in rows if r.monthly_rent==0],[r for r in rows if r.latitude is None],
            [r for r in rows if r.construction_year is None],[r for r in rows if r.natural_light is not None]]
    for group in groups:
        for row in group[:2]: chosen[row.id]=row
    for row in rows:
        if len(chosen)>=20: break
        chosen[row.id]=row
    sampled=list(chosen.values())[:20]
    samples=[{key:getattr(row,key) for key in ['id','source_id','title','neighborhood','deposit','monthly_rent','area_m2','bedrooms','construction_year','parking','elevator','storage','latitude','longitude','location_radius_m','description','evidence','data_conflicts','source_metadata']} for row in sampled]
    scenarios={}
    service=get_ai_service()
    for key,(label,query) in SCENARIOS.items():
        intent=service.parse_full_intent(query,neighborhood_names())
        start=perf_counter();ranked=rank_listings(filter_listings(listings(),intent),intent);elapsed=perf_counter()-start
        scenarios[key]={'label':label,'intent':intent.to_dict(),'eligible_count':len(ranked),'seconds':round(elapsed,4),
            'top': [{'id':r.listing.id,'title':r.listing.title,'neighborhood':r.listing.neighborhood,'deposit':r.listing.deposit,
                     'rent':r.listing.monthly_rent,'area':r.listing.area_m2,'bedrooms':r.listing.bedrooms,
                     'year':r.listing.construction_year,'workplace_distance_km':r.distance,'reasons':r.reasons,'tradeoffs':r.tradeoffs} for r in ranked[:3]]}
    report={'real_count':len(rows),'audit_samples':samples,'scenarios':scenarios,
            'coverage':{key:sum(getattr(r,key) is not None and getattr(r,key)!='' for r in rows) for key in ['latitude','neighborhood','construction_year','parking','elevator','storage','natural_light','quietness','layout_quality','access_quality']},
            'full_deposit_count':sum(r.monthly_rent==0 for r in rows),
            'conflict_count':sum(bool(r.data_conflicts) for r in rows)}
    destination=Path('data/divar-audit.json');destination.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in report.items() if k!='audit_samples'},ensure_ascii=False,indent=2))
    print('20 audit records saved to',destination)


if __name__=='__main__': main()
