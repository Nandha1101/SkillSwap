from django.urls import path

from . import views


urlpatterns = [
    path("", views.landing, name="landing"),
    path("login/", views.login_view, name="login"),
    path("signup/", views.signup_view, name="signup"),
    path("api/colleges/", views.college_search, name="college_search"),
    path("logout/", views.logout_view, name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("explore/", views.explore, name="explore"),
    path("requests/", views.requests_view, name="requests"),
    path("requests/<str:request_id>/", views.update_request, name="update_request"),
    path("requests/new/<int:user_id>/", views.create_exchange_request, name="create_exchange_request"),
    path("sessions/", views.sessions_view, name="sessions"),
    path("sessions/schedule/", views.schedule_session, name="schedule_session"),
    path("sessions/exchanges/<int:exchange_id>/complete/", views.complete_exchange, name="complete_exchange"),
    path("sessions/<int:session_id>/complete/", views.complete_session, name="complete_session"),
    path("exchanges/<int:exchange_id>/learn/", views.exchange_learning, name="exchange_learning"),
    path("exchanges/<int:exchange_id>/lessons/new/", views.publish_exchange_lesson, name="publish_exchange_lesson"),
    path("exchanges/<int:exchange_id>/messages/", views.send_exchange_message, name="send_exchange_message"),
    path("exchanges/<int:exchange_id>/messages/poll/", views.exchange_messages, name="exchange_messages"),
    path("exchanges/<int:exchange_id>/goals/new/", views.add_learning_goal, name="add_learning_goal"),
    path(
        "exchanges/<int:exchange_id>/goals/<int:goal_id>/toggle/",
        views.toggle_learning_goal,
        name="toggle_learning_goal",
    ),
    path("settings/", views.settings_view, name="settings"),
    path("profile/", views.profile_view, name="my_profile"),
    path("profile/<str:user_id>/", views.profile_view, name="profile"),
]
