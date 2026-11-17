from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from . import lessons
from .ai import guardrails


class VoxAuthenticationForm(AuthenticationForm):
    """Django's login form with the site's input classes."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class SignUpForm(UserCreationForm):
    """UserCreationForm (so every password rule still applies) plus an email field."""

    email = forms.EmailField(required=False, help_text="Optional.")

    class Meta(UserCreationForm.Meta):
        fields = ("username", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class TutorForm(forms.Form):
    question = forms.CharField(
        label="Ask the tutor",
        max_length=guardrails.MAX_INPUT_CHARS,
        strip=True,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Ask about your recording…",
        }),
    )
    score = forms.TypedChoiceField(label="Use one of my recordings", required=False,
                                   coerce=int, empty_value=None,
                                   widget=forms.Select(attrs={"class": "form-select"}))
    topic = forms.ChoiceField(choices=[(l["slug"], l["title"]) for l in lessons.LESSONS],
                              widget=forms.HiddenInput)

    def __init__(self, *args, scores=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["score"].choices = [("", "No recording")] + [(s.pk, s.title) for s in scores]


class SettingsForm(forms.Form):
    ai_harmony_enabled = forms.BooleanField(
        label="AI harmony suggestions in the Score editor",
        required=False,
        help_text="Off by default. When on, the AI only suggests parts; you accept or reject each one.",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input", "role": "switch"}),
    )
