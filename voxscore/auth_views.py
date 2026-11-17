"""
The three authentication views: log in, sign up, log out (wireframe screen 1).

Thin subclasses of Django's own views, as in Unopsis: the password check, the session, the
password rules and the ?next= redirect are all Django's. Only the presentation is ours.

Django 5's LogoutView answers POST only, which is why base.html has a small logout form
with {% csrf_token %} rather than a link.
"""

from django.conf import settings
from django.contrib import messages as flash
from django.contrib.auth import login as auth_login
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect, resolve_url
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import CreateView

from .forms import SignUpForm, VoxAuthenticationForm
from .models import Profile


class VoxLoginView(LoginView):
    template_name = "registration/login.html"
    authentication_form = VoxAuthenticationForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        response = super().form_valid(form)
        flash.success(self.request, f"Welcome back, {form.get_user().get_username()}.")
        return response


class VoxLogoutView(LogoutView):
    def post(self, request, *args, **kwargs):
        was_signed_in = request.user.is_authenticated
        response = super().post(request, *args, **kwargs)
        if was_signed_in:
            flash.info(request, "Signed out. See you at your next practice.")
        return response


class SignUpView(CreateView):
    """Create the account, create its Profile, and sign it straight in."""

    form_class = SignUpForm
    template_name = "registration/signup.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(self.get_success_url())
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["next"] = self.request.GET.get("next", "")
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        Profile.objects.get_or_create(user=self.object)
        auth_login(self.request, self.object,
                   backend="django.contrib.auth.backends.ModelBackend")
        flash.success(self.request,
                      f"Welcome to VoxScore, {self.object.get_username()}. "
                      "Start with the tuner, or find your range on your profile.")
        return response

    def get_success_url(self):
        destination = self.request.POST.get("next") or self.request.GET.get("next")
        if destination and url_has_allowed_host_and_scheme(
            destination, allowed_hosts={self.request.get_host()},
            require_https=self.request.is_secure(),
        ):
            return destination
        return resolve_url(settings.LOGIN_REDIRECT_URL)
