from decimal import Decimal

from app.services.apple import AppleCatalogClient


def test_parse_iaps_extracts_subscription_offer() -> None:
    payload = {
        "data": [
            {
                "attributes": {"name": "Example"},
                "views": {
                    "top-in-app-purchasables": {
                        "data": [
                            {
                                "id": "1234567890",
                                "attributes": {
                                    "name": "Pro Monthly",
                                    "isSubscription": True,
                                    "subscriptionFamilyName": "Pro",
                                    "offers": [
                                        {
                                            "price": 19.99,
                                            "currencyCode": "USD",
                                            "priceFormatted": "$19.99",
                                            "recurringSubscriptionPeriod": "P1M",
                                        }
                                    ],
                                },
                            }
                        ]
                    }
                },
            }
        ]
    }

    result = AppleCatalogClient()._parse_iaps("US", payload)

    assert result.ok
    assert result.app_name == "Example"
    assert result.iaps is not None
    assert len(result.iaps) == 1
    assert result.iaps[0].iap_id == "1234567890"
    assert result.iaps[0].amount == Decimal("19.99")
    assert result.iaps[0].period == "P1M"


def test_parse_iaps_treats_empty_data_as_error() -> None:
    result = AppleCatalogClient()._parse_iaps("US", {"data": []})
    assert not result.ok
    assert "空数据" in result.error

