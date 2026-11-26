
import base64
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.test import SimpleTestCase, override_settings

from payments.services.mpesa import (
    generate_password,
    generate_timestamp,
)


@override_settings(
    MPESA_SHORTCODE="174379",
    MPESA_PASSKEY="test-passkey",
)
class DarajaTimestampTests(SimpleTestCase):

    def test_timestamp_uses_nairobi_timezone(self):
        fixed_datetime = datetime(
            2026, 11, 25, 12, 30, 45,
            tzinfo=ZoneInfo("Africa/Nairobi"),
        )

        with patch(
            "payments.services.mpesa.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value = fixed_datetime

            timestamp = generate_timestamp()

        self.assertEqual(timestamp, "20261125123045")
        mock_datetime.now.assert_called_once_with(
            ZoneInfo("Africa/Nairobi")
        )

    def test_password_uses_shortcode_passkey_and_timestamp(self):
        timestamp = "20261125123045"

        expected_raw = (
            "174379"
            "test-passkey"
            "20261125123045"
        )

        expected_password = base64.b64encode(
            expected_raw.encode("utf-8")
        ).decode("utf-8")

        self.assertEqual(
            generate_password(timestamp),
            expected_password,
        )

    def test_password_is_base64_encoded(self):
        timestamp = "20261125123045"

        password = generate_password(timestamp)

        decoded = base64.b64decode(
            password,
            validate=True,
        ).decode("utf-8")

        self.assertEqual(
            decoded,
            "174379test-passkey20261125123045",
        )
