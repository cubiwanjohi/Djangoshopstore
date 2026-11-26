"""Tests for the Safaricom M-Pesa STK Push Query service.

All HTTP requests and access-token calls are mocked.
These tests never contact Safaricom or move real money.
"""

from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings
from requests.exceptions import HTTPError, Timeout

from payments.services.mpesa import stk_push_query


@override_settings(
    MPESA_BASE_URL="https://sandbox.safaricom.co.ke",
    MPESA_SHORTCODE="174379",
    MPESA_PASSKEY="test-passkey",
)
class STKPushQueryTests(SimpleTestCase):

    checkout_request_id = "ws_CO_TEST123456"

    def setUp(self):
        self.access_token_patcher = patch(
            "payments.services.mpesa.get_access_token"
        )
        self.mock_access_token = self.access_token_patcher.start()
        self.mock_access_token.return_value = "test-access-token"
        self.addCleanup(self.access_token_patcher.stop)

        self.post_patcher = patch(
            "payments.services.mpesa.requests.post"
        )
        self.mock_post = self.post_patcher.start()
        self.addCleanup(self.post_patcher.stop)

        self.mock_response = Mock()
        self.mock_response.json.return_value = {
            "ResponseCode": "0",
            "ResponseDescription": (
                "The service request has been accepted."
            ),
            "CheckoutRequestID": self.checkout_request_id,
            "ResultCode": "0",
            "ResultDesc": (
                "The service request is processed successfully."
            ),
        }

        self.mock_post.return_value = self.mock_response

    def test_stk_push_query_success(self):
        result = stk_push_query(self.checkout_request_id)

        self.mock_access_token.assert_called_once_with()
        self.mock_post.assert_called_once()

        args, kwargs = self.mock_post.call_args

        self.assertEqual(
            args[0],
            (
                "https://sandbox.safaricom.co.ke"
                "/mpesa/stkpushquery/v1/query"
            ),
        )

        self.assertEqual(
            kwargs["headers"]["Authorization"],
            "Bearer test-access-token",
        )

        self.assertEqual(
            kwargs["headers"]["Content-Type"],
            "application/json",
        )

        payload = kwargs["json"]

        self.assertEqual(payload["BusinessShortCode"], "174379")
        self.assertEqual(
            payload["CheckoutRequestID"],
            self.checkout_request_id,
        )

        self.assertTrue(payload["Timestamp"])
        self.assertTrue(payload["Password"])

        self.assertEqual(kwargs["timeout"], 30)

        self.mock_response.raise_for_status.assert_called_once_with()
        self.mock_response.json.assert_called_once_with()

        self.assertEqual(
            result["CheckoutRequestID"],
            self.checkout_request_id,
        )
        self.assertEqual(result["ResultCode"], "0")

    def test_stk_push_query_raises_http_error(self):
        self.mock_response.raise_for_status.side_effect = HTTPError(
            "Safaricom returned an HTTP error"
        )

        with self.assertRaises(HTTPError):
            stk_push_query(self.checkout_request_id)

        self.mock_response.raise_for_status.assert_called_once_with()
        self.mock_response.json.assert_not_called()

    def test_stk_push_query_raises_timeout(self):
        self.mock_post.side_effect = Timeout(
            "Safaricom request timed out"
        )

        with self.assertRaises(Timeout):
            stk_push_query(self.checkout_request_id)

        self.mock_post.assert_called_once()

        _, kwargs = self.mock_post.call_args
        self.assertEqual(kwargs["timeout"], 30)

    def test_stk_push_query_raises_error_for_invalid_json(self):
        self.mock_response.json.side_effect = ValueError(
            "Invalid JSON response"
        )

        with self.assertRaises(ValueError):
            stk_push_query(self.checkout_request_id)

        self.mock_response.raise_for_status.assert_called_once_with()
        self.mock_response.json.assert_called_once_with()

    def test_stk_push_query_requests_an_access_token_before_http_call(self):
        stk_push_query(self.checkout_request_id)

        self.mock_access_token.assert_called_once_with()
        self.mock_post.assert_called_once()
