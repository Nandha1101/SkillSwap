from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import Exchange, ExchangeRequest, Profile, Review


class SignupForm(forms.Form):
    full_name = forms.CharField(max_length=150, label="Full name")
    email = forms.EmailField()
    college = forms.CharField(max_length=180, label="College/University")
    password1 = forms.CharField(widget=forms.PasswordInput, label="Password")
    password2 = forms.CharField(widget=forms.PasswordInput, label="Confirm password")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs["class"] = "form-input"
            field.widget.attrs["id"] = f"signup_{name}"
        self.fields["full_name"].widget.attrs.update({
            "placeholder": "Alex Morgan",
            "autocomplete": "name",
        })
        self.fields["email"].widget.attrs.update({
            "placeholder": "you@college.edu",
            "autocomplete": "email",
        })
        self.fields["password1"].widget.attrs["autocomplete"] = "new-password"
        self.fields["password2"].widget.attrs["autocomplete"] = "new-password"
        self.fields["college"].widget.attrs.update({
            "placeholder": "Start typing your college name",
            "role": "combobox",
            "aria-autocomplete": "list",
            "aria-expanded": "false",
            "aria-controls": "college-results",
            "autocomplete": "off",
            "data-college-search": "",
        })

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("An account with this email already exists.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("password1") != cleaned_data.get("password2"):
            self.add_error("password2", "The passwords do not match.")
        elif cleaned_data.get("password1"):
            try:
                validate_password(cleaned_data["password1"])
            except ValidationError as error:
                self.add_error("password1", error)
        return cleaned_data

    @transaction.atomic
    def save(self):
        full_name = self.cleaned_data["full_name"].strip()
        first_name, _, last_name = full_name.partition(" ")
        email = self.cleaned_data["email"]
        username = email[:150]
        suffix = 1
        while User.objects.filter(username=username).exists():
            suffix += 1
            username = f"{email[:140]}{suffix}"
        user = User.objects.create_user(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=self.cleaned_data["password1"],
        )
        Profile.objects.create(user=user, college=self.cleaned_data["college"])
        return user


class EmailLoginForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user = None
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs["class"] = "form-input"
            field.widget.attrs["id"] = f"login_{name}"
        self.fields["email"].widget.attrs.update({
            "placeholder": "you@college.edu",
            "autocomplete": "email",
        })
        self.fields["password"].widget.attrs.update({
            "placeholder": "Your password",
            "autocomplete": "current-password",
        })

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get("email")
        password = cleaned_data.get("password")
        if email and password:
            account = User.objects.filter(email__iexact=email).first()
            if account:
                self.user = authenticate(self.request, username=account.username, password=password)
            if self.user is None:
                raise ValidationError("Email or password is incorrect.")
        return cleaned_data


class ProfileForm(forms.ModelForm):
    name = forms.CharField(max_length=150, label="Name")
    email = forms.EmailField()

    class Meta:
        model = Profile
        fields = ("avatar", "college", "year", "bio", "skills_to_teach", "skills_to_learn", "session_format")
        labels = {
            "avatar": "Profile photo",
            "skills_to_teach": "Skills I can teach (comma separated)",
            "skills_to_learn": "Skills I want to learn (comma separated)",
            "session_format": "Preferred session format",
        }

    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name != "avatar":
                field.widget.attrs["class"] = "form-input"
            else:
                field.widget.attrs["class"] = "form-input-file"
            field.widget.attrs["id"] = f"profile_{name}"
        self.fields["college"].widget.attrs.update({
            "role": "combobox",
            "aria-autocomplete": "list",
            "aria-expanded": "false",
            "aria-controls": "college-results",
            "autocomplete": "off",
            "data-college-search": "",
        })
        self.fields["name"].initial = user.get_full_name()
        self.fields["email"].initial = user.email

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.user.pk).exists():
            raise ValidationError("This email is already in use.")
        return email

    def clean_skills_to_teach(self):
        return self._clean_skills(self.cleaned_data["skills_to_teach"])

    def clean_skills_to_learn(self):
        return self._clean_skills(self.cleaned_data["skills_to_learn"])

    @staticmethod
    def _clean_skills(value):
        skills = []
        seen = set()
        for skill in value.split(","):
            skill = skill.strip()
            key = skill.casefold()
            if skill and key not in seen:
                skills.append(skill)
                seen.add(key)
        if len(skills) > 20:
            raise ValidationError("Please list no more than 20 skills in each section.")
        if any(len(skill) > 100 for skill in skills):
            raise ValidationError("Each skill must be 100 characters or fewer.")
        return ", ".join(skills)

    def save(self, commit=True):
        profile = super().save(commit=False)
        full_name = self.cleaned_data["name"].strip()
        first_name, _, last_name = full_name.partition(" ")
        self.user.first_name = first_name
        self.user.last_name = last_name
        self.user.email = self.cleaned_data["email"]
        if commit:
            with transaction.atomic():
                self.user.save()
                profile.user = self.user
                profile.save()
        return profile


class ExchangeRequestForm(forms.ModelForm):
    offered_skill = forms.ChoiceField(
        choices=(),
        label="I can teach them",
        widget=forms.Select(attrs={"class": "form-input"}),
    )
    requested_skill = forms.ChoiceField(
        choices=(),
        label="I'd like to learn",
        widget=forms.Select(attrs={"class": "form-input"}),
    )

    class Meta:
        model = ExchangeRequest
        fields = ("offered_skill", "requested_skill", "message")
        labels = {"message": "A note to go with your request"}
        widgets = {
            "message": forms.Textarea(attrs={
                "class": "form-input",
                "rows": 3,
                "maxlength": 500,
                "placeholder": "What would you like to learn or share?",
            }),
        }

    def __init__(self, *args, sender_profile, recipient_profile, **kwargs):
        self.sender_profile = sender_profile
        self.recipient_profile = recipient_profile
        offered = [
            skill for skill in sender_profile.teach_skills
            if skill.casefold() in {wanted.casefold() for wanted in recipient_profile.learn_skills}
        ]
        requested = [
            skill for skill in recipient_profile.teach_skills
            if skill.casefold() in {wanted.casefold() for wanted in sender_profile.learn_skills}
        ]
        super().__init__(*args, **kwargs)
        self.fields["offered_skill"].choices = [(skill, skill) for skill in offered]
        self.fields["requested_skill"].choices = [(skill, skill) for skill in requested]

    def clean(self):
        cleaned_data = super().clean()
        offered = cleaned_data.get("offered_skill")
        requested = cleaned_data.get("requested_skill")
        if offered and offered.casefold() not in {
            skill.casefold() for skill in self.sender_profile.teach_skills
        }:
            self.add_error("offered_skill", "Choose a skill listed on your profile.")
        if requested and requested.casefold() not in {
            skill.casefold() for skill in self.recipient_profile.teach_skills
        }:
            self.add_error("requested_skill", "Choose a skill listed on their profile.")
        if not self.fields["offered_skill"].choices:
            self.add_error(None, "You do not currently offer a skill this student wants to learn.")
        if not self.fields["requested_skill"].choices:
            self.add_error(None, "This student does not currently teach a skill you want to learn.")
        return cleaned_data


class SessionForm(forms.Form):
    exchange = forms.ModelChoiceField(
        queryset=None,
        label="Exchange partner",
        widget=forms.Select(attrs={"class": "form-input"}),
    )
    topic = forms.CharField(
        max_length=160,
        widget=forms.TextInput(attrs={
            "class": "form-input",
            "placeholder": "e.g. Getting started with Figma",
        }),
    )
    starts_at = forms.DateTimeField(
        label="Date and time",
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(
            format="%Y-%m-%dT%H:%M",
            attrs={"class": "form-input", "type": "datetime-local"},
        ),
    )
    duration_minutes = forms.TypedChoiceField(
        label="How long",
        choices=((30, "30 minutes"), (45, "45 minutes"), (60, "60 minutes"), (90, "90 minutes")),
        coerce=int,
        initial=60,
        widget=forms.Select(attrs={"class": "form-input"}),
    )

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["exchange"].queryset = (
            Exchange.objects.filter(status=Exchange.Status.ACTIVE)
            .filter(Q(request__sender=user) | Q(request__recipient=user))
            .select_related("request__sender", "request__recipient")
        )

    def clean_starts_at(self):
        starts_at = self.cleaned_data["starts_at"]
        if timezone.is_naive(starts_at):
            starts_at = timezone.make_aware(starts_at, timezone.get_current_timezone())
        if starts_at <= timezone.now():
            raise ValidationError("Choose a session time in the future.")
        return starts_at


class ExchangeLessonForm(forms.Form):
    skill = forms.ChoiceField(
        label="Skill this lesson covers",
        widget=forms.Select(attrs={"class": "form-input"}),
    )
    title = forms.CharField(
        max_length=160,
        widget=forms.TextInput(attrs={
            "class": "form-input",
            "placeholder": "Give the lesson a clear title",
        }),
    )
    content = forms.CharField(
        max_length=5000,
        label="Lesson notes",
        widget=forms.Textarea(attrs={
            "class": "form-input",
            "rows": 6,
            "placeholder": "Write the steps, explanations, or tips you want to share.",
        }),
    )
    resource_url = forms.URLField(
        required=False,
        max_length=500,
        label="Learning resource link (optional)",
        widget=forms.URLInput(attrs={
            "class": "form-input",
            "placeholder": "https://example.com/guide",
        }),
    )
    attachment = forms.FileField(
        required=False,
        label="File or project attachment (optional)",
        widget=forms.FileInput(attrs={"class": "form-input-file"}),
    )

    def __init__(self, *args, exchange, user, **kwargs):
        super().__init__(*args, **kwargs)
        if exchange.request.sender_id == user.pk:
            skills = [exchange.request.offered_skill]
        else:
            skills = [exchange.request.requested_skill]
        self.fields["skill"].choices = [(skill, skill) for skill in skills]

    def clean_title(self):
        title = self.cleaned_data["title"].strip()
        if not title:
            raise ValidationError("Enter a title for this lesson.")
        return title

    def clean_content(self):
        content = self.cleaned_data["content"].strip()
        if not content:
            raise ValidationError("Add some lesson notes before publishing.")
        return content


class LearningGoalForm(forms.Form):
    title = forms.CharField(
        max_length=160,
        label="Learning goal",
        widget=forms.TextInput(attrs={
            "class": "form-input",
            "placeholder": "e.g. Build a responsive page with CSS Grid",
        }),
    )

    def clean_title(self):
        title = self.cleaned_data["title"].strip()
        if not title:
            raise ValidationError("Enter a goal before adding it.")
        return title


class ExchangeMessageForm(forms.Form):
    content = forms.CharField(
        max_length=2000,
        label="Message",
        widget=forms.Textarea(attrs={
            "class": "form-input",
            "rows": 3,
            "placeholder": "Ask a question or share an idea…",
        }),
    )

    def clean_content(self):
        content = self.cleaned_data["content"].strip()
        if not content:
            raise ValidationError("Write a message before sending.")
        return content


class ReviewForm(forms.ModelForm):
    rating = forms.TypedChoiceField(
        choices=((5, "5 ★ — Exceptional exchange"), (4, "4 ★ — Very good session"), (3, "3 ★ — Good"), (2, "2 ★ — Fair"), (1, "1 ★ — Poor")),
        coerce=int,
        label="Rating",
        widget=forms.Select(attrs={"class": "form-input"}),
    )
    comment = forms.CharField(
        max_length=1000,
        required=False,
        label="Review note (optional)",
        widget=forms.Textarea(attrs={
            "class": "form-input",
            "rows": 3,
            "placeholder": "Share what you learned from your partner…",
        }),
    )

    class Meta:
        model = Review
        fields = ("rating", "comment")
