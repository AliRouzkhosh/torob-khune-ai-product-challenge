from abc import ABC, abstractmethod
from django.conf import settings
from .intent import IntentProfile, SCENARIOS, heuristic_parse, normalize


class AIService(ABC):
    @abstractmethod
    def parse_intent(self, text, base=None): ...

    def parse_full_intent(self, text, neighborhoods=()):
        from .patches import parse_full_intent
        return parse_full_intent(self, text, neighborhoods)

    def parse_intent_patch(self, text, current, neighborhoods=()):
        from .patches import parse_intent_patch
        return parse_intent_patch(self, text, current, neighborhoods)

    @abstractmethod
    def enrich_listing(self, description): ...


class MockAIService(AIService):
    def parse_intent(self, text, base=None):
        if base is None:
            for key, (_, query) in SCENARIOS.items():
                if normalize(query) == normalize(text):
                    p = IntentProfile()
                    if key == 'a':
                        p.bedrooms_min, p.deposit_target, p.rent_target = 2, 800_000_000, 25_000_000
                        p.work_location, p.location_priority = 'vanak', 'high'
                        p.preferences.update(natural_light='very_high', parking='medium')
                    elif key == 'b':
                        p.rent_target, p.rent_hard, p.work_location, p.location_priority = 20_000_000, True, 'valiasr', 'very_high'
                        p.preferences.update(elevator='high', parking='low', area='low')
                    else:
                        p.bedrooms_min, p.budget_flexibility, p.work_location, p.location_priority = 2, 'flexible', 'none', 'ignored'
                        p.preferences.update(quietness='high', building_age='high', parking='high', storage='high')
                    return p
        return heuristic_parse(text, base)

    def enrich_listing(self, description):
        # Explicit simulated extraction; seed signals are curated, not live inference.
        return {'evidence': [description], 'simulated': True}


def get_ai_service():
    providers = {'mock': MockAIService}
    return providers[settings.AI_PROVIDER]()
