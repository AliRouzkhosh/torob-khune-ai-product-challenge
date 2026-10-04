"""v0.9-A regression coverage for the expanded Persian language foundation.

These tests intentionally cover only language families activated in v0.9-A.  The
full 320-case declarative corpus lives under docs/search_language and is enabled in
later implementation batches as the SearchIntent schema grows.
"""
from django.test import SimpleTestCase, override_settings

from .ai import get_ai_service
from .intent import heuristic_parse, normalize
from .query import QueryOperation, classify_query
from .search import SearchIntent


@override_settings(AI_PROVIDER='mock')
class SearchLanguageFoundationTests(SimpleTestCase):
    def service(self):
        return get_ai_service()

    def test_normalization_covers_common_colloquial_variants(self):
        self.assertEqual(normalize('پاركينگ   خيلي مهمه'), 'پارکینگ خیلی مهمه')
        self.assertEqual(normalize('اسانسور میخام'), 'آسانسور می خوام')
        self.assertEqual(normalize('بالکون و ۳۰ ملیون تومن'), 'بالکن و 30 میلیون تومان')

    def test_misspelled_parking_and_elevator_keep_existing_semantics(self):
        self.assertEqual(heuristic_parse('پاركينگ خیلی مهمه').preferences['parking'], 'very_high')
        elevator = heuristic_parse('اسانسور برام واجبه')
        self.assertEqual(elevator.preferences['elevator'], 'very_high')
        self.assertTrue(elevator.elevator_required)

    def test_negative_quality_wording_is_positive_requirement(self):
        self.assertEqual(heuristic_parse('خونه دلگیر و تاریک نباشه').preferences['natural_light'], 'high')
        self.assertEqual(heuristic_parse('جای شلوغ نمی خوام').preferences['quietness'], 'high')
        self.assertEqual(heuristic_parse('خونه قدیمی نمی خوام').preferences['building_age'], 'high')

    def test_money_aliases(self):
        p = heuristic_parse('۷۰۰ میلیون پول پیش و ۲۵ میلیون کرایه')
        self.assertEqual(p.deposit_target, 700_000_000)
        self.assertEqual(p.rent_target, 25_000_000)

    def test_budget_flexibility_colloquial(self):
        self.assertEqual(
            heuristic_parse('اگه مورد خیلی خوب بود یه کم بیشتر هم می دم').budget_flexibility,
            'flexible',
        )
        self.assertEqual(
            heuristic_parse('بالاتر از بودجه نمی رم، سقف بودجه ثابته').budget_flexibility,
            'none',
        )

    def test_allowed_bedrooms_are_preserved_in_search_intent(self):
        intent = self.service().parse_full_intent('دو یا سه خوابه می خوام', ())
        self.assertEqual(intent.constraints['bedrooms'], {'mode': 'allowed', 'value': [2, 3]})

    def test_colloquial_nearby_location(self):
        intent = self.service().parse_full_intent('یه خونه دو خواب دوروبر ونک میخام', ('ونک',))
        self.assertEqual(intent.constraints['bedrooms'], {'mode': 'exact', 'value': 2})
        self.assertEqual(intent.desired_location, {'neighborhood': 'ونک', 'mode': 'nearby'})
        self.assertEqual(intent.work_location, 'none')

    def test_rent_alias_patch_preserves_other_state(self):
        service = self.service()
        current = service.parse_full_intent('دوخوابه نزدیک ونک نور خوب و پارکینگ مهمه', ('ونک',))
        after = service.parse_intent_patch('تا ۳۰ میلیون کرایه هم اوکیه', current, ('ونک',)).merge(current)
        self.assertEqual(after.rent_target, 30_000_000)
        self.assertEqual(after.constraints['max_rent'], 30_000_000)
        self.assertEqual(after.constraints['bedrooms'], current.constraints['bedrooms'])
        self.assertEqual(after.preferences['natural_light'], current.preferences['natural_light'])
        self.assertEqual(after.preferences['parking'], current.preferences['parking'])

    def test_required_elevator_colloquial_patch(self):
        service = self.service()
        current = service.parse_full_intent('دوخوابه نور خوب', ())
        after = service.parse_intent_patch('اسانسور برام واجبه', current, ()).merge(current)
        self.assertIn('elevator', after.constraints['required_amenities'])
        self.assertEqual(after.preferences['elevator'], 'very_high')
        self.assertEqual(after.constraints['bedrooms'], current.constraints['bedrooms'])

    def test_classification_counts_new_language_dimensions(self):
        current = SearchIntent()
        self.assertEqual(
            classify_query('دوخوابه، طبقه سوم، نوساز و نزدیک مترو', current),
            QueryOperation.NEW_SEARCH,
        )
        self.assertEqual(
            classify_query('حالا اسانسور هم واجبه', current),
            QueryOperation.PATCH,
        )

    def test_parking_relaxation_colloquial(self):
        service = self.service()
        current = service.parse_full_intent('دوخوابه و پارکینگ مهمه', ())
        after = service.parse_intent_patch('ماشین ندارم، پارکینگ لازم نیست', current, ()).merge(current)
        self.assertEqual(after.preferences['parking'], 'low')
        self.assertNotIn('parking', after.constraints['required_amenities'])

    def test_full_query_does_not_invent_unmentioned_workplace(self):
        intent = self.service().parse_full_intent('دوخوابه نزدیک ونک می خوام، نور خوب باشه', ('ونک',))
        self.assertEqual(intent.work_location, 'none')
        self.assertEqual(intent.desired_location, {'neighborhood': 'ونک', 'mode': 'nearby'})


@override_settings(AI_PROVIDER='mock')
class StructuredHousingConstraintTests(SimpleTestCase):
    """v0.9-B: constraints backed by structured Listing fields."""

    def service(self):
        return get_ai_service()

    def test_area_min_max_and_range(self):
        service = self.service()
        self.assertEqual(service.parse_full_intent('حداقل ۱۰۰ متر باشه', ()).constraints['area'], {'min': 100, 'max': None})
        self.assertEqual(service.parse_full_intent('حداکثر ۹۰ متر', ()).constraints['area'], {'min': None, 'max': 90})
        self.assertEqual(service.parse_full_intent('بین ۸۰ تا ۱۱۰ متر می خوام', ()).constraints['area'], {'min': 80, 'max': 110})

    def test_floor_allowed_range_and_exclusions(self):
        service = self.service()
        self.assertEqual(
            service.parse_full_intent('طبقه دوم یا سوم بهتره', ()).constraints['floor'],
            {'mode': 'allowed', 'value': [2, 3], 'excluded': []},
        )
        self.assertEqual(
            service.parse_full_intent('بالاتر از طبقه چهار نباشه', ()).constraints['floor'],
            {'mode': 'max', 'value': 4, 'excluded': []},
        )
        self.assertEqual(
            set(service.parse_full_intent('همکف و زیرزمین نه', ()).constraints['floor']['excluded']),
            {'ground', 'basement'},
        )

    def test_explicit_building_age_becomes_hard_year_constraint(self):
        intent = self.service().parse_full_intent('زیر ۵ سال ساخت باشه', ())
        self.assertEqual(intent.constraints['construction_year_min'], 1400)
        self.assertIn('ساخت ۱۴۰۰ به بعد', intent.structured_constraint_labels)

    def test_unconditional_renovation_requirement(self):
        intent = self.service().parse_full_intent('بازسازی کامل لازم دارم', ())
        self.assertTrue(intent.constraints['renovation_required'])
        self.assertIn('بازسازی‌شده ضروری', intent.structured_constraint_labels)

    def test_conditional_renovation_is_not_flattened_yet(self):
        intent = self.service().parse_full_intent('قدیمی اشکال نداره اگر بازسازی شده باشه', ())
        self.assertFalse(intent.constraints['renovation_required'])

    def test_max_bedroom_constraint(self):
        intent = self.service().parse_full_intent('حداکثر دو خواب', ())
        self.assertEqual(intent.constraints['bedrooms'], {'mode': 'max', 'value': 2})
        self.assertEqual(intent.bedroom_label, 'حداکثر ۲ خواب')

    def test_structured_patch_preserves_unmentioned_state(self):
        service = self.service()
        current = service.parse_full_intent('دو خوابه نور خوب و پارکینگ مهمه', ())
        after = service.parse_intent_patch('حالا حداقل ۱۲۰ متر باشه', current, ()).merge(current)
        self.assertEqual(after.constraints['area'], {'min': 120, 'max': None})
        self.assertEqual(after.constraints['bedrooms'], current.constraints['bedrooms'])
        self.assertEqual(after.preferences['natural_light'], current.preferences['natural_light'])
        self.assertEqual(after.preferences['parking'], current.preferences['parking'])

    def test_old_search_state_is_migrated_without_losing_values(self):
        data = SearchIntent().to_dict()
        data['constraints']['bedrooms'] = {'mode': 'exact', 'value': 2}
        for key in ('area', 'floor', 'construction_year_min', 'renovation_required'):
            data['constraints'].pop(key)
        migrated = SearchIntent(**data)
        self.assertEqual(migrated.constraints['bedrooms'], {'mode': 'exact', 'value': 2})
        self.assertEqual(migrated.constraints['area'], {'min': None, 'max': None})
        self.assertEqual(migrated.constraints['floor'], {'mode': 'any', 'value': None, 'excluded': []})
        self.assertIsNone(migrated.constraints['construction_year_min'])
        self.assertFalse(migrated.constraints['renovation_required'])

    def test_structured_constraints_can_be_unset_by_refinement(self):
        service = self.service()
        current = service.parse_full_intent('حداقل ۱۰۰ متر و طبقه دوم', ())
        after = service.parse_intent_patch('متراژ دیگه مهم نیست و طبقه هم مهم نیست', current, ()).merge(current)
        self.assertEqual(after.constraints['area'], {'min': None, 'max': None})
        self.assertEqual(after.constraints['floor'], {'mode': 'any', 'value': None, 'excluded': []})


@override_settings(AI_PROVIDER='mock')
class TextEvidenceLanguageTests(SimpleTestCase):
    """v0.9-C: seller/ad-text criteria keep YES/NO/UNKNOWN semantics."""

    def service(self):
        return get_ai_service()

    def test_pet_ownership_becomes_confirmed_allowed_requirement(self):
        intent = self.service().parse_full_intent('گربه دارم و حیوان خانگی حتماً مجاز باشه', ())
        self.assertEqual(intent.constraints['pet_policy'], 'allowed')
        self.assertEqual(intent.evidence_preferences['pet_allowed'], 'very_high')

    def test_two_non_tandem_parking_spaces(self):
        intent = self.service().parse_full_intent('دو تا پارکینگ غیرمزاحم لازم دارم', ())
        self.assertEqual(intent.constraints['parking_count_min'], 2)
        self.assertTrue(intent.constraints['parking_non_tandem_required'])
        self.assertIn('parking', intent.constraints['required_amenities'])

    def test_parking_dedicated_can_be_soft_preference(self):
        intent = self.service().parse_full_intent('پارکینگ اختصاصی ترجیح می دم', ())
        self.assertFalse(intent.constraints['parking_dedicated_required'])
        self.assertEqual(intent.evidence_preferences['parking_dedicated'], 'medium')

    def test_furnishing_hard_vs_soft(self):
        hard = self.service().parse_full_intent('مبله باشه', ())
        soft = self.service().parse_full_intent('ترجیحاً مبله باشه', ())
        self.assertEqual(hard.constraints['furnishing'], 'furnished')
        self.assertEqual(soft.constraints['furnishing'], 'any')
        self.assertEqual(soft.evidence_preferences['furnished'], 'medium')

    def test_multiple_hvac_preferences_and_required_hvac(self):
        soft = self.service().parse_full_intent('پکیج و کولر گازی مهمه', ())
        hard = self.service().parse_full_intent('حتماً کولر گازی داشته باشه', ())
        self.assertEqual(soft.evidence_preferences['package_heating'], 'high')
        self.assertEqual(soft.evidence_preferences['split_ac'], 'high')
        self.assertEqual(hard.constraints['hvac_required'], ['split_ac'])

    def test_density_security_transport_view_and_accessibility(self):
        service = self.service()
        self.assertEqual(service.parse_full_intent('تک واحدی می خوام', ()).constraints['building_density'], 'single_unit')
        self.assertEqual(service.parse_full_intent('نگهبانی 24 ساعته برام مهمه', ()).evidence_preferences['security_24h'], 'high')
        self.assertEqual(service.parse_full_intent('دوربین مداربسته داشته باشه', ()).constraints['security_required'], ['cctv'])
        self.assertEqual(service.parse_full_intent('نزدیک مترو باشه', ()).evidence_preferences['near_metro'], 'high')
        self.assertEqual(service.parse_full_intent('مشرف نباشه', ()).constraints['view_privacy_required'], ['privacy'])
        self.assertEqual(service.parse_full_intent('ورودی بدون پله لازم دارم', ()).constraints['accessibility_required'], ['step_free'])

    def test_evidence_patch_preserves_unmentioned_state(self):
        service = self.service()
        current = service.parse_full_intent('دو خوابه نور خوب و پکیج مهمه', ())
        after = service.parse_intent_patch('حالا دو تا پارکینگ غیرمزاحم لازم دارم', current, ()).merge(current)
        self.assertEqual(after.constraints['bedrooms'], current.constraints['bedrooms'])
        self.assertEqual(after.preferences['natural_light'], current.preferences['natural_light'])
        self.assertEqual(after.evidence_preferences['package_heating'], current.evidence_preferences['package_heating'])
        self.assertEqual(after.constraints['parking_count_min'], 2)

    def test_feature_unset_does_not_erase_sibling_hvac_requirement(self):
        service = self.service()
        current = service.parse_full_intent('حتماً پکیج و کولر گازی داشته باشه', ())
        after = service.parse_intent_patch('کولر گازی دیگه مهم نیست', current, ()).merge(current)
        self.assertIn('package_heating', after.constraints['hvac_required'])
        self.assertNotIn('split_ac', after.constraints['hvac_required'])

    def test_v09b_session_state_migrates_evidence_fields(self):
        data = SearchIntent().to_dict()
        data.pop('evidence_preferences')
        for key in (
            'pet_policy', 'parking_count_min', 'parking_non_tandem_required',
            'parking_dedicated_required', 'furnishing', 'hvac_required',
            'building_density', 'security_required', 'transport_required',
            'view_privacy_required', 'accessibility_required',
        ):
            data['constraints'].pop(key)
        migrated = SearchIntent(**data)
        self.assertEqual(migrated.constraints['pet_policy'], 'any')
        self.assertIsNone(migrated.constraints['parking_count_min'])
        self.assertEqual(migrated.constraints['hvac_required'], [])
        self.assertTrue(all(value == 'ignored' for value in migrated.evidence_preferences.values()))

    def test_unknown_evidence_never_confirms_hard_pet_requirement(self):
        from types import SimpleNamespace
        from .evidence_features import evidence_requirement_matches, extract_listing_evidence, YES, NO, UNKNOWN
        intent = self.service().parse_full_intent('حیوان خانگی حتماً مجاز باشه', ())
        yes = SimpleNamespace(title='آپارتمان', description='داشتن حیوان خانگی مشکلی ندارد', parking=True)
        no = SimpleNamespace(title='آپارتمان', description='فقط خانواده بدون حیوان خانگی', parking=True)
        unknown = SimpleNamespace(title='آپارتمان', description='واحد تمیز و خوش نقشه', parking=True)
        self.assertEqual(extract_listing_evidence(yes).pet_policy, YES)
        self.assertEqual(extract_listing_evidence(no).pet_policy, NO)
        self.assertEqual(extract_listing_evidence(unknown).pet_policy, UNKNOWN)
        self.assertTrue(evidence_requirement_matches(yes, intent.constraints))
        self.assertFalse(evidence_requirement_matches(no, intent.constraints))
        self.assertFalse(evidence_requirement_matches(unknown, intent.constraints))

    def test_rich_parking_evidence_is_conservative(self):
        from types import SimpleNamespace
        from .evidence_features import extract_listing_evidence, YES
        listing = SimpleNamespace(title='دو پارکینگ سندی', description='پارکینگ غیرمزاحم', parking=True)
        evidence = extract_listing_evidence(listing)
        self.assertGreaterEqual(evidence.parking_count, 2)
        self.assertEqual(evidence.parking_non_tandem, YES)
        self.assertEqual(evidence.parking_dedicated, YES)

@override_settings(AI_PROVIDER='mock')
class EvidenceSeparationRegressionTests(SimpleTestCase):
    def test_near_metro_does_not_invent_workplace_commute_priority(self):
        intent = get_ai_service().parse_full_intent('نزدیک مترو باشه', ())
        self.assertEqual(intent.location_priority, 'ignored')
        self.assertEqual(intent.evidence_preferences['near_metro'], 'high')

@override_settings(AI_PROVIDER='mock')
class CompoundHousingLogicTests(SimpleTestCase):
    """v0.9-D: conditions, relative priorities and progressive fallback plans."""

    def service(self):
        return get_ai_service()

    @staticmethod
    def listing(pk=1, **overrides):
        from types import SimpleNamespace
        values = dict(
            id=pk, data_source='synthetic', source_id=str(pk), title='خانه', description='واحد تمیز',
            neighborhood='ونک', deposit=500_000_000, monthly_rent=20_000_000,
            area_m2=100, bedrooms=2, floor=2, construction_year=1400,
            renovated=False, renovation_claim=False, parking=True, elevator=True, storage=True, balcony=True,
            latitude=None, longitude=None, location_radius_m=None, distance_to_work_km=2.0,
            distances={'vanak': 2.0, 'valiasr': 4.0}, natural_light=.8, quietness=.8,
            layout_quality=.8, access_quality=.8,
            evidence=[{'factor': 'natural_light', 'text': 'نور خوب'}], data_conflicts=[], image_name='x',
        )
        values.update(overrides)
        return SimpleNamespace(**values)

    def test_relative_priority_is_canonical_and_explainable(self):
        intent = self.service().parse_full_intent('نور از متراژ مهم تره', ())
        self.assertEqual(intent.preferences['natural_light'], 'very_high')
        self.assertEqual(intent.preferences['area'], 'low')
        self.assertEqual(
            intent.logic['relative_priorities'],
            [{'higher': 'base:natural_light', 'lower': 'base:area'}],
        )
        self.assertIn('نورگیری مهم', intent.logic_labels[0])

    def test_relative_priority_can_cross_into_text_evidence(self):
        intent = self.service().parse_full_intent('آرامش از نزدیکی به مترو مهم تره', ())
        self.assertEqual(intent.preferences['quietness'], 'very_high')
        self.assertEqual(intent.evidence_preferences['near_metro'], 'low')

    def test_high_floor_requires_elevator_without_becoming_global_floor_filter(self):
        from .ranking import eligible
        intent = self.service().parse_full_intent('طبقه چهار به بالا فقط اگر آسانسور داشته باشه', ())
        self.assertEqual(intent.constraints['floor'], {'mode': 'any', 'value': None, 'excluded': []})
        self.assertTrue(eligible(self.listing(floor=5, elevator=True), intent))
        self.assertFalse(eligible(self.listing(floor=5, elevator=False), intent))
        self.assertTrue(eligible(self.listing(floor=2, elevator=False), intent))

    def test_no_elevator_means_max_floor_only_conditionally(self):
        from .ranking import eligible
        intent = self.service().parse_full_intent('طبقه بالا دوست دارم ولی اگر آسانسور نداره بالاتر از دوم نباشه', ())
        self.assertEqual(intent.logic['conditionals'], [{'type': 'require_elevator_if_floor_min', 'floor_min': 3}])
        self.assertFalse(eligible(self.listing(floor=3, elevator=False), intent))
        self.assertTrue(eligible(self.listing(floor=2, elevator=False), intent))

    def test_old_house_is_allowed_only_when_renovated(self):
        from .ranking import eligible
        intent = self.service().parse_full_intent('نوساز بهتره ولی قدیمی بازسازی شده هم قبوله', ())
        self.assertTrue(eligible(self.listing(construction_year=1390, renovated=True), intent))
        self.assertFalse(eligible(self.listing(construction_year=1390, renovated=False, renovation_claim=False), intent))
        self.assertTrue(eligible(self.listing(construction_year=1402, renovated=False), intent))

    def test_old_house_can_conditionally_require_elevator(self):
        from .ranking import eligible
        intent = self.service().parse_full_intent('نوساز بهتره ولی اگه قدیمیه حتما آسانسور داشته باشه', ())
        self.assertFalse(eligible(self.listing(construction_year=1390, elevator=False), intent))
        self.assertTrue(eligible(self.listing(construction_year=1390, elevator=True), intent))
        self.assertTrue(eligible(self.listing(construction_year=1402, elevator=False), intent))

    def test_parking_requirement_can_relax_only_for_close_commute(self):
        from .ranking import eligible
        service = self.service()
        current = service.parse_full_intent('دو خوابه و پارکینگ حتما داشته باشه', ())
        current.context['workplace'] = 'vanak'
        current.preferences['commute'] = 'high'
        current.__post_init__()
        after = service.parse_intent_patch('پارکینگ مهم نیست اگر نزدیک محل کار باشه', current, ()).merge(current)
        self.assertIn('parking', after.constraints['required_amenities'])
        self.assertTrue(eligible(self.listing(parking=False, distances={'vanak': 1.0}), after))
        self.assertFalse(eligible(self.listing(parking=False, distances={'vanak': 4.0}), after))

    def test_conditional_rent_cap_uses_previous_cap_outside_close_commute(self):
        from .ranking import eligible
        service = self.service()
        current = service.parse_full_intent('اجاره بیشتر از 25 میلیون نشه', ())
        current.context['workplace'] = 'vanak'
        current.preferences['commute'] = 'high'
        current.__post_init__()
        after = service.parse_intent_patch('تا 30 میلیون اجاره هم اوکیه ولی فقط اگر خیلی نزدیک محل کار باشه', current, ()).merge(current)
        self.assertEqual(after.constraints['max_rent'], 25_000_000)
        self.assertTrue(eligible(self.listing(monthly_rent=28_000_000, distances={'vanak': 1.0}), after))
        self.assertFalse(eligible(self.listing(monthly_rent=28_000_000, distances={'vanak': 4.0}), after))
        self.assertFalse(eligible(self.listing(monthly_rent=31_000_000, distances={'vanak': 1.0}), after))

    def test_location_fallback_runs_only_when_strict_stage_is_empty(self):
        from .ranking import rank_listings
        intent = self.service().parse_full_intent(
            'اول فقط ونک رو بگرد، اگه چیزی نبود اطراف ونک رو هم ببین',
            ('ونک', 'یوسف‌آباد'),
        )
        strict = rank_listings([self.listing(neighborhood='ونک')], intent)
        self.assertEqual(strict[0].fallback_stage, 0)
        relaxed = rank_listings([self.listing(neighborhood='یوسف‌آباد')], intent)
        self.assertEqual(relaxed[0].fallback_stage, 1)
        self.assertTrue(relaxed[0].fallback_notes)

    def test_rent_fallback_expands_cap_only_after_empty_stage(self):
        from .ranking import rank_listings
        intent = self.service().parse_full_intent(
            'اول تا 25 میلیون اجاره بگرد، اگه نبود تا 30 میلیون هم برو', ()
        )
        rows = [self.listing(pk=1, monthly_rent=28_000_000), self.listing(pk=2, monthly_rent=32_000_000)]
        ranked = rank_listings(rows, intent)
        self.assertEqual([item.listing.id for item in ranked], [1])
        self.assertEqual(ranked[0].fallback_stage, 1)

    def test_few_results_trigger_can_expand_bedroom_set(self):
        from .ranking import rank_listings
        intent = self.service().parse_full_intent(
            'اول دو خوابه ها، اگه کم بود سه خوابه هم نشون بده', ()
        )
        rows = [self.listing(pk=1, bedrooms=2), self.listing(pk=2, bedrooms=3), self.listing(pk=3, bedrooms=3)]
        ranked = rank_listings(rows, intent)
        self.assertEqual(len(ranked), 3)
        self.assertTrue(all(item.fallback_stage == 1 for item in ranked))

    def test_new_then_renovated_old_fallback_keeps_old_unrenovated_out(self):
        from .ranking import rank_listings
        intent = self.service().parse_full_intent(
            'اول نوسازها، اگه کم بود قدیمی های بازسازی شده رو هم نشون بده', ()
        )
        rows = [
            self.listing(pk=1, construction_year=1390, renovated=True),
            self.listing(pk=2, construction_year=1390, renovated=False, renovation_claim=False),
        ]
        ranked = rank_listings(rows, intent)
        self.assertEqual([item.listing.id for item in ranked], [1])
        self.assertEqual(ranked[0].fallback_stage, 1)

    def test_direct_later_update_removes_stale_logic_for_same_criterion(self):
        service = self.service()
        current = service.parse_full_intent('طبقه چهار به بالا فقط اگر آسانسور داشته باشه', ())
        after = service.parse_intent_patch('طبقه دیگه مهم نیست', current, ()).merge(current)
        self.assertEqual(after.constraints['floor'], {'mode': 'any', 'value': None, 'excluded': []})
        self.assertFalse(after.logic['conditionals'])

    def test_direct_priority_update_removes_stale_relative_rule_only_for_that_pair(self):
        service = self.service()
        current = service.parse_full_intent('نور از متراژ مهم تره', ())
        after = service.parse_intent_patch('متراژ خیلی مهمه', current, ()).merge(current)
        self.assertFalse(after.logic['relative_priorities'])

    def test_v09c_session_migrates_empty_logic_without_losing_state(self):
        data = SearchIntent().to_dict()
        data['constraints']['bedrooms'] = {'mode': 'exact', 'value': 2}
        data.pop('logic')
        migrated = SearchIntent(**data)
        self.assertEqual(migrated.constraints['bedrooms'], {'mode': 'exact', 'value': 2})
        self.assertEqual(migrated.logic, {'relative_priorities': [], 'conditionals': [], 'fallbacks': []})

@override_settings(AI_PROVIDER='mock')
class CompoundLanguageRobustnessTests(SimpleTestCase):
    """Additional v0.9-D adversarial phrasing and stage-composition coverage."""

    def service(self):
        return get_ai_service()

    @staticmethod
    def listing(pk=1, **overrides):
        from types import SimpleNamespace
        values = dict(
            id=pk, data_source='synthetic', source_id=str(pk), title='خانه', description='واحد تمیز',
            neighborhood='ونک', deposit=500_000_000, monthly_rent=20_000_000,
            area_m2=100, bedrooms=2, floor=2, construction_year=1400,
            renovated=False, renovation_claim=False, parking=True, elevator=True, storage=True, balcony=True,
            latitude=None, longitude=None, location_radius_m=None, distance_to_work_km=2.0,
            distances={'vanak': 2.0, 'valiasr': 4.0}, natural_light=.8, quietness=.8,
            layout_quality=.8, access_quality=.8,
            evidence=[{'factor': 'natural_light', 'text': 'نور خوب'}], data_conflicts=[], image_name='x',
        )
        values.update(overrides)
        return SimpleNamespace(**values)

    def test_if_floor_four_or_higher_variant_requires_elevator(self):
        from .ranking import eligible
        intent = self.service().parse_full_intent('اگر طبقه چهار یا بالاتره حتما آسانسور داشته باشه', ())
        self.assertFalse(eligible(self.listing(floor=5, elevator=False), intent))
        self.assertTrue(eligible(self.listing(floor=3, elevator=False), intent))

    def test_without_elevator_max_floor_compact_variant(self):
        from .ranking import eligible
        intent = self.service().parse_full_intent('طبقه بالا دوست دارم ولی بدون آسانسور حداکثر طبقه دوم', ())
        self.assertEqual(intent.logic['conditionals'], [{'type': 'require_elevator_if_floor_min', 'floor_min': 3}])
        self.assertFalse(eligible(self.listing(floor=3, elevator=False), intent))
        self.assertTrue(eligible(self.listing(floor=2, elevator=False), intent))

    def test_superlative_priority_without_lower_criterion(self):
        intent = self.service().parse_full_intent('رفت و آمد از همه چیز مهم تره', ())
        self.assertEqual(intent.preferences['commute'], 'very_high')

    def test_relative_priority_uses_current_clause_not_previous_clause(self):
        intent = self.service().parse_full_intent('ویو باز خوبه ولی آرامش محله از ویو مهم تره', ())
        self.assertEqual(intent.preferences['quietness'], 'very_high')
        self.assertEqual(intent.evidence_preferences['open_view'], 'low')
        self.assertEqual(intent.logic['relative_priorities'], [{'higher': 'base:quietness', 'lower': 'evidence:open_view'}])

    def test_inverse_parking_wording_relaxes_requirement_only_when_close(self):
        from .ranking import eligible
        service = self.service()
        current = service.parse_full_intent('پارکینگ حتما داشته باشه', ())
        current.context['workplace'] = 'vanak'
        current.preferences['commute'] = 'high'
        current.__post_init__()
        intent = service.parse_intent_patch(
            'اگه پارکینگ نداره فقط وقتی قبوله که خیلی نزدیک محل کار باشه', current, ()
        ).merge(current)
        self.assertTrue(eligible(self.listing(parking=False, distances={'vanak': 1.0}), intent))
        self.assertFalse(eligible(self.listing(parking=False, distances={'vanak': 4.0}), intent))

    def test_minimum_area_can_relax_only_for_close_commute_when_user_says_so(self):
        from .ranking import eligible
        service = self.service()
        current = service.parse_full_intent('حداقل 120 متر باشه', ())
        current.context['workplace'] = 'vanak'
        current.preferences['commute'] = 'high'
        current.__post_init__()
        intent = service.parse_intent_patch(
            'متراژ کمتر اوکیه اگر رفت و آمد خیلی بهتر بشه', current, ()
        ).merge(current)
        self.assertEqual(intent.constraints['area']['min'], 120)
        self.assertTrue(eligible(self.listing(area_m2=100, distances={'vanak': 1.0}), intent))
        self.assertFalse(eligible(self.listing(area_m2=100, distances={'vanak': 4.0}), intent))

    def test_two_fallback_stages_apply_cumulatively_only_as_needed(self):
        from .ranking import rank_listings
        intent = self.service().parse_full_intent(
            'اول فقط ونک با اجاره تا 25 میلیون رو بگرد، اگه نبود اطراف ونک تا 30 میلیون هم برو',
            ('ونک', 'یوسف‌آباد'),
        )
        self.assertEqual([r['type'] for r in intent.logic['fallbacks']], ['neighborhood_scope', 'max_rent'])
        # Exact Vanak is empty; nearby stage is also empty at 25M; rent stage then admits this listing.
        ranked = rank_listings([
            self.listing(neighborhood='یوسف‌آباد', monthly_rent=28_000_000),
        ], intent)
        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0].fallback_stage, 2)
        self.assertEqual(len(ranked[0].fallback_notes), 2)

    def test_relative_priority_changes_ranking_weight_not_hard_eligibility(self):
        from .ranking import rank_listings
        intent = self.service().parse_full_intent('نور از متراژ مهم تره', ())
        bright_small = self.listing(pk=1, area_m2=75, natural_light=.95)
        large_dim = self.listing(pk=2, area_m2=140, natural_light=.35)
        ranked = rank_listings([large_dim, bright_small], intent)
        self.assertEqual(ranked[0].listing.id, 1)
        self.assertEqual(len(ranked), 2)

@override_settings(AI_PROVIDER='mock')
class SearchEngineStabilizationD1Tests(SimpleTestCase):
    """v0.9-D.1 regression closure for bugs found in the first full Django run."""

    def service(self):
        return get_ai_service()

    def test_parking_non_tandem_allows_short_descriptors_between_terms(self):
        from types import SimpleNamespace
        from .evidence_features import extract_listing_evidence, YES
        listing = SimpleNamespace(
            title='رهن کامل/125متر2خواب/2پارکینگ/فول امکانات/حکیمیه',
            description='2پارکینگ سندی غیر مزاحم',
            parking=True,
        )
        evidence = extract_listing_evidence(listing)
        self.assertGreaterEqual(evidence.parking_count, 2)
        self.assertEqual(evidence.parking_non_tandem, YES)
        self.assertEqual(evidence.parking_dedicated, YES)

    def test_superlative_subject_does_not_leak_from_previous_clause(self):
        current = self.service().parse_full_intent(
            'دوخوابه، نور خوب و پارکینگ مهمه، حوالی ونک کار می‌کنم',
            ('ونک',),
        )
        after = self.service().parse_intent_patch(
            'پارکینگ مهم نیست؛ رفت‌وآمد از همه چیز مهم‌تره', current, ('ونک',)
        ).merge(current)
        self.assertEqual(after.preferences['parking'], 'low')
        self.assertEqual(after.preferences['commute'], 'very_high')

    def test_bedroom_patch_supports_removal_and_additive_acceptance(self):
        current = self.service().parse_full_intent('دوخوابه می‌خوام', ())
        removed = self.service().parse_intent_patch(
            'دوخوابه بودن هم دیگه مهم نیست', current, ()
        ).merge(current)
        self.assertEqual(removed.constraints['bedrooms'], {'mode': 'any', 'value': None})
        additive = self.service().parse_intent_patch(
            'یک خوابه هم اوکیه', current, ()
        ).merge(current)
        self.assertEqual(additive.constraints['bedrooms'], {'mode': 'allowed', 'value': [1, 2]})

    def test_bare_renovation_keyword_remains_literal_browse_search(self):
        from .patches import recognized_text
        self.assertFalse(recognized_text('بازسازی', ('ونک',)))
        self.assertTrue(recognized_text('بازسازی کامل لازم دارم', ('ونک',)))
