"""Admin-account creation form for the setup wizard (Phase 29).

This project ships with AUTH_PASSWORD_VALIDATORS unset (= [], no validation
anywhere else in the app). The wizard creates the FIRST admin account, so it
always enforces Django's four standard validators here regardless of that
global setting -- "Django password validators" per the plan, applied locally
rather than by changing global settings for the whole app.
"""
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import get_password_validators, validate_password
from django.core.exceptions import ValidationError

_STRONG_VALIDATORS = get_password_validators([
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
])


class CreateAdminForm(forms.Form):
    username = forms.CharField(max_length=150)
    email = forms.EmailField(required=False)
    password1 = forms.CharField(widget=forms.PasswordInput, label="Password")
    password2 = forms.CharField(widget=forms.PasswordInput, label="Confirm password")

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if not username:
            raise ValidationError("Username is required.")
        if get_user_model().objects.filter(username=username).exists():
            raise ValidationError("That username is already taken.")
        return username

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Passwords do not match.")
        elif p1:
            dummy_user = get_user_model()(username=cleaned.get("username", ""))
            try:
                validate_password(p1, user=dummy_user, password_validators=_STRONG_VALIDATORS)
            except ValidationError as exc:
                self.add_error("password1", exc)
        return cleaned

    def save(self):
        data = self.cleaned_data
        return get_user_model().objects.create_superuser(
            username=data["username"], email=data.get("email") or "", password=data["password1"],
        )


class ServicesForm(forms.Form):
    """Step 3 (Phase 30): which services to back up. Display/selection only --
    nothing in the pipelines gates on this choice yet; it's used to scope the
    wizard's own test backup (step 6)."""
    services = forms.MultipleChoiceField(
        choices=[("gmail", "Gmail"), ("drive", "Drive"), ("photos", "Photos")],
        widget=forms.CheckboxSelectMultiple,
        required=False,  # so an empty submission reaches our own "at least one" message below
    )

    def clean_services(self):
        selected = self.cleaned_data["services"]
        if not selected:
            raise ValidationError("Choose at least one service.")
        return selected


class ScheduleForm(forms.Form):
    """Step 5 (Phase 30): daily/weekly preset + a time, in TIME_ZONE."""
    preset = forms.ChoiceField(choices=[("daily", "Daily"), ("weekly", "Weekly (Monday)")])
    time = forms.CharField(max_length=5, help_text="24-hour HH:MM, e.g. 02:00")

    def clean_time(self):
        value = self.cleaned_data["time"].strip()
        try:
            hour_str, minute_str = value.split(":")
            hour, minute = int(hour_str), int(minute_str)
        except ValueError:
            raise ValidationError("Enter a time as HH:MM, e.g. 02:00.")
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValidationError("Enter a valid 24-hour time, e.g. 02:00.")
        return value

    def clean(self):
        cleaned = super().clean()
        if "time" in cleaned:
            hour, minute = cleaned["time"].split(":")
            cleaned["hour"], cleaned["minute"] = int(hour), int(minute)
        return cleaned
