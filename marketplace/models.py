import uuid

from django.conf import settings
from django.db import models


class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    college = models.CharField(max_length=180, blank=True)
    year = models.CharField(max_length=100, blank=True)
    bio = models.TextField(blank=True)
    skills_to_teach = models.CharField(max_length=500, blank=True)
    skills_to_learn = models.CharField(max_length=500, blank=True)
    session_format = models.CharField(max_length=30, default="Either")

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username}'s profile"

    @staticmethod
    def split_skills(value):
        return [skill.strip() for skill in value.split(",") if skill.strip()]

    @property
    def teach_skills(self):
        return self.split_skills(self.skills_to_teach)

    @property
    def learn_skills(self):
        return self.split_skills(self.skills_to_learn)


class ExchangeRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_exchange_requests",
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="received_exchange_requests",
    )
    offered_skill = models.CharField(max_length=100)
    requested_skill = models.CharField(max_length=100)
    message = models.TextField(blank=True, max_length=500)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.sender} ↔ {self.recipient}: {self.offered_skill}/{self.requested_skill}"


class Exchange(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"

    request = models.OneToOneField(
        ExchangeRequest,
        on_delete=models.CASCADE,
        related_name="exchange",
    )
    video_room = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)

    @property
    def participants(self):
        return (self.request.sender, self.request.recipient)

    def includes(self, user):
        return user.pk in (self.request.sender_id, self.request.recipient_id)

    def __str__(self):
        return f"{self.request.offered_skill} ↔ {self.request.requested_skill}"


class Session(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        COMPLETED = "completed", "Completed"

    exchange = models.ForeignKey(Exchange, on_delete=models.CASCADE, related_name="sessions")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    topic = models.CharField(max_length=160)
    starts_at = models.DateTimeField()
    duration_minutes = models.PositiveSmallIntegerField(default=60)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.SCHEDULED)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("starts_at",)

    def __str__(self):
        return f"{self.topic} ({self.starts_at:%Y-%m-%d %H:%M})"


class ExchangeLesson(models.Model):
    exchange = models.ForeignKey(Exchange, on_delete=models.CASCADE, related_name="lessons")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    skill = models.CharField(max_length=100)
    title = models.CharField(max_length=160)
    content = models.TextField(max_length=5000)
    resource_url = models.URLField(blank=True, max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.title} ({self.skill})"


class ExchangeMessage(models.Model):
    exchange = models.ForeignKey(Exchange, on_delete=models.CASCADE, related_name="messages")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at",)

    def __str__(self):
        return f"Message from {self.author} in exchange {self.exchange_id}"


class LearningGoal(models.Model):
    exchange = models.ForeignKey(Exchange, on_delete=models.CASCADE, related_name="goals")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_learning_goals",
    )
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="completed_learning_goals",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=160)
    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("is_completed", "created_at")

    def __str__(self):
        return self.title
