"""Final release cleanup contracts; canonical search and sorting remain server-owned."""
from pathlib import Path
from django.test import TestCase, override_settings, Client
from django.core.management import call_command
from .models import Listing

@override_settings(DATA_MODE='synthetic')
class ReleaseCleanupTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_demo', verbosity=0)
        cls.ids=list(Listing.objects.values_list('pk',flat=True)[:3])
    def select(self):
        s=self.client.session;s['comparison']=self.ids;s['saved_listing_ids']=[self.ids[0]];s.save()
    def test_clear_all_normal_request(self):
        self.select()
        from .search import SearchIntent
        intent=SearchIntent().to_dict()
        session=self.client.session;session['intent']=intent;session.save()
        r=self.client.post('/compare/toggle/',{'action':'clear','return':'browse'})
        self.assertRedirects(r,'/browse/?continue=1')
        self.assertEqual(self.client.session['comparison'],[])
        self.assertEqual(self.client.session['saved_listing_ids'],[self.ids[0]])
        self.assertEqual(self.client.session['intent'],intent)
    def test_clear_partial_updates_utilities_and_zero_count(self):
        self.select()
        state=self.client.post('/compare/toggle/',{'action':'clear','return':'browse'},HTTP_X_REQUESTED_WITH='XMLHttpRequest').json()
        self.assertTrue(state['cleared']);self.assertEqual(state['count'],0)
        self.assertNotIn('class="comparison-tray"',state['utilities'])
        self.assertIn('class="comparison-count">۰</strong>',state['utilities'])
        self.assertNotContains(self.client.get('/browse/?continue=1'),'class="comparison-tray"')
    def test_clear_idempotent_and_post_only(self):
        self.assertEqual(self.client.get('/compare/toggle/?action=clear').status_code,405)
        for _ in range(2):
            self.client.post('/compare/toggle/',{'action':'clear'})
            self.assertEqual(self.client.session['comparison'],[])
    def test_clear_requires_csrf(self):
        self.assertEqual(Client(enforce_csrf_checks=True).post('/compare/toggle/',{'action':'clear'}).status_code,403)
    def test_final_individual_removal_hides_tray(self):
        s=self.client.session;s['comparison']=[self.ids[0]];s.save()
        r=self.client.post('/compare/toggle/',{'listing':self.ids[0],'return':'browse'},HTTP_X_REQUESTED_WITH='XMLHttpRequest').json()
        self.assertEqual(r['count'],0);self.assertNotIn('class="comparison-tray"',r['utilities'])
    def test_cancel_accessible_and_compact_labels(self):
        self.select();r=self.client.get('/browse/')
        self.assertContains(r,'aria-label="لغو مقایسه"')
        self.assertContains(r,'class="cancel-mobile">لغو')
        self.assertContains(r,'name="action" value="clear"')
    def test_sort_sheet_uses_browse_values_and_selected_label(self):
        r=self.client.get('/browse/?sort=cost')
        self.assertContains(r,'data-sort-open aria-controls="sort-sheet" aria-expanded="false"')
        self.assertContains(r,'مرتب‌سازی: <span>کم‌هزینه‌تر</span>')
        sheet=r.content.decode().split('<dialog id="sort-sheet"',1)[1].split('</dialog>',1)[0]
        for value in ('default','cost','new'):self.assertIn('?sort='+value,sheet)
        self.assertNotIn('?sort=near',sheet)
        self.assertContains(r,'class="sort-tabs"')
    def test_sort_partial_keeps_canonical_intent(self):
        from .ai import get_ai_service
        intent=get_ai_service().parse_full_intent('دوخوابه حداقل ۱۰۰ متر',('ونک',))
        session=self.client.session;session['intent']=intent.to_dict();session.save()
        before=dict(self.client.session)
        r=self.client.get('/results/?sort=cost',HTTP_X_RESULTS_PARTIAL='1')
        self.assertContains(r,'data-sort-open');self.assertContains(r,'data-results-region')
        self.assertNotContains(r,'<!DOCTYPE')
        for key in ('intent','search_intent','intent_profile'):
            self.assertEqual(self.client.session.get(key),before.get(key))
    def test_one_search_form_with_sticky_contract(self):
        r=self.client.get('/browse/')
        self.assertContains(r,'class="refinement-search browse-search"',count=1)
        self.assertContains(r,'id="browse-query"',count=1)
        self.assertContains(r,'class="search-sticky-sentinel"',count=1)
        self.assertContains(r,'class="search-sticky-space"',count=1)
    def test_mobile_sort_visibility_and_desktop_tabs_contract(self):
        css=Path(__file__).parent.joinpath('static/finder/src.css').read_text(encoding='utf8')
        self.assertIn('.filter-control-row .sort-tabs{display:none}',css)
        self.assertIn('.enhanced .mobile-sort{display:flex',css)
        self.assertIn('.header{position:static}',css)
        self.assertIn('.header{position:sticky;top:0',css)
    def test_sort_focus_and_sticky_observer_contract(self):
        js=Path(__file__).parent.joinpath('static/finder/app.js').read_text(encoding='utf8')
        self.assertIn('closeOtherSheets(sheet)',js)
        self.assertIn('sortOpener.focus({preventScroll:true})',js)
        self.assertIn('initializeSort();initializeStickySearch();',js)
        self.assertIn('searchObserver=new IntersectionObserver',js)
        self.assertNotIn("addEventListener('scroll'",js)
