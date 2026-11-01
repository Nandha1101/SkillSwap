from django.contrib.auth import views as auth_views
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
    path("requests/<int:request_id>/", views.update_request, name="update_request"),
    path("requests/new/<int:user_id>/", views.create_exchange_request, name="create_exchange_request"),
    path("sessions/", views.sessions_view, name="sessions"),
    path("sessions/schedule/", views.schedule_session, name="schedule_session"),
    path("sessions/exchanges/<int:exchange_id>/complete/", views.complete_exchange, name="complete_exchange"),
    path("sessions/exchanges/<int:exchange_id>/review/", views.submit_review, name="submit_review"),
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
    path("notifications/", views.notifications_view, name="notifications"),
    path("notifications/<int:notification_id>/read/", views.mark_notification_read, name="mark_notification_read"),
    path("notifications/read-all/", views.mark_all_notifications_read, name="mark_all_notifications_read"),
    path("settings/", views.settings_view, name="settings"),
    path("profile/", views.profile_view, name="my_profile"),
    path("profile/<str:user_id>/", views.profile_view, name="profile"),
    # Password Reset Flow
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="marketplace/password_reset.html",
            email_template_name="marketplace/password_reset_email.html",
            subject_template_name="marketplace/password_reset_subject.txt",
            success_url="/password-reset/done/",
        ),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="marketplace/password_reset_done.html",
        ),
        name="password_reset_done",
    ),
    path(
        "password-reset/confirm/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="marketplace/password_reset_confirm.html",
            success_url="/password-reset/complete/",
        ),
        name="password_reset_confirm",
    ),
    path(
        "password-reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="marketplace/password_reset_complete.html",
        ),
        name="password_reset_complete",
    ),
]
