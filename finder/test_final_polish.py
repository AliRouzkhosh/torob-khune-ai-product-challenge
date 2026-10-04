"""Public brand and server-authoritative progressive enhancement contracts."""
from django.test import TestCase, override_settings
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.urls import reverse
from .models import Listing
from .search import SearchIntent
from .test_v010 import form_data, full


@override_settings(DATA_MODE='synthetic')
class FinalPolishTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_demo', verbosity=0)
        cls.user=get_user_model().objects.create_user('polish-qa',password='test-only-password')

    def put(self, intent=None):
        state=self.client.session;state['intent']=(intent or SearchIntent()).to_dict();state.save()

    def partial(self, data=None, path='/results/'):
        return (self.client.post(path,data,follow=True,HTTP_X_RESULTS_PARTIAL='1') if data is not None
                else self.client.get(path,HTTP_X_RESULTS_PARTIAL='1'))

    def test_public_brand_on_core_pages(self):
        self.put()
        for path in ('/','/about/','/intent/','/results/','/browse/','/saved/','/compare/','/accounts/login/'):
            with self.subTest(path=path):
                response=self.client.get(path)
                self.assertContains(response,'ترب‌خونه')
                self.assertNotContains(response,'خانه‌یاب')

    def test_brand_disclosure(self):
        for path in ('/','/about/'):
            self.assertContains(self.client.get(path),'نمونه مفهومی مستقل برای چالش AI Product Engineer ترب؛ محصول رسمی ترب نیست.')

    def test_logo_and_favicon_public_references(self):
        response=self.client.get('/')
        self.assertContains(response,'finder/brand/mark.svg')
        self.assertContains(response,'finder/brand/favicon.svg')
        self.assertNotContains(response,'finder/logo.svg')

    def test_mobile_menu_accessible_markup_and_desktop_fallback(self):
        response=self.client.get('/')
        self.assertContains(response,'id="mobile-menu"')
        self.assertContains(response,'aria-controls="mobile-menu" aria-expanded="false"')
        self.assertContains(response,'aria-label="ناوبری موبایل"')
        self.assertContains(response,'class="global-nav"')
        self.assertContains(response,'data-menu-close')

    def test_results_partial_is_complete_single_region(self):
        self.put(full('دوخوابه حداقل ۱۰۰ متر'))
        response=self.partial()
        self.assertContains(response,'id="results-region"',count=1)
        for fragment in ('unified-filters','active-filters','results-toolbar','criteria-responsive','listing-grid','advanced-filters','data-utility-update'):
            self.assertContains(response,fragment)
        self.assertNotContains(response,'<!doctype html>')
        self.assertNotContains(response,'<header class="header"')
        self.assertIn('X-Results-Partial',response.headers['Vary'])
        self.assertEqual(response.headers['Cache-Control'],'private, no-store')

    def test_normal_results_remains_full_document(self):
        self.put();response=self.client.get('/results/')
        self.assertContains(response,'<!doctype html>')
        self.assertContains(response,'id="results-region"',count=1)

    def test_refinement_partial_updates_canonical_intent_and_criteria(self):
        self.put(full('دوخوابه حداقل ۱۰۰ متر'))
        response=self.partial({'update':'دو تا پارکینگ غیرمزاحم لازم دارم'})
        state=SearchIntent(**self.client.session['intent'])
        self.assertEqual(state.constraints['parking_count_min'],2)
        self.assertTrue(state.constraints['parking_non_tandem_required'])
        self.assertEqual(state.constraints['area']['min'],100)
        self.assertContains(response,'درخواستت به‌روزرسانی شد')
        self.assertContains(response,'id="results-region"')
        self.assertNotContains(response,'<!doctype html>')

    def test_filter_apply_partial_preserves_one_canonical_state(self):
        intent=full('دوخوابه');self.put(intent)
        response=self.partial({'action':'advanced',**form_data(intent,max_rent='30',workplace='vanak')})
        state=SearchIntent(**self.client.session['intent'])
        self.assertEqual(state.constraints['max_rent'],30_000_000)
        self.assertEqual(state.work_location,'vanak')
        self.assertContains(response,'✓ فیلترها به‌روزرسانی شدند')
        self.assertNotContains(response,'<!doctype html>')

    def test_chip_removal_partial_cleans_related_logic(self):
        self.put(full('دوخوابه حداقل ۱۰۰ متر'))
        response=self.partial({'action':'remove','key':'area'})
        state=SearchIntent(**self.client.session['intent'])
        self.assertIsNone(state.constraints['area']['min'])
        self.assertEqual(state.constraints['bedrooms']['value'],2)
        self.assertContains(response,'data-results-region')

    def test_sort_partial_never_mutates_intent(self):
        self.put(full('دوخوابه'))
        before=self.client.session['intent']
        response=self.partial(path='/results/?sort=cost')
        self.assertEqual(self.client.session['intent'],before)
        self.assertContains(response,'?sort=cost" aria-current="true"')
        self.assertNotContains(response,'<!doctype html>')

    def test_no_js_refinement_redirect_contract(self):
        self.put()
        response=self.client.post('/results/',{'update':'دوخوابه می‌خوام'})
        self.assertRedirects(response,'/results/')

    def test_no_js_filter_redirect_contract(self):
        intent=SearchIntent();self.put(intent)
        response=self.client.post('/results/',{'action':'advanced',**form_data(intent,bedrooms='2')})
        self.assertRedirects(response,'/results/')

    def test_home_filter_keeps_meaningful_review_navigation(self):
        response=self.client.post('/',{'action':'advanced',**form_data(SearchIntent(),bedrooms='2')})
        self.assertRedirects(response,'/intent/')

    def test_invalid_filter_partial_preserves_state_and_exposes_errors(self):
        intent=full('دوخوابه');self.put(intent);before=self.client.session['intent']
        response=self.partial({'action':'advanced',**form_data(intent,parking_count_min=99)})
        self.assertEqual(self.client.session['intent'],before)
        self.assertContains(response,'data-open-on-load')
        self.assertContains(response,'errorlist')

    def test_conflict_partial_distinct_from_zero_results(self):
        self.put(full('دوخوابه'))
        response=self.partial({'update':'فقط دو خواب و فقط سه خواب'})
        self.assertContains(response,'دو شرط ناسازگار پیدا کردیم')
        self.assertNotContains(response,'results-toolbar')
        self.assertNotContains(response,'<!doctype html>')

    def test_valid_zero_results_partial_retains_recovery(self):
        intent=SearchIntent();intent.constraints['area']['min']=1500;self.put(intent)
        response=self.partial()
        self.assertContains(response,'recovery-actions')
        self.assertNotContains(response,'دو شرط ناسازگار پیدا کردیم')

    def test_browse_partial_sort_preserves_smart_intent(self):
        self.put(full('دوخوابه'));before=self.client.session['intent']
        response=self.partial(path='/browse/?sort=cost')
        self.assertEqual(self.client.session['intent'],before)
        self.assertContains(response,'خانه‌های اجاره‌ای تهران')
        self.assertNotContains(response,'<!doctype html>')

    def test_bookmark_inline_json_and_no_js_redirect(self):
        row=Listing.objects.first()
        response=self.client.post('/saved/toggle/',{'listing':row.pk},HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertTrue(response.json()['saved']);self.assertEqual(response.json()['count'],1)
        response=self.client.post('/saved/toggle/',{'listing':row.pk,'return':'saved'})
        self.assertRedirects(response,'/saved/')
        self.assertEqual(self.client.session['saved_listing_ids'],[])

    def test_comparison_inline_lifecycle_and_tray_content(self):
        row=Listing.objects.first()
        response=self.client.post('/compare/toggle/',{'listing':row.pk,'return':'browse'},HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        state=response.json();self.assertTrue(state['selected']);self.assertEqual(state['count'],1)
        self.assertIn('comparison-tray',state['utilities']);self.assertIn('comparison-count',state['utilities'])
        response=self.client.post('/compare/toggle/',{'listing':row.pk,'return':'browse'},HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        state=response.json();self.assertFalse(state['selected']);self.assertEqual(state['count'],0)
        self.assertNotIn('class="comparison-tray"',state['utilities'])

    def test_comparison_max_three_preserved_inline(self):
        rows=list(Listing.objects.all()[:4])
        for row in rows:response=self.client.post('/compare/toggle/',{'listing':row.pk,'return':'browse'},HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.json()['count'],3)
        self.assertFalse(response.json()['selected'])
        self.assertTrue(response.json()['error'])

    def test_comparison_no_js_redirect_and_scroll_region(self):
        rows=list(Listing.objects.all()[:2])
        for row in rows:
            self.assertRedirects(self.client.post('/compare/toggle/',{'listing':row.pk,'return':'compare'}),'/compare/')
        response=self.client.get('/compare/')
        self.assertContains(response,'comparison-scroll compare-count-2')
        self.assertContains(response,'scope="row"')

    def test_comparison_table_partial_is_not_full_document(self):
        rows=list(Listing.objects.all()[:3]);state=self.client.session;state['comparison']=[r.pk for r in rows];state.save()
        response=self.client.get('/compare/',HTTP_X_COMPARE_PARTIAL='1')
        self.assertContains(response,'id="compare-region"')
        self.assertContains(response,'comparison-scroll compare-count-3')
        self.assertNotContains(response,'<!doctype html>')

    def test_phone_and_bale_stay_inline_authenticated(self):
        self.client.force_login(self.user);row=Listing.objects.first()
        for action in ('phone','bale'):
            response=self.client.get(f'/homes/{row.pk}/contact/?action={action}',HTTP_X_REQUESTED_WITH='XMLHttpRequest')
            self.assertEqual(response.status_code,200)
            self.assertContains(response,'contact-feedback')
            self.assertNotContains(response,'<!doctype html>')

    def test_anonymous_contact_still_requires_login(self):
        row=Listing.objects.first()
        response=self.client.get(f'/homes/{row.pk}/contact/',HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code,302);self.assertIn('/accounts/login/',response.url)

    def test_inline_updates_require_csrf(self):
        from django.test import Client
        client=Client(enforce_csrf_checks=True);row=Listing.objects.first()
        response=client.post('/compare/toggle/',{'listing':row.pk},HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code,403)

    def test_mobile_criteria_has_count_and_non_nested_strategy_markup(self):
        self.put(full('دوخوابه حداقل ۱۰۰ متر'))
        response=self.client.get('/results/')
        self.assertContains(response,'معیارهای انتخاب تو ·')
        self.assertContains(response,'class="criteria-scroll"')
        self.assertContains(response,'class="criteria-details"')

    def test_review_primary_action_precedes_detailed_editing(self):
        self.put();response=self.client.get('/intent/');html=response.content.decode()
        self.assertLess(html.index('summary-actions'),html.index('class="advanced-intent"'))
