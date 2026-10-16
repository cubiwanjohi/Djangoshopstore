# ShopStore

A small ecommerce site built with **Django**, containerised with **Docker Compose** (PostgreSQL, Gunicorn), and connected to Safaricom's **M-Pesa Daraja STK Push** for payments. All prices are in Kenyan shillings (KSh).

> **Status:** development / sandbox project. It is not production-ready. See [Known limitations](#known-limitations-and-roadmap).

## Contents

- [Features](#features)
- [Tech stack](#tech-stack)
- [Project structure](#project-structure)
- [Quick start: local (SQLite)](#quick-start-local-sqlite)
- [Quick start: Docker (PostgreSQL)](#quick-start-docker-postgresql)
- [Configuration](#configuration)
- [M-Pesa setup (Daraja sandbox)](#m-pesa-setup-daraja-sandbox)
- [How a payment flows](#how-a-payment-flows)
- [Data model](#data-model)
- [URLs](#urls)
- [Useful commands](#useful-commands)
- [Troubleshooting](#troubleshooting)
- [Known limitations and roadmap](#known-limitations-and-roadmap)

## Features

- Product catalogue with images, prices and stock levels
- Session-based shopping cart, limited to the stock available
- Guest checkout (no account needed) with server-side validation
- Delivery details: address, city and contact phone
- M-Pesa STK Push payment (the customer approves on their phone)
- Callback endpoint that marks orders as paid or failed
- Stock is reserved at checkout and returned if the payment fails
- Order and payment emails (printed to the console in development)
- Django admin with order items and payment shown inline, plus delivery tracking (processing, shipped, delivered)

## Tech stack

| Area | Technology |
|---|---|
| Backend | Django 6.1, Python 3.12+ (developed on 3.14, container uses 3.13) |
| Database | PostgreSQL 16 in Docker, SQLite for plain local runs |
| App server | Gunicorn (in Docker), WhiteNoise for static files |
| Payments | Safaricom Daraja API (STK Push), `requests` |
| Config | `python-dotenv` (`.env` file) |
| Images | Pillow |
| Containers | Docker, Docker Compose |
| Local tunnel | ngrok (so Safaricom can reach the callback URL) |

## Project structure

```
shopstore/
├── config/                 # Django project: settings, root URLs, WSGI
├── store/                  # The shop app
│   ├── models.py           # Product, Order, OrderItem, Payment
│   ├── views.py            # Catalogue, cart, checkout, M-Pesa callback
│   ├── mpesa.py            # Daraja client: access token + STK Push
│   ├── context_processors.py  # Cart item count for the header badge
│   ├── admin.py            # Admin configuration
│   ├── urls.py
│   ├── static/store/       # style.css
│   └── templates/store/    # HTML templates
├── media/                  # Uploaded product images (created at runtime, not committed)
├── Dockerfile
├── docker-compose.yml
├── entrypoint.sh           # Runs migrations and collectstatic, then starts Gunicorn
├── requirements.txt
├── .env.example            # Template for your .env
└── manage.py
```

## Quick start: local (SQLite)

Prerequisites: Python 3.12 or newer.

```powershell
# 1. Create and activate a virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# 2. Install dependencies
python -m pip install -r requirements.txt

# 3. Create your .env file, then edit the values (see Configuration)
Copy-Item .env.example .env

# 4. Create the database and an admin user
python manage.py migrate
python manage.py createsuperuser

# 5. Run the server
python manage.py runserver
```

Open <http://127.0.0.1:8000> for the shop and <http://127.0.0.1:8000/admin> for the admin. Add a few products in the admin first.

Local runs use SQLite because `USE_SQLITE=True` by default.

## Quick start: Docker (PostgreSQL)

Prerequisites: Docker Desktop, running (wait for "Engine running").

```powershell
# 1. Create your .env file and edit the values
Copy-Item .env.example .env

# 2. Build and start the web and database containers
docker-compose up -d --build

# 3. Check that db is "healthy" and web is "Up"
docker-compose ps

# 4. Create an admin user (migrations are applied automatically on start)
docker-compose exec web python manage.py createsuperuser
```

Open <http://127.0.0.1:8000>. Use `127.0.0.1` or `localhost`. The address `0.0.0.0` that Docker prints is not a browsable address.

How the Docker setup works:

- `docker-compose.yml` forces `USE_SQLITE=False` and `POSTGRES_HOST=db` for the web container, so it uses PostgreSQL whatever your `.env` says.
- The web container starts through `entrypoint.sh`, which applies database migrations and collects static files, then starts Gunicorn.
- Static files are served by WhiteNoise. Uploaded media is served by Django only while `DEBUG=True`.
- The project folder is bind-mounted into the container (`.:/app`), so the container runs your working copy. Gunicorn does not auto-reload, so run `docker-compose restart web` after changing Python code or templates.
- `entrypoint.sh` is copied into the image at build time. After editing it, rebuild with `docker-compose up -d --build`.
- Your `.env` is excluded from the image by `.dockerignore` and injected at runtime, so secrets are never baked into the image.
- Data lives in the `pgdata` Docker volume and survives `docker-compose down`.

## Configuration

All settings come from `.env`. Copy `.env.example` and fill it in. **Never commit `.env`.**

| Variable | Purpose | Example / notes |
|---|---|---|
| `SECRET_KEY` | Django secret key (required) | Generate one, see below |
| `DEBUG` | Debug mode | `True` for development |
| `ALLOWED_HOSTS` | Comma-separated hosts Django accepts | `127.0.0.1,localhost,your-tunnel-domain.ngrok-free.dev` |
| `USE_SQLITE` | `True` = SQLite, `False` = PostgreSQL | Docker overrides to `False` |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | Database credentials, also used by the `db` container | |
| `POSTGRES_HOST` / `POSTGRES_PORT` | Database address | `db` / `5432` in Docker |
| `MPESA_CONSUMER_KEY` / `MPESA_CONSUMER_SECRET` | Daraja app credentials | From the Daraja portal |
| `MPESA_SHORTCODE` | Business shortcode | `174379` in the sandbox |
| `MPESA_PASSKEY` | STK Push passkey | Sandbox value from the Daraja portal |
| `MPESA_CALLBACK_URL` | Public URL Safaricom posts results to | `https://<tunnel-domain>/mpesa/callback/` |
| `MPESA_BASE_URL` | Daraja API base URL | `https://sandbox.safaricom.co.ke` |

Generate a secret key:

```powershell
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

If the key contains `$` or `#`, wrap it in single quotes in `.env` (`SECRET_KEY='...'`), otherwise Docker Compose can cut it short.

`.env` is read once at startup. After editing it, restart the server, or for Docker run `docker-compose up -d --force-recreate web`.

## M-Pesa setup (Daraja sandbox)

1. Register at the [Safaricom Developer Portal](https://developer.safaricom.co.ke) and create a **sandbox app** with the **Lipa Na M-Pesa Sandbox** product enabled.
2. Copy the app's **Consumer Key** and **Consumer Secret**, and the sandbox **passkey** shown on the portal's test credentials page, into `.env`.
3. Safaricom must reach your callback over the internet, so expose your local server with [ngrok](https://ngrok.com/download):
   ```powershell
   ngrok http 8000
   ```
4. Copy the `https://...` forwarding domain ngrok prints, then in `.env`:
   - add the domain to `ALLOWED_HOSTS`
   - set `MPESA_CALLBACK_URL=https://<domain>/mpesa/callback/`
5. Restart the app. Keep ngrok running while you test. On the free plan the domain can change between sessions, so repeat steps 4 and 5 if it does.

### Testing payments safely

- Use Safaricom's sandbox test number `254708374149` for checkout tests.
- Sending an STK prompt to a real Safaricom line can move real money, even in the sandbox. Small deductions have been observed, so avoid it unless you intend to test with a live line.
- To test the paid and failed paths without spending anything, simulate Safaricom's callback. Copy the order's `transaction_id` from its Payment section in the admin, then:

```powershell
$body = @{
  Body = @{
    stkCallback = @{
      MerchantRequestID = "test-123"
      CheckoutRequestID = "PASTE_THE_TRANSACTION_ID_HERE"
      ResultCode = 0        # 0 = success; use 1032 to simulate a cancelled payment
      ResultDesc = "The service request is processed successfully."
    }
  }
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Uri http://localhost:8000/mpesa/callback/ -Method Post -Body $body -ContentType "application/json"
```

The order should change to **Paid** in the admin (or the payment to **failed**, with the stock returned).

## How a payment flows

1. The customer adds products to the cart and submits the checkout form.
2. The server validates the input, then, in one database transaction, locks the products, checks stock, creates the order and its items, reduces stock and creates a `pending` payment.
3. The server asks Safaricom to send an STK Push prompt to the customer's phone and stores the returned `CheckoutRequestID` on the payment.
4. If Safaricom rejects the request, the payment is marked `failed` and the stock is returned.
5. The customer enters their M-Pesa PIN on their phone.
6. Safaricom posts the result to `/mpesa/callback/`:
   - success: payment `completed`, order `paid`, confirmation email sent
   - failure or cancellation: payment `failed`, stock returned
7. A payment that is no longer `pending` ignores repeated callbacks.

## Data model

| Model | Key fields |
|---|---|
| `Product` | name, description, price, stock, image |
| `Order` | customer name and email, shipping address/city/phone, `status` (pending, paid), `delivery_status` (processing, shipped, delivered) |
| `OrderItem` | order, product, quantity, price at time of purchase |
| `Payment` | one per order: method (`mpesa`), status (pending, completed, failed), amount, M-Pesa phone, transaction ID |

## URLs

| Path | Description |
|---|---|
| `/` | Product list |
| `/product/<id>/` | Product detail |
| `/cart/add/<id>/` | Add to cart (POST only) |
| `/cart/` | View the cart |
| `/checkout/` | Checkout form and order placement |
| `/mpesa/callback/` | Safaricom payment callback (POST only) |
| `/admin/` | Django admin |

## Useful commands

```powershell
docker-compose up -d                    # start
docker-compose up -d --build            # rebuild after changing the Dockerfile, entrypoint.sh or requirements.txt
docker-compose restart web              # reload after changing Python code or templates
docker-compose down                     # stop, keep data
docker-compose down -v                  # stop and WIPE the database
docker-compose logs -f web              # follow Django logs (emails print here)
docker-compose exec web python manage.py createsuperuser
docker-compose exec web python manage.py makemigrations
docker-compose exec web python manage.py collectstatic --noinput
docker-compose config                   # validate docker-compose.yml
```

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `failed to connect to the docker API` | Docker Desktop is not running. Start it and wait for "Engine running". |
| `no configuration file provided: not found` | Run the command from the folder that contains `docker-compose.yml`. |
| Container exits at once, logs show `exec /entrypoint.sh: no such file or directory` | `entrypoint.sh` has Windows (CRLF) line endings. Save it with LF (VS Code status bar: click `CRLF`, choose `LF`) and rebuild. The repository's `.gitattributes` keeps it LF on clone. |
| Container exits at once, logs show a `SyntaxError` or `ImportError` | A Python error in the code. The last lines of `docker-compose logs --tail=50 web` name the file and line. |
| Code or template changes do not show up | Gunicorn does not auto-reload. Run `docker-compose restart web`. |
| Pages load without styling in Docker | Run `docker-compose exec web python manage.py collectstatic --noinput`, then `docker-compose restart web`. |
| `yaml: ... found character that cannot start any token` | The file has a hidden BOM or a stray ` ``` ` line. Recreate it with ASCII encoding (`Out-File -Encoding ascii`). |
| `ERR_ADDRESS_INVALID` for `http://0.0.0.0:8000` | Browse to `http://127.0.0.1:8000` instead. |
| ngrok shows `400 Bad Request` for `/mpesa/callback/` | The tunnel domain is missing from `ALLOWED_HOSTS`. Add it and restart. |
| Order stays `Pending` after payment | The callback did not arrive or the payment failed. Check `http://127.0.0.1:4040` (ngrok inspector) and the payment status in the admin. |
| `could not translate host name "db"` | You ran a management command on your machine, not in the container. Use `docker-compose exec web ...`, or run locally with `USE_SQLITE=True`. |
| `ImageField ... Pillow is not installed` | Install requirements again and rebuild the image. |

## Known limitations and roadmap

- **Callback is not verified.** The callback endpoint trusts the posted payload. Before taking real money, confirm payments with Safaricom's STK Push Query API and restrict callback sources.
- **Sandbox only.** Going live needs a production Daraja app, a real shortcode and passkey, and a permanent HTTPS domain.
- **No customer accounts.** Checkout is guest-only, so there is no order history yet.
- **Development-style Docker setup.** The container runs Gunicorn with `DEBUG=True` and a bind-mounted source folder. For production, set `DEBUG=False` with a strict `ALLOWED_HOSTS`, remove the bind mount, and put a reverse proxy with HTTPS in front.
- **Uploaded images need a real file server in production.** Django only serves `/media/` while `DEBUG=True`. With `DEBUG=False`, serve media from Nginx or object storage.
- **Emails go to the console.** Configure a real SMTP backend for production.
- **Whole shillings only.** M-Pesa takes whole-shilling amounts, so price products without cents.

Possible next steps: removing items and changing quantities in the cart, customer accounts and order history, an order tracking page, automated tests, a GitHub Actions CI pipeline that builds the image, and deployment to a cloud host.