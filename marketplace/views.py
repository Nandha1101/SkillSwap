import hashlib
import json
import logging
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.mail import send_mail
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import transaction
from django.db.models import Avg, Count, Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST

from .forms import (
    EmailLoginForm,
    ExchangeLessonForm,
    ExchangeMessageForm,
    ExchangeRequestForm,
    LearningGoalForm,
    ProfileForm,
    ReviewForm,
    SessionForm,
    SignupForm,
)
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

logger = logging.getLogger(__name__)


def profile_for(user):
    profile, _ = Profile.objects.get_or_create(user=user)
    return profile


def notify_user(recipient, actor, notification_type, title, message="", link=""):
    try:
        Notification.objects.create(
            recipient=recipient,
            actor=actor,
            notification_type=notification_type,
            title=title,
            message=message,
            link=link,
        )
        cache.delete(f"user_unread_notif_{recipient.pk}")
    except Exception as error:
        logger.warning("Could not create notification: %s", error)


def send_email_notification(recipient, subject, body):
    if not recipient.email:
        return
    try:
        send_mail(
            subject=f"[SkillSwap] {subject}",
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient.email],
            fail_silently=True,
        )
    except Exception as error:
        logger.warning("Could not send email notification: %s", error)


def landing(request):
    member_count = Profile.objects.exclude(
        skills_to_teach="",
    ).exclude(skills_to_learn="").count()
    return render(request, "marketplace/landing.html", {"member_count": member_count})


@require_GET
def college_search(request):
    query = request.GET.get("name", "").strip()
    if len(query) < 2 or len(query) > 100:
        return JsonResponse({"error": "Enter between 2 and 100 characters to search."}, status=400)

    cache_key = "college-search:" + hashlib.sha256(query.casefold().encode("utf-8")).hexdigest()
    cached_results = cache.get(cache_key)
    if cached_results is not None:
        return JsonResponse(cached_results, safe=False)

    endpoint = "https://api.openalex.org/institutions"
    parameters = urlencode({
        "search": query,
        "per-page": 20,
        "select": "id,display_name,country_code,homepage_url,type",
    })
    directory_request = Request(
        f"{endpoint}?{parameters}",
        headers={"Accept": "application/json", "User-Agent": "SkillSwap/1.0"},
    )
    try:
        with urlopen(directory_request, timeout=8) as response:
            payload = json.loads(response.read(2_000_000))
    except HTTPError as error:
        logger.warning("Institution directory returned HTTP %s for college search.", error.code)
        return JsonResponse(
            {"error": "The college directory is temporarily unavailable. Please try again or enter the name manually."},
            status=502,
        )
    except (URLError, TimeoutError, OSError) as error:
        logger.warning("Institution directory could not be reached: %s", error)
        return JsonResponse(
            {"error": "Could not reach the college directory. Check your internet connection or enter the name manually."},
            status=503,
        )
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        logger.warning("Institution directory returned invalid JSON: %s", error)
        return JsonResponse(
            {"error": "The college directory returned an invalid response. Please try again or enter the name manually."},
            status=502,
        )

    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        logger.warning("Institution directory returned an unexpected response type.")
        return JsonResponse(
            {"error": "The college directory returned an invalid response. Please try again or enter the name manually."},
            status=502,
        )

    results = []
    for institution in payload["results"]:
        if not isinstance(institution, dict) or institution.get("type") != "education":
            continue
        name = institution.get("display_name")
        if not isinstance(name, str) or not name.strip():
            continue
        homepage = institution.get("homepage_url")
        domain = urlparse(homepage).hostname if isinstance(homepage, str) else None
        if domain and domain.startswith("www."):
            domain = domain[4:]
        results.append({
            "name": name,
            "country": institution.get("country_code") or "",
            "domains": [domain] if domain else [],
        })
        if len(results) == 8:
            break

    cache.set(cache_key, results, timeout=60 * 60 * 6)
    return JsonResponse(results, safe=False)


def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = EmailLoginForm(request, request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.user)
        next_url = request.GET.get("next", "")
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
            return redirect(next_url)
        return redirect("dashboard")
    return render(request, "marketplace/auth.html", {
        "form": form,
        "login_form": form,
        "signup_form": SignupForm(),
        "active_panel": "login",
        "signup": False,
    })


def signup_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        notify_user(
            recipient=user,
            actor=None,
            notification_type=Notification.NotificationType.REQUEST_RECEIVED,
            title="Welcome to SkillSwap! Add skills to your profile to find matches.",
            link=reverse("settings"),
        )
        return redirect("dashboard")
    return render(request, "marketplace/auth.html", {
        "form": form,
        "signup_form": form,
        "login_form": EmailLoginForm(request),
        "active_panel": "signup",
        "signup": True,
    })


@require_POST
def logout_view(request):
    logout(request)
    return redirect("landing")


@login_required
def dashboard(request):
    profile = profile_for(request.user)
    pending_count = ExchangeRequest.objects.filter(
        recipient=request.user, status=ExchangeRequest.Status.PENDING
    ).count()
    pending_requests = (
        ExchangeRequest.objects.filter(
            recipient=request.user, status=ExchangeRequest.Status.PENDING
        ).select_related("sender", "sender__profile")[:3]
    )
    active_exchanges = list(
        Exchange.objects.filter(status=Exchange.Status.ACTIVE)
        .filter(Q(request__sender=request.user) | Q(request__recipient=request.user))
        .select_related("request__sender__profile", "request__recipient__profile")
    )
    for exchange in active_exchanges:
        exchange.partner = exchange.partner_for(request.user)
    next_session = (
        Session.objects.filter(
            status=Session.Status.SCHEDULED,
            starts_at__gte=timezone.now(),
        )
        .filter(Q(exchange__request__sender=request.user) | Q(exchange__request__recipient=request.user))
        .select_related("exchange__request__sender", "exchange__request__recipient")
        .first()
    )
    if next_session:
        next_session.partner = next_session.exchange.partner_for(request.user)
    suggestions = matching_profiles(request.user, profile)[:3]
    return render(request, "marketplace/dashboard.html", {
        "profile": profile,
        "users": suggestions,
        "pending_count": pending_count,
        "pending_requests": pending_requests,
        "active_exchanges": active_exchanges,
        "active_count": len(active_exchanges),
        "upcoming_count": Session.objects.filter(
            status=Session.Status.SCHEDULED,
            starts_at__gte=timezone.now(),
        ).filter(Q(exchange__request__sender=request.user) | Q(exchange__request__recipient=request.user)).count(),
        "next_session": next_session,
    })


@login_required
def explore(request):
    teach = request.GET.get("teach", "").strip()
    learn = request.GET.get("learn", "").strip()
    profile = profile_for(request.user)
    matches = matching_profiles(request.user, profile)
    if teach:
        matches = [person for person in matches if skill_matches(teach, person["learn_skills"])]
    if learn:
        matches = [person for person in matches if skill_matches(learn, person["teach_skills"])]

    page = request.GET.get("page", 1)
    paginator = Paginator(matches, 6)
    try:
        page_obj = paginator.page(page)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)

    return render(request, "marketplace/explore.html", {
        "users": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "teach": teach,
        "learn": learn,
    })


@login_required
def requests_view(request):
    tab = request.GET.get("tab", "received")
    if tab not in {"received", "sent"}:
        tab = "received"
    lookup = {"received": {"recipient": request.user}, "sent": {"sender": request.user}}[tab]
    exchange_requests = ExchangeRequest.objects.filter(**lookup).select_related(
        "sender__profile", "recipient__profile", "exchange"
    )
    items = []
    for exchange_request in exchange_requests:
        other = exchange_request.sender if tab == "received" else exchange_request.recipient
        other_profile = getattr(other, "profile", None)
        related_exchange = getattr(exchange_request, "exchange", None)
        items.append({
            "id": exchange_request.pk,
            "name": other.get_full_name() or other.username,
            "college": getattr(other_profile, "college", ""),
            "avatar_url": other_profile.avatar.url if (other_profile and other_profile.avatar) else None,
            "requested": exchange_request.requested_skill if tab == "received" else exchange_request.offered_skill,
            "offered": exchange_request.offered_skill if tab == "received" else exchange_request.requested_skill,
            "message": exchange_request.message,
            "created": exchange_request.created_at,
            "status": exchange_request.status,
            "exchange_id": (
                related_exchange.pk
                if exchange_request.status == ExchangeRequest.Status.ACCEPTED and related_exchange
                else None
            ),
        })
    return render(request, "marketplace/requests.html", {"items": items, "tab": tab})


@login_required
@require_POST
def update_request(request, request_id):
    action = request.POST.get("action")
    if action not in {ExchangeRequest.Status.ACCEPTED, ExchangeRequest.Status.DECLINED}:
        messages.error(request, "That request action could not be completed.")
        return redirect("requests")
    with transaction.atomic():
        exchange_request = get_object_or_404(
            ExchangeRequest.objects.select_for_update().select_related("sender"),
            pk=request_id,
            recipient=request.user,
        )
        if exchange_request.status != ExchangeRequest.Status.PENDING:
            messages.error(request, "This request has already been handled.")
            return redirect("requests")
        if action == ExchangeRequest.Status.ACCEPTED:
            sender_profile = profile_for(exchange_request.sender)
            recipient_profile = profile_for(exchange_request.recipient)
            if not skill_matches(exchange_request.offered_skill, sender_profile.teach_skills) or not skill_matches(
                exchange_request.offered_skill, recipient_profile.learn_skills
            ) or not skill_matches(exchange_request.requested_skill, recipient_profile.teach_skills) or not skill_matches(
                exchange_request.requested_skill, sender_profile.learn_skills
            ):
                messages.error(request, "This request no longer matches the students' current skills.")
                return redirect("requests")
        exchange_request.status = action
        exchange_request.save(update_fields=("status", "updated_at"))
        exchange = None
        if action == ExchangeRequest.Status.ACCEPTED:
            exchange, _ = Exchange.objects.get_or_create(request=exchange_request)
            ExchangeRequest.objects.filter(
                Q(sender=exchange_request.sender, recipient=exchange_request.recipient)
                | Q(sender=exchange_request.recipient, recipient=exchange_request.sender),
                status=ExchangeRequest.Status.PENDING,
            ).exclude(pk=exchange_request.pk).update(
                status=ExchangeRequest.Status.DECLINED,
                updated_at=timezone.now(),
            )

    notif_type = (
        Notification.NotificationType.REQUEST_ACCEPTED
        if action == ExchangeRequest.Status.ACCEPTED
        else Notification.NotificationType.REQUEST_DECLINED
    )
    link = reverse("exchange_learning", args=[exchange.pk]) if exchange else reverse("requests")
    notify_user(
        recipient=exchange_request.sender,
        actor=request.user,
        notification_type=notif_type,
        title=f"{request.user.get_full_name() or request.user.username} {action} your skill exchange request!",
        message=f"{exchange_request.offered_skill} ↔ {exchange_request.requested_skill}",
        link=link,
    )
    send_email_notification(
        recipient=exchange_request.sender,
        subject=f"Exchange request {action} by {request.user.get_full_name() or request.user.username}",
        body=(
            f"Hi {exchange_request.sender.first_name or exchange_request.sender.username},\n\n"
            f"{request.user.get_full_name() or request.user.username} has {action} your request to swap "
            f"{exchange_request.offered_skill} for {exchange_request.requested_skill}.\n\n"
            f"Check your SkillSwap dashboard to get started!\n- The SkillSwap Team"
        ),
    )
    messages.success(request, f"Request {action}.")
    return redirect("requests")


@login_required
def sessions_view(request):
    sessions = (
        Session.objects.filter(
            Q(exchange__request__sender=request.user) | Q(exchange__request__recipient=request.user)
        )
        .select_related("exchange__request__sender", "exchange__request__recipient")
    )
    upcoming = list(sessions.filter(status=Session.Status.SCHEDULED, starts_at__gte=timezone.now()))
    past = list(sessions.filter(Q(status=Session.Status.COMPLETED) | Q(starts_at__lt=timezone.now())).order_by("-starts_at"))
    for session in upcoming + past:
        session.partner = session.exchange.partner_for(request.user)

    form = SessionForm(user=request.user)
    exchange_choices = [("", "---------")]
    for exchange in form.fields["exchange"].queryset:
        partner = exchange.partner_for(request.user)
        exchange_choices.append(
            (exchange.pk, f"{partner.get_full_name() or partner.username} · {exchange.request.offered_skill} ↔ {exchange.request.requested_skill}")
        )
    form.fields["exchange"].choices = exchange_choices
    active_exchanges = list(form.fields["exchange"].queryset)
    completed_exchanges = list(
        Exchange.objects.filter(status=Exchange.Status.COMPLETED)
        .filter(Q(request__sender=request.user) | Q(request__recipient=request.user))
        .select_related("request__sender", "request__recipient")
    )
    reviewed_exchange_ids = set(
        Review.objects.filter(reviewer=request.user, exchange__in=completed_exchanges).values_list("exchange_id", flat=True)
    )
    for exchange in completed_exchanges:
        exchange.partner = exchange.partner_for(request.user)
        exchange.has_reviewed = exchange.pk in reviewed_exchange_ids

    return render(request, "marketplace/sessions.html", {
        "upcoming": upcoming,
        "past": past,
        "form": form,
        "active_exchanges": active_exchanges,
        "completed_exchanges": completed_exchanges,
        "review_form": ReviewForm(),
    })


@login_required
@require_POST
def schedule_session(request):
    form = SessionForm(request.POST, user=request.user)
    if form.is_valid():
        exchange = form.cleaned_data["exchange"]
        session = Session(
            exchange=exchange,
            created_by=request.user,
            topic=form.cleaned_data["topic"],
            starts_at=form.cleaned_data["starts_at"],
            duration_minutes=form.cleaned_data["duration_minutes"],
        )
        session.save()
        partner = exchange.partner_for(request.user)
        notify_user(
            recipient=partner,
            actor=request.user,
            notification_type=Notification.NotificationType.SESSION_SCHEDULED,
            title=f"New session scheduled: {session.topic}",
            message=f"{session.starts_at.strftime('%A, %b %d at %I:%M %p')} ({session.duration_minutes} min)",
            link=reverse("sessions"),
        )
        send_email_notification(
            recipient=partner,
            subject=f"New session scheduled by {request.user.get_full_name() or request.user.username}",
            body=(
                f"Hi {partner.first_name or partner.username},\n\n"
                f"{request.user.get_full_name() or request.user.username} scheduled a session with you on \"{session.topic}\".\n"
                f"Date & Time: {session.starts_at.strftime('%A, %b %d at %I:%M %p')}\n"
                f"Duration: {session.duration_minutes} minutes\n\n"
                f"View your calendar on SkillSwap!\n- The SkillSwap Team"
            ),
        )
        messages.success(request, "Your session is on the calendar.")
    else:
        messages.error(request, "Please choose a valid exchange and future session time.")
    return redirect("sessions")


@login_required
@require_POST
def complete_exchange(request, exchange_id):
    exchange = get_object_or_404(
        Exchange.objects.select_related("request"),
        pk=exchange_id,
    )
    if not exchange.includes(request.user):
        messages.error(request, "You are not a participant in this exchange.")
    elif exchange.status == Exchange.Status.COMPLETED:
        messages.info(request, "This exchange is already complete.")
    else:
        exchange.status = Exchange.Status.COMPLETED
        exchange.completed_at = timezone.now()
        exchange.save(update_fields=("status", "completed_at"))
        partner = exchange.partner_for(request.user)
        notify_user(
            recipient=partner,
            actor=request.user,
            notification_type=Notification.NotificationType.SESSION_COMPLETED,
            title="Skill exchange completed! Please leave a review.",
            message=f"{exchange.request.offered_skill} ↔ {exchange.request.requested_skill}",
            link=reverse("sessions"),
        )
        send_email_notification(
            recipient=partner,
            subject="Skill exchange completed — Leave a review!",
            body=(
                f"Hi {partner.first_name or partner.username},\n\n"
                f"Your exchange with {request.user.get_full_name() or request.user.username} was marked complete!\n"
                f"Head over to SkillSwap to leave a review and share feedback.\n\n- The SkillSwap Team"
            ),
        )
        messages.success(request, "Exchange marked complete. Thanks for sharing what you know! Don't forget to leave a review below.")
    return redirect("sessions")


@login_required
@require_POST
def complete_session(request, session_id):
    session = get_object_or_404(
        Session.objects.select_related("exchange__request"),
        pk=session_id,
    )
    if not session.exchange.includes(request.user):
        messages.error(request, "You are not a participant in this session.")
    elif session.status == Session.Status.COMPLETED:
        messages.info(request, "This session is already marked complete.")
    elif session.starts_at > timezone.now():
        messages.error(request, "A session can only be completed after its scheduled start time.")
    else:
        session.status = Session.Status.COMPLETED
        session.completed_at = timezone.now()
        session.save(update_fields=("status", "completed_at"))
        partner = session.exchange.partner_for(request.user)
        notify_user(
            recipient=partner,
            actor=request.user,
            notification_type=Notification.NotificationType.SESSION_COMPLETED,
            title=f"Session completed: {session.topic}",
            link=reverse("sessions"),
        )
        messages.success(request, "Session marked complete. Nice work!")
    return redirect("sessions")


@login_required
@require_POST
def submit_review(request, exchange_id):
    exchange = get_object_or_404(Exchange.objects.select_related("request"), pk=exchange_id)
    if not exchange.includes(request.user):
        messages.error(request, "You are not a participant in this exchange.")
        return redirect("sessions")
    if exchange.status != Exchange.Status.COMPLETED:
        messages.error(request, "You can only review an exchange after it is completed.")
        return redirect("sessions")

    partner = exchange.partner_for(request.user)
    if Review.objects.filter(exchange=exchange, reviewer=request.user).exists():
        messages.info(request, "You have already submitted a review for this exchange.")
        return redirect("sessions")

    form = ReviewForm(request.POST)
    if form.is_valid():
        review = form.save(commit=False)
        review.exchange = exchange
        review.reviewer = request.user
        review.reviewee = partner
        review.save()
        notify_user(
            recipient=partner,
            actor=request.user,
            notification_type=Notification.NotificationType.REVIEW_RECEIVED,
            title=f"{request.user.get_full_name() or request.user.username} left you a {review.rating}★ review!",
            message=review.comment[:100] if review.comment else "Thank you for the skill exchange!",
            link=reverse("my_profile"),
        )
        send_email_notification(
            recipient=partner,
            subject=f"New review received from {request.user.get_full_name() or request.user.username}",
            body=(
                f"Hi {partner.first_name or partner.username},\n\n"
                f"{request.user.get_full_name() or request.user.username} left a {review.rating}★ rating on your profile:\n\n"
                f"\"{review.comment}\"\n\n- The SkillSwap Team"
            ),
        )
        messages.success(request, f"Review submitted for {partner.get_full_name() or partner.username}!")
    else:
        messages.error(request, "Please choose a valid rating.")
    return redirect("sessions")


def get_exchange_for_user(exchange_id, user, *, active_only=False):
    exchanges = Exchange.objects.filter(
        Q(request__sender=user) | Q(request__recipient=user)
    ).select_related("request__sender", "request__recipient")
    if active_only:
        exchanges = exchanges.filter(status=Exchange.Status.ACTIVE)
    return get_object_or_404(exchanges, pk=exchange_id)


@login_required
def exchange_learning(request, exchange_id):
    try:
        exchange = get_exchange_for_user(exchange_id, request.user)
    except Http404:
        return render(
            request,
            "marketplace/exchange_unavailable.html",
            status=404,
        )
    lessons = exchange.lessons.select_related("author").all()
    messages_list = exchange.messages.select_related("author").order_by("-created_at")[:100]
    messages_list = list(reversed(messages_list))
    goals = exchange.goals.select_related("created_by", "completed_by").all()
    partner = exchange.partner_for(request.user)

    if exchange.request.sender_id == request.user.pk:
        teaching_skill = exchange.request.offered_skill
        learning_skill = exchange.request.requested_skill
    else:
        teaching_skill = exchange.request.requested_skill
        learning_skill = exchange.request.offered_skill

    lesson_form = ExchangeLessonForm(exchange=exchange, user=request.user)
    can_edit = exchange.status == Exchange.Status.ACTIVE
    can_teach = can_edit and bool(lesson_form.fields["skill"].choices)
    latest_message_id = messages_list[-1].pk if messages_list else 0

    return render(request, "marketplace/exchange_learning.html", {
        "exchange": exchange,
        "partner": partner,
        "teaching_skill": teaching_skill,
        "learning_skill": learning_skill,
        "lessons": lessons,
        "chat_messages": messages_list,
        "goals": goals,
        "latest_message_id": latest_message_id,
        "lesson_form": lesson_form,
        "goal_form": LearningGoalForm(),
        "message_form": ExchangeMessageForm(),
        "can_teach": can_teach,
        "can_edit": can_edit,
        "display_name": request.user.get_full_name() or request.user.username,
    })


@login_required
@require_POST
def publish_exchange_lesson(request, exchange_id):
    exchange = get_exchange_for_user(exchange_id, request.user, active_only=True)
    form = ExchangeLessonForm(request.POST, request.FILES, exchange=exchange, user=request.user)
    if form.is_valid():
        lesson = ExchangeLesson(
            exchange=exchange,
            author=request.user,
            skill=form.cleaned_data["skill"],
            title=form.cleaned_data["title"],
            content=form.cleaned_data["content"],
            resource_url=form.cleaned_data["resource_url"],
        )
        if "attachment" in request.FILES:
            att = request.FILES["attachment"]
            lesson.attachment = att
            lesson.attachment_name = att.name
        lesson.save()

        partner = exchange.partner_for(request.user)
        notify_user(
            recipient=partner,
            actor=request.user,
            notification_type=Notification.NotificationType.MESSAGE_RECEIVED,
            title=f"{request.user.get_full_name() or request.user.username} shared a new lesson: {lesson.title}",
            message=f"Covering {lesson.skill}",
            link=reverse("exchange_learning", args=[exchange.pk]),
        )
        messages.success(request, "Your lesson has been shared with your exchange partner.")
    else:
        messages.error(request, "Please check the lesson details and try again.")
    return redirect("exchange_learning", exchange_id=exchange.pk)


@login_required
@require_POST
def send_exchange_message(request, exchange_id):
    exchange = get_exchange_for_user(exchange_id, request.user, active_only=True)
    form = ExchangeMessageForm(request.POST)
    if form.is_valid():
        msg = ExchangeMessage.objects.create(
            exchange=exchange,
            author=request.user,
            content=form.cleaned_data["content"],
        )
        partner = exchange.partner_for(request.user)
        notify_user(
            recipient=partner,
            actor=request.user,
            notification_type=Notification.NotificationType.MESSAGE_RECEIVED,
            title=f"New message from {request.user.get_full_name() or request.user.username}",
            message=msg.content[:100],
            link=reverse("exchange_learning", args=[exchange.pk]),
        )
    else:
        messages.error(request, "Enter a message before sending.")
    return redirect("exchange_learning", exchange_id=exchange.pk)


@login_required
@require_GET
def exchange_messages(request, exchange_id):
    exchange = get_exchange_for_user(exchange_id, request.user)
    after = request.GET.get("after", "0")
    if (
        not after.isascii()
        or not after.isdigit()
        or len(after) > 19
        or int(after) > 9_223_372_036_854_775_807
    ):
        return JsonResponse({"error": "Message cursor must be a non-negative integer."}, status=400)
    new_messages = exchange.messages.filter(pk__gt=int(after)).select_related("author").order_by("pk")[:50]
    return JsonResponse({
        "messages": [{
            "id": message.pk,
            "author": message.author.get_full_name() or message.author.username,
            "content": message.content,
            "created_at": timezone.localtime(message.created_at).isoformat(),
            "is_mine": message.author_id == request.user.pk,
        } for message in new_messages],
    })


@login_required
@require_POST
def add_learning_goal(request, exchange_id):
    exchange = get_exchange_for_user(exchange_id, request.user, active_only=True)
    form = LearningGoalForm(request.POST)
    if form.is_valid():
        LearningGoal.objects.create(
            exchange=exchange,
            created_by=request.user,
            title=form.cleaned_data["title"],
        )
        partner = exchange.partner_for(request.user)
        notify_user(
            recipient=partner,
            actor=request.user,
            notification_type=Notification.NotificationType.GOAL_COMPLETED,
            title=f"New goal added: {form.cleaned_data['title']}",
            link=reverse("exchange_learning", args=[exchange.pk]),
        )
        messages.success(request, "Learning goal added.")
    else:
        messages.error(request, "Enter a goal before adding it.")
    return redirect("exchange_learning", exchange_id=exchange.pk)


@login_required
@require_POST
def toggle_learning_goal(request, exchange_id, goal_id):
    exchange = get_exchange_for_user(exchange_id, request.user, active_only=True)
    with transaction.atomic():
        goal = get_object_or_404(
            LearningGoal.objects.select_for_update(),
            pk=goal_id,
            exchange=exchange,
        )
        goal.is_completed = not goal.is_completed
        goal.completed_by = request.user if goal.is_completed else None
        goal.completed_at = timezone.now() if goal.is_completed else None
        goal.save(update_fields=("is_completed", "completed_by", "completed_at"))

    if goal.is_completed:
        partner = exchange.partner_for(request.user)
        notify_user(
            recipient=partner,
            actor=request.user,
            notification_type=Notification.NotificationType.GOAL_COMPLETED,
            title=f"Goal completed: {goal.title}",
            link=reverse("exchange_learning", args=[exchange.pk]),
        )
    return redirect("exchange_learning", exchange_id=exchange.pk)


@login_required
def settings_view(request):
    profile = profile_for(request.user)
    form = ProfileForm(request.POST or None, request.FILES or None, instance=profile, user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Your profile settings and photo have been saved.")
        return redirect("settings")
    return render(request, "marketplace/settings.html", {"form": form, "profile": profile})


@login_required
def profile_view(request, user_id=None):
    profile = profile_for(request.user)
    if user_id and user_id not in {"me", str(request.user.pk)}:
        other_profile = get_object_or_404(
            Profile.objects.select_related("user"),
            user_id=user_id,
        )
        other_user = other_profile.user
        form = ExchangeRequestForm(
            sender_profile=profile,
            recipient_profile=other_profile,
        )
        existing_request = ExchangeRequest.objects.filter(
            Q(sender=request.user, recipient=other_user)
            | Q(sender=other_user, recipient=request.user),
            status=ExchangeRequest.Status.PENDING,
        ).exists()
        existing_exchange = Exchange.objects.filter(
            Q(request__sender=request.user, request__recipient=other_user)
            | Q(request__sender=other_user, request__recipient=request.user),
            status=Exchange.Status.ACTIVE,
        ).exists()
        person = profile_context(other_profile)
        history = exchange_history(other_user)
        person["exchanges"] = len(history)
        reviews = Review.objects.filter(reviewee=other_user).select_related("reviewer", "reviewer__profile")
        return render(request, "marketplace/profile.html", {
            "person": person,
            "is_current_user": False,
            "request_form": form,
            "can_propose": bool(form.fields["offered_skill"].choices and form.fields["requested_skill"].choices),
            "existing_request": existing_request,
            "existing_exchange": existing_exchange,
            "exchange_history": history,
            "reviews": reviews,
        })

    history = exchange_history(request.user)
    person = profile_context(profile)
    person["exchanges"] = len(history)
    reviews = Review.objects.filter(reviewee=request.user).select_related("reviewer", "reviewer__profile")
    return render(request, "marketplace/profile.html", {
        "person": person,
        "is_current_user": True,
        "exchange_history": history,
        "reviews": reviews,
    })


@login_required
@require_POST
def create_exchange_request(request, user_id):
    recipient_profile = get_object_or_404(Profile.objects.select_related("user"), user_id=user_id)
    sender_profile = profile_for(request.user)
    if recipient_profile.user_id == request.user.pk:
        messages.error(request, "You cannot send an exchange request to yourself.")
        return redirect("my_profile")
    form = ExchangeRequestForm(
        request.POST,
        sender_profile=sender_profile,
        recipient_profile=recipient_profile,
    )
    if form.is_valid():
        with transaction.atomic():
            duplicate = ExchangeRequest.objects.select_for_update().filter(
                Q(sender=request.user, recipient=recipient_profile.user)
                | Q(sender=recipient_profile.user, recipient=request.user),
                status=ExchangeRequest.Status.PENDING,
            ).exists()
            if duplicate:
                messages.info(request, "You already have a pending request with this student.")
            elif Exchange.objects.filter(
                Q(request__sender=request.user, request__recipient=recipient_profile.user)
                | Q(request__sender=recipient_profile.user, request__recipient=request.user),
                status=Exchange.Status.ACTIVE,
            ).exists():
                messages.info(request, "You already have an active exchange with this student.")
            else:
                exchange_request = form.save(commit=False)
                exchange_request.sender = request.user
                exchange_request.recipient = recipient_profile.user
                exchange_request.save()
                notify_user(
                    recipient=recipient_profile.user,
                    actor=request.user,
                    notification_type=Notification.NotificationType.REQUEST_RECEIVED,
                    title=f"{request.user.get_full_name() or request.user.username} wants to swap skills with you!",
                    message=f"{exchange_request.offered_skill} ↔ {exchange_request.requested_skill}",
                    link=reverse("requests"),
                )
                send_email_notification(
                    recipient=recipient_profile.user,
                    subject=f"New skill exchange request from {request.user.get_full_name() or request.user.username}",
                    body=(
                        f"Hi {recipient_profile.user.first_name or recipient_profile.user.username},\n\n"
                        f"{request.user.get_full_name() or request.user.username} sent you an exchange request:\n"
                        f"They teach: {exchange_request.offered_skill}\n"
                        f"They want to learn: {exchange_request.requested_skill}\n\n"
                        f"Note: \"{exchange_request.message}\"\n\n"
                        f"Review and respond on SkillSwap!\n- The SkillSwap Team"
                    ),
                )
                messages.success(request, "Your exchange request has been sent.")
    else:
        messages.error(request, "That exchange could not be sent. Check that your profiles list matching skills.")
    return redirect("profile", user_id=recipient_profile.user_id)


@login_required
def notifications_view(request):
    notifications_qs = Notification.objects.filter(recipient=request.user).select_related("actor")
    page = request.GET.get("page", 1)
    paginator = Paginator(notifications_qs, 15)
    try:
        page_obj = paginator.page(page)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)

    return render(request, "marketplace/notifications.html", {
        "notifications": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
    })


@login_required
@require_POST
def mark_notification_read(request, notification_id):
    notification = get_object_or_404(Notification, pk=notification_id, recipient=request.user)
    notification.is_read = True
    notification.save(update_fields=("is_read",))
    cache.delete(f"user_unread_notif_{request.user.pk}")
    next_url = request.POST.get("next") or notification.link or reverse("notifications")
    return redirect(next_url)


@login_required
@require_POST
def mark_all_notifications_read(request):
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    cache.delete(f"user_unread_notif_{request.user.pk}")
    messages.success(request, "All notifications marked as read.")
    return redirect("notifications")


def skill_matches(query, skills):
    normalized_query = query.casefold()
    return any(normalized_query == skill.casefold() for skill in skills)


def matching_profiles(user, profile):
    my_teach = {skill.casefold() for skill in profile.teach_skills}
    my_learn = {skill.casefold() for skill in profile.learn_skills}
    matches = []
    completed_counts = {}
    for sender_id, recipient_id in Exchange.objects.filter(
        status=Exchange.Status.COMPLETED,
    ).values_list("request__sender_id", "request__recipient_id"):
        completed_counts[sender_id] = completed_counts.get(sender_id, 0) + 1
        completed_counts[recipient_id] = completed_counts.get(recipient_id, 0) + 1

    review_stats = {
        row["reviewee"]: (round(row["avg_r"], 1), row["count_r"])
        for row in Review.objects.values("reviewee").annotate(
            avg_r=Avg("rating"), count_r=Count("id")
        )
    }

    profiles = (
        Profile.objects.exclude(user=user)
        .exclude(skills_to_teach="")
        .exclude(skills_to_learn="")
        .select_related("user")
    )
    for other_profile in profiles:
        teach = other_profile.teach_skills
        learn = other_profile.learn_skills
        if my_teach.intersection(skill.casefold() for skill in learn) and my_learn.intersection(
            skill.casefold() for skill in teach
        ):
            person = profile_context(other_profile, review_stats=review_stats)
            person["exchanges"] = completed_counts.get(other_profile.user_id, 0)
            matches.append(person)
    return matches


def exchange_history(user):
    completed = (
        Exchange.objects.filter(status=Exchange.Status.COMPLETED)
        .filter(Q(request__sender=user) | Q(request__recipient=user))
        .select_related("request__sender", "request__recipient")
    )
    history = []
    for exchange in completed:
        partner = exchange.partner_for(user)
        history.append({
            "offered_skill": exchange.request.offered_skill,
            "requested_skill": exchange.request.requested_skill,
            "partner": partner.get_full_name() or partner.username,
            "completed_at": exchange.completed_at or exchange.created_at,
        })
    return history


def profile_context(profile, review_stats=None):
    user = profile.user
    if review_stats is not None and user.pk in review_stats:
        avg_rating, review_count = review_stats[user.pk]
    else:
        avg_rating, review_count = profile.avg_rating, profile.review_count
    person = {
        "id": user.pk,
        "name": user.get_full_name() or user.username,
        "avatar_url": profile.avatar.url if profile.avatar else None,
        "college": profile.college or "Add your college",
        "bio": profile.bio or "Add a short introduction about yourself.",
        "year": profile.year,
        "teach_skills": profile.teach_skills,
        "learn_skills": profile.learn_skills,
        "can_teach": profile.teach_skills or ["No skills listed yet"],
        "wants_to_learn": profile.learn_skills or ["No skills listed yet"],
        "avg_rating": avg_rating,
        "review_count": review_count,
        "exchanges": 0,
    }
    return person
