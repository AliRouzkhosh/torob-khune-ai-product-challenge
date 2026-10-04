from io import StringIO
from unittest.mock import patch
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase, override_settings
from .contact import get_demo_contact
from .models import Listing
from .search import SearchIntent


@override_settings(DATA_MODE='synthetic', DEBUG=True, ENABLE_DEMO_LOGIN=True, DEMO_BALE_URL='')
class ContactAuthTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_demo', stdout=StringIO())
        cls.user = get_user_model().objects.create_user('evaluator', password='test-only-long-password')
        with patch.dict('os.environ', {'KHANE_DEMO_PASSWORD': ''}):
            call_command('seed_demo_user', stdout=StringIO())

    def setUp(self):
        self.listing = Listing.objects.get(pk=1)
        self.detail = '/homes/1/'
        self.contact = '/homes/1/contact/'
        self.phone = get_demo_contact(self.listing)['display_phone']

    def seed_state(self):
        state = {'intent': SearchIntent().to_dict(), 'saved_listing_ids': [1, 2],
                 'comparison': [1, 3], 'query': 'دوخوابه نزدیک ونک',
                 'listing_context': 'results', 'browse_query': 'ونک'}
        session = self.client.session
        session.update(state)
        session.save()
        return state

    def test_anonymous_detail_gated_and_no_contact_in_html(self):
        response = self.client.get(self.detail)
        self.assertContains(response, 'نمایش اطلاعات تماس')
        self.assertContains(response, 'برای دیدن اطلاعات تماس وارد شو.')
        self.assertNotContains(response, self.phone)
        self.assertNotContains(response, 'data-contact-action')

    def test_anonymous_endpoint_redirects_to_original_detail(self):
        response = self.client.get(self.contact)
        self.assertRedirects(response, '/accounts/login/?next=/homes/1/')
        self.assertNotIn(self.phone, response.content.decode())

    def test_authenticated_inline_partial_and_disclosure(self):
        self.client.force_login(self.user)
        self.assertNotContains(self.client.get(self.detail), self.phone)
        response = self.client.get(self.contact, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertContains(response, self.phone)
        self.assertContains(response, 'اطلاعات تماس در این نمونه نمایشی است و متعلق به آگهی اصلی نیست.')
        self.assertNotContains(response, '<html')
        self.assertIn('no-store', response.headers['Cache-Control'])
        self.assertNotContains(response, 'tel:')

    def test_no_js_contact_stays_in_detail(self):
        self.client.force_login(self.user)
        response = self.client.get(self.contact)
        self.assertContains(response, self.listing.title)
        self.assertContains(response, self.phone)
        self.assertContains(response, '<html')

    def test_password_login_preserves_search_saved_compare_and_returns(self):
        state = self.seed_state()
        old_key = self.client.session.session_key
        response = self.client.post('/accounts/login/', {'username': 'evaluator',
            'password': 'test-only-long-password', 'next': self.detail})
        self.assertRedirects(response, self.detail)
        self.assertNotEqual(old_key, self.client.session.session_key)
        for key, value in state.items(): self.assertEqual(self.client.session[key], value)
        page = self.client.get(self.detail)
        self.assertEqual(page.context['saved_count'], 2)
        self.assertEqual(page.context['comparison_count'], 2)

    def test_demo_login_and_logout_preserve_utilities_and_regate(self):
        state = self.seed_state()
        response = self.client.post('/accounts/login/demo/', {'next': self.detail})
        self.assertRedirects(response, self.detail)
        self.assertTrue(self.client.get(self.detail).wsgi_request.user.is_authenticated)
        self.assertContains(self.client.get(self.detail), 'کاربر آزمایشی')
        for key, value in state.items(): self.assertEqual(self.client.session[key], value)
        authenticated_key = self.client.session.session_key
        self.assertContains(self.client.get(self.contact), self.phone)
        response = self.client.post('/accounts/logout/', {'next': self.detail})
        self.assertRedirects(response, self.detail)
        self.assertNotEqual(authenticated_key, self.client.session.session_key)
        self.assertNotIn('_auth_user_id', self.client.session)
        for key, value in state.items(): self.assertEqual(self.client.session[key], value)
        self.assertNotContains(self.client.get(self.detail), self.phone)
        self.assertEqual(self.client.get(self.contact).status_code, 302)

    def test_bale_fallback_without_message_or_number(self):
        self.client.force_login(self.user)
        response = self.client.get(self.contact+'?action=bale', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertContains(response, 'ارسال پیام در نسخه نمایشی شبیه‌سازی شده است.')
        self.assertContains(response, 'پیامی ارسال نشده')
        self.assertNotContains(response, self.phone)

    @override_settings(DEMO_BALE_URL='https://ble.ir/example-demo')
    def test_configured_bale_is_explicit_demo_link(self):
        self.client.force_login(self.user)
        self.assertNotContains(self.client.get(self.detail), settings.DEMO_BALE_URL)
        response = self.client.get(self.contact+'?action=bale')
        self.assertContains(response, settings.DEMO_BALE_URL)
        self.assertContains(response, 'متعلق به صاحب آگهی نیست')

    @override_settings(DEMO_BALE_URL='javascript:alert(1)')
    def test_unsafe_bale_config_suppressed(self):
        self.assertEqual(get_demo_contact(self.listing)['bale_url'], '')

    def test_contact_is_stable_masked_and_mode_scoped(self):
        self.assertEqual(get_demo_contact(self.listing)['display_phone'], self.phone)
        self.assertRegex(self.phone, r'^09xx xxx xx\d{2}$')
        self.client.force_login(self.user)
        with override_settings(DATA_MODE='real'):
            self.assertEqual(self.client.get(self.contact).status_code, 404)

    def test_post_only_auth_mutations_and_csrf(self):
        for route in ('/accounts/login/demo/', '/accounts/logout/'):
            self.assertEqual(self.client.get(route).status_code, 405)
        csrf_client = Client(enforce_csrf_checks=True)
        for route in ('/accounts/login/', '/accounts/login/demo/', '/accounts/logout/'):
            self.assertEqual(csrf_client.post(route).status_code, 403)

    def test_external_next_rejected_for_all_auth_paths(self):
        for target in ('https://evil.example/', '//evil.example/', 'javascript:alert(1)'):
            response = self.client.post('/accounts/login/demo/', {'next': target})
            self.assertRedirects(response, '/browse/')
            response = self.client.post('/accounts/logout/', {'next': target})
            self.assertRedirects(response, '/browse/')
        response = self.client.post('/accounts/login/', {'username': 'evaluator',
            'password': 'test-only-long-password', 'next': 'https://evil.example/'})
        self.assertRedirects(response, '/browse/')

    @override_settings(ENABLE_DEMO_LOGIN=False)
    def test_demo_login_can_be_disabled(self):
        self.assertNotContains(self.client.get('/accounts/login/'), 'ورود با حساب آزمایشی')
        self.assertEqual(self.client.post('/accounts/login/demo/').status_code, 404)

    def test_demo_seed_idempotent_unusable_password_and_privilege_guard(self):
        user = get_user_model().objects.get(username=settings.DEMO_USERNAME)
        self.assertFalse(user.has_usable_password())
        with patch.dict('os.environ', {'KHANE_DEMO_PASSWORD': ''}):
            call_command('seed_demo_user', stdout=StringIO())
        self.assertEqual(get_user_model().objects.filter(username=settings.DEMO_USERNAME).count(), 1)
        user.is_staff = True
        user.save()
        with self.assertRaises(CommandError): call_command('seed_demo_user', stdout=StringIO())
        self.assertEqual(self.client.post('/accounts/login/demo/').status_code, 503)

    def test_anonymous_product_surfaces_remain_public(self):
        for route in ('/', '/browse/', '/saved/', '/compare/', self.detail):
            self.assertEqual(self.client.get(route).status_code, 200)

    def test_incorrect_password_does_not_authenticate(self):
        response = self.client.post('/accounts/login/', {'username': 'evaluator', 'password': 'wrong', 'next': self.detail})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_user_center_coming_soon_is_focusable_non_navigation(self):
        response = self.client.get(self.detail)
        self.assertContains(response, 'ثبت آگهی')
        self.assertContains(response, 'aria-disabled="true" aria-describedby="listing-soon-help"')
        self.assertNotContains(response, 'ورود / فضای من')
        from django.urls import resolve, Resolver404
        with self.assertRaises(Resolver404): resolve('/listings/new/')

    def test_contact_partial_retains_copy_and_bale_actions(self):
        self.client.force_login(self.user)
        response = self.client.get(self.contact, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertContains(response, 'data-copy-contact')
        self.assertContains(response, 'کپی شماره')
        self.assertContains(response, 'پیام در بله')
        self.assertContains(response, 'contact-actions')
        self.assertContains(response, self.phone)

    def test_bale_partial_has_inline_feedback_and_reveal_action(self):
        self.client.force_login(self.user)
        response = self.client.get(self.contact+'?action=bale', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'contact-feedback')
        self.assertContains(response, 'data-contact-action="phone"')
        self.assertNotContains(response, '<html')

    def test_long_description_preserved_with_accessible_disclosure(self):
        description = ('متن اصلی آگهی؛ نور خوب، پنجره رو به حیاط.\n' * 30).strip()
        self.listing.description = description
        self.listing.save(update_fields=['description'])
        response = self.client.get(self.detail)
        self.assertContains(response, description)
        self.assertContains(response, 'description-text is-collapsed')
        self.assertContains(response, 'aria-expanded="false" aria-controls="source-description"')
        self.assertContains(response, 'توضیحات آگهی')
        self.assertContains(response, 'برداشت ترب‌خونه')

    def test_login_back_link_only_for_safe_listing_next(self):
        response = self.client.get('/accounts/login/', {'next': self.detail})
        self.assertContains(response, '← بازگشت به آگهی')
        self.assertEqual(response.context['safe_back'], self.detail)
        for target in ('https://evil.example/homes/1/', '//evil.example/homes/1/', '/accounts/logout/'):
            response = self.client.get('/accounts/login/', {'next': target})
            self.assertNotContains(response, '← بازگشت به آگهی')

    @override_settings(DEMO_BALE_URL='https://ble.ir/example-demo')
    def test_configured_bale_partial_opens_separately(self):
        self.client.force_login(self.user)
        response = self.client.get(self.contact, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertContains(response, 'target="_blank" rel="noopener noreferrer" data-bale-link')
