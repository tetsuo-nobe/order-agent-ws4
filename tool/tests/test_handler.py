"""見積書 Lambda（Gateway Lambda ターゲット）のユニットテスト"""

import os
from types import SimpleNamespace
from unittest.mock import patch

import pytest

os.environ.setdefault("AWS_DEFAULT_REGION", "us-west-2")

import handler  # noqa: E402


def _context(tool_name="quote-lambda-target___create_quote"):
    """Gateway から渡される Lambda context を模擬する"""
    return SimpleNamespace(
        client_context=SimpleNamespace(custom={"bedrockAgentCoreToolName": tool_name})
    )


@pytest.fixture(autouse=True)
def env():
    with patch.dict(os.environ, {"QUOTE_BUCKET_NAME": "test-bucket"}):
        yield


@pytest.fixture
def mock_s3():
    with patch.object(handler, "s3_client") as client:
        client.generate_presigned_url.return_value = "https://example.com/quote.pdf"
        yield client


VALID = {"product_id": "PROD-001", "customer_name": "テスト太郎", "quantity": 10, "currency": "JPY"}


def test_create_quote_success_generates_real_pdf(mock_s3):
    """実フォントで PDF を生成し、換算済み金額と URL を返す"""
    result = handler.lambda_handler(dict(VALID), _context())

    assert result["quote_url"] == "https://example.com/quote.pdf"
    assert result["unit_price"] == round(29.99 * 150)
    assert result["total"] == round(29.99 * 150) * 10
    assert result["currency"] == "JPY"
    body = mock_s3.put_object.call_args.kwargs["Body"]
    assert body.startswith(b"%PDF")


def test_usd_quote_for_jpy_product(mock_s3):
    params = {**VALID, "product_id": "PROD-002", "currency": "usd", "quantity": "3"}
    result = handler.lambda_handler(params, _context())
    assert result["unit_price"] == 30.0
    assert result["total"] == 90.0
    assert result["quantity"] == 3


@pytest.mark.parametrize(
    "override",
    [
        {"product_id": ""},
        {"customer_name": None},
        {"quantity": 0},
        {"quantity": 1.5},
        {"quantity": True},
        {"quantity": "abc"},
        {"currency": "EUR"},
    ],
)
def test_validation_errors(mock_s3, override):
    result = handler.lambda_handler({**VALID, **override}, _context())
    assert "error" in result
    mock_s3.put_object.assert_not_called()


def test_unknown_product(mock_s3):
    result = handler.lambda_handler({**VALID, "product_id": "PROD-999"}, _context())
    assert result == {"error": "製品が見つかりません: PROD-999"}


def test_unknown_tool(mock_s3):
    result = handler.lambda_handler(dict(VALID), _context("quote-lambda-target___other"))
    assert "error" in result


def test_s3_failure(mock_s3):
    mock_s3.put_object.side_effect = Exception("boom")
    result = handler.lambda_handler(dict(VALID), _context())
    assert result == {"error": "ファイル保存に失敗しました"}
