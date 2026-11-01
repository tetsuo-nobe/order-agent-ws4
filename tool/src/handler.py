"""注文見積り書 PDF 生成 Lambda ハンドラー（AgentCore Gateway Lambda ターゲット）

AgentCore Gateway から MCP ツール `create_quote` として呼び出される。
Gateway の Lambda ターゲットでは、ツールの入力引数がそのまま event（dict）として渡され、
ツール名は context.client_context.custom["bedrockAgentCoreToolName"] に
"<ターゲット名>___<ツール名>" の形式で格納される。
戻り値の dict は Gateway によって MCP のツール結果へ変換される。
"""

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from io import BytesIO

import boto3
from botocore.config import Config
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Gateway が付与するツール名の区切り文字（"<ターゲット名>___<ツール名>"）
TOOL_NAME_DELIMITER = "___"
# このLambdaが提供するツール名
TOOL_NAME_CREATE_QUOTE = "create_quote"

# 製品カタログデータ（エージェント側の get_product_info と同一内容）
PRODUCTS = [
    {"id": "PROD-001", "name": "ウィジェットA", "unit_price": 29.99, "currency": "USD"},
    {"id": "PROD-002", "name": "ガジェットB", "unit_price": 4500, "currency": "JPY"},
    {"id": "PROD-003", "name": "モジュールC", "unit_price": 89.50, "currency": "USD"},
]

# 通貨換算レート（固定レート: 1 USD = 150 JPY）
EXCHANGE_RATES = {
    "USD_TO_JPY": 150.0,
    "JPY_TO_USD": 1 / 150.0,
}

# 対応通貨
SUPPORTED_CURRENCIES = ("USD", "JPY")

# 署名付き URL の有効期限（秒）。Lambda 実行ロールの一時認証情報で署名するため、
# 実際の有効期限は認証情報の失効時刻までに制限される点に注意。
PRESIGNED_URL_EXPIRES_IN = int(os.environ.get("PRESIGNED_URL_EXPIRES_IN", "3600"))

# フォントファイルパス（Lambda 環境では /var/task 配下）
FONT_NAME = "NotoSansJP"
FONT_PATH = os.path.join(os.path.dirname(__file__), "fonts", "NotoSansJP-VariableFont_wght.ttf")

# 日本時間（発行日の表示用）
JST = timezone(timedelta(hours=9))

# S3 クライアント
# 作成直後のバケットではグローバルエンドポイント（s3.amazonaws.com）宛ての署名付きURLが
# リダイレクトされ署名不一致になる場合があるため、リージョンエンドポイントと SigV4 を明示する
_REGION = os.environ.get("AWS_REGION", "us-west-2")
s3_client = boto3.client(
    "s3",
    region_name=_REGION,
    endpoint_url=f"https://s3.{_REGION}.amazonaws.com",
    config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
)

_font_registered = False


def _register_font():
    """日本語フォントを reportlab に登録する（初回のみ）"""
    global _font_registered
    if not _font_registered:
        pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_PATH))
        _font_registered = True


def _find_product(product_id):
    """製品カタログから製品情報を取得する"""
    for product in PRODUCTS:
        if product["id"] == product_id:
            return product
    return None


def _convert_price(price, from_currency, to_currency):
    """通貨換算を行う"""
    if from_currency == to_currency:
        return price
    rate = EXCHANGE_RATES.get(f"{from_currency}_TO_{to_currency}")
    if rate is None:
        return price
    return price * rate


def _format_amount(amount, currency):
    """通貨に応じた金額表記を返す"""
    if currency == "JPY":
        return f"¥{round(amount):,}"
    return f"${amount:,.2f}"


def _generate_pdf(customer_name, product, unit_price, quantity, total, currency):
    """見積書 PDF を生成してバイトデータを返す"""
    _register_font()

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title="注文見積書",
    )

    # スタイル定義
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "JapaneseTitle", parent=styles["Title"], fontName=FONT_NAME, fontSize=24
    )
    normal_style = ParagraphStyle(
        "JapaneseNormal", parent=styles["Normal"], fontName=FONT_NAME, fontSize=12
    )

    elements = []

    # タイトル
    elements.append(Paragraph("注文見積書", title_style))
    elements.append(Spacer(1, 10 * mm))

    # 発行日・顧客名
    issue_date = datetime.now(JST).strftime("%Y年%m月%d日")
    elements.append(Paragraph(f"発行日: {issue_date}", normal_style))
    elements.append(Spacer(1, 5 * mm))
    elements.append(Paragraph(f"顧客名: {customer_name} 様", normal_style))
    elements.append(Spacer(1, 10 * mm))

    # 見積明細テーブル
    table_data = [
        ["項目", "内容"],
        ["製品ID", product["id"]],
        ["製品名", product["name"]],
        ["単価", _format_amount(unit_price, currency)],
        ["数量", str(quantity)],
        ["合計金額（税抜き）", _format_amount(total, currency)],
        ["通貨", currency],
    ]
    table = Table(table_data, colWidths=[50 * mm, 80 * mm])
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
                ("FONTSIZE", (0, 0), (-1, -1), 11),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4472C4")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F2F2")]),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(table)
    elements.append(Spacer(1, 10 * mm))
    elements.append(Paragraph("※ 換算レートは 1 USD = 150 JPY（固定）です。", normal_style))

    doc.build(elements)
    return buffer.getvalue()


def _upload_to_s3(pdf_bytes, bucket_name):
    """PDF を S3 にアップロードし、ダウンロード用の署名付き URL を返す"""
    file_key = f"quotes/{datetime.now(JST).strftime('%Y%m%d')}/{uuid.uuid4()}.pdf"

    s3_client.put_object(
        Bucket=bucket_name,
        Key=file_key,
        Body=pdf_bytes,
        ContentType="application/pdf",
    )

    # ブラウザでダウンロードさせるため Content-Disposition を指定
    return s3_client.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": bucket_name,
            "Key": file_key,
            "ResponseContentDisposition": 'attachment; filename="quote.pdf"',
        },
        ExpiresIn=PRESIGNED_URL_EXPIRES_IN,
    )


def _get_tool_name(context):
    """Gateway から渡されたツール名（ターゲット名のプレフィックスを除去）を取得する"""
    try:
        full_name = context.client_context.custom["bedrockAgentCoreToolName"]
    except (AttributeError, KeyError, TypeError):
        # 直接呼び出し（テスト等）の場合は create_quote とみなす
        return TOOL_NAME_CREATE_QUOTE
    if TOOL_NAME_DELIMITER in full_name:
        return full_name.split(TOOL_NAME_DELIMITER, 1)[1]
    return full_name


def _validate(event):
    """入力引数を検証し、(正規化済みパラメータ, エラーメッセージ) を返す"""
    if not isinstance(event, dict):
        return None, "リクエスト形式が不正です"

    required = ["product_id", "customer_name", "quantity", "currency"]
    missing = [p for p in required if event.get(p) in (None, "")]
    if missing:
        return None, f"必須パラメータが不足しています: {', '.join(missing)}"

    product_id = str(event["product_id"]).strip().upper()
    customer_name = str(event["customer_name"]).strip()
    currency = str(event["currency"]).strip().upper()
    quantity = event["quantity"]

    # 数量は 1 以上の整数（"10" のような文字列も許容）
    try:
        if isinstance(quantity, bool):
            raise ValueError
        quantity_num = float(quantity)
        if not quantity_num.is_integer() or quantity_num < 1:
            raise ValueError
        quantity = int(quantity_num)
    except (TypeError, ValueError):
        return None, "数量は1以上の整数で指定してください"

    if not customer_name:
        return None, "必須パラメータが不足しています: customer_name"
    if len(customer_name) > 100:
        return None, "顧客名は100文字以内で指定してください"

    if currency not in SUPPORTED_CURRENCIES:
        return None, "通貨は USD または JPY を指定してください"

    return {
        "product_id": product_id,
        "customer_name": customer_name,
        "quantity": quantity,
        "currency": currency,
    }, None


def create_quote(params, bucket_name):
    """見積書を作成し、結果の dict を返す"""
    product = _find_product(params["product_id"])
    if product is None:
        return {"error": f"製品が見つかりません: {params['product_id']}"}

    currency = params["currency"]
    quantity = params["quantity"]
    # 単価を先に丸めて（JPY は整数、USD は小数2桁）から合計を計算し、
    # 見積書上で「単価 × 数量 = 合計」が一致するようにする
    digits = 0 if currency == "JPY" else 2
    unit_price = round(
        _convert_price(product["unit_price"], product["currency"], currency), digits
    )
    total = round(unit_price * quantity, digits)
    if currency == "JPY":
        unit_price, total = int(unit_price), int(total)

    try:
        pdf_bytes = _generate_pdf(
            params["customer_name"], product, unit_price, quantity, total, currency
        )
    except Exception:
        logger.exception("PDF生成に失敗しました")
        return {"error": "PDF生成に失敗しました"}

    try:
        quote_url = _upload_to_s3(pdf_bytes, bucket_name)
    except Exception:
        logger.exception("ファイル保存に失敗しました")
        return {"error": "ファイル保存に失敗しました"}

    return {
        "quote_url": quote_url,
        "url_expires_in_seconds": PRESIGNED_URL_EXPIRES_IN,
        "product_id": product["id"],
        "product_name": product["name"],
        "customer_name": params["customer_name"],
        "unit_price": unit_price,
        "quantity": quantity,
        "total": total,
        "currency": currency,
    }


def lambda_handler(event, context):
    """Lambda エントリポイント"""
    tool_name = _get_tool_name(context)
    logger.info("ツール呼び出し: %s", tool_name)

    if tool_name != TOOL_NAME_CREATE_QUOTE:
        return {"error": f"未対応のツールです: {tool_name}"}

    params, error = _validate(event)
    if error:
        return {"error": error}

    bucket_name = os.environ.get("QUOTE_BUCKET_NAME")
    if not bucket_name:
        logger.error("環境変数 QUOTE_BUCKET_NAME が未設定です")
        return {"error": "ファイル保存に失敗しました"}

    return create_quote(params, bucket_name)
