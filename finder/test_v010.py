"""Canonical manual/NLP controls and display/session lifecycle regressions."""
from django.test import SimpleTestCase,TestCase,Client,override_settings
from django.urls import reverse
from django.core.management import call_command
from .advanced import AdvancedFilters,initial_values,ui_context,remove_logic,reset_filters
from .search import SearchIntent,apply_filters,filter_initial
from .ai import get_ai_service
from .location_registry import display_location,location_key,source_labels,REGISTRY
from .models import Listing
from .query import resolve_references
from .ranking import eligible,rank_listings

NAMES=('ونک','میرداماد','ولیعصر','پاسداران','کن')
def full(text):return get_ai_service().parse_full_intent(text,NAMES)
def patch(text,current):return get_ai_service().parse_intent_patch(text,current,NAMES).merge(current)
def form_data(intent,**changes):
    values=initial_values(intent);values.update(changes)
    return {'advanced-'+k:([] if v is None else 'on' if v is True else '' if v is False else v) for k,v in values.items()}
def edited(intent,**changes):
    form=AdvancedFilters(form_data(intent,**changes),intent=intent,neighborhoods=NAMES)
    if not form.is_valid():raise AssertionError(form.errors.as_json())
    return form.apply()

class ManualControlTests(SimpleTestCase):
    def test_shared_form_no_op_retains_structured_and_logic(self):
        i=full('حداقل ۱۰۰ متر، طبقه دوم یا سوم، دوخوابه می‌خوام')
        i=patch('نور از متراژ مهم‌تره',i)
        i.constraints['floor']['excluded']=['basement']
        i.constraints['transport_required']=['near_metro']
        i.constraints['neighborhoods']=['ونک','میرداماد']
        i.constraints['max_rent']=25_500_001
        after=edited(i)
        for key in ('constraints','preferences','evidence_preferences','context','targets','logic'):self.assertEqual(getattr(after,key),getattr(i,key),key)
    def test_all_advanced_families_roundtrip(self):
        i=edited(SearchIntent(),neighborhood='ونک',neighborhood_scope='nearby',workplace='mirdamad',commute='very_high',max_deposit='700',max_rent='25',flexibility='flexible',area_min=100,area_max=180,bedrooms='2',floor_mode='allowed',floor_value='۲،۳',construction_year_min=1395,renovation_required=True,parking='required',parking_count_min=2,parking_non_tandem_required=True,parking_dedicated_required=True,elevator=True,storage=True,balcony=True,pet_policy='allowed',furnishing='unfurnished',natural_light='very_high',quietness='high',building_density='single_unit',security_required=['cctv'],hvac_required=['package_heating','fan_coil'])
        self.assertEqual(i.constraints['floor']['value'],[2,3]);self.assertEqual(i.constraints['max_rent'],25_000_000)
        self.assertEqual(i.context['workplace'],'mirdamad');self.assertEqual(i.constraints['parking_count_min'],2)
        self.assertEqual(edited(i).constraints,i.constraints)
    def test_count_clear_wins_without_clearing_non_tandem(self):
        i=full('دو تا پارکینگ غیرمزاحم لازم دارم');i=edited(i,parking_count_min=None)
        self.assertIsNone(i.constraints['parking_count_min']);self.assertTrue(i.constraints['parking_non_tandem_required'])
    def test_parking_irrelevant_clears_evidence_and_only_related_logic(self):
        i=full('دو تا پارکینگ غیرمزاحم لازم دارم');i=patch('پارکینگ مهم نیست اگر نزدیک محل کار باشه',i);i=patch('نور از متراژ مهم‌تره',i)
        i=edited(i,parking='irrelevant')
        self.assertIsNone(i.constraints['parking_count_min']);self.assertFalse(i.constraints['parking_non_tandem_required']);self.assertEqual(i.logic['conditionals'],[]);self.assertTrue(i.logic['relative_priorities'])
    def test_clearing_light_removes_relative_rule(self):
        i=full('نور از متراژ مهم‌تره');self.assertTrue(i.logic['relative_priorities'])
        i=edited(i,natural_light='ignored');self.assertEqual(i.logic['relative_priorities'],[])
    def test_unrelated_edit_retains_fallback_and_conditional(self):
        i=full('اول فقط ونک، اگه نبود اطرافش');i=patch('طبقه چهار به بالا فقط اگر آسانسور داشته باشه',i)
        i=edited(i,quietness='high');self.assertTrue(i.logic['fallbacks']);self.assertTrue(i.logic['conditionals'])
    def test_explicit_neighborhood_edit_removes_stale_fallback(self):
        i=full('اول فقط ونک، اگه نبود اطرافش');i=edited(i,neighborhood='میرداماد');self.assertEqual(i.logic['fallbacks'],[])
    def test_manual_workplace_used_by_next_reference(self):
        i=full('محل کارم ونکه');i=edited(i,workplace='mirdamad');i=patch('نزدیک محل کارم باشه',i)
        self.assertEqual(i.desired_location,{'neighborhood':'میرداماد','mode':'nearby'})
    def test_manual_workplace_clear_clarifies_and_removes_commute_rules(self):
        i=full('محل کارم ونکه');i=patch('پارکینگ مهم نیست اگر نزدیک محل کار باشه',i);i=edited(i,workplace='none')
        self.assertEqual(resolve_references('نزدیک محل کارم باشه',i,neighborhoods=NAMES).needs_clarification,'workplace');self.assertEqual(i.logic['conditionals'],[])
    def test_invalid_area_and_floor_do_not_apply(self):
        i=SearchIntent()
        for values in ({'area_min':200,'area_max':100},{'floor_mode':'exact','floor_value':'خانه'}):
            f=AdvancedFilters(form_data(i,**values),intent=i,neighborhoods=NAMES);self.assertFalse(f.is_valid())
    def test_remove_one_rule_preserves_others(self):
        i=full('نور از متراژ مهم‌تره');i=patch('طبقه چهار به بالا فقط اگر آسانسور داشته باشه',i)
        i=remove_logic(i,'relative_priorities:0');self.assertFalse(i.logic['relative_priorities']);self.assertTrue(i.logic['conditionals'])
    def test_reset_clears_context_constraints_and_logic(self):
        i=reset_filters();self.assertEqual(i.work_location,'none');self.assertFalse(i.logic_labels);self.assertTrue(all(p=='ignored' for p in i.preferences.values()))
    def test_quick_summary_includes_evidence_requirements(self):
        i=full('حداقل ۱۰۰ متر طبقه دوم یا سوم دوخوابه می‌خوام');i=patch('دو تا پارکینگ غیرمزاحم لازم دارم',i);i=edited(i,max_rent='25')
        ctx=ui_context(i);self.assertIn('۲۵ میلیون',ctx['quick_budget']);self.assertNotEqual(ctx['quick_amenities'],'بدون الزام');self.assertEqual(i.bedroom_label,'۲ خواب')
    def test_soft_amenities_are_visible_without_becoming_hard(self):
        i=SearchIntent();i.preferences['parking']='high'
        ctx=ui_context(i);self.assertEqual(ctx['quick_amenities'],'۱ ترجیح');self.assertIn('پارکینگ: مهم',dict((k,rows) for k,title,rows in ctx['criteria_groups'])['amenities']);self.assertNotIn('parking',i.constraints['required_amenities'])
    def test_older_source_alias_remains_selected_in_quick_form(self):
        from .forms import PrecisionFilters
        i=SearchIntent();i.constraints['neighborhoods']=['jey']
        f=PrecisionFilters(initial=filter_initial(i),neighborhoods=['جی'])
        self.assertEqual(dict(f.fields['neighborhood'].choices)['jey'],'جی')
    def test_full_registry_refinement_does_not_match_eram_inside_daram(self):
        from .query import classify_query,QueryOperation
        names=[r['display_fa'] for r in REGISTRY]
        i=full('حداقل ۱۰۰ متر طبقه دوم یا سوم دوخوابه می‌خوام')
        self.assertEqual(classify_query('دو تا پارکینگ غیرمزاحم لازم دارم',i,neighborhoods=names),QueryOperation.PATCH)
        after=get_ai_service().parse_intent_patch('دو تا پارکینگ غیرمزاحم لازم دارم',i,names).merge(i)
        self.assertEqual(after.constraints['floor'],i.constraints['floor']);self.assertEqual(after.constraints['area'],i.constraints['area'])
    def test_literal_browse_does_not_match_eram_inside_daram(self):
        from .patches import recognized_text
        self.assertFalse(recognized_text('اطلاع دارم',[r['display_fa'] for r in REGISTRY]))
    def test_preferred_location_does_not_narrow(self):
        i=edited(SearchIntent(),neighborhood='ونک',neighborhood_scope='preferred')
        row=Listing(data_source='real',neighborhood='jey',area_m2=100,bedrooms=2,deposit=0,monthly_rent=0)
        self.assertTrue(eligible(row,i))
    def test_full_deposit_and_conversion_have_explicit_requirements(self):
        row=Listing(data_source='real',area_m2=100,bedrooms=2,deposit=500,monthly_rent=25)
        self.assertFalse(eligible(row,edited(SearchIntent(),full_deposit=True)))
        self.assertFalse(eligible(row,edited(SearchIntent(),convertible=True)))
        row.alternative_deposit=700;row.alternative_rent=0
        self.assertTrue(eligible(row,edited(SearchIntent(),convertible=True)))
    def test_homepage_conditional_requires_amenities_only_for_old(self):
        from .views import HOME_EXAMPLES
        i=full(HOME_EXAMPLES['conditional'][1])
        self.assertNotIn('elevator',i.constraints['required_amenities'])
        new=Listing(data_source='synthetic',area_m2=100,bedrooms=2,deposit=0,monthly_rent=0,construction_year=1401,elevator=False)
        old=Listing(data_source='synthetic',area_m2=100,bedrooms=2,deposit=0,monthly_rent=0,construction_year=1390,renovated=True,elevator=False)
        self.assertTrue(eligible(new,i));self.assertFalse(eligible(old,i));old.elevator=True;self.assertTrue(eligible(old,i))

class WorkplaceLanguageTests(SimpleTestCase):
    def test_workplace_context_preserves_existing_residence(self):
        i=full('فقط میرداماد خونه می‌خوام');i=patch('من ونک کار می‌کنم',i)
        self.assertEqual(i.work_location,'vanak');self.assertEqual(i.constraints['neighborhoods'],['میرداماد'])
    def test_nested_district_name_not_replaced_by_shorter_name(self):
        i=get_ai_service().parse_full_intent('فقط شهرک پاسداران خونه می‌خوام',('شهرک پاسداران','پاسداران'))
        self.assertEqual(i.constraints['neighborhoods'],['شهرک پاسداران'])
    def test_context_nearby_and_exact_are_distinct(self):
        i=full('من ونک کار می‌کنم');self.assertIsNone(i.desired_location['neighborhood'])
        self.assertEqual(patch('نزدیک محل کارم باشه',i).desired_location,{'neighborhood':'ونک','mode':'nearby'})
        self.assertEqual(patch('خود محل کارم باشه',i).desired_location,{'neighborhood':'ونک','mode':'exact'})
    def test_negative_exact_workplace_selects_nearby(self):
        i=full('محل کارم ونکه');i=patch('خود محل کارم نه، اطرافش خوبه',i)
        self.assertEqual(i.desired_location,{'neighborhood':'ونک','mode':'nearby'})
        self.assertEqual(i.constraints['excluded_neighborhoods'],['ونک'])
        row=Listing(data_source='real',neighborhood='vanak',area_m2=100,bedrooms=2,deposit=0,monthly_rent=0)
        self.assertFalse(eligible(row,i))
    def test_home_neighborhood_clear_retains_workplace_commute(self):
        i=full('محل کارم ونکه');i=patch('فقط میرداماد خونه می‌خوام',i);i=patch('محله خونه مهم نیست، فقط مسیر تا محل کار کوتاه باشه',i)
        self.assertFalse(i.constraints['neighborhoods']);self.assertEqual(i.work_location,'vanak');self.assertIn(i.location_priority,('high','very_high'))

def workplace_test(text,key):
    def test(self):
        i=full(text);self.assertEqual(i.work_location,key);self.assertIsNone(i.desired_location['neighborhood'])
    return test
for n,(text,key) in enumerate([('محل کارم ونکه','vanak'),('من ونک کار می‌کنم','vanak'),('تو ونک کار می‌کنم','vanak'),('دفترم میرداماده','mirdamad'),('شرکتم حوالی ولیعصره','valiasr'),('اداره‌م پاسدارانه','pasdaran'),('برای کار هر روز میرم ونک','vanak'),('سر کارم ونکه','vanak')]):setattr(WorkplaceLanguageTests,f'test_workplace_variant_{n+1}',workplace_test(text,key))

class LocationRegistryTests(SimpleTestCase):
    def test_confident_mappings(self):
        for source,name in [('jey','جی'),('eram','ارم'),('qoba','قبا'),('Vanak','ونک')]:self.assertEqual(display_location(source),name)
    def test_english_alias_and_persian_same_search(self):
        self.assertEqual(full('فقط Vanak خونه می‌خوام').desired_location,full('فقط ونک خونه می‌خوام').desired_location)
    def test_source_spelling_union(self):
        self.assertTrue({'aboozar','abouzar'}<=set(source_labels(['ابوذر'])))
    def test_unmapped_and_ambiguous_not_invented(self):
        self.assertEqual(display_location('east-shareq'),'east-shareq');self.assertEqual(display_location('never-known'),'never-known')
    def test_model_projection_does_not_mutate_source(self):
        l=Listing(neighborhood='jey');self.assertEqual(l.neighborhood_display,'جی');self.assertEqual(l.neighborhood,'jey')

@override_settings(DATA_MODE='synthetic')
class ControlIntegrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):call_command('seed_demo',verbosity=0)
    def set_intent(self,i):s=self.client.session;s['intent']=i.to_dict();s.save()
    def test_fresh_home_results_login_have_no_tray(self):
        self.assertNotContains(self.client.get(reverse('home')),'class="comparison-tray"')
        self.set_intent(SearchIntent());self.assertNotContains(self.client.get(reverse('results')),'class="comparison-tray"')
        self.assertEqual(self.client.session.get('comparison',[]),[])
    def test_tray_add_remove_last(self):
        self.set_intent(SearchIntent());pk=Listing.objects.first().pk
        self.client.post(reverse('compare_toggle'),{'listing':pk});self.assertContains(self.client.get(reverse('results')),'class="comparison-tray"')
        self.client.post(reverse('compare_toggle'),{'listing':pk});self.assertNotContains(self.client.get(reverse('results')),'class="comparison-tray"')
    def test_login_logout_do_not_seed_comparison(self):
        for url in ('/accounts/login/','/accounts/logout/'):
            response=self.client.post(url) if 'logout' in url else self.client.get(url)
            self.assertIn(response.status_code,(200,302))
            self.assertEqual(self.client.session.get('comparison',[]),[])
        self.assertNotContains(self.client.get(reverse('home')),'class="comparison-tray"')
    def test_login_page_hides_tray_even_with_selection(self):
        s=self.client.session;s['comparison']=[Listing.objects.first().pk];s.save()
        self.assertNotContains(self.client.get('/accounts/login/'),'class="comparison-tray"')
        self.assertEqual(len(self.client.session['comparison']),1)
    def test_noop_advanced_post_preserves_zero_result_recovery(self):
        i=edited(SearchIntent(),area_min=1500,pet_policy='allowed');self.set_intent(i)
        r=self.client.post(reverse('results'),{'action':'advanced',**form_data(i)},follow=True)
        self.assertEqual(r.context['eligible_count'],0);self.assertTrue(r.context['recoveries'])
        self.assertEqual(self.client.session['intent']['constraints']['area']['min'],1500)
    def test_shared_drawer_review_and_results(self):
        self.set_intent(full('دو تا پارکینگ غیرمزاحم لازم دارم'))
        for route in ('intent','results'):
            r=self.client.get(reverse(route));self.assertContains(r,'id="advanced-filters"');self.assertEqual(r.context['advanced_form'].initial['parking_count_min'],2)
    def test_workplace_clarification_accepts_broader_registry(self):
        self.set_intent(SearchIntent());r=self.client.post(reverse('results'),{'update':'نزدیک محل کارم باشه'},follow=True)
        self.assertEqual(self.client.session['pending_query']['reference'],'workplace');self.assertIn('میرداماد',r.context['reference_choices'])
        self.client.post(reverse('intent'),{'action':'clarify','reference_place':'میرداماد'},follow=True)
        i=SearchIntent(**self.client.session['intent']);self.assertEqual(i.work_location,'mirdamad');self.assertEqual(i.desired_location,{'neighborhood':'میرداماد','mode':'nearby'})
    def test_post_advanced_updates_only_same_session_intent(self):
        i=full('حداقل ۱۰۰ متر طبقه دوم یا سوم دوخوابه می‌خوام');self.set_intent(i)
        r=self.client.post(reverse('results'),{'action':'advanced',**form_data(i,workplace='vanak',commute='very_high')})
        self.assertEqual(r.status_code,302);after=SearchIntent(**self.client.session['intent']);self.assertEqual(after.work_location,'vanak');self.assertEqual(after.constraints['floor'],i.constraints['floor']);self.assertNotIn('precision_filters',self.client.session)
    def test_invalid_post_keeps_intent_and_opens_bound_form(self):
        i=SearchIntent();self.set_intent(i);r=self.client.post(reverse('results'),{'action':'advanced',**form_data(i,area_min=200,area_max=100)})
        self.assertContains(r,'data-open-on-load');self.assertEqual(self.client.session['intent'],i.to_dict())
    def test_sidebar_groups_and_canonical_quick_labels(self):
        i=full('حداقل ۱۰۰ متر طبقه دوم یا سوم دوخوابه می‌خوام');i=patch('دو تا پارکینگ غیرمزاحم لازم دارم',i);self.set_intent(i)
        r=self.client.get(reverse('results'))
        for text in ('خانه','بودجه','موقعیت و رفت‌وآمد','امکانات','حداقل ۲ پارکینگ','پارکینگ غیرمزاحم ضروری','اتاق؛ ۲ خواب'):self.assertContains(r,text)
        self.assertNotContains(r,'امکانات؛ بدون الزام');self.assertContains(r,'data-section="amenities"')
    def test_reset_preserves_saved_and_comparison(self):
        self.set_intent(full('دو تا پارکینگ لازم دارم'));s=self.client.session;s['comparison']=[1];s['saved_listing_ids']=[2];s.save()
        self.client.post(reverse('results'),{'action':'reset_filters'});self.assertEqual(self.client.session['comparison'],[1]);self.assertEqual(self.client.session['saved_listing_ids'],[2]);self.assertIsNone(self.client.session['intent']['constraints']['parking_count_min'])
