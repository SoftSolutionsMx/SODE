# SODE

SODE is a Django project in its initial setup stage. It currently includes Django's built-in administration, authentication, and session support, with SQLite for local storage. No custom applications or project-specific pages have been added yet.

## Branch strategy

Name branches using `{type}/#n`, where `n` is the issue number:

- Feature: `feat/#n`
- Task: `task/#n`
- Bug fix: `fix/#n`

For example, use `feat/#123` for a feature associated with issue 123. When work is complete, open a pull request targeting `master`.


## Requirements

- Python 3.12 or newer, with `pip` and `venv` available.
- Django 6.1.2, matching the version used to generate the project.

The existing development environment uses Python 3.14.8. Dependencies are listed in `requirements.txt`.

## Getting started

Run these commands from the repository root, where `manage.py` lives.

### 1. Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

On Windows PowerShell, use:

```powershell
py -m venv venv
.\venv\Scripts\Activate.ps1
```

### 2. Install Django

```bash
python -m pip install -r requirements.txt
```

### 3. Initialize the database

```bash
python manage.py migrate
```

This creates the built-in application tables in `db.sqlite3` at the repository root. No separate database server is required.

### 4. Create an administrator account

```bash
python manage.py createsuperuser
```

Follow the prompts to choose your login credentials.

### 5. Start the development server

```bash
python manage.py runserver
```

Open <http://127.0.0.1:8000/> to see Django's default welcome page. Sign in at <http://127.0.0.1:8000/admin/> with the administrator account you created.

## Run with Docker

The Docker image is for local development and uses Python 3.14.8. On Windows, install [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/) and use Linux containers with the WSL 2 backend. Run these commands in PowerShell from the repository root.

Build the image:

```powershell
docker build -t sode .
```

Initialize the database:

```powershell
docker run --rm --mount "type=bind,source=${PWD},target=/app" sode python manage.py migrate
```

Create an administrator account:

```powershell
docker run --rm -it --mount "type=bind,source=${PWD},target=/app" sode python manage.py createsuperuser
```

Start the development server:

```powershell
docker run --rm -it --mount "type=bind,source=${PWD},target=/app" -p 127.0.0.1:8000:8000 sode
```

Open <http://127.0.0.1:8000/> or <http://127.0.0.1:8000/admin/>. Press Ctrl+C to stop the server.

The bind mount enables automatic reload when source files change and keeps `db.sqlite3` on the Windows host after the container exits. Docker Desktop handles access to the host files; no Linux user ID is needed. Quoting the mount argument supports project paths containing spaces. Migrations run explicitly, never during the image build. Rebuild the image after changing `requirements.txt`.

## Development commands

Run Django's configuration checks:

```bash
python manage.py check
```

Run the test suite:

```bash
python manage.py test
```

There are currently no project-specific tests or configured linting and formatting commands.

After adding or changing models in a registered application, generate and apply migrations:

```bash
python manage.py makemigrations
python manage.py migrate
```

## Project structure

```text
SODE/
├── manage.py          # Django management command entry point
└── sode/
    ├── __init__.py
    ├── settings.py    # Applications, middleware, database, and local settings
    ├── urls.py        # URL routes; currently exposes /admin/
    ├── asgi.py        # ASGI application entry point
    └── wsgi.py        # WSGI application entry point
```

Local setup also creates `venv/` and `db.sqlite3`; both are excluded from version control.

## Configuration

Project settings live in [`sode/settings.py`](sode/settings.py). The current defaults use SQLite, English (`en-us`), and UTC. Email is written to the console.

The settings are intended for local development: `DEBUG` is enabled, `ALLOWED_HOSTS` is empty, and `SECRET_KEY` is hardcoded. Before deploying, configure a private secret key, disable debug mode, set allowed hosts, and review the database, static file, and email settings. Use a production application server instead of `runserver`.

## User account email verification

Email verification is disabled by default for local development. Set
`SODE_EMAIL_VERIFICATION=true` to enable django-allauth's mandatory email
confirmation flow. The configured development backend writes confirmation
messages to the console; configure a real SMTP backend only in an environment
where email delivery is available.

Browser authentication uses django-allauth sessions, limited to 30 days.

Tailwind is compiled by `django-tailwind-cli` from `tailwind/input.css`:

```powershell
python manage.py tailwind build
```

Assistant profiles include username, name, email, location, and optional
interests. Organizer profiles additionally include organization description and
event typology.

Unverified accounts older than 30 days can be removed with:

```powershell
python manage.py delete_unverified_users
```
