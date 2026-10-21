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
