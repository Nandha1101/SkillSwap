from django.core.cache import cache

from .models import Notification, Profile


def navigation(request):
    context = {
        "current_route": request.resolver_match.url_name if request.resolver_match else "",
        "nav_items": [
            ("Explore", "explore"),
            ("Dashboard", "dashboard"),
            ("Requests", "requests"),
            ("Sessions", "sessions"),
        ],
        "mobile_nav_items": [
            ("Explore", "explore"),
            ("Home", "dashboard"),
            ("Requests", "requests"),
            ("Sessions", "sessions"),
        ],
    }
    if request.user.is_authenticated:
        cache_key = f"user_profile_{request.user.pk}"
        profile = cache.get(cache_key)
        if profile is None:
            profile, _ = Profile.objects.get_or_create(user=request.user)
            cache.set(cache_key, profile, 60)
        context["user_profile"] = profile
    else:
        context["user_profile"] = None
    return context


def notifications(request):
    if not request.user.is_authenticated:
        return {
            "unread_notifications_count": 0,
        }
    cache_key = f"user_unread_notif_{request.user.pk}"
    unread_count = cache.get(cache_key)
    if unread_count is None:
        unread_count = Notification.objects.filter(recipient=request.user, is_read=False).count()
        cache.set(cache_key, unread_count, 15)
    return {
        "unread_notifications_count": unread_count,
    }
