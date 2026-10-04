"""Minimal contact-only authentication. Search utilities remain session-backed."""
from django.conf import settings
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import LoginView as DjangoLoginView, redirect_to_login
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST, require_GET
from urllib.parse import urlsplit
import re
from .contact import get_demo_contact
from .selectors import listings


# Explicit allowlist: never copy auth keys or revealed contact through logout.
UTILITY_KEYS = ('intent', 'query', 'precision_filters', 'refinement_diff', 'rank_changes',
                'promotions', 'last_update', 'listing_context', 'pending_query',
                'search_notice', 'last_query_operation', 'browse_intent', 'browse_query',
                'saved_listing_ids', 'comparison')


def safe_next(request):
    target = request.POST.get('next', request.GET.get('next', ''))
    return target if url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ) else settings.LOGIN_REDIRECT_URL


class LoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = 'نام کاربری'
        self.fields['password'].label = 'رمز عبور'
        self.fields['username'].widget.attrs.update(autocomplete='username', dir='ltr')
        self.fields['password'].widget.attrs.update(autocomplete='current-password', dir='ltr')


class LoginView(DjangoLoginView):
    template_name = 'finder/login.html'
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def get_context_data(self, **kwargs):
        target = self.get_redirect_url()
        back = target if target and re.fullmatch(r'/homes/\d+/', urlsplit(target).path) else ''
        return super().get_context_data(**kwargs, safe_back=back,
            demo_login_enabled=settings.DEBUG and settings.ENABLE_DEMO_LOGIN)


@never_cache
@require_POST
def demo_login(request):
    if not settings.DEBUG or not settings.ENABLE_DEMO_LOGIN:
        raise Http404
    if request.user.is_authenticated:
        return redirect(safe_next(request))
    user = get_user_model().objects.filter(username=settings.DEMO_USERNAME,
        is_active=True, is_staff=False, is_superuser=False).first()
    if user is None:
        return render(request, 'finder/login.html', {'form': LoginForm(request),
            'next': safe_next(request), 'demo_login_enabled': True,
            'demo_error': 'حساب آزمایشی هنوز آماده نیست. دستور seed_demo_user را اجرا کنید.'}, status=503)
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    return redirect(safe_next(request))


@never_cache
@require_POST
def logout_view(request):
    target = safe_next(request)
    preserved = {key: request.session[key] for key in UTILITY_KEYS if key in request.session}
    logout(request)
    request.session.update(preserved)
    return redirect(target)


@never_cache
@require_GET
def contact(request, pk):
    listing = get_object_or_404(listings(), pk=pk)
    if not request.user.is_authenticated:
        return redirect_to_login(reverse('detail', args=[pk]))
    action = 'bale' if request.GET.get('action') == 'bale' else 'phone'
    data = get_demo_contact(listing)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'finder/_contact_value.html', {'demo_contact': data,
            'contact_action': action, 'item': {'listing': listing}})
    # No-JS fallback reveals inline in the normal detail page, never a bare fragment.
    from .views import detail
    return detail(request, pk, demo_contact=data, contact_action=action)
