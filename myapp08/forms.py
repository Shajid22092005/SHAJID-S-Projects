from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.forms import inlineformset_factory

from .models import (
    Event,
    EventSchedule,
    EventMedia,
    TicketTier,
    UserProfile,
)

class CustomUserCreationForm(UserCreationForm):
    role = forms.ChoiceField(
        choices=UserProfile.ROLE_CHOICES,
        initial="ATTENDEE",
        label="Sign up as",
        widget=forms.Select(attrs={"class": "form-select"})
    )

    class Meta(UserCreationForm.Meta):
        fields = UserCreationForm.Meta.fields + ("first_name", "last_name", "email",)

class ProfileForm(forms.ModelForm):
    # Let users edit basic info too
    first_name = forms.CharField(max_length=30, required=False)
    last_name = forms.CharField(max_length=30, required=False)
    email = forms.EmailField(required=True)

    class Meta:
        model = UserProfile
        fields = ("role",)  # show role dropdown; remove if you don't want users to change role

class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = [
            "title",
            "description",
            "date",
            "time",
            "location",
            "image",
            "category",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "time": forms.TimeInput(attrs={"type": "time"}),
        }

class EventScheduleForm(forms.ModelForm):
    class Meta:
        model = EventSchedule
        fields = ["title", "start_time", "end_time", "description"]
        widgets = {
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
        }

class EventMediaForm(forms.ModelForm):
    class Meta:
        model = EventMedia
        fields = ["type", "file", "url", "caption"]

class TicketTierForm(forms.ModelForm):
    class Meta:
        model = TicketTier
        fields = ["name", "price", "capacity"]


TicketTierFormSet = inlineformset_factory(
    parent_model=Event,
    model=TicketTier,
    form=TicketTierForm,
    extra=3,
    can_delete=True,
)
