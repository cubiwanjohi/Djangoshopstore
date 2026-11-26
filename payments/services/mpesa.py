
import base64
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from django.conf import settings


EAT = ZoneInfo("Africa/Nairobi")


def generate_timestamp():
    """Generate a Daraja timestamp in East Africa Time."""
    return datetime.now(EAT).strftime("%Y%m%d%H%M%S")


def generate_password(timestamp):
    """Generate the Daraja Base64 password."""
    raw_password = (
        f"{settings.MPESA_SHORTCODE}"
        f"{settings.MPESA_PASSKEY}"
        f"{timestamp}"
    )

    return base64.b64encode(
        raw_password.encode("utf-8")
    ).decode("utf-8")


def get_access_token():
    url = (
        f"{settings.MPESA_BASE_URL}"
        "/oauth/v1/generate?grant_type=client_credentials"
    )

    response = requests.get(
        url,
        auth=(
            settings.MPESA_CONSUMER_KEY,
            settings.MPESA_CONSUMER_SECRET,
        ),
        timeout=30,
    )

    response.raise_for_status()
    return response.json()["access_token"]


def stk_push(phone_number, amount, account_reference, transaction_desc):
    access_token = get_access_token()

    timestamp = generate_timestamp()
    password = generate_password(timestamp)

    url = (
        f"{settings.MPESA_BASE_URL}"
        "/mpesa/stkpush/v1/processrequest"
    )

    headers = {
        "Authorization": f"Bearer {access_token}",
    }

    payload = {
        "BusinessShortCode": settings.MPESA_SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": int(amount),
        "PartyA": phone_number,
        "PartyB": settings.MPESA_SHORTCODE,
        "PhoneNumber": phone_number,
        "CallBackURL": settings.MPESA_CALLBACK_URL,
        "AccountReference": account_reference,
        "TransactionDesc": transaction_desc,
    }

    response = requests.post(
        url,
        json=payload,
        headers=headers,
        timeout=30,
    )

    response.raise_for_status()
    return response.json()


def stk_push_query(checkout_request_id):
    """Query an STK Push transaction using its CheckoutRequestID."""

    access_token = get_access_token()

    timestamp = generate_timestamp()
    password = generate_password(timestamp)

    url = (
        f"{settings.MPESA_BASE_URL}"
        "/mpesa/stkpushquery/v1/query"
    )

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    payload = {
        "BusinessShortCode": settings.MPESA_SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "CheckoutRequestID": checkout_request_id,
    }

    response = requests.post(
        url,
        json=payload,
        headers=headers,
        timeout=30,
    )

    response.raise_for_status()
    return response.json()
