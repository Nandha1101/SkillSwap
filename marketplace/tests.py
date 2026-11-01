import json
from datetime import timedelta
from io import BytesIO
from unittest.mock import patch
from urllib.error import URLError

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    Exchange,
    ExchangeLesson,
    ExchangeMessage,
    ExchangeRequest,
    LearningGoal,
    Profile,
    Session,
)


class MarketplaceFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="student@example.edu",
            email="student@example.edu",
            first_name="Nandha",
            password="Nandha!SkillSwap9284",
        )
        self.profile = Profile.objects.create(
            user=self.user,
            college="NIT Trichy",
            skills_to_teach="Python",
            skills_to_learn="UI Design",
        )
        self.partner = User.objects.create_user(
            username="designer@example.edu",
            email="designer@example.edu",
            first_name="Priya",
            last_name="Sharma",
            password="Priya!SkillSwap9284",
        )
        self.partner_profile = Profile.objects.create(
            user=self.partner,
            college="BITS Pilani",
            bio="A design student.",
            skills_to_teach="UI Design",
            skills_to_learn="Python",
        )

    def test_landing_and_protected_pages(self):
        landing = self.client.get(reverse("landing"))
        self.assertEqual(landing.status_code, 200)
        self.assertContains(landing, "What if learning")
        self.assertContains(landing, 'id="community"')
        self.assertContains(landing, "added both teach and learn skills")
        response = self.client.get(reverse("dashboard"))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('dashboard')}")

    @patch("marketplace.views.urlopen")
    def test_college_search_proxies_directory_results(self, mock_urlopen):
        mock_urlopen.return_value = BytesIO(json.dumps({
            "results": [
                {
                    "id": "https://openalex.org/I24676775",
                    "display_name": "Indian Institute of Technology Madras",
                    "country_code": "IN",
                    "homepage_url": "https://www.iitm.ac.in/",
                    "type": "education",
                },
            ],
        }).encode())

        response = self.client.get(reverse("college_search"), {"name": "  IIT Madras  "})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [{
            "name": "Indian Institute of Technology Madras",
            "country": "IN",
            "domains": ["iitm.ac.in"],
        }])
        request = mock_urlopen.call_args.args[0]
        self.assertIn("search=IIT+Madras", request.full_url)
        self.assertEqual(mock_urlopen.call_args.kwargs["timeout"], 8)

    @patch("marketplace.views.urlopen")
    def test_college_search_reports_directory_unavailability(self, mock_urlopen):
        mock_urlopen.side_effect = URLError("offline")

        response = self.client.get(reverse("college_search"), {"name": "MIT"})

        self.assertEqual(response.status_code, 503)
        self.assertIn("Check your internet connection", response.json()["error"])

    @patch("marketplace.views.urlopen")
    def test_college_search_rejects_short_queries(self, mock_urlopen):
        response = self.client.get(reverse("college_search"), {"name": "A"})

        self.assertEqual(response.status_code, 400)
        mock_urlopen.assert_not_called()

    def test_signup_creates_account_and_profile(self):
        page = self.client.get(reverse("signup"))
        self.assertContains(page, 'data-college-search=""')
        self.assertContains(page, 'id="college-results"')
        self.assertContains(page, 'id="signup_full_name"')
        self.assertContains(page, 'id="login_email"')
        response = self.client.post(reverse("signup"), {
            "full_name": "New Student",
            "email": "new@example.edu",
            "college": "Example University",
            "password1": "Student!SkillSwap9284",
            "password2": "Student!SkillSwap9284",
        })
        self.assertRedirects(response, reverse("dashboard"))
        created = User.objects.get(email="new@example.edu")
        self.assertTrue(created.check_password("Student!SkillSwap9284"))
        self.assertEqual(created.profile.college, "Example University")

    def test_login_uses_email_and_password(self):
        response = self.client.post(reverse("login"), {
            "email": "STUDENT@example.edu",
            "password": "Nandha!SkillSwap9284",
        })
        self.assertRedirects(response, reverse("dashboard"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_auth_switch_page_keeps_validation_errors_in_active_form(self):
        login_page = self.client.get(reverse("login"))
        self.assertContains(login_page, 'data-active-panel="login"')
        self.assertContains(login_page, 'data-auth-toggle="signup"')
        self.assertContains(login_page, 'action="/signup/"')

        failed_login = self.client.post(reverse("login"), {
            "email": self.user.email,
            "password": "incorrect",
        })
        self.assertContains(failed_login, "Email or password is incorrect.")
        self.assertContains(failed_login, 'data-active-panel="login"')

        failed_signup = self.client.post(reverse("signup"), {
            "full_name": "New Student",
            "email": "new@example.edu",
            "college": "Example University",
            "password1": "FirstPassword!9284",
            "password2": "DifferentPassword!9284",
        })
        self.assertContains(failed_signup, "The passwords do not match.")
        self.assertContains(failed_signup, 'data-active-panel="signup"')
        self.assertContains(failed_signup, 'value="New Student"')

    def test_explore_and_exchange_request_acceptance_use_database_records(self):
        self.client.force_login(self.user)
        explore = self.client.get(reverse("explore"))
        self.assertContains(explore, 'class="member-site theme-explore font-sans text-text-primary"')
        self.assertContains(explore, "Priya Sharma")
        self.assertContains(explore, "UI Design")
        self.assertNotContains(explore, "Arjun Nair")
        profile_page = self.client.get(reverse("profile", args=[self.partner.pk]))
        self.assertContains(profile_page, '<option value="Python">Python</option>', html=True)
        self.assertContains(profile_page, '<option value="UI Design">UI Design</option>', html=True)

        response = self.client.post(
            reverse("create_exchange_request", args=[self.partner.pk]),
            {
                "offered_skill": "Python",
                "requested_skill": "UI Design",
                "message": "Let's learn together.",
            },
        )
        self.assertRedirects(response, reverse("profile", args=[self.partner.pk]))
        exchange_request = ExchangeRequest.objects.get(sender=self.user, recipient=self.partner)

        self.client.force_login(self.partner)
        response = self.client.post(
            reverse("update_request", args=[exchange_request.pk]),
            {"action": "accepted"},
        )
        self.assertRedirects(response, reverse("requests"))
        exchange_request.refresh_from_db()
        self.assertEqual(exchange_request.status, ExchangeRequest.Status.ACCEPTED)
        self.assertEqual(Exchange.objects.filter(request=exchange_request).count(), 1)
        exchange = Exchange.objects.get(request=exchange_request)
        self.assertContains(
            self.client.get(reverse("requests")),
            reverse("exchange_learning", args=[exchange.pk]),
        )

        self.client.post(reverse("update_request", args=[exchange_request.pk]), {"action": "accepted"})
        self.assertEqual(Exchange.objects.filter(request=exchange_request).count(), 1)
        self.client.post(reverse("complete_exchange", args=[exchange.pk]))
        exchange.refresh_from_db()
        self.assertEqual(exchange.status, Exchange.Status.COMPLETED)
        self.assertIsNotNone(exchange.completed_at)

    def test_exchange_request_rejects_skills_not_available_for_swap(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("create_exchange_request", args=[self.partner.pk]),
            {
                "offered_skill": "Django",
                "requested_skill": "UI Design",
                "message": "",
            },
        )
        self.assertRedirects(response, reverse("profile", args=[self.partner.pk]))
        self.assertFalse(ExchangeRequest.objects.exists())

    def test_only_recipient_can_accept_and_decline_request(self):
        exchange_request = ExchangeRequest.objects.create(
            sender=self.user,
            recipient=self.partner,
            offered_skill="Python",
            requested_skill="UI Design",
        )
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("update_request", args=[exchange_request.pk]),
            {"action": "accepted"},
        )
        self.assertEqual(response.status_code, 404)
        exchange_request.refresh_from_db()
        self.assertEqual(exchange_request.status, ExchangeRequest.Status.PENDING)

        self.client.force_login(self.partner)
        self.client.post(
            reverse("update_request", args=[exchange_request.pk]),
            {"action": "declined"},
        )
        exchange_request.refresh_from_db()
        self.assertEqual(exchange_request.status, ExchangeRequest.Status.DECLINED)
        self.assertFalse(Exchange.objects.filter(request=exchange_request).exists())

    def test_nonparticipant_cannot_complete_exchange_or_session(self):
        exchange_request = ExchangeRequest.objects.create(
            sender=self.user,
            recipient=self.partner,
            offered_skill="Python",
            requested_skill="UI Design",
            status=ExchangeRequest.Status.ACCEPTED,
        )
        exchange = Exchange.objects.create(request=exchange_request)
        session = Session.objects.create(
            exchange=exchange,
            created_by=self.user,
            topic="Python basics",
            starts_at=timezone.now() - timedelta(minutes=1),
        )
        stranger = User.objects.create_user(
            username="stranger@example.edu",
            email="stranger@example.edu",
            password="Stranger!SkillSwap9284",
        )
        self.client.force_login(stranger)
        self.client.post(reverse("complete_exchange", args=[exchange.pk]))
        self.client.post(reverse("complete_session", args=[session.pk]))
        exchange.refresh_from_db()
        session.refresh_from_db()
        self.assertEqual(exchange.status, Exchange.Status.ACTIVE)
        self.assertEqual(session.status, Session.Status.SCHEDULED)

    def test_exchange_learning_space_restricts_access_to_participants(self):
        exchange_request = ExchangeRequest.objects.create(
            sender=self.user,
            recipient=self.partner,
            offered_skill="Python",
            requested_skill="UI Design",
            status=ExchangeRequest.Status.ACCEPTED,
        )
        exchange = Exchange.objects.create(request=exchange_request)
        self.client.force_login(self.user)
        page = self.client.get(reverse("exchange_learning", args=[exchange.pk]))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Learn")
        self.assertContains(page, "Conversation")
        self.assertContains(page, "Shared goals")
        self.assertContains(page, "TEACHING")
        self.assertContains(page, "Python")
        self.assertContains(page, "LEARNING")
        self.assertContains(page, "UI Design")

        self.client.force_login(self.partner)
        partner_page = self.client.get(reverse("exchange_learning", args=[exchange.pk]))
        self.assertContains(partner_page, "TEACHING")
        self.assertContains(partner_page, "UI Design")
        self.assertContains(partner_page, "LEARNING")
        self.assertContains(partner_page, "Python")

        stranger = User.objects.create_user(
            username="outsider@example.edu",
            email="outsider@example.edu",
            password="Outsider!SkillSwap9284",
        )
        self.client.force_login(stranger)
        unavailable = self.client.get(reverse("exchange_learning", args=[exchange.pk]))
        self.assertEqual(unavailable.status_code, 404)
        self.assertContains(unavailable, "This learning space", status_code=404)
        self.assertEqual(
            self.client.get(reverse("exchange_messages", args=[exchange.pk])).status_code,
            404,
        )

    def test_completed_exchange_learning_space_is_read_only_and_linked_from_sessions(self):
        exchange_request = ExchangeRequest.objects.create(
            sender=self.user,
            recipient=self.partner,
            offered_skill="Python",
            requested_skill="UI Design",
            status=ExchangeRequest.Status.ACCEPTED,
        )
        exchange = Exchange.objects.create(
            request=exchange_request,
            status=Exchange.Status.COMPLETED,
        )
        lesson = ExchangeLesson.objects.create(
            exchange=exchange,
            author=self.partner,
            skill="UI Design",
            title="Color and contrast",
            content="Start with clear visual hierarchy.",
        )
        message = ExchangeMessage.objects.create(
            exchange=exchange,
            author=self.user,
            content="Thanks for the lesson!",
        )
        goal = LearningGoal.objects.create(
            exchange=exchange,
            created_by=self.user,
            title="Build a small portfolio page",
        )

        self.client.force_login(self.user)
        page = self.client.get(reverse("exchange_learning", args=[exchange.pk]))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Exchange completed")
        self.assertContains(page, lesson.title)
        self.assertContains(page, message.content)
        self.assertContains(page, goal.title)
        self.assertContains(page, "Read only")
        self.assertNotContains(
            page,
            f'action="{reverse("publish_exchange_lesson", args=[exchange.pk])}"',
        )
        self.assertNotContains(
            page,
            f'action="{reverse("send_exchange_message", args=[exchange.pk])}"',
        )
        self.assertNotContains(
            page,
            f'action="{reverse("add_learning_goal", args=[exchange.pk])}"',
        )

        sessions_page = self.client.get(reverse("sessions"))
        self.assertContains(sessions_page, "Past swaps")
        self.assertContains(sessions_page, reverse("exchange_learning", args=[exchange.pk]))

        self.client.post(
            reverse("send_exchange_message", args=[exchange.pk]),
            {"content": "A message after completion"},
        )
        self.client.post(
            reverse("add_learning_goal", args=[exchange.pk]),
            {"title": "A goal after completion"},
        )
        self.client.post(
            reverse("toggle_learning_goal", args=[exchange.pk, goal.pk]),
        )
        self.assertEqual(ExchangeMessage.objects.filter(exchange=exchange).count(), 1)
        self.assertEqual(LearningGoal.objects.filter(exchange=exchange).count(), 1)
        goal.refresh_from_db()
        self.assertFalse(goal.is_completed)

    def test_exchange_partners_can_share_lessons_messages_and_goals(self):
        exchange_request = ExchangeRequest.objects.create(
            sender=self.user,
            recipient=self.partner,
            offered_skill="Python",
            requested_skill="UI Design",
            status=ExchangeRequest.Status.ACCEPTED,
        )
        exchange = Exchange.objects.create(request=exchange_request)

        self.client.force_login(self.partner)
        response = self.client.post(
            reverse("publish_exchange_lesson", args=[exchange.pk]),
            {
                "skill": "UI Design",
                "title": "Visual hierarchy basics",
                "content": "Start with size and contrast.",
                "resource_url": "https://example.edu/design",
            },
        )
        self.assertRedirects(response, reverse("exchange_learning", args=[exchange.pk]))
        lesson = ExchangeLesson.objects.get(exchange=exchange)
        self.assertEqual(lesson.author, self.partner)

        self.client.post(
            reverse("publish_exchange_lesson", args=[exchange.pk]),
            {
                "skill": "UI Design",
                "title": "Invalid resource",
                "content": "Should reject executable links.",
                "resource_url": "javascript:alert(1)",
            },
        )
        self.assertEqual(ExchangeLesson.objects.filter(exchange=exchange).count(), 1)

        response = self.client.post(
            reverse("publish_exchange_lesson", args=[exchange.pk]),
            {
                "skill": "Python",
                "title": "Not my teaching skill",
                "content": "This should not be posted.",
            },
        )
        self.assertRedirects(response, reverse("exchange_learning", args=[exchange.pk]))
        self.assertEqual(ExchangeLesson.objects.filter(exchange=exchange).count(), 1)

        response = self.client.post(
            reverse("send_exchange_message", args=[exchange.pk]),
            {"content": "<script>alert('x')</script> Let's begin!"},
        )
        self.assertRedirects(response, reverse("exchange_learning", args=[exchange.pk]))
        chat_message = ExchangeMessage.objects.get(exchange=exchange)
        self.assertEqual(chat_message.author, self.partner)
        self.assertContains(
            self.client.get(reverse("exchange_learning", args=[exchange.pk])),
            "&lt;script&gt;",
        )

        self.client.force_login(self.user)
        poll_response = self.client.get(
            reverse("exchange_messages", args=[exchange.pk]),
            {"after": "0"},
        )
        self.assertEqual(poll_response.status_code, 200)
        self.assertEqual(poll_response.json()["messages"][0]["content"], chat_message.content)
        invalid_cursor = self.client.get(
            reverse("exchange_messages", args=[exchange.pk]),
            {"after": "999999999999999999999999999999999"},
        )
        self.assertEqual(invalid_cursor.status_code, 400)

        self.client.post(
            reverse("add_learning_goal", args=[exchange.pk]),
            {"title": "Create a small portfolio page"},
        )
        goal = LearningGoal.objects.get(exchange=exchange)
        self.assertEqual(goal.created_by, self.user)
        self.client.post(
            reverse("toggle_learning_goal", args=[exchange.pk, goal.pk]),
        )
        goal.refresh_from_db()
        self.assertTrue(goal.is_completed)
        self.assertEqual(goal.completed_by, self.user)

    def test_schedule_and_complete_exchange_session(self):
        exchange_request = ExchangeRequest.objects.create(
            sender=self.user,
            recipient=self.partner,
            offered_skill="Python",
            requested_skill="UI Design",
            status=ExchangeRequest.Status.ACCEPTED,
        )
        exchange = Exchange.objects.create(request=exchange_request)
        self.client.force_login(self.user)
        past = timezone.localtime(timezone.now() - timedelta(days=1)).replace(second=0, microsecond=0)
        response = self.client.post(reverse("schedule_session"), {
            "exchange": exchange.pk,
            "topic": "Python basics",
            "starts_at": past.strftime("%Y-%m-%dT%H:%M"),
            "duration_minutes": "60",
        })
        self.assertRedirects(response, reverse("sessions"))
        self.assertFalse(Session.objects.filter(exchange=exchange).exists())

        start = timezone.localtime(timezone.now() + timedelta(days=2)).replace(second=0, microsecond=0)
        response = self.client.post(reverse("schedule_session"), {
            "exchange": exchange.pk,
            "topic": "Python basics",
            "starts_at": start.strftime("%Y-%m-%dT%H:%M"),
            "duration_minutes": "60",
        })
        self.assertRedirects(response, reverse("sessions"))
        session = Session.objects.get(exchange=exchange)
        self.assertEqual(session.created_by, self.user)
        self.assertContains(self.client.get(reverse("sessions")), "Python basics")

        response = self.client.post(reverse("complete_session", args=[session.pk]))
        self.assertRedirects(response, reverse("sessions"))
        session.refresh_from_db()
        self.assertEqual(session.status, Session.Status.SCHEDULED)

        Session.objects.filter(pk=session.pk).update(starts_at=timezone.now() - timedelta(minutes=1))
        response = self.client.post(reverse("complete_session", args=[session.pk]))
        self.assertRedirects(response, reverse("sessions"))
        session.refresh_from_db()
        self.assertEqual(session.status, Session.Status.COMPLETED)
        self.assertIsNotNone(session.completed_at)

    def test_profile_settings_normalize_skills_and_member_pages_show_no_demo_activity(self):
        self.client.force_login(self.user)
        for route in ("dashboard", "explore", "requests", "sessions", "settings", "my_profile"):
            with self.subTest(route=route):
                self.assertEqual(self.client.get(reverse(route)).status_code, 200)
        self.assertContains(self.client.get(reverse("dashboard")), "People worth meeting.")
        self.assertContains(self.client.get(reverse("requests")), "Little <em>openings.</em>")
        self.assertContains(self.client.get(reverse("sessions")), "On the <em>calendar.</em>")
        self.assertContains(self.client.get(reverse("profile", args=[self.partner.pk])), "Priya Sharma")

        response = self.client.post(reverse("settings"), {
            "name": "Nandha Kumar",
            "email": "student@example.edu",
            "college": "NIT Trichy",
            "year": "3rd Year",
            "bio": "I teach Python.",
            "skills_to_teach": " Python, Python, Django ",
            "skills_to_learn": "UI Design",
            "session_format": "Video call",
        })
        self.assertRedirects(response, reverse("settings"))
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.bio, "I teach Python.")
        self.assertEqual(self.profile.skills_to_teach, "Python, Django")
