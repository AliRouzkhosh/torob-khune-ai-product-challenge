"""Mobile presentation contracts, without pixel-dependent assertions."""
from pathlib import Path
from django.test import TestCase, override_settings
from django.core.management import call_command
from django.contrib.auth import get_user_model
from .models import Listing


@override_settings(DATA_MODE='synthetic')
class MobileReleaseCandidateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_demo',verbosity=0)
        cls.rows=list(Listing.objects.all()[:4])
        cls.user=get_user_model().objects.create_user('mobile-rc-test',password='test-only')

    def select(self,n=3):
        session=self.client.session;session['comparison']=[x.pk for x in self.rows[:n]];session.save()

    def test_theme_controls_only_in_my_space_not_menu(self):
        response=self.client.get('/');html=response.content.decode()
        menu=html.split('<dialog id="mobile-menu"',1)[1].split('</dialog>',1)[0]
        self.assertNotIn('data-theme-choice',menu)
        self.assertNotIn('user-panel',menu)
        self.assertEqual(html.count('data-theme-choice='),3)
        self.assertIn('class="display-options"',html)

    def test_comparison_page_never_renders_redundant_tray(self):
        self.select();response=self.client.get('/compare/')
        self.assertNotContains(response,'class="comparison-tray"')
        self.assertEqual(self.client.session['comparison'],[x.pk for x in self.rows[:3]])

    def test_comparison_toggle_partial_does_not_recreate_comparison_page_tray(self):
        self.select(2)
        result=self.client.post('/compare/toggle/',{'listing':self.rows[2].pk,'return':'compare'},HTTP_X_REQUESTED_WITH='XMLHttpRequest').json()
        self.assertEqual(result['count'],3);self.assertNotIn('class="comparison-tray"',result['utilities'])

    def test_mobile_tray_compact_summary_keeps_desktop_management(self):
        self.select(2);response=self.client.get('/browse/')
        self.assertContains(response,'class="mobile-tray-summary"')
        self.assertContains(response,'class="tray-homes"')
        self.assertContains(response,'مقایسه ۲ خانه')

    def test_comparison_semantic_columns_and_local_scroll_retained(self):
        self.select();response=self.client.get('/compare/')
        self.assertContains(response,'class="comparison-feature"',count=1)
        self.assertContains(response,'class="comparison-home"',count=3)
        self.assertContains(response,'class="comparison-home-title"',count=3)
        self.assertContains(response,'scope="row"')
        self.assertContains(response,'aria-label="جدول مقایسه خانه‌ها"')

    def test_detail_contact_gate_and_inline_simulation_unchanged(self):
        pk=self.rows[0].pk
        self.assertEqual(self.client.get(f'/homes/{pk}/contact/').status_code,302)
        self.client.force_login(self.user)
        result=self.client.get(f'/homes/{pk}/contact/?action=bale',HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertContains(result,'پیامی ارسال نشده')
        self.assertContains(result,'contact-feedback')

    def test_mobile_detail_tray_hidden_without_dropping_selection(self):
        self.select();response=self.client.get(f'/homes/{self.rows[0].pk}/')
        self.assertContains(response,'has-contact')
        self.assertEqual(len(self.client.session['comparison']),3)
        css=Path(__file__).parent.joinpath('static/finder/src.css').read_text(encoding='utf8')
        self.assertIn('.has-contact .comparison-tray{display:none}',css)

    def test_backdrop_gesture_requires_outside_start_and_end(self):
        js=Path(__file__).parent.joinpath('static/finder/app.js').read_text(encoding='utf8')
        self.assertIn("document.addEventListener('pointerdown'",js)
        self.assertIn('dialog===backdropStart',js)
        self.assertIn('event.target===dialog&&outsideSheet(dialog,event)',js)

    def test_all_three_sheets_share_mutual_exclusion(self):
        js=Path(__file__).parent.joinpath('static/finder/app.js').read_text(encoding='utf8')
        for dialog in ('drawer','menu','userSheet'):
            self.assertIn(f'closeOtherSheets({dialog})',js)
        self.assertIn("querySelectorAll('dialog[open]')",js)

    def test_contact_observer_changes_presentation_only(self):
        js=Path(__file__).parent.joinpath('static/finder/app.js').read_text(encoding='utf8')
        self.assertIn("'IntersectionObserver' in window",js)
        self.assertIn("classList.toggle('contact-card-visible'",js)
        self.assertIn("headers: {'X-Requested-With':'XMLHttpRequest'}",js)

    def test_partial_focus_and_scroll_contract(self):
        js=Path(__file__).parent.joinpath('static/finder/app.js').read_text(encoding='utf8')
        self.assertIn('window.scrollTo(scrollPosition)',js)
        self.assertIn('sortFocus||chipFocus',js)
        self.assertIn('criteria.open=criteriaOpen',js)

    def test_comparison_max_and_final_remove_still_canonical(self):
        self.select()
        response=self.client.post('/compare/toggle/',{'listing':self.rows[3].pk,'return':'browse'},HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.json()['count'],3);self.assertTrue(response.json()['error'])
        for row in self.rows[:3]:
            response=self.client.post('/compare/toggle/',{'listing':row.pk,'return':'browse'},HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.json()['count'],0)
        self.assertNotIn('class="comparison-tray"',response.json()['utilities'])
