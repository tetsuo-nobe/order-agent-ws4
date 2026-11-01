"""エージェントと共にデプロイするローカルツール（Strands @tool）。

- get_product_info: 製品カタログの照会
- convert_currency: USD と JPY 間の通貨換算（固定レート）

見積書の作成・ダウンロードは AgentCore Gateway（Lambda ターゲット）のツールとして呼び出すため、
ここには定義しない。製品カタログと換算レートは Lambda 側（tool/src/handler.py）と同じ内容にすること。
"""

from strands import tool

# 製品カタログ
PRODUCTS = [
    {"id": "PROD-001", "name": "ウィジェットA", "unit_price": 29.99, "currency": "USD"},
    {"id": "PROD-002", "name": "ガジェットB", "unit_price": 4500, "currency": "JPY"},
    {"id": "PROD-003", "name": "モジュールC", "unit_price": 89.50, "currency": "USD"},
]

# 固定換算レート（1 USD = 150 JPY）
USD_JPY_RATE = 150.0
EXCHANGE_RATES = {
    "USD_TO_JPY": USD_JPY_RATE,
    "JPY_TO_USD": 1 / USD_JPY_RATE,
}

# 通貨ごとの丸め桁数（JPY は整数、USD はセント単位）
CURRENCY_DIGITS = {"USD": 2, "JPY": 0}


def _round_amount(amount: float, currency: str) -> float | int:
    """通貨に応じて金額を丸める"""
    digits = CURRENCY_DIGITS[currency]
    rounded = round(amount, digits)
    return int(rounded) if digits == 0 else rounded


@tool
def get_product_info(product_id: str | None = None) -> dict:
    """製品カタログから製品情報を取得する。product_id を省略すると全製品を返す。

    Args:
        product_id: 製品ID（例: PROD-001）。省略時は全製品の一覧を返す。

    Returns:
        product_id 指定時は {"product": {...}}、省略時は {"products": [...]}。
        該当する製品が無い場合は {"error": "..."}。
        各製品は id, name, unit_price, currency を持つ。
    """
    if product_id is None or not str(product_id).strip():
        return {"products": PRODUCTS}

    normalized_id = str(product_id).strip().upper()
    for product in PRODUCTS:
        if product["id"] == normalized_id:
            return {"product": product}

    return {
        "error": f"製品が見つかりません: {product_id}",
        "available_product_ids": [p["id"] for p in PRODUCTS],
    }


@tool
def convert_currency(amount: float, from_currency: str, to_currency: str) -> dict:
    """USD と JPY の間で通貨を換算する。固定レート（1 USD = 150 JPY）を使用する。

    Args:
        amount: 換算する金額（0 以上）
        from_currency: 換算元の通貨コード（USD または JPY）
        to_currency: 換算先の通貨コード（USD または JPY）

    Returns:
        original_amount, converted_amount, from_currency, to_currency, rate を含む辞書。
        入力が不正な場合は {"error": "..."}。
    """
    from_code = str(from_currency).strip().upper()
    to_code = str(to_currency).strip().upper()

    if from_code not in CURRENCY_DIGITS or to_code not in CURRENCY_DIGITS:
        return {"error": f"サポートされていない通貨です: {from_currency} → {to_currency}（USD と JPY のみ対応）"}

    try:
        amount_value = float(amount)
    except (TypeError, ValueError):
        return {"error": f"金額が数値ではありません: {amount}"}
    if amount_value < 0:
        return {"error": "金額は 0 以上で指定してください"}

    rate = 1.0 if from_code == to_code else EXCHANGE_RATES[f"{from_code}_TO_{to_code}"]

    return {
        "original_amount": amount_value,
        "converted_amount": _round_amount(amount_value * rate, to_code),
        "from_currency": from_code,
        "to_currency": to_code,
        "rate": rate,
        "rate_note": "固定レート 1 USD = 150 JPY",
    }
