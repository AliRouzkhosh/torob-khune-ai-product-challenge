from django import template
from finder.ranking import fa, money

register = template.Library()
register.filter('fa', fa)
register.filter('money', money)

@register.filter
def yesno_fa(value):
    return 'نامشخص' if value is None else 'دارد' if value else 'ندارد'
