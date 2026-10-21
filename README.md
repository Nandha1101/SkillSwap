# Peer Skill Exchange

The application is a server-rendered Django site.

## Run locally

```powershell
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Open `http://127.0.0.1:8000/`. Account registration, login, profiles, skills, exchange requests, accepted
swaps, and session schedules are stored in the configured Django database.
There are no seeded student, request, or session records: the marketplace
starts empty and fills with the accounts that register.

## Start exchanging skills

1. Register two student accounts and add each student's college, skills they
   can teach, and skills they want to learn under **Settings**.
2. A student will appear in **Explore** when both profiles have reciprocal
   skills: one student's teach skill matches the other's learn skill in both
   directions.
3. Open their profile, choose the two skills, and send an exchange request.
   The recipient accepts or declines it from **Requests**. Acceptance creates
   one active exchange.
4. Either student can schedule a future session for an active exchange from
   **Sessions**. After the scheduled start time, either participant can mark
   the session complete.
5. Open **Open learning space** from the dashboard, Sessions, or accepted
   request to share lesson notes and links, chat with your partner, track
   shared goals, and join the exchange's embedded video room.
6. Completed exchanges remain available under **Past swaps** in Sessions.
   Their saved learning notes, messages, and goals are read-only; the video
   room and editing controls are closed.

Video calls are embedded with Jitsi Meet (`meet.jit.si`). The call provider is
third-party software and handles the audio/video connection; the browser asks
each student for camera and microphone access. Each exchange gets a unique
room; share it only with your partner. Chat messages, lessons, and progress
goals are stored in the SkillSwap database and visible only to the two exchange
participants through the app.

Use `python manage.py test marketplace` to run the application tests.

Before deploying, set a private `SECRET_KEY`, turn off `DEBUG`, configure
`ALLOWED_HOSTS`, and serve the collected static files with a production web
server.
