# Bodhrik Backend Assessment (Full Stack Engineer)

This repository contains a FastAPI-based backend service designed to model the core components of an educational platform, including Users, Students, Sessions, and Evaluations. It enforces strict, data-aware Role-Based Access Control (RBAC), integrates Redis for read-caching and background task queuing (via Celery), and is fully dockerized.

---

## 🛠 Tech Stack & Architecture

-   **Backend Framework**: FastAPI (Python 3.11)
-   **Database**: Supabase / PostgreSQL (managed using SQLAlchemy ORM)
-   **Task Queue & Cache**: Redis (Celery background worker for asynchronous evaluations + `redis-py` for caching)
-   **Containerization**: Docker & Docker Compose
-   **CI/CD**: GitHub Actions (running `black`, `flake8`, and `pytest` suite)

```
                     ┌──────────────────┐
                     │   FastAPI Client │
                     └────────┬─────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
       ┌─────────────┐                 ┌─────────────┐
       │ Redis Cache │                 │ Postgres DB │ (Supabase)
       └─────────────┘                 └──────▲──────┘
                                              │
              ┌─────────────┐                 │
              │ Redis Queue ├─────────────────┘
              └──────┬──────┘ (Updates evaluation status)
                     │
                     ▼
             ┌──────────────┐
             │ Celery Worker│ (Simulates LLM evaluation)
             └──────────────┘
```

---

## 🚀 Setup & Execution

### Prerequisites
Make sure you have the following installed:
-   [Docker Desktop](https://www.docker.com/products/docker-desktop/) (includes Docker Compose)
-   [Python 3.11](https://www.python.org/downloads/) (optional, for local non-Docker development and testing)

### Step 1: Clone and Set Up Environments
Create your local environment file by copying the example environment:
```bash
cp .env.example .env
```

*By default, the `.env` is configured to run with a local fallback PostgreSQL container. If you wish to connect directly to your remote **Supabase** database, update the `DATABASE_URL` in `.env` to your Supabase Postgres connection string.*

### Step 2: Spin Up the Docker Environment
Run the following command to build the images and launch the entire stack:
```bash
docker-compose up --build
```
This spins up four services:
1.  **bodhrik_db**: Fallback local Postgres database (port `5432`).
2.  **bodhrik_redis**: Redis instance used for cache and message queuing (port `6379`).
3.  **bodhrik_api**: FastAPI web server (port `8000`).
4.  **bodhrik_worker**: Celery worker instance processing evaluations.

Once running, the interactive API documentation will be available at:  
👉 **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)

### Step 3: Seed Database with Test Data
To easily verify RBAC and check endpoints, execute a `POST` request to the seed endpoint. This will reset the database and create a set of mock users, students, and sessions:
```bash
curl -X POST http://localhost:8000/auth/seed
```
This seeds the database with the following accounts:
-   **Admin**: `admin@bodhrik.com` (password: `password123`)
-   **Teacher 1**: `teacher1@bodhrik.com` (password: `password123`)
-   **Teacher 2**: `teacher2@bodhrik.com` (password: `password123`)
-   **Parent 1**: `parent1@bodhrik.com` (password: `password123`) — *Child: Student John & Jane*
-   **Parent 2**: `parent2@bodhrik.com` (password: `password123`) — *Child: Student Bob*

---

## 🔒 Role-Based Access Control (RBAC) Rules

The application enforces strict data-level access policies:
1.  **Admin**: Can perform full CRUD on all sessions, get any evaluation, and trigger evaluations.
2.  **Teacher**:
    -   Can only read, create, update, or delete sessions where they are the assigned `teacher_id`.
    -   Cannot read sessions assigned to other teachers.
    -   Can trigger evaluations for their own sessions.
3.  **Parent**:
    -   Can only read (`GET`) sessions that belong to their children (linked via the `Student` relationship).
    -   Cannot modify any sessions or access sessions of unrelated students.
    -   Cannot trigger evaluation jobs.

---

## 📝 API Endpoints Summary

### Authentication
-   `POST /auth/register`: Create a new user account.
-   `POST /auth/token`: Authenticate and obtain JWT token (Form Data: `username`, `password`).
-   `POST /auth/seed`: Populates DB with clean mock data.

### Sessions (CRUD with RBAC & Cache)
-   `GET /sessions`: Retrieve all sessions (automatically filtered based on user role).
-   `POST /sessions`: Create a session (restricted to teachers/admins).
-   `GET /sessions/{id}`: Retrieve a specific session (checks cache first, enforces RBAC).
-   `PUT /sessions/{id}`: Update session details (invalidates cache).
-   `DELETE /sessions/{id}`: Delete a session (invalidates cache).

### Evaluations
-   `POST /evaluations/trigger`: Trigger background evaluation job for a session (enqueues Celery task).
-   `GET /evaluations/{id}`: Check the processing status and results of an evaluation.

---

## 🧪 Running Tests & Linting

### Local Testing (Non-Docker)
Create a Python virtual environment and run the test suite:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
pip install -r requirements.txt
pytest
```

### Running Linter
Verify code formatting standards:
```bash
black --check . --exclude venv
flake8 . --exclude venv
```
