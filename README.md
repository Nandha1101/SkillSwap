# SkillSwap · Peer Skill Exchange

A focused peer-to-peer skill exchange platform designed for college students.
**A student teaches something they know in exchange for learning something they want to learn.**

---

## Key Features

- **Reciprocal Skill Matching**: Discover compatible peers where *I can teach ↔ You want to learn*.
- **Exchange Requests & Agreements**: Propose exchanges with specific skill pairs and custom notes.
- **Dedicated Learning Space**:
  - Real-time chat powered by Django Channels & WebSockets (with automatic polling fallback).
  - Shared lesson repository with downloadable attachments and external resources.
  - Interactive shared progress goals.
- **Reviews & Ratings**: Post-exchange feedback, star ratings, and exchange completion badges.
- **In-App Notification Center**: Instant alerts for incoming requests, session milestones, and new messages.
- **Student Profiles & Avatars**: Clean, editorial-style profile layout highlighting college, skills, bio, and student reputation.
- **Password Reset Flow**: Complete email-based reset workflow.

---

## Local Development Setup

### 1. Activate Environment & Install Dependencies
```powershell
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment Variables (`.env`)
Create a `.env` file in the root directory:
```env
DJANGO_SECRET_KEY=your-secret-key-here
DJANGO_DEBUG=1
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1

# Database (PostgreSQL)
DB_ENGINE=postgresql
DB_NAME=skillswap_db
DB_USER=postgres
DB_PASSWORD=your_password
DB_HOST=127.0.0.1
DB_PORT=5432

# Channels / Redis (Optional in local dev, uses in-memory layer by default)
# REDIS_URL=redis://127.0.0.1:6379/0
```

### 3. Apply Database Migrations
```powershell
python manage.py migrate
```

### 4. Run the Development Server
For HTTP + WebSocket real-time chat:
```powershell
daphne -b 127.0.0.1 -p 8000 skillswap.asgi:application
```
*(Or standard `python manage.py runserver` for standard HTTP testing).*

Open `http://127.0.0.1:8000/`.

---

## Running Automated Tests

Run the full Django test suite (all tests passing):
```powershell
python manage.py test
```

---

## Production Deployment Options

### Option A: Docker Compose (Full Stack with Nginx & Redis)
The repository includes production-ready `Dockerfile`, `docker-compose.yml`, and `nginx.conf`:

```bash
docker-compose up -d --build
```
This spins up:
1. `db`: PostgreSQL 16 container with persistent volumes
2. `redis`: Redis 7 container for WebSocket channel layer
3. `web`: ASGI application running Daphne
4. `nginx`: Reverse proxy with SSL termination and direct static/media caching

### Option B: Cloud PaaS (Railway / Render / Fly.io / Heroku)
The project includes a ready `Procfile` and `WhiteNoise` for zero-configuration static asset serving.

1. Connect your GitHub repository to Railway or Render.
2. Add a **PostgreSQL** service and a **Redis** service.
3. Configure the Environment Variables:
   - `DJANGO_SECRET_KEY`: A cryptographically secure random 50+ character string
   - `DJANGO_DEBUG`: `0`
   - `DJANGO_ALLOWED_HOSTS`: `yourdomain.com,your-app.up.railway.app`
   - `CSRF_TRUSTED_ORIGINS`: `https://yourdomain.com,https://your-app.up.railway.app`
   - `DB_ENGINE`: `postgresql`
   - `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`: From your database provider
   - `REDIS_URL`: From your Redis provider (e.g., `rediss://...`)
4. Build & start commands are handled automatically via the `Procfile`:
   - Release: `python manage.py migrate`
   - Web: `daphne -b 0.0.0.0 -p $PORT skillswap.asgi:application`
