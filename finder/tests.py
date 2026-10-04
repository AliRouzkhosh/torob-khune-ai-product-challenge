from dataclasses import replace
from django.test import TestCase, SimpleTestCase, Client, override_settings
from django.core.management import call_command
from .ai import get_ai_service
from .intent import IntentProfile, SCENARIOS, heuristic_parse
from .models import Listing
from .ranking import rank_listings, eligible, score_listing


@override_settings(DATA_MODE='synthetic')
class IntentTests(SimpleTestCase):
    def test_validation(self):
        for kwargs in ({'bedrooms_min': -1}, {'rent_target': -20}, {'location_priority': 'ultimate'}, {'preferences': {'invented': 'high'}}, {'rent_hard': 'yes'}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                IntentProfile(**kwargs)
        with self.assertRaises(TypeError):
            IntentProfile(unknown_llm_field='x')

    def test_persian_rules_and_amounts(self):
        p = heuristic_parse('سه خوابه با ۸۰۰ میلیون ودیعه و ۲۵ میلیون اجاره. نور خیلی مهمه؛ پارکینگ مهم نیست. آسانسور و انباری مهمه')
        self.assertEqual(p.bedrooms_min, 3)
        self.assertEqual((p.deposit_target, p.rent_target), (800_000_000, 25_000_000))
        self.assertEqual(p.preferences['natural_light'], 'very_high')
        self.assertEqual(p.preferences['parking'], 'low')
        self.assertEqual(p.preferences['elevator'], 'high')
        self.assertEqual(p.preferences['storage'], 'high')
        self.assertEqual(heuristic_parse('دوخوابه، پارکینگ مهمه').bedrooms_min, 2)
        self.assertEqual(heuristic_parse('دوخوابه').work_location, 'none')
        self.assertTrue(heuristic_parse('آسانسور حتماً لازم است').elevator_required)

    def test_demo_personas(self):
        b = get_ai_service().parse_intent(SCENARIOS['b'][1])
        self.assertTrue(b.rent_hard)
        self.assertEqual(b.rent_target, 20_000_000)
        self.assertEqual(b.work_location, 'valiasr')
        c = get_ai_service().parse_intent(SCENARIOS['c'][1])
        self.assertEqual(c.bedrooms_min, 2)
        self.assertIsNone(c.rent_target)
        self.assertEqual(c.preferences['quietness'], 'high')

    def test_parking_phrase_families(self):
        negative = ['پارکینگ مهم نیست', 'پارکینگ لازم نیست', 'پارکینگ نمی‌خوام', 'پارکینگ نمیخوام', 'ماشین ندارم', 'بدون پارکینگ هم اوکیه', 'بدون پارکینگ مشکلی نیست', 'پارکینگ برام اهمیتی نداره', 'پارکینگ اصلاً مهم نیست']
        for text in negative:
            with self.subTest(text=text):
                self.assertEqual(heuristic_parse(text).preferences['parking'], 'low')
        for text, expected in [('پارکینگ مهمه', 'high'), ('پارکینگ خیلی مهمه', 'very_high'), ('حتماً پارکینگ داشته باشه', 'very_high'), ('پارکینگ لازم دارم', 'high')]:
            with self.subTest(text=text):
                self.assertEqual(heuristic_parse(text).preferences['parking'], expected)

    def test_quality_phrase_families(self):
        groups = {
            'natural_light': ['نور خوب', 'نورگیر', 'نورگیره', 'روشن باشه', 'آفتاب‌گیر', 'آفتابگیر', 'خونه تاریک نباشه', 'پنجره بزرگ', 'نور طبیعی'],
            'quietness': ['آروم', 'آرام', 'ساکت', 'دنج', 'شلوغ نباشه', 'آرامش محله مهمه', 'کوچه خلوت'],
            'building_age': ['نوساز', 'جدید', 'ساختمان جدید', 'خیلی قدیمی نباشه', 'قدیمی نباشه', 'سن بنا پایین'],
            'elevator': ['آسانسور لازم دارم', 'آسانسور مهمه'], 'storage': ['انباری لازم دارم', 'انباری مهمه'],
        }
        for key, phrases in groups.items():
            for text in phrases:
                with self.subTest(key=key, text=text):
                    self.assertEqual(heuristic_parse(text).preferences[key], 'high')
        for text, key in [('قدیمی بودن مهم نیست', 'building_age'), ('آسانسور مهم نیست', 'elevator'), ('انباری مهم نیست', 'storage')]:
            self.assertEqual(heuristic_parse(text).preferences[key], 'low')
        self.assertEqual(heuristic_parse('نور خیلی مهمه').preferences['natural_light'], 'very_high')

    def test_relative_and_superlative_priorities(self):
        for phrase in ['رفت‌وآمد از پارکینگ مهم‌تره', 'رفت و آمد از پارکینگ مهم‌تره']:
            p = heuristic_parse(phrase)
            self.assertEqual(p.location_priority, 'very_high')
            self.assertEqual(p.preferences['parking'], 'low')
        p = heuristic_parse('نور از متراژ مهم‌تره')
        self.assertEqual(p.preferences['natural_light'], 'very_high')
        self.assertEqual(p.preferences['area'], 'low')
        for phrase in ['رفت‌وآمد از همه چیز مهم‌تره', 'رفت‌وآمد مهم‌ترین چیزه']:
            self.assertEqual(heuristic_parse(phrase).location_priority, 'very_high')
        self.assertEqual(heuristic_parse('نور اولویت اولمه').preferences['natural_light'], 'very_high')
        self.assertEqual(heuristic_parse('بودجه مهم‌ترین چیزه').budget_priority, 'very_high')

    def test_update_merges_without_mutating_original(self):
        base = get_ai_service().parse_intent(SCENARIOS['a'][1])
        updated = get_ai_service().parse_intent('پارکینگ مهم نیست', base=base)
        expected = base.to_dict()
        expected['preferences']['parking'] = 'low'
        self.assertEqual(updated.to_dict(), expected)
        self.assertEqual(base.preferences['parking'], 'medium')
        self.assertEqual(heuristic_parse('پاركينگ   خيلي مهمه').preferences['parking'], 'very_high')


@override_settings(DATA_MODE='synthetic')
class RankingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_demo', verbosity=0)

    def setUp(self):
        self.intent = get_ai_service().parse_intent(SCENARIOS['a'][1])

    def test_hard_constraints(self):
        ranked = rank_listings(Listing.objects.all(), self.intent)
        self.assertTrue(all(r.listing.bedrooms >= 2 for r in ranked))
        b = get_ai_service().parse_intent(SCENARIOS['b'][1])
        self.assertTrue(all(r.listing.monthly_rent <= 20_000_000 for r in rank_listings(Listing.objects.all(), b)))
        no_elevator = Listing.objects.get(id=4)
        self.assertFalse(eligible(no_elevator, replace(self.intent, elevator_required=True)))
        self.assertFalse(eligible(Listing.objects.get(id=3), replace(self.intent, budget_flexibility='none')))

    def test_parking_low_changes_relative_ranking(self):
        with_parking, without = Listing.objects.get(id=1), Listing.objects.get(id=2)
        with_parking.distance_to_work_km = without.distance_to_work_km = 1
        with_parking.distances = without.distances = {'vanak': 1}
        with_parking.natural_light, without.natural_light = .8, 1
        rows = [with_parking, without]
        self.assertEqual(rank_listings(rows, self.intent)[0].listing.id, 1)
        preferences = dict(self.intent.preferences, parking='low')
        self.assertEqual(rank_listings(rows, replace(self.intent, preferences=preferences))[0].listing.id, 2)

    def test_commute_weight_changes_order(self):
        rows = list(Listing.objects.filter(id__in=[1, 2]))
        self.assertEqual(rank_listings(rows, self.intent)[0].listing.id, 1)
        self.assertEqual(rank_listings(rows, replace(self.intent, location_priority='very_high'))[0].listing.id, 2)

    def test_hero_demo_regression_and_determinism(self):
        rows = list(Listing.objects.all())
        before = rank_listings(rows, self.intent)
        self.assertEqual(before[0].listing.id, 1)
        updated = get_ai_service().parse_intent('پارکینگ مهم نیست؛ رفت‌وآمد از همه چیز مهم‌تره.', base=self.intent)
        self.assertEqual(updated.preferences['parking'], 'low')
        self.assertEqual(updated.location_priority, 'very_high')
        after = rank_listings(rows, updated)
        self.assertEqual(after[0].listing.id, 2)
        self.assertEqual([(r.listing.id, r.score) for r in after], [(r.listing.id, r.score) for r in rank_listings(reversed(rows), updated)])
        self.assertEqual(self.intent.preferences['parking'], 'medium')

    def test_grounded_explanations_and_breakdown(self):
        bright = score_listing(Listing.objects.get(id=3), self.intent)
        evidence = next(e['text'] for e in bright.listing.evidence if e['factor'] == 'natural_light')
        self.assertIn('متن آگهی: «' + evidence + '»', bright.reasons)
        self.assertTrue(any('۲ میلیون' in t for t in bright.tradeoffs))
        self.assertAlmostEqual(sum(row['points'] for row in bright.breakdown), bright.score)
        weak = score_listing(Listing.objects.get(id=11), self.intent)
        self.assertNotIn('آگهی روی نورگیری خوب تأکید دارد', weak.reasons)
        conflict = score_listing(Listing.objects.get(id=10), self.intent)
        self.assertTrue(any('تناقض' in t for t in conflict.tradeoffs))

    def test_seed_is_idempotent(self):
        call_command('seed_demo', verbosity=0)
        self.assertEqual(Listing.objects.count(), 12)

    def test_four_screen_flow_and_reranking(self):
        self.assertEqual(self.client.get('/').status_code, 200)
        self.assertRedirects(self.client.post('/intent/', {'scenario': 'a'}), '/intent/')
        self.assertContains(self.client.get('/intent/'), 'منظورت رو این‌طور فهمیدیم')
        fields = dict(self.intent.preferences, action='confirm', bedrooms_min='2', bedrooms_hard='on', deposit='800', rent='25', budget_flexibility='medium', work_location='vanak', location_priority='high')
        self.assertRedirects(self.client.post('/intent/', fields), '/results/')
        self.assertEqual(self.client.get('/results/').context['items'][0].listing.id, 1)
        self.client.post('/results/', {'update': 'پارکینگ مهم نیست؛ رفت‌وآمد از همه چیز مهم‌تره.'})
        response = self.client.get('/results/')
        self.assertEqual(response.context['items'][0].listing.id, 2)
        self.assertContains(response, 'نداشتن پارکینگ دیگر اهمیت کمی دارد')
        for id in (1, 2, 3, 4):
            self.client.post('/compare/toggle/', {'listing': id})
        self.assertEqual(len(self.client.session['comparison']), 3)
        comparison = self.client.get('/compare/')
        self.assertContains(comparison, 'چرا این گزینه بالاتر قرار گرفته؟')
        self.assertEqual(len(comparison.context['items']), 3)
        self.assertEqual(self.client.get('/homes/2/').status_code, 200)

    def test_refinement_diff_filters_and_comparison_state(self):
        self.client.post('/intent/', {'scenario': 'a'})
        self.client.post('/results/', {'update': 'پارکینگ مهم نیست؛ رفت‌وآمد از همه چیز مهم‌تره'})
        response = self.client.get('/results/')
        self.assertEqual(len(response.context['refinement']['changes']), 2)
        self.assertGreater(response.context['refinement']['moved'], 0)
        self.assertEqual(response.context['items'][0].listing.id, 2)
        original = self.client.session['intent']
        filtered = self.client.get('/results/', {'action': 'filter', 'neighborhood': 'ونک', 'max_rent': 25, 'bedrooms': 2}, follow=True)
        self.assertEqual([r.listing.id for r in filtered.context['items']], [2])
        self.assertEqual(self.client.session['intent']['preferences'], original['preferences'])
        self.client.post('/compare/toggle/', {'listing': 2})
        self.assertEqual(self.client.get('/results/').context['comparison_count'], 1)
        self.client.post('/results/', {'action': 'clear'})
        amenities = self.client.get('/results/', {'action': 'filter', 'amenities': ['parking', 'elevator'], 'max_deposit': 800}, follow=True)
        self.assertTrue(all(r.listing.parking and r.listing.elevator and r.listing.deposit <= 800_000_000 for r in amenities.context['items']))
        invalid = self.client.get('/results/', {'action': 'filter', 'max_rent': -1})
        self.assertContains(invalid, 'مقدار فیلتر معتبر نیست')
        self.assertEqual(self.client.session['intent']['context'], original['context'])

    def test_summary_disclosures_and_detail_context(self):
        self.client.post('/intent/', {'scenario': 'a'})
        review = self.client.get('/intent/')
        self.assertContains(review, 'interpretation-summary')
        self.assertNotContains(review, 'class="advanced-intent" open')
        detail = self.client.get('/homes/2/')
        self.assertNotContains(detail, 'aria-label="مسیر انتخاب خانه"')
        self.assertContains(detail, 'نمایش جزئیات فنی رتبه‌بندی')
        self.assertEqual(self.client.get('/about/').status_code, 200)
        self.client.post('/compare/toggle/', {'listing': 1, 'return': 'detail'})
        self.assertRedirects(self.client.post('/compare/toggle/', {'listing': 1, 'return': 'detail', 'return_pk': 2}), '/homes/2/')

    def test_errors_and_csrf(self):
        self.assertEqual(self.client.post('/intent/', {'query': ''}).status_code, 400)
        self.assertEqual(self.client.post('/intent/', {'query': '۹۹۹۹۹۹۹ میلیون ودیعه'}).status_code, 400)
        self.assertEqual(self.client.post('/compare/toggle/', {'listing': 'bad'}).status_code, 404)
        self.assertRedirects(self.client.get('/results/'), '/')
        protected = Client(enforce_csrf_checks=True)
        self.assertEqual(protected.post('/intent/', {'scenario': 'a'}).status_code, 403)

@override_settings(DATA_MODE='synthetic')
class CanonicalStateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_demo', verbosity=0)

    def state(self):
        from .search import SearchIntent
        return SearchIntent(**self.client.session['intent'])

    def start(self, query=None):
        self.client.post('/intent/', {'query': query} if query else {'scenario':'a'})

    def filters(self, **overrides):
        from .search import filter_initial
        values = filter_initial(self.state())
        values = {k: '' if v is None else v for k,v in values.items()}
        values.update(overrides, action='filter')
        return self.client.post('/results/', values, follow=True)

    def test_a_exact_bedrooms_replace_prompt(self):
        self.start('دوخوابه می‌خوام')
        self.assertEqual(self.state().constraints['bedrooms'], {'mode':'exact','value':2})
        response=self.filters(bedrooms='1')
        self.assertEqual(self.state().constraints['bedrooms'], {'mode':'exact','value':1})
        self.assertTrue(response.context['items'])
        self.assertTrue(all(r.listing.bedrooms==1 for r in response.context['items']))
        self.assertContains(response,'۱ خواب')

    def test_b_required_parking_filters_and_raises_priority(self):
        self.start()
        response=self.filters(amenities=['parking'])
        self.assertIn('parking',self.state().constraints['required_amenities'])
        self.assertIn(self.state().preferences['parking'],('high','very_high'))
        self.assertTrue(all(r.listing.parking for r in response.context['items']))
        self.assertContains(response,'پارکینگ ضروری')

    def test_c_nl_negation_clears_required_control_and_returns_homes(self):
        self.start()
        self.filters(amenities=['parking'])
        response=self.client.post('/results/',{'update':'پارکینگ مهم نیست'},follow=True)
        self.assertNotIn('parking',self.state().constraints['required_amenities'])
        self.assertEqual(self.state().preferences['parking'],'low')
        self.assertNotIn('parking',response.context['filter_form']['amenities'].value())
        self.assertTrue(any(not r.listing.parking for r in response.context['items']))
        self.assertNotIn('amenity:parking',self.state().metadata['manual'])

    def test_d_merge_only_parking(self):
        self.start()
        before=self.state().to_dict()
        self.client.post('/results/',{'update':'پارکینگ مهم نیست'})
        after=self.state().to_dict()
        self.assertEqual(after['constraints'],before['constraints'])
        self.assertEqual(after['targets'],before['targets'])
        self.assertEqual(after['context'],before['context'])
        expected=before['preferences'].copy();expected['parking']='low'
        self.assertEqual(after['preferences'],expected)

    def test_e_minimum_nl_replaces_exact_filter(self):
        self.start()
        self.filters(bedrooms='1')
        response=self.client.post('/results/',{'update':'حداقل دو خواب لازم دارم'},follow=True)
        self.assertEqual(self.state().constraints['bedrooms'],{'mode':'min','value':2})
        self.assertEqual(response.context['filter_form']['bedrooms'].value(),'min2')
        self.assertTrue(all(r.listing.bedrooms>=2 for r in response.context['items']))

    def test_f_commute_superlative_preserves_other_fields(self):
        self.start()
        before=self.state().to_dict()
        self.client.post('/results/',{'update':'رفت‌وآمد از همه چیز مهم‌تره'})
        after=self.state().to_dict()
        self.assertEqual(after['preferences']['commute'],'very_high')
        for k in ('constraints','targets','context'):self.assertEqual(after[k],before[k])
        expected=before['preferences'].copy();expected['commute']='very_high'
        self.assertEqual(after['preferences'],expected)

    def test_g_clear_bedroom_chip(self):
        self.start()
        self.filters(bedrooms='1')
        response=self.client.post('/results/',{'action':'remove','key':'bedrooms'},follow=True)
        self.assertEqual(self.state().constraints['bedrooms'],{'mode':'any','value':None})
        self.assertEqual(response.context['filter_form']['bedrooms'].value(),'')
        self.assertTrue(any(r.listing.bedrooms==2 for r in response.context['items']))

    def test_h_clear_all_manual_preserves_preferences(self):
        self.start()
        self.filters(bedrooms='1',amenities=['parking'],max_rent=20,neighborhood='ونک')
        before=self.state().preferences.copy()
        response=self.client.post('/results/',{'action':'clear'},follow=True)
        self.assertEqual(self.state().metadata['manual'],[])
        self.assertEqual(self.state().preferences,before)
        self.assertEqual(self.state().constraints['bedrooms']['mode'],'any')
        self.assertEqual(self.state().constraints['required_amenities'],[])
        self.assertEqual(self.state().constraints['neighborhoods'],[])
        self.assertIsNone(self.state().constraints['max_rent'])
        self.assertFalse(response.context['active_chips'])

    def test_budget_and_neighborhood_refinement_overrides(self):
        self.start()
        self.filters(max_rent=20,neighborhood='یوسف‌آباد')
        response=self.client.post('/results/',{'update':'اجاره بیشتر از ۲۸ میلیون نشه؛ فقط محله ونک'},follow=True)
        self.assertEqual(self.state().constraints['max_rent'],28_000_000)
        self.assertEqual(self.state().constraints['neighborhoods'],['ونک'])
        self.assertEqual(response.context['filter_form']['max_rent'].value(),28)
        self.assertEqual(response.context['filter_form']['neighborhood'].value(),'ونک')

    def test_zero_recovery_returns_results_and_diff_dismisses(self):
        self.start()
        response=self.filters(neighborhood='ونک',amenities=['parking'])
        self.assertFalse(response.context['items'])
        self.assertContains(response,'با ترکیب این خواسته‌ها گزینه‌ای پیدا نکردیم')
        self.assertTrue(response.context['recoveries'])
        option=next(o for o in response.context['recoveries'] if o['action']=='amenity:parking')
        response=self.client.post('/results/',{'action':'recover','key':option['action']},follow=True)
        self.assertTrue(response.context['items'])
        self.client.post('/results/',{'action':'dismiss'})
        self.assertNotIn('refinement_diff',self.client.session)

    def test_canonical_validation_and_single_session_state(self):
        from .search import SearchIntent
        intent=SearchIntent();data=intent.to_dict();data['constraints']['bedrooms']={'mode':'exact','value':-1}
        with self.assertRaises(ValueError):SearchIntent(**data)
        self.start()
        self.filters(bedrooms='1')
        self.assertNotIn('precision_filters',self.client.session)
        self.assertEqual(set(self.client.session['intent']),{'constraints','preferences','evidence_preferences','targets','context','metadata','logic'})

    def test_wishlist_navigation_and_comparison(self):
        self.start()
        self.client.post('/saved/toggle/',{'listing':2})
        self.assertEqual(self.client.session['saved_listing_ids'],[2])
        results=self.client.get('/results/')
        self.assertEqual(results.context['saved_count'],1)
        self.assertTrue(next(r for r in results.context['items'] if r.listing.id==2).saved)
        self.assertTrue(self.client.get('/homes/2/').context['item'].saved)
        saved=self.client.get('/saved/')
        self.assertEqual([r.listing.id for r in saved.context['items']],[2])
        self.assertRedirects(self.client.post('/compare/toggle/',{'listing':2,'return':'saved'}),'/saved/')
        self.client.post('/saved/toggle/',{'listing':1})
        self.client.post('/compare/toggle/',{'listing':1,'return':'saved'})
        self.assertEqual(len(self.client.get('/compare/').context['items']),2)
        self.client.post('/saved/toggle/',{'listing':2})
        self.assertEqual(self.client.session['saved_listing_ids'],[1])

    def test_wishlist_async_invalid_and_deduplication(self):
        self.start()
        response=self.client.post('/saved/toggle/',{'listing':2},HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.json(),{'id':2,'saved':True,'count':1})
        session=self.client.session;session['saved_listing_ids']=[2,2];session.save()
        self.client.post('/saved/toggle/',{'listing':1})
        self.assertEqual(self.client.session['saved_listing_ids'],[2,1])
        for value in ('bad','999999'):
            self.client.post('/saved/toggle/',{'listing':value})
        self.assertEqual(self.client.session['saved_listing_ids'],[2,1])
        self.assertEqual(self.client.post('/saved/toggle/',{'listing':'bad'},HTTP_X_REQUESTED_WITH='XMLHttpRequest').status_code,404)

    def test_review_preserves_filters_and_inline_changes(self):
        self.start()
        self.filters(bedrooms='1',amenities=['parking'],neighborhood='ونک',max_rent=20)
        intent=self.state()
        fields=dict({k:intent.preferences[k] for k in ('natural_light','parking','elevator','storage','quietness','building_age','area')},action='confirm',bedrooms='1',deposit='800',rent='20',rent_hard='on',work_location='vanak',location_priority='very_high',budget_flexibility='medium',required_amenities_present='1',required_amenities=['parking'])
        response=self.client.post('/intent/',fields,follow=True)
        self.assertEqual(response.status_code,200)
        self.assertEqual(self.state().constraints['neighborhoods'],['ونک'])
        self.assertEqual(self.state().constraints['max_rent'],20_000_000)
        self.assertEqual(self.state().constraints['bedrooms']['value'],1)
        self.assertEqual(self.state().location_priority,'very_high')

    def test_neighborhood_does_not_reassign_workplace_and_compound_recovery(self):
        self.start('دوخوابه نزدیک میدان ولیعصر با ۸۰۰ میلیون ودیعه و ۲۵ میلیون اجاره')
        self.client.post('/results/',{'update':'فقط محله ونک'})
        self.assertEqual(self.state().context['workplace'],'none')
        response=self.filters(bedrooms='1',neighborhood='ونک',amenities=['parking'])
        self.assertFalse(response.context['items'])
        self.assertTrue(response.context['recoveries'])
        action=response.context['recoveries'][0]['action']
        self.assertTrue(self.client.post('/results/',{'action':'recover','key':action},follow=True).context['items'])


@override_settings(DATA_MODE='synthetic')
class BrowseModeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_demo')

    def start(self):
        self.client.post('/intent/', {'scenario':'a'})
        self.client.get('/results/')
        return self.client.session['intent']

    def test_neutral_browse_preserves_personalized_state(self):
        original = self.start()
        response = self.client.get('/browse/')
        self.assertEqual(len(response.context['items']),12)
        neutral = response.context['intent']
        self.assertEqual(neutral.constraints['bedrooms']['mode'],'any')
        self.assertIsNone(neutral.constraints['max_deposit'])
        self.assertIsNone(neutral.constraints['max_rent'])
        self.assertFalse(neutral.constraints['required_amenities'])
        self.assertFalse(neutral.constraints['neighborhoods'])
        self.assertEqual(neutral.work_location,'none')
        self.assertTrue(all(p=='ignored' for p in neutral.preferences.values()))
        self.assertNotContains(response,'معیارهای انتخاب تو')
        self.assertNotContains(response,'چی رو می‌خوای تغییر بدی؟')
        self.assertEqual(self.client.session['intent'],original)
        self.client.get('/results/')
        self.assertEqual(self.client.session['intent'],original)

    def test_browse_exact_rooms_and_clear(self):
        self.client.get('/browse/')
        response=self.client.post('/browse/',{'action':'filter','bedrooms':'1'},follow=True)
        self.assertEqual(len(response.context['items']),2)
        self.assertTrue(all(r.listing.bedrooms==1 for r in response.context['items']))
        response=self.client.post('/browse/',{'action':'remove','key':'bedrooms'},follow=True)
        self.assertEqual(len(response.context['items']),12)
        self.assertEqual(response.context['filter_form']['bedrooms'].value(),'')

    def test_browse_entry_resets_only_browse_constraints(self):
        original=self.start()
        self.client.post('/browse/',{'action':'filter','bedrooms':'1'})
        response=self.client.get('/browse/')
        self.assertEqual(len(response.context['items']),12)
        self.assertEqual(self.client.session['intent'],original)

    def test_browse_sort_and_literal_search(self):
        self.client.get('/browse/')
        response=self.client.post('/browse/',{'action':'search','q':'ونک'},follow=True)
        self.assertEqual(response.resolver_match.url_name,'intent')
        self.assertEqual(response.context['intent'].desired_location,{'neighborhood':'ونک','mode':'exact'})
        self.client.get('/browse/')
        response=self.client.post('/browse/',{'action':'search','q':'بازسازی'},follow=True)
        self.assertTrue(response.context['items'])
        response=self.client.get('/browse/?sort=new')
        years=[r.listing.construction_year for r in response.context['items']]
        self.assertEqual(years,sorted(years,reverse=True))
        response=self.client.post('/browse/',{'action':'clear'},follow=True)
        self.assertEqual(len(response.context['items']),12)

    def test_new_search_preserves_utilities(self):
        self.start()
        self.client.post('/saved/toggle/',{'listing':1})
        self.client.post('/compare/toggle/',{'listing':1})
        session=self.client.session
        session['refinement_diff']={'changes':[]}
        session.save()
        response=self.client.get('/new-search/')
        self.assertRedirects(response,'/')
        self.assertNotIn('intent',self.client.session)
        self.assertNotIn('refinement_diff',self.client.session)
        self.assertNotIn('listing_context',self.client.session)
        self.assertEqual(self.client.session['saved_listing_ids'],[1])
        self.assertEqual(self.client.session['comparison'],[1])

    def test_navigation_has_single_saved_and_compare_entry(self):
        response=self.client.get('/browse/')
        html=response.content.decode()
        nav=html.split('<nav class="global-nav"')[1].split('</nav>')[0]
        self.assertNotIn('/saved/',nav)
        self.assertNotIn('/compare/',nav)
        self.assertIn('/browse/',nav)
        self.assertIn('/new-search/',nav)
        self.assertNotContains(response,'جستجوی فعلی')
        self.start()
        self.assertContains(self.client.get('/browse/'),'جستجوی فعلی')

    def test_bookmarks_saved_browse_detail_comparison(self):
        self.client.get('/browse/')
        response=self.client.get('/browse/?continue=1')
        self.assertContains(response,'class="bookmark-icon"')
        self.assertContains(response,'aria-label="ذخیره خانه"')
        self.client.post('/saved/toggle/',{'listing':1,'return':'browse'})
        for path in ('/browse/?continue=1','/homes/1/','/saved/'):
            response=self.client.get(path)
            self.assertContains(response,'aria-label="حذف از ذخیره‌ها"')
            self.assertContains(response,'fill="currentColor"')
            self.assertNotContains(response,'♥')
            self.assertNotContains(response,'♡')
        self.client.post('/compare/toggle/',{'listing':1,'return':'saved'})
        self.client.post('/compare/toggle/',{'listing':2,'return':'saved'})
        response=self.client.get('/compare/')
        self.assertEqual(len(response.context['items']),2)
        self.assertContains(response,'aria-label="حذف از ذخیره‌ها"')
        self.assertNotContains(response,'خارج از محدودیت‌های فعلی')
        self.assertNotContains(response,'چرا این گزینه بالاتر قرار گرفته؟')

    def test_browse_save_compare_returns_preserve_filters(self):
        self.client.get('/browse/')
        self.client.post('/browse/',{'action':'filter','bedrooms':'1'})
        for route in ('/saved/toggle/','/compare/toggle/'):
            response=self.client.post(route,{'listing':8,'return':'browse'},follow=True)
            self.assertEqual(len(response.context['items']),2)

    def test_personalized_bookmark_and_sidebar_remain(self):
        self.start()
        self.client.post('/saved/toggle/',{'listing':1})
        response=self.client.get('/results/')
        self.assertContains(response,'معیارهای انتخاب تو')
        self.assertContains(response,'بهترین تطابق')
        self.assertContains(response,'aria-label="حذف از ذخیره‌ها"')
        self.assertContains(self.client.get('/homes/1/'),'نمایش جزئیات فنی رتبه‌بندی')



@override_settings(DATA_MODE='synthetic')
class StatefulRefinementTests(TestCase):
    INITIAL = 'خونه دوخوابه نزدیک ونک می‌خوام، نور خوب باشه و پارکینگ مهمه'
    FOLLOW = 'حالا داخل ونک هم نبود اشکال نداره، ولی نزدیکش باشه و حتما آسانسور داشته باشه'

    @classmethod
    def setUpTestData(cls): call_command('seed_demo')

    def state(self):
        from .search import SearchIntent
        return SearchIntent(**self.client.session['intent'])

    def start(self,text=None,route='/intent/'):
        self.client.post(route,{'query':text or self.INITIAL} if route=='/intent/' else {'action':'search','q':text or self.INITIAL})
        return self.state()

    def update(self,text):
        return self.client.post('/results/',{'update':text},follow=True)

    def test_required_full_query_followup_and_compound_flow(self):
        original=self.start()
        self.assertEqual(original.constraints['bedrooms'],{'mode':'exact','value':2})
        self.assertEqual(original.desired_location,{'neighborhood':'ونک','mode':'nearby'})
        self.assertEqual(original.preferences['natural_light'],'high')
        self.assertEqual(original.preferences['parking'],'high')
        self.assertEqual(original.preferences['elevator'],'ignored')
        initial_order=[r.listing.id for r in self.client.get('/results/').context['items']]
        self.update(self.FOLLOW)
        after=self.state()
        for field in ('bedrooms','neighborhoods','neighborhood_mode'): self.assertEqual(after.constraints[field],original.constraints[field])
        for key in ('natural_light','parking'): self.assertEqual(after.preferences[key],original.preferences[key])
        self.assertIn('elevator',after.constraints['required_amenities'])
        self.assertEqual(after.preferences['elevator'],'very_high')
        response=self.update('پارکینگ دیگه مهم نیست و تا ۳۰ میلیون اجاره هم اوکیه')
        final=self.state()
        self.assertEqual(final.constraints['max_rent'],30_000_000)
        self.assertEqual(final.rent_target,30_000_000)
        self.assertEqual(final.preferences['parking'],'low')
        self.assertEqual(final.constraints['bedrooms'],original.constraints['bedrooms'])
        self.assertEqual(final.desired_location,original.desired_location)
        self.assertEqual(final.preferences['natural_light'],'high')
        self.assertIn('elevator',final.constraints['required_amenities'])
        self.assertNotEqual(initial_order,[r.listing.id for r in response.context['items']])

    def test_patch_is_sparse_and_validated(self):
        from .patches import IntentPatch
        current=self.start()
        patch=get_ai_service().parse_intent_patch('حالا آسانسور هم حتما داشته باشه',current,list(Listing.objects.values_list('neighborhood',flat=True)))
        self.assertEqual(set(patch.set),{'constraints.required_amenities','preferences.elevator'})
        self.assertFalse(patch.unset)
        with self.assertRaises(ValueError): IntentPatch(set={'unknown.x':1}).merge(current)
        with self.assertRaises(ValueError): IntentPatch(set={'preferences.parking':'invented'}).merge(current)
        empty=get_ai_service().parse_intent_patch('حالا',current,[])
        self.assertFalse(empty.set); self.assertFalse(empty.unset)

    def test_remove_parking_preserves_every_unrelated_value(self):
        self.start(); self.update('حتما پارکینگ داشته باشه')
        before=self.state().to_dict()
        self.update('پارکینگ دیگه مهم نیست')
        after=self.state().to_dict()
        self.assertNotIn('parking',after['constraints']['required_amenities'])
        self.assertEqual(after['preferences']['parking'],'low')
        for group in ('context','targets'): self.assertEqual(after[group],before[group])
        self.assertEqual(after['constraints']['bedrooms'],before['constraints']['bedrooms'])
        self.assertEqual(after['preferences']['natural_light'],before['preferences']['natural_light'])

    def test_remove_bedrooms_only(self):
        before=self.start()
        self.update('دوخوابه بودن هم دیگه مهم نیست')
        after=self.state()
        self.assertEqual(after.constraints['bedrooms'],{'mode':'any','value':None})
        self.assertEqual(after.preferences,before.preferences)
        self.assertEqual(after.desired_location,before.desired_location)

    def test_budget_update_and_removal(self):
        self.start('دوخوابه نزدیک ونک با ۲۵ میلیون اجاره')
        before=self.state()
        self.update('تا ۳۰ میلیون اجاره هم اوکیه')
        self.assertEqual(self.state().rent_target,30_000_000)
        self.assertEqual(self.state().constraints['max_rent'],30_000_000)
        self.assertEqual(self.state().constraints['bedrooms'],before.constraints['bedrooms'])
        self.update('بودجه فعلاً مهم نیست')
        self.assertIsNone(self.state().rent_target)
        self.assertIsNone(self.state().constraints['max_rent'])

    def test_exact_nearby_and_ui_synchronize(self):
        self.start()
        self.client.post('/results/',{'action':'filter','neighborhood':'ونک','neighborhood_scope':'exact','bedrooms':'2'})
        self.assertEqual(self.state().desired_location['mode'],'exact')
        response=self.update('اطراف ونک هم خوبه')
        self.assertEqual(response.context['filter_form']['neighborhood_scope'].value(),'nearby')
        self.assertEqual(response.context['filter_form']['neighborhood'].value(),'ونک')
        response=self.update('فقط خود ونک باشه')
        self.assertEqual(self.state().desired_location['mode'],'exact')
        self.assertEqual(response.context['filter_form']['neighborhood_scope'].value(),'exact')
        self.assertEqual(self.state().preferences['natural_light'],'high')

    def test_workplace_separate_from_residence(self):
        for text in ('حوالی ونک کار می‌کنم','حوالی ونک کار می‌کنم، نزدیک محل کار بودن خیلی مهمه'):
            self.client.get('/new-search/')
            current=self.start(text)
            self.assertEqual(current.work_location,'vanak')
            self.assertIsNone(current.desired_location['neighborhood'])
            self.assertIn(current.location_priority,('high','very_high'))
        self.client.get('/new-search/')
        current=self.start('حوالی ونک کار می‌کنم و می‌خوام نزدیک ونک خونه بگیرم')
        self.assertEqual(current.work_location,'vanak')
        self.assertEqual(current.desired_location,{'neighborhood':'ونک','mode':'nearby'})

    def test_home_and_browse_share_pipeline_and_followups(self):
        home=self.start().to_dict()
        self.client.get('/new-search/');self.client.get('/browse/')
        response=self.client.post('/browse/',{'action':'search','q':self.INITIAL},follow=True)
        self.assertEqual(response.resolver_match.url_name,'intent')
        self.assertEqual(self.state().to_dict(),home)
        self.client.get('/browse/')
        response=self.client.post('/browse/',{'action':'search','q':self.FOLLOW},follow=True)
        self.assertEqual(response.resolver_match.url_name,'intent')
        self.assertEqual(self.state().constraints['bedrooms']['value'],2)
        self.assertEqual(self.state().preferences['parking'],'high')
        self.assertIn('elevator',self.state().constraints['required_amenities'])

    def test_short_queries_and_no_structured_literal_fallback(self):
        for text,check in [('ونک',lambda i:i.desired_location['mode']=='exact'),('دوخوابه',lambda i:i.constraints['bedrooms']['value']==2),('پارکینگ',lambda i:i.preferences['parking']=='high')]:
            self.client.get('/new-search/');self.client.get('/browse/')
            self.start(text,'/browse/')
            self.assertTrue(check(self.state()))
        self.client.get('/new-search/');self.client.get('/browse/')
        response=self.client.post('/browse/',{'action':'search','q':'بازسازی'},follow=True)
        self.assertEqual(response.resolver_match.url_name,'browse')
        self.assertNotIn('intent',self.client.session)

    def test_browse_manual_scope_and_default_exact(self):
        self.client.get('/browse/')
        exact=self.client.post('/browse/',{'action':'filter','neighborhood':'ونک'},follow=True)
        self.assertEqual([r.listing.neighborhood for r in exact.context['items']],['ونک'])
        near=self.client.post('/browse/',{'action':'filter','neighborhood':'ونک','neighborhood_scope':'nearby'},follow=True)
        self.assertGreater(len(near.context['items']),1)
        self.assertTrue(any(r.listing.neighborhood=='یوسف‌آباد' for r in near.context['items']))
        self.assertNotIn('intent',self.client.session)

    def test_proximity_scoring_and_explanation(self):
        current=self.start('نزدیک ونک')
        target=score_listing(Listing.objects.get(pk=2),current)
        near=score_listing(Listing.objects.get(pk=1),current)
        self.assertGreater(next(r['points'] for r in target.breakdown if r['key']=='location'),next(r['points'] for r in near.breakdown if r['key']=='location'))
        self.assertTrue(any('محدوده نزدیک به ونک' in r for r in near.reasons))
        self.assertFalse(any('کیلومتر' in r for r in near.reasons))

    def test_acceptable_bedrooms_and_manual_override(self):
        self.start('دوخوابه')
        response=self.update('یک خوابه هم اوکیه')
        self.assertEqual(self.state().constraints['bedrooms'],{'mode':'allowed','value':[1,2]})
        self.assertTrue(any(r.listing.bedrooms==1 for r in response.context['items']))
        self.assertTrue(any(r.listing.bedrooms==2 for r in response.context['items']))
        self.assertFalse(any(r.listing.bedrooms==3 for r in response.context['items']))
        self.client.post('/results/',{'action':'filter','bedrooms':'1'})
        self.assertEqual(self.state().constraints['bedrooms'],{'mode':'exact','value':1})

    def test_remove_location_and_light(self):
        self.start();self.update('محله مهم نیست')
        self.assertIsNone(self.state().desired_location['neighborhood'])
        self.assertEqual(self.state().constraints['bedrooms']['value'],2)
        self.update('نور دیگه مهم نیست')
        self.assertEqual(self.state().preferences['natural_light'],'low')
        self.assertEqual(self.state().preferences['parking'],'high')

    def test_compound_diff_only_changes_and_user_center(self):
        self.start()
        response=self.update('پارکینگ مهم نیست، تا ۳۰ میلیون اجاره اوکیه، حتما آسانسور داشته باشه')
        labels=[r['label'] for r in response.context['refinement']['changes']]
        self.assertIn('پارکینگ',labels);self.assertIn('آسانسور',labels)
        self.assertNotIn('اتاق خواب',labels);self.assertNotIn('نورگیری',labels)
        panel=response.content.decode().split('<div class="user-panel">')[1].split('</details>')[0]
        self.assertIn('ونک و اطراف',panel);self.assertIn('خانه‌های من',panel)
        self.assertNotIn('روش کار',panel)
        self.client.get('/new-search/')
        self.assertNotContains(self.client.get('/browse/'),'جستجوی فعلی')

    def test_zero_recovery_acceptable_bedrooms(self):
        self.start('سه خوابه فقط ونک')
        response=self.client.get('/results/')
        self.assertFalse(response.context['items'])
        self.assertContains(response,'۳ خواب')
        self.assertTrue(any(o['action']=='accept:bedrooms' for o in response.context['recoveries']))
        response=self.client.post('/results/',{'action':'recover','key':'accept:bedrooms'},follow=True)
        self.assertTrue(response.context['items'])
        self.assertEqual(self.state().constraints['bedrooms'],{'mode':'allowed','value':[2,3]})


    def test_residential_patch_does_not_lower_workplace_priority(self):
        self.start('حوالی ونک کار می‌کنم، رفت‌وآمد از همه چیز مهم‌تره')
        before=self.state()
        self.update('نزدیک ونک خونه می‌خوام')
        self.assertEqual(self.state().location_priority,before.location_priority)
        self.assertEqual(self.state().work_location,before.work_location)
        self.assertEqual(self.state().desired_location['mode'],'nearby')


@override_settings(DATA_MODE='synthetic')
class QueryOperationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_demo')

    def state(self):
        from .search import SearchIntent
        return SearchIntent(**self.client.session['intent'])

    def start(self, text):
        self.client.post('/intent/', {'query': text})
        return self.state()

    def update(self, text, **kwargs):
        return self.client.post('/results/', {'update': text, **kwargs}, follow=True)

    def test_classification(self):
        from .query import classify_query, QueryOperation
        current = self.start(SCENARIOS['c'][1])
        for text in (SCENARIOS['c'][1], 'سه خوابه، ساکت و نوساز با انباری'):
            self.assertEqual(classify_query(text,current), QueryOperation.NEW_SEARCH)
        for text in ('حتما داخل ونک باشه','حالا نور مهم‌تره','اطرافش هم خوبه','نزدیک محل کارم','همچنان دوخوابه'):
            self.assertEqual(classify_query(text,current), QueryOperation.PATCH)

    def test_family_vanak_family_replaces_stale_location(self):
        first = self.start(SCENARIOS['c'][1]).to_dict()
        self.update('حتما داخل ونک باشه')
        self.assertEqual(self.state().desired_location, {'neighborhood':'ونک','mode':'exact'})
        response = self.update(SCENARIOS['c'][1])
        self.assertEqual(self.client.session['last_query_operation'],'NEW_SEARCH')
        self.assertEqual(self.state().to_dict(),first)
        self.assertContains(response,'جستجوی جدید از درخواستت ساخته شد.')
        self.assertIsNone(self.state().desired_location['neighborhood'])

    def test_workplace_commands_preserve_unmentioned_fields(self):
        before = self.start(SCENARIOS['a'][1])
        for text, mode in [('داخل محل کارم خانه پیدا کن','exact'),('نزدیک محل کارم','nearby'),('اطراف محل کارم هم خوبه','nearby'),('خود محل کارم باشه','exact'),('نزدیک همون جایی که کار می‌کنم خانه پیدا کن','nearby')]:
            self.update(text)
            after = self.state()
            self.assertEqual(after.desired_location,{'neighborhood':'ونک','mode':mode})
            self.assertEqual(after.constraints['bedrooms'],before.constraints['bedrooms'])
            self.assertEqual(after.targets,before.targets)
            self.assertEqual(after.preferences,before.preferences)
            self.assertEqual(after.context,before.context)

    def test_unknown_workplace_requests_clarification_without_mutation(self):
        before = self.start('دوخوابه نور خوب و پارکینگ مهمه').to_dict()
        response = self.update('نزدیک محل کارم باشه')
        self.assertEqual(self.state().to_dict(),before)
        self.assertEqual(self.client.session['pending_query']['reference'],'workplace')
        self.assertContains(response,'محل کارت رو هنوز نمی‌دونیم. کجا کار می‌کنی؟')
        self.client.post('/intent/',{'action':'clarify','reference_place':'نامعلوم'})
        self.assertEqual(self.state().to_dict(),before)
        response = self.client.post('/intent/',{'action':'clarify','reference_place':'ونک'},follow=True)
        self.assertEqual(self.state().work_location,'vanak')
        self.assertEqual(self.state().desired_location,{'neighborhood':'ونک','mode':'nearby'})
        self.assertEqual(self.state().constraints['bedrooms'],before['constraints']['bedrooms'])
        self.assertNotIn('pending_query',self.client.session)

    def test_direct_provider_unresolved_reference_is_explicit(self):
        from .query import UnresolvedReference
        current = self.start('دوخوابه')
        with self.assertRaises(UnresolvedReference) as error:
            get_ai_service().parse_intent_patch('نزدیک محل کارم',current,['ونک'])
        self.assertEqual(error.exception.needs_clarification,'workplace')

    def test_previous_neighborhood_references(self):
        before = self.start('دوخوابه فقط ونک با نور خوب و ۲۵ میلیون اجاره')
        for text,mode in [('اطرافش هم خوبه','nearby'),('فقط خودش باشه','exact'),('نزدیک همون محله باشه','nearby'),('داخل همان محله باشه','exact')]:
            self.update(text)
            self.assertEqual(self.state().desired_location,{'neighborhood':'ونک','mode':mode})
            self.assertEqual(self.state().targets,before.targets)
            self.assertEqual(self.state().preferences,before.preferences)

    def test_missing_previous_location_and_resume(self):
        self.start('دوخوابه')
        before=self.state().to_dict()
        self.update('اطرافش هم خوبه')
        self.assertEqual(self.state().to_dict(),before)
        self.assertEqual(self.client.session['pending_query']['reference'],'desired_location')
        self.client.post('/intent/',{'action':'clarify','reference_place':'ونک'})
        self.assertEqual(self.state().desired_location,{'neighborhood':'ونک','mode':'nearby'})

    def test_force_new_and_preserve_utilities(self):
        self.start(SCENARIOS['a'][1])
        session=self.client.session
        session['saved_listing_ids']=[1];session['comparison']=[1,2];session['theme']='dark';session.save()
        response=self.update('دوخوابه',operation='NEW_SEARCH')
        self.assertEqual(self.client.session['last_query_operation'],'NEW_SEARCH')
        self.assertIsNone(self.state().deposit_target)
        self.assertEqual(self.state().work_location,'none')
        self.assertEqual(self.state().preferences['natural_light'],'ignored')
        self.assertEqual(self.client.session['saved_listing_ids'],[1])
        self.assertEqual(self.client.session['comparison'],[1,2])
        self.assertEqual(self.client.session['theme'],'dark')
        self.assertContains(response,'name="operation" value="NEW_SEARCH"')

    def test_shared_home_browse_classification(self):
        for route,data in [('/intent/',{'query':SCENARIOS['c'][1]}),('/browse/',{'action':'search','q':SCENARIOS['c'][1]})]:
            self.start('دوخوابه فقط ونک')
            response=self.client.post(route,data,follow=True)
            self.assertEqual(response.resolver_match.url_name,'intent')
            self.assertIsNone(self.state().desired_location['neighborhood'])
            self.assertEqual(self.client.session['last_query_operation'],'NEW_SEARCH')

    def test_first_query_unknown_context_can_resume(self):
        response=self.client.post('/browse/',{'action':'search','q':'داخل محل کارم خانه پیدا کن'},follow=True)
        self.assertNotIn('intent',self.client.session)
        self.assertContains(response,'محل کارت رو هنوز نمی‌دونیم')
        self.client.post('/intent/',{'action':'clarify','reference_place':'ولیعصر'})
        self.assertEqual(self.state().work_location,'valiasr')
        self.assertEqual(self.state().desired_location,{'neighborhood':'ولیعصر','mode':'exact'})

    def test_cancel_and_reset_clear_pending_reference(self):
        before=self.start('دوخوابه').to_dict()
        self.update('نزدیک محل کارم')
        self.client.post('/intent/',{'action':'clarify','cancel':'1'})
        self.assertNotIn('pending_query',self.client.session)
        self.assertEqual(self.state().to_dict(),before)
        self.update('نزدیک محل کارم')
        self.client.get('/new-search/')
        self.assertNotIn('pending_query',self.client.session)
        self.assertNotIn('search_notice',self.client.session)
