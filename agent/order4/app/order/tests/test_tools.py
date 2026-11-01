"""ローカルツールとエントリポイント補助関数のユニットテスト"""

import base64
import json
from types import SimpleNamespace

import pytest

from tools import convert_currency, get_product_info


def test_get_all_products():
    result = get_product_info()
    assert [p["id"] for p in result["products"]] == ["PROD-001", "PROD-002", "PROD-003"]


def test_get_product_case_insensitive():
    assert get_product_info(product_id=" prod-002 ")["product"]["name"] == "ガジェットB"


def test_get_unknown_product():
    result = get_product_info(product_id="PROD-999")
    assert "error" in result
    assert "PROD-001" in result["available_product_ids"]


def test_usd_to_jpy():
    result = convert_currency(amount=500, from_currency="usd", to_currency="JPY")
    assert result["converted_amount"] == 75000
    assert result["rate"] == 150.0


def test_jpy_to_usd():
    assert convert_currency(amount=4500, from_currency="JPY", to_currency="USD")["converted_amount"] == 30.0


def test_same_currency():
    assert convert_currency(amount=12.34, from_currency="USD", to_currency="USD")["converted_amount"] == 12.34


@pytest.mark.parametrize(
    "amount,src,dst",
    [(100, "EUR", "JPY"), (100, "USD", "GBP"), (-1, "USD", "JPY"), ("abc", "USD", "JPY")],
)
def test_convert_errors(amount, src, dst):
    assert "error" in convert_currency(amount=amount, from_currency=src, to_currency=dst)


def _jwt(claims: dict) -> str:
    body = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return f"eyJhbGciOiJub25lIn0.{body}.sig"


def test_actor_id_from_jwt():
    import main

    ctx = SimpleNamespace(request_headers={"authorization": f"Bearer {_jwt({'sub': 'user-123'})}"})
    assert main._actor_id_from_jwt(ctx) == "user-123"
    assert main._actor_id_from_jwt(SimpleNamespace(request_headers={})) == "anonymous"
    bad = SimpleNamespace(request_headers={"Authorization": "Bearer broken"})
    assert main._actor_id_from_jwt(bad) == "anonymous"


@pytest.mark.parametrize("payload", [None, {}, {"prompt": ""}, {"prompt": 1}, {"prompt": "a" * 4001}])
def test_extract_prompt_rejects_invalid(payload):
    import main

    with pytest.raises(ValueError):
        main._extract_prompt(payload)
