# ProfiFlow Backend

## Getting Started

1. Clone the repository
2. Install dependencies with `pip install -r requirements.txt`
3. Set up environment variables
4. Apply migrations `alembic upgrade head`
5. Run the application with `uvicorn app.main:app --reload`

## API Endpoints

The API is organized around the following resources:

- `/api/v1/auth`: Authentication endpoints
- `/api/v1/reports`: Sprint and team report generation
- `/api/v1/trackers`: Yandex Tracker integration
- `/api/v1/profile`: User profile management
- `/api/v1/users`: User administration
- `/api/v1/health`: System health check

## To create reports

1. POST `/api/v1/trackers` Create tracker
2. GET `/api/v1/users` Get tracker users list
3. POST `/api/v1/users/{user_id}/role` Update user roles
4. GET `/api/v1/reports/sprints` Get sprint lists
5. POST `/api/v1/reports/team` Generate team report

## Database Migrations

We use Alembic for database migrations:

- Initialize migrations: `alembic init migrations`
- Create a new migration: `alembic revision --autogenerate -m "description"`
- Apply migrations: `alembic upgrade head`
- Rollback migration: `alembic downgrade -1`
- View migration history: `alembic history`
- Get current version: `alembic current`

## Development

- Code formatting is enforced with Ruff
- CI/CD pipeline is configured with GitHub Actions

