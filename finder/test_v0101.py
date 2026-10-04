"""v0.10.1 semantic and canonical editor contracts; no pixel assertions."""
from datetime import date
from unittest.mock import patch as mock_patch
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.core.management import call_command
from .ai import get_ai_service
from .calendar import jalali_year, current_jalali_year
from .conflicts import IntentConflict, request_conflicts
from .query import UnresolvedReference, QueryOperation, resolve_references
from .search import SearchIntent, active_filter_chips, remove_constraint
from .advanced import AdvancedFilters, initial_values, ui_context
from .models import Listing
from .ranking import eligible, score_listing
from .test_v010 import form_data, edited

NAMES=('ونک','میرداماد','ولیعصر','پاسداران')
LONG_ONE=('من ونک کار می‌کنم. دوخوابه حداقل ۱۰۰ متر می‌خوام، '
          'ترجیحاً نوساز، ولی اگه قدیمیه کامل بازسازی شده باشه. '
          'طبقه چهار به بالا فقط با آسانسور. '
          'دو تا پارکینگ ترجیح می‌دم ولی اگه خیلی نزدیک محل کار باشه یکی هم قبوله. '
          'نور از متراژ مهم‌تره، اجاره بیشتر از ۳۰ میلیون نشه '
          'و حیوان خانگی هم باید مجاز باشه.')
LONG_TWO=('من میرداماد کار می‌کنم؛ اول فقط ونک، اگه نبود اطرافش. '
          'دوخوابه حداقل ۱۱۰ متر، اجاره حداکثر ۲۵ میلیون. طبقه دوم یا سوم؛ '
          'آسانسور حتماً داشته باشه. حداقل دو پارکینگ غیرمزاحم لازم دارم. '
          'نوساز ترجیح می‌دم ولی قدیمی بازسازی‌شده هم قبوله. '
          'محله آروم و نور خوب می‌خوام. گربه دارم و حیوان خانگی باید مجاز باشه.')

def full(text):return get_ai_service().parse_full_intent(text,NAMES)
def refine(text,i):return get_ai_service().parse_intent_patch(text,i,NAMES).merge(i)
def listing(**kw):
    return Listing(**dict(dict(id=1,title='',description='',deposit=0,monthly_rent=0,area_m2=125,bedrooms=2,floor=2,construction_year=None,parking=True,elevator=True,natural_light=.8,quietness=.8,layout_quality=.8,access_quality=.8,distances={'vanak':1},data_source='synthetic'),**kw))


class AgeSemanticsTests(SimpleTestCase):
    def test_nowruz_boundaries_including_gregorian_and_jalali_leap_years(self):
        for day,year in [(date(2024,3,19),1402),(date(2024,3,20),1403),(date(2025,3,20),1403),(date(2025,3,21),1404),(date(2026,3,20),1404),(date(2026,3,21),1405),(date(2026,10,3),1405)]:
            with self.subTest(day=day):self.assertEqual(jalali_year(day),year)
    def test_dynamic_threshold_rolls_forward(self):
        with mock_patch('finder.calendar.current_jalali_year',return_value=1407):
            self.assertEqual(full('نوساز').constraints['construction_year_min'],1404)
    def test_neighboring_soft_parking_does_not_make_new_build_soft(self):
        self.assertEqual(full('نوساز می‌خوام و پارکینگ ترجیح می‌دم').constraints['construction_year_min'],current_jalali_year()-3)
    def test_neighboring_soft_light_does_not_make_new_build_soft(self):
        self.assertEqual(full('نور ترجیح می‌دم و ساختمان نوساز باشه').constraints['construction_year_min'],current_jalali_year()-3)
    def test_soft_age_explanation_uses_same_three_year_definition(self):
        i=full('نوساز ترجیح می‌دم');i.preferences['building_age']='high';year=current_jalali_year()
        self.assertTrue(any('حداکثر ۳ سال' in r for r in score_listing(listing(construction_year=year-3),i).reasons))
        self.assertFalse(any('نوساز' in r for r in score_listing(listing(construction_year=year-4),i).reasons))
    def test_unknown_year_is_ineligible_for_hard_new(self):
        i=full('نوساز');year=current_jalali_year()-3
        self.assertFalse(eligible(listing(),i))
        self.assertFalse(eligible(listing(construction_year=year-1),i))
        self.assertTrue(eligible(listing(construction_year=year),i))
    def test_unknown_year_has_no_soft_age_points(self):
        i=full('نوساز ترجیح می‌دم');r=score_listing(listing(),i)
        age=next(row for row in r.breakdown if row['key']=='building_age')
        self.assertIsNone(age['fit']);self.assertEqual(age['points'],0)
        self.assertTrue(eligible(listing(),i))
    def test_older_renovated_exception_remains_conditional(self):
        i=full('نوساز بهتره ولی قدیمی بازسازی‌شده هم قبوله')
        self.assertIsNone(i.constraints['construction_year_min']);self.assertFalse(i.constraints['renovation_required'])
        self.assertTrue(eligible(listing(construction_year=1390,renovated=True),i))
        self.assertFalse(eligible(listing(construction_year=1390,renovated=False,renovation_claim=False),i))
    def test_soft_refinement_replaces_hard_new(self):
        i=refine('نوساز ترجیح می‌دم',full('فقط نوساز'))
        self.assertIsNone(i.constraints['construction_year_min']);self.assertNotEqual(i.preferences['building_age'],'ignored')
    def test_age_presets_are_only_projections(self):
        i=SearchIntent()
        for age in (3,5,10):
            i=edited(i,age_preset=str(age));self.assertEqual(i.constraints['construction_year_min'],current_jalali_year()-age)
            self.assertEqual(initial_values(i)['age_preset'],str(age))
        i=edited(i,age_preset='custom',construction_year_min=1390);self.assertEqual(i.constraints['construction_year_min'],1390)
        i=edited(i,age_preset='any');self.assertIsNone(i.constraints['construction_year_min'])
    def test_custom_age_requires_a_year(self):
        form=AdvancedFilters(form_data(SearchIntent(),age_preset='custom'),intent=SearchIntent())
        self.assertFalse(form.is_valid());self.assertIn('construction_year_min',form.errors)

def age_phrase_test(text,hard):
    def test(self):
        i=full(text)
        self.assertEqual(i.constraints['construction_year_min'],current_jalali_year()-3 if hard else None)
        self.assertIn(i.preferences['building_age'],('medium','high','very_high'))
    return test
for n,text in enumerate(('نوساز','نوساز می‌خوام','خونه نوساز باشه','فقط نوساز','حتماً نوساز','ساختمان نوساز می‌خوام')):
    setattr(AgeSemanticsTests,f'test_hard_phrase_{n}',age_phrase_test(text,True))
for n,text in enumerate(('نوساز ترجیح می‌دم','نوساز بهتره','ترجیحاً نوساز','ساختمان جدیدتر بهتره')):
    setattr(AgeSemanticsTests,f'test_soft_phrase_{n}',age_phrase_test(text,False))


class WorkplaceExactTests(SimpleTestCase):
    def test_missing_workplace_clarifies_without_guessing(self):
        i=SearchIntent();before=i.to_dict()
        with self.assertRaises(UnresolvedReference) as error:refine('در محل کارم باشد',i)
        self.assertEqual(error.exception.needs_clarification,'workplace');self.assertEqual(i.to_dict(),before)
    def test_nearby_excludes_exact_when_requested(self):
        i=SearchIntent();i.context['workplace']='vanak'
        i=refine('خود محل کارم نه، اطرافش باشه',i)
        self.assertEqual(i.context['workplace'],'vanak');self.assertEqual(i.constraints['neighborhood_mode'],'nearby')
        self.assertEqual(i.constraints['neighborhoods'],['ونک']);self.assertEqual(i.constraints['excluded_neighborhoods'],['ونک'])
    def test_manual_workplace_is_used_by_formal_reference(self):
        i=edited(SearchIntent(),workplace='mirdamad')
        i=refine('خانه در محل کارم باشد',i);self.assertEqual(i.constraints['neighborhoods'],['میرداماد'])
        i=edited(i,workplace='none')
        with self.assertRaises(UnresolvedReference):refine('در محل کارم باشد',i)

def workplace_test(text,scope):
    def test(self):
        i=SearchIntent();i.context['workplace']='vanak'
        i=refine(text,i)
        self.assertEqual(i.work_location,'vanak');self.assertEqual(i.constraints['neighborhoods'],['ونک'])
        self.assertEqual(i.constraints['neighborhood_mode'],scope)
    return test
for n,text in enumerate(('در محل کارم باشد','داخل محل کارم باشد','در محل کارم باشه','داخل محل کارم باشه','همان محله محل کارم باشد','همون محله محل کارم باشه','خود محله محل کارم','خونه در محل کارم باشه','خانه در محل کارم باشد')):
    setattr(WorkplaceExactTests,f'test_exact_{n}',workplace_test(text,'exact'))
for n,text in enumerate(('نزدیک محل کارم باشد','نزدیک محل کارم باشه','اطراف محل کارم باشد','حوالی محل کارم')):
    setattr(WorkplaceExactTests,f'test_nearby_{n}',workplace_test(text,'nearby'))


class LongRequestTests(SimpleTestCase):
    def assert_first(self,i):
        c=i.constraints
        self.assertEqual(i.work_location,'vanak');self.assertEqual(c['bedrooms'],{'mode':'exact','value':2})
        self.assertEqual(c['area'],{'min':100,'max':None});self.assertIsNone(c['construction_year_min'])
        self.assertIn(i.preferences['building_age'],('medium','high','very_high'))
        self.assertFalse(c['renovation_required']);self.assertEqual(c['floor']['mode'],'any')
        self.assertNotIn('elevator',c['required_amenities']);self.assertNotIn('parking',c['required_amenities']);self.assertIsNone(c['parking_count_min'])
        self.assertEqual(c['max_rent'],30_000_000);self.assertEqual(c['pet_policy'],'allowed')
        self.assertIn({'higher':'base:natural_light','lower':'base:area'},i.logic['relative_priorities'])
        rules=i.logic['conditionals'];self.assertIn({'type':'require_elevator_if_floor_min','floor_min':4},rules)
        self.assertTrue(any(r['type']=='require_renovation_if_old' for r in rules))
        self.assertTrue(any(r.get('preferred_count')==2 and r.get('close_count')==1 for r in rules))
    def test_first_complete_query(self):self.assert_first(full(LONG_ONE))
    def test_second_complete_query_keeps_independent_dimensions(self):
        i=full(LONG_TWO);c=i.constraints
        self.assertEqual(i.work_location,'mirdamad');self.assertEqual(c['neighborhoods'],['ونک']);self.assertEqual(c['neighborhood_mode'],'exact')
        self.assertEqual(c['bedrooms'],{'mode':'exact','value':2});self.assertEqual(c['area']['min'],110);self.assertEqual(c['max_rent'],25_000_000)
        self.assertEqual(c['floor']['value'],[2,3]);self.assertIn('elevator',c['required_amenities']);self.assertIn('parking',c['required_amenities'])
        self.assertEqual(c['parking_count_min'],2);self.assertTrue(c['parking_non_tandem_required']);self.assertEqual(c['pet_policy'],'allowed')
        self.assertIsNone(c['construction_year_min']);self.assertFalse(c['renovation_required'])
        self.assertEqual(i.preferences['quietness'],'high');self.assertEqual(i.preferences['natural_light'],'high')
        self.assertEqual(i.logic['fallbacks'],[{'type':'neighborhood_scope','to':'nearby','trigger_min_results':1}])
        self.assertTrue(any(r['type']=='require_renovation_if_old' for r in i.logic['conditionals']))
    def test_long_patch_preserves_unmentioned_context_and_evidence(self):
        i=full('من میرداماد کار می‌کنم؛ دوخوابه حداقل ۱۱۰ متر، طبقه دوم یا سوم؛ گربه دارم؛ پارکینگ اختصاصی حتماً لازم دارم')
        old=i.copy();i=refine('حالا اجاره حداکثر ۳۰ میلیون باشد؛ نور از متراژ مهم‌تره؛ آسانسور حتماً داشته باشه؛ محله آروم باشه و انباری هم حتماً لازم دارم',i)
        for key in ('bedrooms','area','floor','pet_policy','parking_dedicated_required'):self.assertEqual(i.constraints[key],old.constraints[key])
        self.assertEqual(i.context,old.context);self.assertEqual(i.constraints['max_rent'],30_000_000)
        self.assertTrue({'parking','elevator','storage'}<=set(i.constraints['required_amenities']))
        self.assertEqual(i.preferences['natural_light'],'very_high');self.assertEqual(i.preferences['area'],'low')
        self.assertEqual(i.preferences['quietness'],'high');self.assertEqual(len(i.logic['relative_priorities']),1)
    def test_long_patch_removes_only_explicit_parking_and_replaces_bedrooms(self):
        i=full(LONG_TWO)
        i=refine('نه، سه خواب می‌خوام؛ پارکینگ دیگه مهم نیست؛ اجاره حداکثر ۳۰ میلیون؛ نور خوب همچنان مهمه و آرامش محله هم مهم باشه',i)
        self.assertEqual(i.constraints['bedrooms'],{'mode':'exact','value':3});self.assertEqual(i.constraints['max_rent'],30_000_000)
        self.assertIsNone(i.constraints['parking_count_min']);self.assertFalse(i.constraints['parking_non_tandem_required']);self.assertNotIn('parking',i.constraints['required_amenities'])
        self.assertIn('elevator',i.constraints['required_amenities']);self.assertEqual(i.work_location,'mirdamad');self.assertEqual(i.constraints['area']['min'],110)
        self.assertEqual(i.constraints['floor']['value'],[2,3]);self.assertEqual(i.constraints['pet_policy'],'allowed')
        self.assertEqual(i.constraints['neighborhoods'],['ونک']);self.assertEqual(len(i.logic['fallbacks']),1)
    def test_long_new_search_drops_all_unrelated_previous_state(self):
        before=full(LONG_TWO);after=full('من ولیعصر کار می‌کنم؛ سه خوابه حداقل ۸۰ متر می‌خوام؛ اجاره حداکثر ۲۰ میلیون. طبقه اول یا دوم؛ نور خوب مهمه و محله آروم باشه.')
        self.assertEqual(after.work_location,'valiasr');self.assertEqual(after.constraints['bedrooms'],{'mode':'exact','value':3});self.assertEqual(after.constraints['area']['min'],80)
        self.assertEqual(after.constraints['max_rent'],20_000_000);self.assertEqual(after.constraints['floor']['value'],[1,2]);self.assertEqual(after.constraints['neighborhoods'],[])
        self.assertEqual(after.constraints['required_amenities'],[]);self.assertEqual(after.constraints['pet_policy'],'any');self.assertIsNone(after.constraints['parking_count_min'])
        self.assertEqual(after.logic,SearchIntent().logic);self.assertNotEqual(before.to_dict(),after.to_dict())
    def test_preferred_count_never_excludes_one_parking(self):
        i=full(LONG_ONE)
        row=listing(description='یک پارکینگ، حیوان خانگی مجاز',construction_year=1404)
        self.assertTrue(eligible(row,i))
        close=score_listing(row,i);row.distances={'vanak':5};far=score_listing(row,i)
        self.assertEqual(next(r['fit'] for r in close.breakdown if r['key']=='parking'),1)
        self.assertEqual(next(r['fit'] for r in far.breakdown if r['key']=='parking'),.5)
    def test_soft_count_exception_cannot_waive_a_separate_hard_parking_requirement(self):
        i=full(LONG_ONE);i.constraints['required_amenities']=['parking']
        self.assertFalse(eligible(listing(parking=False,description='حیوان خانگی مجاز',construction_year=1404),i))


class ContradictionTests(SimpleTestCase):
    def test_bedrooms_conflict(self):self.assertEqual(request_conflicts('فقط دو خواب و فقط سه خواب')[0]['field'],'bedrooms')
    def test_floor_conflict(self):self.assertEqual(request_conflicts('حداکثر طبقه دو و حداقل طبقه چهار')[0]['field'],'floor')
    def test_rent_conflict(self):self.assertEqual(request_conflicts('اجاره حداکثر ۲۰ میلیون و حداقل ۳۰ میلیون')[0]['field'],'max_rent')
    def test_new_and_old_conflict(self):self.assertEqual(request_conflicts('حتماً نوساز باشه ولی حتماً قدیمی باشه')[0]['field'],'construction_year_min')
    def test_parser_exposes_structured_conflict(self):
        with self.assertRaises(IntentConflict) as error:full('فقط دو خواب و فقط سه خواب')
        self.assertEqual(error.exception.conflicts[0]['code'],'incompatible_hard_requirements')
    def test_valid_exceptions_and_fallback_are_not_conflicts(self):
        for q in ('پارکینگ لازم دارم ولی اگر نزدیک محل کار باشه لازم نیست','نوساز ترجیح می‌دم ولی قدیمی بازسازی‌شده هم قبوله','طبقه چهار به بالا فقط اگر آسانسور داشته باشه','اول فقط ونک، اگه نبود اطرافش',LONG_ONE,LONG_TWO):
            with self.subTest(q=q):self.assertEqual(request_conflicts(q),[]);full(q)
    def test_later_bedroom_replacement_is_not_a_conflict(self):
        i=refine('نه، سه خواب می‌خوام',full('فقط دو خواب'));self.assertEqual(i.constraints['bedrooms'],{'mode':'exact','value':3})
    def test_rent_and_deposit_numbers_do_not_conflict(self):self.assertEqual(request_conflicts('اجاره حداکثر ۲۰ میلیون و ودیعه حداقل ۳۰ میلیون'),[])


class FilterProjectionTests(SimpleTestCase):
    def test_count_is_user_level_obligations_not_raw_keys(self):
        i=full('دوخوابه حداقل ۱۰۰ متر، طبقه دوم یا سوم؛ دو تا پارکینگ غیرمزاحم لازم دارم')
        rows=active_filter_chips(i)
        self.assertEqual([r['key'] for r in rows],['bedrooms','area','floor','amenity:parking','parking_count_min','parking_non_tandem_required'])
        self.assertEqual(ui_context(i)['filter_count'],6);self.assertEqual(len(ui_context(i)['visible_filter_chips']),4);self.assertEqual(ui_context(i)['extra_filter_count'],2)
    def test_logic_counts_as_one_group_and_is_removable(self):
        i=full(LONG_ONE);rows=active_filter_chips(i)
        self.assertEqual(sum(r['key']=='logic' for r in rows),1)
        self.assertEqual(remove_constraint(i,'logic').logic,SearchIntent().logic)
    def test_chip_cleanup_preserves_unrelated_fields(self):
        i=full(LONG_TWO);after=remove_constraint(i,'floor')
        self.assertEqual(after.constraints['floor'],SearchIntent().constraints['floor'])
        self.assertEqual(after.constraints['parking_count_min'],2);self.assertEqual(after.logic['fallbacks'],i.logic['fallbacks'])
    def test_chip_cleanup_removes_related_logic(self):
        i=full(LONG_ONE);i=remove_constraint(i,'preference:natural_light')
        self.assertEqual(i.preferences['natural_light'],'ignored');self.assertEqual(i.logic['relative_priorities'],[])
        self.assertEqual(len(i.logic['conditionals']),3)
    def test_disclosure_is_not_state_and_noop_preserves_everything(self):
        i=full(LONG_ONE);data=form_data(i);data['advanced-expanded']='on'
        f=AdvancedFilters(data,intent=i);self.assertTrue(f.is_valid(),f.errors)
        after=f.apply().to_dict();before=i.to_dict();after['metadata']=before['metadata'];self.assertEqual(after,before)
    def test_shared_form_fields_render_once_across_simple_and_advanced(self):
        f=AdvancedFilters(intent=SearchIntent())
        names=[field.name for _,_,fields in f.simple_groups+f.advanced_groups for field in fields]
        self.assertEqual(len(names),len(set(names)));self.assertEqual(set(names),set(f.fields))


class FinalizationIntegrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):call_command('seed_demo',verbosity=0)
    def put(self,i):s=self.client.session;s['intent']=i.to_dict();s.save()
    @override_settings(DATA_MODE='synthetic')
    def test_browse_new_label_uses_same_dynamic_threshold(self):
        row=Listing.objects.first();row.construction_year=current_jalali_year()-4;row.save()
        r=self.client.get(reverse('browse'));item=next(x for x in r.context['items'] if x.listing.pk==row.pk)
        self.assertEqual(item.label,'')
        row.construction_year=current_jalali_year()-3;row.save()
        r=self.client.get(reverse('browse'));item=next(x for x in r.context['items'] if x.listing.pk==row.pk)
        self.assertEqual(item.label,'نوساز')
    def test_home_filter_entry_does_not_require_a_prompt(self):
        r=self.client.get(reverse('home'));self.assertContains(r,'data-advanced-open');self.assertContains(r,'id="advanced-filters"');self.assertNotIn('intent',self.client.session)
        i=SearchIntent();r=self.client.post(reverse('home'),{'action':'advanced',**form_data(i,bedrooms='2',age_preset='3')})
        self.assertRedirects(r,reverse('intent'));after=SearchIntent(**self.client.session['intent'])
        self.assertEqual(after.constraints['bedrooms']['value'],2);self.assertEqual(after.constraints['construction_year_min'],current_jalali_year()-3)
    def test_home_editor_starts_empty_after_a_previous_search(self):
        self.put(full(LONG_TWO));r=self.client.get(reverse('home'));self.assertEqual(r.context['advanced_form'].initial['bedrooms'],'')
    def test_results_one_unified_control_no_public_quick_row(self):
        self.put(full(LONG_TWO));r=self.client.get(reverse('results'))
        self.assertContains(r,'class="secondary unified-filters"',count=1);self.assertNotContains(r,'class="precision-filters"');self.assertNotContains(r,'class="filter-row"')
        self.assertContains(r,'فیلترهای اصلی');self.assertContains(r,'class="advanced-expansion"');self.assertContains(r,'class="filter-section"')
    def test_nlp_chip_removal_updates_canonical_state(self):
        i=full(LONG_TWO);self.put(i);r=self.client.post(reverse('results'),{'action':'remove','key':'bedrooms'})
        self.assertRedirects(r,reverse('results'));after=SearchIntent(**self.client.session['intent'])
        self.assertEqual(after.constraints['bedrooms']['mode'],'any');self.assertEqual(after.constraints['parking_count_min'],2)
    def test_sidebar_edit_outside_scroll_region(self):
        self.put(full(LONG_TWO));r=self.client.get(reverse('results'));html=r.content.decode()
        self.assertContains(r,'class="criteria-scroll"');self.assertContains(r,'criteria-responsive')
        self.assertLess(html.index('class="sidebar-heading"'),html.index('class="criteria-scroll"'))
        self.assertContains(r,'aria-label="جزئیات معیارهای انتخاب"')
    def test_success_feedback_is_neutral(self):
        i=full('دوخوابه');self.put(i)
        r=self.client.post(reverse('results'),{'action':'advanced',**form_data(i,max_rent=30)},follow=True)
        self.assertContains(r,'✓ فیلترها به‌روزرسانی شدند');self.assertContains(r,'update-feedback');self.assertNotContains(r,'فیلتر اعمال شد')
    def test_natural_update_feedback_is_readable(self):
        self.put(full('دوخوابه'));r=self.client.post(reverse('results'),{'update':'پارکینگ حتماً لازم دارم'},follow=True)
        self.assertContains(r,'درخواستت به‌روزرسانی شد');self.assertNotContains(r,'برداشت جدید')
    def test_contradiction_pauses_ranking_and_preserves_last_valid_intent(self):
        i=full('دوخوابه');self.put(i)
        with mock_patch('finder.views.decorated_results') as rank:
            r=self.client.post(reverse('results'),{'update':'فقط دو خواب و فقط سه خواب'},follow=True)
            rank.assert_not_called()
        self.assertEqual(self.client.session['intent'],i.to_dict());self.assertContains(r,'دو شرط ناسازگار');self.assertNotContains(r,'با ترکیب این خواسته‌ها گزینه‌ای پیدا نکردیم')
        self.assertContains(r,'ویرایش خواسته‌ها');self.assertEqual(self.client.session['pending_query']['reference'],'conflict')
    def test_home_contradiction_creates_no_canonical_intent(self):
        r=self.client.post(reverse('intent'),{'query':'اجاره حداکثر ۲۰ میلیون و حداقل ۳۰ میلیون'},follow=True)
        self.assertContains(r,'حداقل اجاره از حداکثر اجاره');self.assertNotIn('intent',self.client.session)
    def test_manual_resolution_clears_conflict(self):
        i=full('دوخوابه');self.put(i);self.client.post(reverse('results'),{'update':'فقط دو خواب و فقط سه خواب'})
        self.client.post(reverse('results'),{'action':'advanced',**form_data(i,bedrooms='3')})
        self.assertNotIn('pending_query',self.client.session);self.assertEqual(self.client.session['intent']['constraints']['bedrooms']['value'],3)
    def test_long_new_search_replaces_session_and_clears_old_rules(self):
        self.put(full(LONG_TWO));r=self.client.post(reverse('results'),{'update':LONG_ONE,'operation':'NEW_SEARCH'})
        self.assertEqual(r.status_code,302);after=SearchIntent(**self.client.session['intent'])
        self.assertEqual(after.work_location,'vanak');self.assertEqual(after.constraints['neighborhoods'],[]);self.assertEqual(after.logic['fallbacks'],[])
    def test_missing_workplace_formal_reference_uses_existing_clarification(self):
        r=self.client.post(reverse('intent'),{'query':'در محل کارم باشد'},follow=True)
        self.assertContains(r,'کجا کار می‌کنی؟');self.assertNotIn('intent',self.client.session)
