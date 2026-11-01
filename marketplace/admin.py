from django.contrib import admin

from .models import (
    Exchange,
    ExchangeLesson,
    ExchangeMessage,
    ExchangeRequest,
    LearningGoal,
    Notification,
    Profile,
    Review,
    Session,
)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "college", "year", "session_format", "avg_rating", "review_count")
    search_fields = ("user__username", "user__email", "user__first_name", "user__last_name", "college")
    list_filter = ("session_format", "college")


@admin.register(ExchangeRequest)
class ExchangeRequestAdmin(admin.ModelAdmin):
    list_display = ("sender", "recipient", "offered_skill", "requested_skill", "status", "created_at")
    search_fields = ("sender__username", "recipient__username", "offered_skill", "requested_skill")
    list_filter = ("status", "created_at")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Exchange)
class ExchangeAdmin(admin.ModelAdmin):
    list_display = ("request", "status", "created_at", "completed_at")
    list_filter = ("status", "created_at")
    readonly_fields = ("created_at", "completed_at")


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ("topic", "exchange", "created_by", "starts_at", "duration_minutes", "status")
    search_fields = ("topic", "created_by__username")
    list_filter = ("status", "starts_at")
    readonly_fields = ("created_at", "completed_at")


@admin.register(ExchangeLesson)
class ExchangeLessonAdmin(admin.ModelAdmin):
    list_display = ("title", "skill", "exchange", "author", "attachment", "created_at")
    search_fields = ("title", "skill", "author__username")
    readonly_fields = ("created_at",)


@admin.register(ExchangeMessage)
class ExchangeMessageAdmin(admin.ModelAdmin):
    list_display = ("exchange", "author", "created_at")
    search_fields = ("content", "author__username")
    readonly_fields = ("created_at",)


@admin.register(LearningGoal)
class LearningGoalAdmin(admin.ModelAdmin):
    list_display = ("title", "exchange", "created_by", "is_completed", "completed_by")
    list_filter = ("is_completed",)
    search_fields = ("title", "created_by__username")
    readonly_fields = ("created_at", "completed_at")


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("exchange", "reviewer", "reviewee", "rating", "created_at")
    list_filter = ("rating", "created_at")
    search_fields = ("reviewer__username", "reviewee__username", "comment")
    readonly_fields = ("created_at",)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("recipient", "notification_type", "title", "is_read", "created_at")
    list_filter = ("notification_type", "is_read", "created_at")
    search_fields = ("recipient__username", "title", "message")
    readonly_fields = ("created_at",)
