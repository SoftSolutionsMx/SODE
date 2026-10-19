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

The existing development environment uses Python 3.14.8. The repository does not yet include a dependency manifest or lockfile.

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
python -m pip install "Django==6.1.2"
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

