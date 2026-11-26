
# ShopStore

A Django-based e-commerce and inventory management platform built using a **modular monolith architecture**. ShopStore brings together product browsing, customer accounts, order processing, inventory control, M-Pesa payments, product reviews and customer notifications in one Django project.

The project is designed to demonstrate practical backend engineering, database management, payment integration, automated testing and containerized deployment.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Technology Stack](#technology-stack)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Environment Configuration](#environment-configuration)
- [Running with Docker](#running-with-docker)
- [Database Migrations](#database-migrations)
- [Testing](#testing)
- [M-Pesa Integration](#m-pesa-integration)
- [Payment Status Verification](#payment-status-verification)
- [Cloudinary Media Storage](#cloudinary-media-storage)
- [Email Notifications](#email-notifications)
- [Static Files](#static-files)
- [Deployment](#deployment)
- [Security Considerations](#security-considerations)
- [Current Limitations and Future Improvements](#current-limitations-and-future-improvements)

## Overview

ShopStore is an e-commerce application developed with Django. It combines customer-facing shopping functionality with administrative inventory and order-management capabilities.

The application follows a modular monolith architecture: individual Django applications handle separate business responsibilities while sharing one Django project and database.

This approach keeps the system organized without introducing the operational complexity of independently deployed microservices.

## Features

### Storefront

- Product catalogue and product detail pages.
- Shopping cart and checkout.
- Product images.
- Order creation and order confirmation.
- Stock reservation and restoration during relevant order and payment flows.

### Customer Management

- Customer registration.
- Login and logout.
- Customer dashboard.
- Customer order history.
- Individual order details.
- Ownership checks to prevent customers from accessing other customers' orders.

### Inventory Management

- Staff-only inventory dashboard.
- Stock receiving and stock removal.
- Inventory movement history.
- Product-specific stock history.
- Low-stock monitoring.
- Inventory reports.
- CSV inventory export.

### Order Management

- Order processing and fulfilment functionality.
- Order status management.
- Delivery status tracking.
- Order history and related records.

### Payment Processing

- Safaricom Daraja M-Pesa STK Push integration.
- STK Push transaction querying.
- M-Pesa callback handling.
- Payment status validation.
- Payment confirmation and failure handling.
- Stock restoration following relevant failed payments.
- Payment status endpoint for the order confirmation page.

### Product Reviews

- Product ratings from 1 to 5.
- Reviews restricted to customers with qualifying paid purchases.
- One review per customer per product.
- Review editing and deletion by the review owner.
- Product average ratings.

### Customer Notifications

- Order confirmation emails.
- Payment confirmation emails.
- Shipping notifications.
- Delivery notifications.
- Error handling so email delivery failures do not unnecessarily interrupt order processing.

## Technology Stack

| Component | Technology |
|---|---|
| Backend | Python 3.14 |
| Web framework | Django 6.1.3 |
| Database | PostgreSQL 16 |
| Local development database | SQLite |
| API and payment requests | Requests |
| Payment gateway | Safaricom Daraja API |
| Media storage | Cloudinary |
| Static file handling | WhiteNoise |
| Application server | Gunicorn |
| Containerization | Docker |
| Container orchestration | Docker Compose |
| Image processing | Pillow |
| Database driver | psycopg2-binary |

Dependencies are pinned in `requirements.txt`.

## Architecture

ShopStore uses a modular monolith architecture.

Each Django application owns a specific business responsibility. The applications run within the same Django project and use a shared database.

### Django applications

| Application | Responsibility |
|---|---|
| `store` | Product catalogue, shopping cart, checkout and storefront |
| `customers` | Customer registration, authentication, dashboard and order history |
| `inventory` | Stock adjustments, inventory history, reports and CSV exports |
| `orders` | Order fulfilment and delivery management |
| `payments` | M-Pesa integration, payment callbacks and payment status |
| `notifications` | Customer notification email services |
| `reviews` | Product ratings and verified-purchase reviews |
| `config` | Django project settings, URL configuration and storage integration |

### Database design

The applications share one database rather than maintaining separate databases for each business module.

Core commerce models, including `Product`, `Order`, `OrderItem` and `Payment`, currently reside in `store/models.py`.

This keeps the application deployable as one Django service while allowing business responsibilities to be separated into individual apps.

## Project Structure

The following is a simplified view of the project:

```text
shopstore/
│
├── config/
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── cloudinary_storage.py
│
├── customers/
│   ├── views.py
│   ├── urls.py
│   └── test_orders.py
│
├── inventory/
│   ├── views.py
│   └── urls.py
│
├── orders/
│   ├── views.py
│   └── urls.py
│
├── payments/
│   ├── services/
│   │   └── mpesa.py
│   ├── views.py
│   ├── urls.py
│   ├── test_mpesa.py
│   ├── test_status.py
│   └── test_timestamp.py
│
├── notifications/
│   ├── services.py
│   └── tests.py
│
├── reviews/
│   ├── views.py
│   ├── models.py
│   └── urls.py
│
├── store/
│   ├── templates/
│   │   └── store/
│   ├── static/
│   │   └── store/
│   ├── models.py
│   ├── views.py
│   ├── urls.py
│   ├── tests.py
│   └── test_shop_flow.py
│
├── .github/
│   └── workflows/
│       └── ci.yml
│
├── Dockerfile
├── docker-compose.yml
├── entrypoint.sh
├── requirements.txt
├── .env.example
├── .gitignore
└── manage.py
```

The tree is representative; individual applications also contain their migrations, configuration and supporting files.

## Getting Started

### Prerequisites

Install the following:

- Python 3.14
- Git
- Docker Desktop (for Docker-based development)
- A Cloudinary account if using Cloudinary media uploads.
- Safaricom Daraja Sandbox credentials if testing M-Pesa.

### 1. Clone the repository

```powershell
git clone https://github.com/cubiwanjohi/Djangoshopstore.git
cd Djangoshopstore
```

### 2. Create a virtual environment

On Windows PowerShell:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

On Linux:

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure environment variables

Copy the example configuration:

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Linux:

```bash
cp .env.example .env
```

Update `.env` with your own development configuration and credentials.

Never commit `.env` to Git.

### 5. Run database migrations

For local SQLite development, ensure:

```env
USE_SQLITE=True
```

Then run:

```bash
python manage.py migrate
```

### 6. Create an administrator

```bash
python manage.py createsuperuser
```

### 7. Start the development server

```bash
python manage.py runserver
```

Open:

```text
http://127.0.0.1:8000/
```

Django administration:

```text
http://127.0.0.1:8000/admin/
```

## Environment Configuration

ShopStore reads configuration from environment variables.

The `.env.example` file provides the configuration template.

Important variables include:

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | Django secret key |
| `DEBUG` | Enables or disables Django debug mode |
| `ALLOWED_HOSTS` | Permitted hostnames |
| `USE_SQLITE` | Selects SQLite or PostgreSQL |
| `POSTGRES_DB` | PostgreSQL database name |
| `POSTGRES_USER` | PostgreSQL username |
| `POSTGRES_PASSWORD` | PostgreSQL password |
| `POSTGRES_HOST` | PostgreSQL hostname |
| `POSTGRES_PORT` | PostgreSQL port |
| `MPESA_CONSUMER_KEY` | Daraja consumer key |
| `MPESA_CONSUMER_SECRET` | Daraja consumer secret |
| `MPESA_SHORTCODE` | Daraja business shortcode |
| `MPESA_PASSKEY` | Daraja passkey |
| `MPESA_CALLBACK_URL` | Publicly accessible callback URL |
| `MPESA_BASE_URL` | Daraja API base URL |
| `CLOUDINARY_URL` | Cloudinary connection URL |
| `EMAIL_BACKEND` | Django email backend |
| `EMAIL_HOST` | SMTP server |
| `EMAIL_PORT` | SMTP port |
| `EMAIL_HOST_USER` | SMTP username |
| `EMAIL_HOST_PASSWORD` | SMTP password |
| `DEFAULT_FROM_EMAIL` | Default sender address |

Generate a Django secret key with:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

For local development, the example uses SQLite.

For Docker Compose, PostgreSQL is selected automatically through the Compose environment configuration.

## Running with Docker

Docker Compose runs the Django application and PostgreSQL database.

### 1. Configure environment variables

Make sure `.env` exists and contains valid PostgreSQL credentials.

For Docker Compose, the example uses:

```env
USE_SQLITE=False
POSTGRES_DB=shopdb
POSTGRES_USER=shopuser
POSTGRES_PASSWORD=your-secure-password
POSTGRES_HOST=db
POSTGRES_PORT=5432
```

Use your own secure password.

### 2. Build and start the services

```powershell
docker compose up --build -d
```

### 3. Check running containers

```powershell
docker compose ps
```

### 4. View application logs

```powershell
docker compose logs -f web
```

### 5. Open the application

```text
http://localhost:8000/
```

### 6. Run Django management commands

Create a superuser:

```powershell
docker compose exec web python manage.py createsuperuser
```

Run migrations:

```powershell
docker compose exec web python manage.py migrate
```

The web container runs `entrypoint.sh`, which applies migrations and collects static files when Gunicorn starts.

The PostgreSQL data is stored in the persistent Docker volume named `pgdata`.

Stopping containers does not require deleting the database volume:

```powershell
docker compose down
```

Do not use `docker compose down -v` unless you intentionally want to delete the persistent database volume and its data.

## Database Migrations

After changing Django models, generate migrations:

```bash
python manage.py makemigrations
```

Apply migrations:

```bash
python manage.py migrate
```

Check whether model changes are missing migrations:

```bash
python manage.py makemigrations --check --dry-run
```

For Docker:

```powershell
docker compose exec web python manage.py makemigrations
docker compose exec web python manage.py migrate
```

## Testing

ShopStore includes automated tests for storefront workflows, customers, payments, inventory-related functionality, reviews and notifications.

Run the complete test suite locally:

```powershell
python manage.py test --verbosity 2
```

Run the complete test suite using Docker and PostgreSQL:

```powershell
docker compose run --rm web python manage.py test --verbosity 2
```

Run Django system checks:

```powershell
python manage.py check
```

Check for missing migrations:

```powershell
python manage.py makemigrations --check --dry-run
```

Check Git whitespace errors:

```powershell
git diff --check
```

### Latest validated test result

The latest recorded full test run completed successfully:

```text
Ran 178 tests
OK
```

The 178-test suite passed locally and in Docker using PostgreSQL 16.

This is a record of the latest validated run, not a guarantee that future changes will pass.

**Important:** M-Pesa network requests are mocked in automated tests. Passing the tests does not establish that a live Safaricom transaction will succeed.

## M-Pesa Integration

ShopStore integrates with Safaricom Daraja for M-Pesa STK Push payments.

The payment service is located at:

```text
payments/services/mpesa.py
```

The implementation includes:

1. Daraja access-token generation.
2. STK Push request construction.
3. East Africa Time timestamp generation.
4. Daraja password generation.
5. STK Push transaction querying.
6. HTTP response and error handling.

### STK Push flow

```text
Customer
   |
   v
ShopStore Checkout
   |
   v
Create Order and Payment
   |
   v
Request Daraja Access Token
   |
   v
Send STK Push Request
   |
   v
Customer Receives M-Pesa Prompt
   |
   v
Safaricom Processes Payment
   |
   v
M-Pesa Callback
   |
   v
Query Transaction for Verification
   |
   v
Update Payment and Order
   |
   v
Notify Customer
```

### Sandbox configuration

The example environment uses:

```env
MPESA_BASE_URL=https://sandbox.safaricom.co.ke
```

Configure valid Daraja Sandbox credentials before testing.

The callback URL must be publicly reachable by Safaricom. During local development, a secure tunnelling service can expose the local callback endpoint.

The callback endpoint is:

```text
/mpesa/callback/
```

The application uses transaction querying to verify callback details before applying payment changes.

A failed or inconclusive verification does not automatically mark an order as paid.

## Payment Status Verification

The application provides a signed payment-status endpoint:

```text
/status/<token>/
```

The order confirmation page polls this endpoint periodically to display the current payment state.

The endpoint:

- Accepts GET requests.
- Validates signed tokens.
- Rejects invalid or malformed tokens.
- Returns the payment status as JSON.
- Uses a maximum token age of 24 hours.
- Sets `Cache-Control: no-store`.

The token acts as a bearer link. Anyone who obtains it may access the associated payment status until it expires. Avoid exposing these URLs in logs, analytics or external systems.

## Cloudinary Media Storage

ShopStore includes a custom Cloudinary storage backend:

```text
config/cloudinary_storage.py
```

The Django default storage configuration uses:

```python
"BACKEND": "config.cloudinary_storage.CloudinaryMediaStorage"
```

The example environment variable is:

```env
CLOUDINARY_URL=cloudinary://<api_key>:<api_secret>@<cloud_name>
```

Replace the placeholders with credentials from your Cloudinary account.

Do not commit Cloudinary credentials to Git.

Cloudinary is used for uploaded media, while WhiteNoise handles collected static files.

## Email Notifications

Customer notification services are implemented in:

```text
notifications/services.py
```

The notification service supports:

- Order confirmation.
- Payment confirmation.
- Shipping updates.
- Delivery updates.

The default development email backend writes email messages to the console:

```env
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
```

For actual email delivery, configure an SMTP provider or another supported Django email backend.

Automated tests use Django's in-memory email backend and do not prove that external email delivery is configured.

## Static Files

ShopStore uses WhiteNoise for static file handling.

The configured static paths include:

```python
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
```

The static files storage backend is:

```python
"whitenoise.storage.CompressedManifestStaticFilesStorage"
```

Collect static files with:

```bash
python manage.py collectstatic --noinput
```

The Docker entrypoint automatically collects static files when starting Gunicorn.

## Deployment

The project includes Docker-based deployment configuration and a Gunicorn application server.

The Docker image:

- Uses Python 3.14 slim.
- Installs the application dependencies.
- Copies the application source.
- Uses `entrypoint.sh` to prepare the application.
- Starts Gunicorn using `config.wsgi:application`.

The entrypoint runs:

```bash
python manage.py migrate --noinput
python manage.py collectstatic --noinput
```

It then starts Gunicorn using the assigned `PORT`, falling back to port `8000`.

For Railway or another hosting provider, configure the required environment variables in the hosting dashboard.

Before deploying a public production environment:

- Set `DEBUG=False`.
- Configure `ALLOWED_HOSTS`.
- Configure trusted CSRF origins.
- Use a secure Django secret key.
- Configure production PostgreSQL credentials.
- Configure a production email provider.
- Configure Cloudinary credentials.
- Configure the appropriate Daraja API environment.
- Ensure the M-Pesa callback URL is publicly reachable over HTTPS.

The current Daraja example configuration points to the Sandbox environment. Sandbox testing must not be treated as proof of production payment readiness.

## Security Considerations

The project includes several security-related controls:

- Django authentication for customer functionality.
- Customer order ownership checks.
- Staff access checks for inventory management.
- CSRF protection through Django's standard mechanisms.
- Signed payment-status tokens.
- Payment callback verification using Daraja transaction queries.
- Database transactions for sensitive payment updates.
- Payment status checks to handle duplicate callbacks.
- Review ownership restrictions.
- Review eligibility checks against paid orders.
- Environment-based configuration for secrets.

Further production hardening should include a comprehensive deployment security review, payment reconciliation procedures, monitoring, backups and operational alerting.

## Current Limitations and Future Improvements

Potential next development areas include:

- Production Daraja integration and end-to-end payment testing.
- Automated reconciliation for payments that remain pending.
- Stronger payment callback monitoring and operational alerting.
- More comprehensive inventory permissions and audit reporting.
- Additional order fulfilment workflows.
- Improved reporting and business analytics.
- Expanded integration and deployment testing.
- Production database backup and recovery procedures.
- Performance monitoring and structured logging.

## Author

**Peter Cubi Wanjohi**

Backend Software Engineer | Django | Python | PostgreSQL | Docker

GitHub: [cubiwanjohi](https://github.com/cubiwanjohi)

Repository: [Djangoshopstore](https://github.com/cubiwanjohi/Djangoshopstore)
