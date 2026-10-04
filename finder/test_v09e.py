"""v0.9-E fixed-fixture corpus and adversarial contract tests."""
import json
from pathlib import Path
import sys
from django.test import SimpleTestCase
from .ai import get_ai_service
from .models import Listing
from .evidence_features import extract_listing_evidence, evidence_feature_state, evidence_requirement_matches, YES, NO, UNKNOWN
from .query import QueryOperation, classify_query
from .ranking import eligible, rank_listings
from .search import SearchIntent
from .language import floor_constraint, bedroom_constraint, area_constraint, extract_money
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'audit_v09e'))
from corpus_harness import run_case, failures

class ImplementedCorpusTests(SimpleTestCase):
    pass

def corpus_test(row):
    def test(self):
        state,clarification,unsupported=run_case(row['case'])
        self.assertFalse(unsupported)
        self.assertEqual(failures(state,clarification,row['checks']),[],row['case']['text'])
    return test

for row in json.loads(Path(__file__).with_name('corpus_v09e_implemented.json').read_text(encoding='utf8')):
    setattr(ImplementedCorpusTests,'test_'+row['case']['id'],corpus_test(row))

class AuditContractTests(SimpleTestCase):
    def listing(self, text='', **kw):
        defaults=dict(id=1,title='',description=text,deposit=0,monthly_rent=0,area_m2=125,bedrooms=2,floor=2,construction_year=1401,parking=True,elevator=True,distances={'vanak':1},data_source='synthetic',natural_light=.8,quietness=.8,layout_quality=.8,access_quality=.8)
        return Listing(**(defaults|kw))
    def full(self,text):return get_ai_service().parse_full_intent(text,('ونک','ولیعصر'))
    def patch(self,text,current):return get_ai_service().parse_intent_patch(text,current,('ونک','ولیعصر')).merge(current)
    def test_unrelated_numbers_never_count_as_parking(self):
        for text in ['طبقه 5 پارکینگ غیر مزاحم','طبقه ۵\nپارکینگ غیرمزاحم','پارکینگ 3سال ساخت','پارکینگ 500 میلیون رهن','125 متر 2 خواب پارکینگ','طبقه دوم پارکینگ','بدون پارکینگ ۵۰۰ رهن']:
            with self.subTest(text=text):self.assertEqual(extract_listing_evidence(self.listing(text,parking=None)).parking_count,None)
    def test_separate_numbers(self):
        text='125 متر 2 خواب 2 پارکینگ'
        self.assertEqual(extract_listing_evidence(self.listing(text)).parking_count,2)
        self.assertEqual(bedroom_constraint(text),{'mode':'exact','value':2})
        self.assertEqual(area_constraint('حداقل '+text),{'min':125,'max':None})
        self.assertEqual(floor_constraint('طبقه 12 پارکینگ'),{'mode':'exact','value':12,'excluded':[]})
    def test_unknown_hard_evidence_rejected(self):
        row=self.listing('')
        for c in [{'pet_policy':'allowed'},{'parking_count_min':2},{'parking_non_tandem_required':True},{'hvac_required':['split_ac']},{'accessibility_required':['wheelchair']}]:
            with self.subTest(c=c):self.assertFalse(evidence_requirement_matches(row,c))
    def test_explicit_negatives_across_evidence_families(self):
        e=extract_listing_evidence(self.listing('حیوان خانگی مجاز نیست؛ پارکینگ غیرمزاحم نیست؛ پارکینگ سندی ندارد؛ تک واحدی نیست؛ مبله نیست'))
        self.assertEqual(e.pet_policy,NO);self.assertEqual(e.parking_non_tandem,NO);self.assertEqual(e.parking_dedicated,NO)
        self.assertEqual(evidence_feature_state(e,'single_unit'),NO);self.assertEqual(e.furnishing,'unfurnished')
    def test_negated_hvac_does_not_become_yes(self):
        row=self.listing('فاقد پکیج؛ چیلر ندارد؛ بدون کولر گازی')
        e=extract_listing_evidence(row)
        for k in ['package_heating','chiller','split_ac']:self.assertEqual(evidence_feature_state(e,k),NO)
        self.assertEqual(evidence_feature_state(e,'fan_coil'),UNKNOWN)
    def test_furnishing_scope(self):
        for text in ['لابی مبله','آشپزخانه فرنیش بوش','نیمه فرنیش','نیمه مبله','مبله و غیر مبله']:
            with self.subTest(text=text):self.assertEqual(extract_listing_evidence(self.listing(text)).furnishing,'unknown')
        self.assertEqual(extract_listing_evidence(self.listing('واحد کاملا مبله')).furnishing,'furnished')
        self.assertEqual(extract_listing_evidence(self.listing('واحد غیرمبله')).furnishing,'unfurnished')
    def test_broad_access_and_view_are_not_specific_evidence(self):
        e=extract_listing_evidence(self.listing('دسترسی عالی؛ تک بازدید بازدید = قرارداد؛ ویو بازسازی شده؛ ویو شهرک لاله؛ پارکینگ انباری آسانسور دسترسی عالی به مترو'))
        for k in ['good_road_access','open_view','city_view','elevator_from_parking']:self.assertEqual(evidence_feature_state(e,k),UNKNOWN)
    def test_parking_ramp_is_not_wheelchair_entry(self):
        e=extract_listing_evidence(self.listing('پارکینگ بدون مزاحم با دسترسی آسان به رمپ'))
        self.assertEqual(evidence_feature_state(e,'ramp'),UNKNOWN)
        self.assertEqual(evidence_feature_state(extract_listing_evidence(self.listing('ورودی ساختمان دارای رمپ مناسب ویلچر')),'ramp'),YES)
    def test_pet_cannot_infer_permission_from_quiet_animal(self):
        self.assertEqual(extract_listing_evidence(self.listing('با حیوان خانگی بی صدا')).pet_policy,UNKNOWN)
        self.assertEqual(extract_listing_evidence(self.listing('مشکلی با حیوان خانگی دارد')).pet_policy,UNKNOWN)
    def test_explicit_real_text_spelling_variants(self):
        examples = [('پکیچ','package_heating'),('وشوفاژ','radiator'),('کولر ابی','water_cooler'),('دوربین های مداربسته','cctv'),('سرایدارمقیم','concierge'),('تک واحد','single_unit'),('برج کم جمعیت','low_density'),('ویوی ابدی به کوهستان','mountain_view'),('ویو شهر و کوهستان','mountain_view'),('همکف بدون پله','step_free'),('2پارکینگ باکس سندی','parking_dedicated')]
        for text,key in examples:
            with self.subTest(text=text):self.assertEqual(evidence_feature_state(extract_listing_evidence(self.listing(text)),key),YES)
        for text,key in [('خانواده کم جمعیت','low_density'),('همکف','step_free'),('دوربین','cctv')]:
            with self.subTest(text=text):self.assertEqual(evidence_feature_state(extract_listing_evidence(self.listing(text)),key),UNKNOWN)
    def test_parking_removal_clears_all_evidence_and_rules(self):
        i=self.full('دو تا پارکینگ غیرمزاحم لازم دارم')
        i=self.patch('پارکینگ مهم نیست اگر نزدیک محل کار باشه',i)
        i.logic['relative_priorities']=[{'higher':'base:parking','lower':'base:area'}]
        i.logic['fallbacks']=[{'type':'relax_parking','trigger_min_results':1}]
        i=self.patch('پارکینگ دیگه مهم نیست و تا ۳۰ میلیون اجاره هم اوکیه',i)
        self.assertIsNone(i.constraints['parking_count_min']);self.assertFalse(i.constraints['parking_non_tandem_required'])
        self.assertNotIn('parking',i.constraints['required_amenities']);self.assertEqual(i.evidence_preferences['parking_non_tandem'],'ignored')
        self.assertFalse(any(i.logic.values()));self.assertEqual(i.constraints['max_rent'],30_000_000)
    def test_deposit_removal_preserves_rent(self):
        i=self.full('۸۰۰ میلیون ودیعه و اجاره بیشتر از ۲۵ میلیون نشه')
        j=self.patch('ودیعه رو بیخیال ولی اجاره همون ۲۵ بمونه',i)
        self.assertIsNone(j.constraints['max_deposit']);self.assertIsNone(j.targets['deposit']);self.assertEqual(j.constraints['max_rent'],i.constraints['max_rent'])
    def test_unmentioned_budget_preserved(self):
        i=self.full('۸۰۰ میلیون ودیعه و اجاره بیشتر از ۲۵ میلیون نشه')
        j=self.patch('حالا تا ۳۵ میلیون اجاره اوکیه، ولی ودیعه قبلی عوض نشه',i)
        self.assertEqual(j.constraints['max_deposit'],i.constraints['max_deposit'])
        self.assertIsNone(extract_money('ودیعه رو بیخیال ولی اجاره تا ۳۰ میلیون',('ودیعه',)))
    def test_context_and_patch_preserve_earlier_state(self):
        i=self.full('حداقل ۱۰۰ متر، طبقه دوم یا سوم، دوخوابه نزدیک ونک می خوام')
        i.context['workplace']='vanak'
        for text in ['حالا آسانسور هم حتما داشته باشه','اطرافش هم خوبه','نزدیک محل کارم','این بار فقط خود ونک باشه، بقیه چیزها همون']:
            j=self.patch(text,i)
            for key in ['bedrooms','floor','area']:self.assertEqual(j.constraints[key],i.constraints[key])
            self.assertEqual(j.context,i.context)
    def test_new_search_clears_stale_logic_and_evidence(self):
        i=self.full('دو پارکینگ غیرمزاحم لازم دارم')
        i.logic['fallbacks']=[{'type':'relax_parking','trigger_min_results':1}]
        text='حداقل ۱۰۰ متر، طبقه دوم یا سوم، دوخوابه می خوام'
        self.assertEqual(classify_query(text,i),QueryOperation.NEW_SEARCH)
        j=self.full(text);self.assertFalse(any(j.logic.values()));self.assertIsNone(j.constraints['parking_count_min']);self.assertTrue(all(v=='ignored' for v in j.evidence_preferences.values()))
    def test_conditional_floor_eligibility(self):
        for text in ['طبقه چهار به بالا فقط اگر آسانسور داشته باشه','طبقه بالا دوست دارم ولی اگر آسانسور نداره بالاتر از دوم نباشه']:
            i=self.full(text);self.assertEqual(i.constraints['floor']['mode'],'any');self.assertNotIn('elevator',i.constraints['required_amenities'])
            self.assertTrue(eligible(self.listing(floor=2,elevator=False),i));self.assertFalse(eligible(self.listing(floor=5,elevator=False),i));self.assertTrue(eligible(self.listing(floor=5,elevator=True),i))
    def test_latest_conditional_threshold_replaces_old_rule(self):
        i=self.full('طبقه چهار به بالا فقط اگر آسانسور داشته باشه')
        j=self.patch('طبقه ششم به بالا فقط اگر آسانسور داشته باشه',i)
        self.assertEqual(j.logic['conditionals'],[{'type':'require_elevator_if_floor_min','floor_min':6}])
        self.assertTrue(eligible(self.listing(floor=5,elevator=False),j))
        k=self.patch('آسانسور دیگه مهم نیست',j);self.assertFalse(k.logic['conditionals'])
    def test_old_building_conditions(self):
        for text,field in [('نوساز بهتره ولی قدیمی بازسازی شده هم قبوله','renovated'),('نوساز بهتره ولی اگه قدیمیه حتما آسانسور داشته باشه','elevator')]:
            i=self.full(text)
            self.assertFalse(eligible(self.listing(construction_year=1380,**{field:False}),i))
            self.assertTrue(eligible(self.listing(construction_year=1380,**{field:True}),i))
            self.assertTrue(eligible(self.listing(construction_year=1401,**{field:False}),i))
    def test_conditional_rent_and_area(self):
        i=self.full('حداقل ۱۲۰ متر و اجاره بیشتر از ۲۵ میلیون نشه');i.context['workplace']='vanak'
        j=self.patch('تا ۳۰ میلیون اجاره اوکیه ولی فقط اگر خیلی نزدیک محل کار باشه',i)
        self.assertEqual(j.constraints['max_rent'],25_000_000)
        self.assertTrue(eligible(self.listing(monthly_rent=29_000_000),j));self.assertFalse(eligible(self.listing(monthly_rent=29_000_000,distances={'vanak':6}),j));self.assertFalse(eligible(self.listing(monthly_rent=31_000_000),j))
        j=self.patch('متراژ کمتر اوکیه اگر رفت و آمد خیلی بهتر بشه',i)
        self.assertTrue(eligible(self.listing(area_m2=100),j));self.assertFalse(eligible(self.listing(area_m2=100,distances={'vanak':6}),j))
        k=self.patch('متراژ دیگه مهم نیست',j);self.assertFalse(k.logic['conditionals'])
    def test_conditional_parking_preserves_far_requirement(self):
        for text,close in [('پارکینگ مهم نیست اگر نزدیک محل کار باشه',''),('پارکینگ رو می تونم بیخیال شم اگه مترو خیلی نزدیک باشه','نزدیک مترو')]:
            i=self.full('پارکینگ حتما داشته باشه');i.context['workplace']='vanak'
            j=self.patch(text,i)
            self.assertTrue(eligible(self.listing(close,parking=False),j));self.assertFalse(eligible(self.listing(parking=False,distances={'vanak':6}),j))
    def test_conditional_and_fallback_relax_rich_parking_only_when_active(self):
        i=self.full('دو پارکینگ غیرمزاحم لازم دارم');i.context['workplace']='vanak'
        j=self.patch('پارکینگ مهم نیست اگر نزدیک محل کار باشه',i)
        self.assertEqual(j.constraints['parking_count_min'],2)
        self.assertTrue(eligible(self.listing(parking=False),j))
        self.assertFalse(eligible(self.listing(parking=False,distances={'vanak':6}),j))
        k=self.patch('اول پارکینگ دارها، اگر چیزی نبود بدون پارکینگ هم ببین',i)
        results=rank_listings([self.listing(parking=False)],k)
        self.assertEqual(len(results),1);self.assertEqual(results[0].fallback_stage,1)
    def test_relative_and_minimum_do_not_change_eligibility(self):
        i=self.full('حداقل ۱۰۰ متر');j=self.patch('نور از متراژ مهم تره',i)
        self.assertEqual(i.preferences['area'],'ignored');self.assertEqual(j.constraints,i.constraints)
        small=self.listing(area_m2=105,natural_light=.95);big=self.listing(id=2,area_m2=150,natural_light=.1)
        self.assertEqual(rank_listings([big,small],j)[0].listing.id,small.id)
    def test_fallback_stages_do_not_run_unnecessarily(self):
        i=self.full('اول تا ۲۰ میلیون اجاره بگرد، اگه نبود تا ۲۵ هم اوکیه')
        self.assertEqual(i.constraints['max_rent'],20_000_000)
        cheap=self.listing(monthly_rent=19_000_000);costly=self.listing(id=2,monthly_rent=24_000_000)
        r=rank_listings([cheap,costly],i);self.assertEqual(len(r),1);self.assertEqual(r[0].fallback_stage,0)
        r=rank_listings([costly],i);self.assertEqual(r[0].fallback_stage,1);self.assertTrue(r[0].fallback_notes);self.assertTrue(r[0].reasons)
        j=self.patch('تا ۳۰ میلیون اجاره اوکیه',i);self.assertFalse(j.logic['fallbacks'])
    def test_fallback_bedrooms_threshold_and_cleanup(self):
        i=self.full('اول دوخوابه، اگه کم بود سه خوابه هم نشون بده')
        r=rank_listings([self.listing(),self.listing(id=2,bedrooms=3)],i);self.assertEqual(len(r),2);self.assertEqual(r[0].fallback_stage,1)
        r=rank_listings([self.listing(id=n) for n in range(1,4)],i);self.assertEqual(r[0].fallback_stage,0)
        j=self.patch('دوخوابه حتما باشه',i);self.assertFalse(j.logic['fallbacks'])
    def test_fallback_age_and_location(self):
        i=self.full('اول نوساز، اگه نبود قدیمی بازسازی شده هم نشون بده')
        r=rank_listings([self.listing(construction_year=1380,renovated=True)],i);self.assertEqual(len(r),1);self.assertEqual(r[0].fallback_stage,1)
        self.assertFalse(rank_listings([self.listing(construction_year=1380,renovated=False)],i))
        i=self.full('اول فقط ونک، اگه نبود اطرافش');self.assertEqual(i.constraints['neighborhood_mode'],'exact');self.assertEqual(i.logic['fallbacks'][0]['type'],'neighborhood_scope')
        j=self.patch('این بار فقط خود ونک باشه، بقیه چیزها همون',i);self.assertFalse(j.logic['fallbacks'])

def parking_variant(text,count=2,non=False):
    def test(self):
        e=extract_listing_evidence(self.listing(text,parking=None))
        self.assertEqual(e.parking_count,count)
        self.assertEqual(e.parking_non_tandem,YES if non else UNKNOWN)
    return test
for n,text in enumerate(['2پارکینگ','۲ پارکینگ','دو پارکینگ','دو تا پارکینگ','2تاپارکینگ','دو جای پارک','۲ عدد پارکینگ']):setattr(AuditContractTests,f'test_parking_count_variant_{n}',parking_variant(text))
for n,text in enumerate(['پارکینگ غیر مزاحم','پارکینگ غیرمزاحم','پارکینگ بدون مزاحم','پارکینگ مستقل','پارکینگ سندی غیر مزاحم','پارکینگ سندی بدون مزاحم','پارکینگ اختصاصی بدون مزاحم','پارکینگ سرراست و بدون مزاحم']):setattr(AuditContractTests,f'test_non_tandem_variant_{n}',parking_variant(text,None,True))
for n,text in enumerate(['دو پارکینگ هر دو مستقل','دو پارکینگ سندی بدون مزاحم','ملک دارای 2 پارکینگ بدون مزاحم و مستقل','2پارکینگ سندی غیر مزاحم']):setattr(AuditContractTests,f'test_both_parking_variant_{n}',parking_variant(text,2,True))
