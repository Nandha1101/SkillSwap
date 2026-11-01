from .models import Notification


def navigation(request):
    return {
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


def notifications(request):
    if not request.user.is_authenticated:
        return {
            "unread_notifications_count": 0,
        }
    unread_count = Notification.objects.filter(recipient=request.user, is_read=False).count()
    return {
        "unread_notifications_count": unread_count,
    }
