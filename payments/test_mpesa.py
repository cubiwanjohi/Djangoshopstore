from unittest.mock import patch, Mock

from django.test import SimpleTestCase, override_settings

from payments.services.mpesa import stk_push_query


@override_settings(
    MPESA_BASE_URL="https://sandbox.safaricom.co.ke",
    MPESA_SHORTCODE="174379",
    MPESA_PASSKEY="test-passkey",
)
class STKPushQueryTests(SimpleTestCase):

    @patch("payments.services.mpesa.requests.post")
    @patch("payments.services.mpesa.get_access_token")
    def test_stk_push_query_success(
        self,
        mock_access_token,
        mock_post,
    ):
        # Simulate a successful access token response.
        mock_access_token.return_value = "test-access-token"

        # Simulate Safaricom's query response.
        mock_response = Mock()
        mock_response.json.return_value = {
            "ResponseCode": "0",
            "ResponseDescription": "The service request has been accepted.",
            "ResultCode": "0",
            "ResultDesc": "The service request is processed successfully.",
        }

        mock_post.return_value = mock_response

        checkout_request_id = "ws_CO_TEST123456"

        result = stk_push_query(checkout_request_id)

        # Confirm that the access token was requested.
        mock_access_token.assert_called_once()

        # Confirm that the query was sent to the correct endpoint.
        mock_post.assert_called_once()

        args, kwargs = mock_post.call_args

        self.assertEqual(
            args[0],
            "https://sandbox.safaricom.co.ke/mpesa/stkpushquery/v1/query",
        )

        # Confirm the transaction ID was included.
        self.assertEqual(
            kwargs["json"]["CheckoutRequestID"],
            checkout_request_id,
        )

        # Confirm the authorization header.
        self.assertEqual(
            kwargs["headers"]["Authorization"],
            "Bearer test-access-token",
        )

        # Confirm the response was checked for HTTP errors.
        mock_response.raise_for_status.assert_called_once()

        # Confirm the response was returned.
        self.assertEqual(result["ResultCode"], "0")