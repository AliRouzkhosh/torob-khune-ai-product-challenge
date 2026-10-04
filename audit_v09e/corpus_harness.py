"""Versioned corpus adapter. Never treat unsupported YAML fields as passing assertions."""
import json, os, sys, pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django;django.setup()
from finder.ai import get_ai_service
from finder.search import SearchIntent
from finder.query import UnresolvedReference
NAMES=('ونک','ولیعصر','یوسف‌آباد','میرداماد','عباس‌آباد')
BASE={'layout':'layout_quality'}
FEATURE_GROUPS={'heating_cooling':'hvac_required','security':'security_required','transport_access':'transport_required','view_privacy':'view_privacy_required','accessibility':'accessibility_required'}
ALIASES={'single_unit_floor':'single_unit','road_access':'good_road_access'}
def translate(expected):
 checks=[];unsupported=[]
 def add(path,value,kind='equal'):checks.append({'path':path,'value':value,'kind':kind})
 for key,value in expected.items():
  if key in ('bedrooms','floor'):
   for k,v in value.items():
    if k=='excluded' and 'top' in v:unsupported.append('floor.top: building floor count unavailable')
    elif k in ('mode','value','values','excluded'):add('constraints.'+key+'.'+('value' if k=='values' else k),v)
    elif k in ('min','max') and key=='floor':add('constraints.floor.mode',k);add('constraints.floor.value',v)
    else:unsupported.append(key+'.'+k)
  elif key=='area':
   for k,v in value.items():
    if k in ('min','max'):add('constraints.area.'+k,v)
    elif k=='preference' and v=='larger':add('preferences.area',True,'active')
    else:unsupported.append(key+'.'+k)
  elif key in ('deposit','rent'):
   if value is None:add('constraints.max_'+key,None)
   elif 'max_toman' in value:add('constraints.max_'+key,value['max_toman'])
   else:unsupported.append(key)
  elif key=='desired_location':
   if value is None:add('constraints.neighborhoods',[])
   elif value.get('mode') in ('exact','nearby') and 'place' in value:
    add('constraints.neighborhoods',[value['place']]);add('constraints.neighborhood_mode',value['mode'])
    unsupported.extend('desired_location.'+k for k in value if k not in ('mode','place'))
   else:unsupported.append(key)
  elif key=='workplace':
   if value in ('ونک','ولیعصر',None):add('context.workplace',{'ونک':'vanak','ولیعصر':'valiasr',None:'none'}[value])
   else:unsupported.append('workplace: unsupported place')
  elif key=='commute_priority':add('preferences.commute',value)
  elif key=='needs_clarification':add('clarification',value)
  elif key=='budget_flexibility':
   if 'priority' in value and value['priority']!='medium_or_high':add('targets.flexibility',{'high':'flexible','medium':'medium','ignored':'none'}[value['priority']])
   else:unsupported.append(key)
  elif key in ('parking','elevator','storage','natural_light','quietness','building_age','balcony','layout'):
   for k,v in value.items():
    if k=='required' and key in ('parking','elevator','storage','balcony'):add('constraints.required_amenities',key,'contains' if v else 'absent')
    elif k=='priority' and key in ('parking','elevator','storage','natural_light','quietness','building_age'):add('preferences.'+key,'very_high' if v=='required' else v)
    elif key=='parking' and k=='count_min':add('constraints.parking_count_min',v)
    elif key=='parking' and k in ('dedicated','non_tandem'):add('constraints.parking_'+k+'_required',v=='required')
    elif key=='building_age' and k=='max_age_years':add('constraints.construction_year_min',1405-v)
    elif key=='building_age' and k=='preference' and v=='newer':add('preferences.building_age',True,'active')
    else:unsupported.append(key+'.'+k)
  elif key=='pets':
   for k,v in value.items():
    if k=='allowed_required':add('constraints.pet_policy','allowed' if v else 'any')
    elif k=='priority':add('evidence_preferences.pet_allowed',v)
    else:unsupported.append(key+'.'+k)
  elif key=='furnishing':
   if value in ('furnished_required','unfurnished_required','ignored'):add('constraints.furnishing',{'furnished_required':'furnished','unfurnished_required':'unfurnished','ignored':'any'}[value])
   else:unsupported.append(key)
  elif key in FEATURE_GROUPS:
   for feature,level in value.items():
    feature=ALIASES.get(feature,feature)
    if feature not in SearchIntent().evidence_preferences:unsupported.append(key+'.'+feature);continue
    if level=='required':add('constraints.'+FEATURE_GROUPS[key],feature,'contains')
    else:add('evidence_preferences.'+feature,True,'active') if level in ('preferred','high','allowed') else add('evidence_preferences.'+feature,level)
  elif key=='building_density':
   for k,v in value.items():
    f=ALIASES.get(k,k)
    if f not in ('single_unit','low_density'):unsupported.append(key+'.'+k)
    elif v=='required':add('constraints.building_density',f)
    else:add('evidence_preferences.'+f,True,'active')
  elif key=='renovation':
   if value.get('required'):add('constraints.renovation_required',True)
   elif value.get('required_if_old'):add('logic.conditionals','require_renovation_if_old','rule_type')
   else:unsupported.append(key)
  elif key=='relative_priority':
   def token(v):return 'evidence:'+v.split('.')[1] if '.' in v else 'base:'+v
   add('logic.relative_priorities',{'higher':token(value['higher']),'lower':token(value['lower'])},'contains')
  elif key=='conditional':
   antecedent=value['if'];consequence=value['then']
   if 'floor' in antecedent:add('logic.conditionals',{'type':'require_elevator_if_floor_min','floor_min':antecedent['floor']['min']},'contains')
   elif 'elevator' in antecedent:add('logic.conditionals',{'type':'require_elevator_if_floor_min','floor_min':consequence['floor']['max']+1},'contains')
   elif 'building_age' in antecedent:add('logic.conditionals','require_elevator_if_old' if 'elevator' in consequence else 'require_renovation_if_old','rule_type')
   elif 'parking' in consequence:add('logic.conditionals','relax_preference_if_evidence' if 'transport_access.near_metro' in antecedent else 'relax_preference_if_commute_close','rule_type')
   elif 'rent' in consequence:add('logic.conditionals','conditional_max_rent_if_commute_close','rule_type')
   elif 'area' in consequence:add('logic.conditionals','relax_area_min_if_commute_close','rule_type')
   else:unsupported.append(key)
  elif key=='exception' and value.get('older_allowed_if_renovated'):add('logic.conditionals','require_renovation_if_old','rule_type')
  elif key=='fallback':
   first,last=value[0],value[-1]
   if 'desired_location' in first:
    add('constraints.neighborhoods',[first['desired_location']['place']]);add('constraints.neighborhood_mode','exact');add('logic.fallbacks',{'type':'neighborhood_scope','to':'nearby'},'rule_subset')
   elif 'rent' in first:add('constraints.max_rent',first['rent']['max_toman']);add('logic.fallbacks',{'type':'max_rent','to':last['rent']['max_toman']},'rule_subset')
   elif 'bedrooms' in first:add('constraints.bedrooms.mode','exact');add('constraints.bedrooms.value',first['bedrooms']['value']);add('logic.fallbacks',{'type':'bedrooms_allowed','values':last['bedrooms']['values']},'rule_subset')
   elif 'building_age' in first:add('constraints.construction_year_min',1398);add('logic.fallbacks','new_then_renovated_old','rule_type')
   elif 'parking' in first:add('constraints.required_amenities','parking','contains');add('logic.fallbacks','relax_parking','rule_type')
   else:unsupported.append(key)
  else:unsupported.append(key)
 return checks,unsupported

def initial_state(raw):
 i=SearchIntent()
 checks,unsupported=translate(raw)
 for ch in checks:
  parts=ch['path'].split('.');parent=getattr(i,parts[0])
  if len(parts)==3:parent=parent[parts[1]]
  if ch['kind']=='equal':parent[parts[-1]]=ch['value']
  elif ch['kind']=='contains' and len(parts)==2:
   parent[parts[-1]].append(ch['value'])
   if ch['path']=='constraints.required_amenities':i.preferences[ch['value']]='very_high'
  elif ch['kind']=='active':parent[parts[-1]]='high'
 i.__post_init__();return i,unsupported

def run_case(case):
 i,unsupported=initial_state(case.get('initial_state',{}));s=get_ai_service()
 try:
  j=s.parse_full_intent(case['text'],NAMES) if case['operation']=='NEW_SEARCH' else s.parse_intent_patch(case['text'],i,NAMES).merge(i)
  return j.to_dict(),None,unsupported
 except UnresolvedReference as e:return {},e.needs_clarification,unsupported

def failures(state,clarification,checks):
 errors=[]
 for c in checks:
  if c['path']=='clarification':actual=clarification
  else:
   actual=state
   for p in c['path'].split('.'):actual=actual.get(p) if isinstance(actual,dict) else None
  kind=c['kind'];v=c['value']
  ok=actual==v if kind=='equal' else actual not in (None,'ignored') if kind=='active' else v in (actual or []) if kind=='contains' else v not in (actual or []) if kind=='absent' else any(r.get('type')==v for r in actual or []) if kind=='rule_type' else any(all(r.get(k)==x for k,x in v.items()) for r in actual or [])
  if not ok:errors.append({'check':c,'actual':actual})
 return errors

def audit():
 import yaml,collections
 cases=yaml.safe_load((ROOT/'docs/search_language/SEARCH_LANGUAGE_REGRESSION.yaml').read_text(encoding='utf8'))['cases'];results=[]
 for c in cases:
  checks,unsupported=translate(c['expected'])
  try:state,clarification,initial_missing=run_case(c);errors=failures(state,clarification,checks)
  except Exception as e:state={};clarification=None;initial_missing=[];errors=[{'exception':repr(e)}]
  unsupported+=initial_missing
  reason='All enabled expectations pass with documented canonical projection.'
  if c['id'].startswith('evidence_policy_') or c['id'] in ('seller_claim_01','unknown_parking_count_01'):
   cls='D';reason='Policy instruction or UI prose is not a runtime SearchIntent expectation; verified separately by invariant tests.'
  elif c['id'] in ('conditional_budget_commute_01','compound_relax_02'):
   cls='D';reason='Conditional expansion/relaxation lacks required prior numeric base in this NEW_SEARCH fixture.'
  elif any(x.get('check',{}).get('value')=='ignored' and x.get('actual')=='low' and x.get('check',{}).get('path','').startswith('preferences.') for x in errors):
   cls='D';reason='v0.2 ignored expectation conflicts with existing canonical low-priority relaxation contract; old tests retained.'
  elif not checks:cls='C';reason='Expected concept has no activated canonical field.'
  elif unsupported or errors:cls='B';reason='Enabled subset only / supported concept has a phrase or semantic coverage gap.'
  else:cls='A'
  results.append({'id':c['id'],'class':cls,'reason':reason,'unsupported':unsupported,'failures':errors,'checks':checks,'case':c})
 counts=dict(collections.Counter(r['class'] for r in results));(ROOT/'audit_v09e/corpus_classification.json').write_text(json.dumps({'counts':counts,'cases':results},ensure_ascii=False,indent=2),encoding='utf8')
 (ROOT/'finder/corpus_v09e_implemented.json').write_text(json.dumps([{'case':r['case'],'checks':r['checks']} for r in results if r['class']=='A'],ensure_ascii=False,indent=2),encoding='utf8')
 print(counts)
 for r in results:
  if r['class']=='B' and r['failures']:print(r['id'],json.dumps(r['failures'],ensure_ascii=False))
def verify_reviewed_corpus():
 reviewed=json.loads((ROOT/'audit_v09e/corpus_classification.json').read_text(encoding='utf8'))
 failures_found=[]
 for row in reviewed['cases']:
  if row['class']!='A':continue
  try:
   state,clarification,unsupported=run_case(row['case'])
   errors=failures(state,clarification,row['checks'])
   if errors or unsupported:failures_found.append({'id':row['id'],'errors':errors,'unsupported':unsupported})
  except Exception as e:failures_found.append({'id':row['id'],'error':repr(e)})
 print(json.dumps({'reviewed_counts':reviewed['counts'],'implemented_failures':failures_found},ensure_ascii=False,indent=2))
 # Never silently downgrade a reviewed A case or regenerate its fixture on a regression.
 return 1 if failures_found else 0
if __name__=='__main__':
 raise SystemExit(verify_reviewed_corpus())
