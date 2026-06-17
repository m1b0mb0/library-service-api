# Library Service API

DRF API for managing a small library service: books inventory, user accounts,
book borrowings, returns, filtering, and Telegram notifications for newly
created borrowings.

## Features

- JWT authentication with email-based users.
- Book CRUD API.
- Book write permissions: only staff users can create, update, or delete books.
- Borrowing list and detail API.
- Borrowing creation with automatic book inventory decrement.
- Borrowing return endpoint with automatic book inventory increment.
- Borrowing filtering by active status.
- Admin borrowing filtering by user.
- Telegram notification on new borrowing creation.

## Tech Stack

- Python
- Django
- Django REST Framework
- Simple JWT
- PostgreSQL
- Docker
- Docker Compose
- python-dotenv
- python-telegram-bot

## Setup

Create `.env` from the sample:

```powershell
copy .env.sample .env
```

Configure PostgreSQL and Telegram credentials in `.env`:

```env
POSTGRES_DB=library_service
POSTGRES_PORT=5432
POSTGRES_USER=library_user
POSTGRES_PASSWORD=library_password
POSTGRES_HOST=db
PGDATA=/var/lib/postgresql/data
TELEGRAM_BOT_TOKEN=your_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

Use `POSTGRES_HOST=db` when running with Docker Compose. For local setup, use
your local database host, for example `POSTGRES_HOST=localhost`.

### Docker Setup

Build and start the containers:

```powershell
docker compose up --build
```

The API will be available at:

```http
http://127.0.0.1:8000/
```

The web container waits for PostgreSQL, applies migrations, and then starts the
Django development server.

Stop containers:

```powershell
docker compose down
```

Stop containers and remove the database volume:

```powershell
docker compose down -v
```

### Local Setup

Create and activate a virtual environment:

```powershell
python -m venv .venv
.venv\Scripts\activate
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

For local setup, make sure PostgreSQL is installed and running before applying
migrations.

Apply migrations:

```powershell
python manage.py migrate
```

Run the development server:

```powershell
python manage.py runserver
```

## Authentication

Use JWT access tokens in the `Authorization` header:

```http
Authorization: Bearer <access_token>
```

## API Endpoints

### Users

| Method | Endpoint | Description |
| --- | --- | --- |
| `POST` | `/users/` | Register a new user |
| `POST` | `/users/token/` | Get JWT access and refresh tokens |
| `POST` | `/users/token/refresh/` | Refresh JWT access token |
| `GET` | `/users/me/` | Get current user profile |
| `PUT/PATCH` | `/users/me/` | Update current user profile |

User fields:

- `id`
- `email`
- `first_name`
- `last_name`
- `password`
- `is_staff` read-only

### Books

| Method | Endpoint | Description | Access |
| --- | --- | --- | --- |
| `GET` | `/books/` | List books | Public |
| `GET` | `/books/{id}/` | Retrieve book detail | Public |
| `POST` | `/books/` | Create book | Staff only |
| `PUT/PATCH` | `/books/{id}/` | Update book | Staff only |
| `DELETE` | `/books/{id}/` | Delete book | Staff only |

Book fields:

- `id`
- `title`
- `author`
- `cover`: `HARD` or `SOFT`
- `inventory`
- `daily_fee`

### Borrowings

All borrowing endpoints require authentication.

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/borrowings/` | List borrowings |
| `GET` | `/borrowings/{id}/` | Retrieve borrowing detail |
| `POST` | `/borrowings/` | Create borrowing |
| `POST` | `/borrowings/{id}/return/` | Return borrowed book |

Regular users can see only their own borrowings. Staff users can see all
borrowings and receive user information in borrowing responses.

Borrowing creation accepts:

- `book`
- `expected_return_date`

On successful creation:

- the current user is attached to the borrowing;
- the selected book inventory is decreased by 1;
- a Telegram notification is sent after the database transaction commits.

Returning a borrowing:

- sets `actual_return_date` to the current date;
- increases the book inventory by 1;
- prevents returning the same borrowing twice.

#### Borrowing Filters

`GET /borrowings/?is_active=true`

Returns active borrowings where `actual_return_date` is `null`.

`GET /borrowings/?is_active=false`

Returns returned borrowings where `actual_return_date` is set.

`GET /borrowings/?user_id=<id>`

Available for staff users. Returns borrowings for a specific user.

Filters can be combined:

```http
GET /borrowings/?user_id=1&is_active=true
```

## Telegram Notifications

The project sends a Telegram message when a new borrowing is created.

Required environment variables:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

The message includes:

- borrowing ID;
- user email;
- book title;
- borrow date;
- expected return date.

## Running Tests

With local Python:

```powershell
python manage.py test
```

Inside Docker:

```powershell
docker compose run --rm library-service python manage.py test
```
