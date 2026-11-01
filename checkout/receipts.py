from decimal import Decimal
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    LongTable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def receipt_details(order):
    lines = list(order.items.all())
    gross = sum((item.regular_price * item.quantity for item in lines), Decimal("0.00"))
    discount = sum(
        ((item.regular_price - item.unit_price) * item.quantity for item in lines), Decimal("0.00")
    )
    pickup = order.delivery_method == "pickup"
    pending = order.status == "delivery_review"
    return {
        "items": lines,
        "gross_subtotal": gross,
        "item_discount": discount,
        "quantity": sum(item.quantity for item in lines),
        "product_count": len(lines),
        "date": timezone.localtime(order.created_at, ZoneInfo("Asia/Karachi")).strftime(
            "%d %b %Y, %I:%M %p PKT"
        ),
        "fulfillment": "Store Pickup" if pickup else "Standard Home Delivery",
        "payment": "Cash on collection" if pickup else "Cash on delivery",
        "payment_status": order.payment_status.replace("_", " ").capitalize(),
        "status": "Pending delivery-distance review" if pending else "Order received",
        "message": "Your pickup order has been received. The store will confirm when it is ready for collection. Payment is due at pickup."
        if pickup
        else "Your order is pending delivery-distance review. The store will verify your address and confirm delivery. Payment is due on delivery."
        if pending
        else "Your order has been received. Payment is due on delivery.",
    }


def receipt_pdf(order):
    """Generate a private downloadable PDF from saved order snapshots only."""
    data = receipt_details(order)
    font_name = "ZillyReceipt"
    if font_name not in pdfmetrics.getRegisteredFontNames():
        font_dir = (
            Path(__file__).resolve().parents[1]
            / "catalog/static/catalog/home02/reference/fonts.gstatic.com/s/inter/v20"
        )
        font_path = next(iter(sorted(font_dir.glob("*.ttf"))))
        pdfmetrics.registerFont(TTFont(font_name, str(font_path)))
    body = ParagraphStyle(
        "ReceiptBody",
        fontName=font_name,
        fontSize=9,
        leading=14,
        textColor=colors.HexColor("#253244"),
    )
    small = ParagraphStyle("ReceiptSmall", parent=body, fontSize=8, leading=12)
    heading = ParagraphStyle(
        "ReceiptHeading", parent=body, fontSize=20, leading=25, textColor=colors.white
    )
    white = ParagraphStyle("ReceiptWhite", parent=small, textColor=colors.white)
    label = ParagraphStyle("ReceiptLabel", parent=small, textColor=colors.HexColor("#68766d"))
    right = ParagraphStyle("ReceiptRight", parent=small, alignment=TA_RIGHT)
    centered = ParagraphStyle("ReceiptCentered", parent=small, alignment=TA_CENTER)
    green = colors.HexColor("#126344")
    pale = colors.HexColor("#f1f7f3")
    border = colors.HexColor("#e0e7e2")
    width = A4[0] - 80
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=38,
        bottomMargin=44,
        title=f"Order receipt {order.number}",
        author="Zilly",
    )

    def paragraph(text, style=body):
        return Paragraph(escape(str(text)).replace("\n", "<br/>"), style)

    def money(value):
        return f"PKR {value:.2f}"

    story = []
    banner = Table(
        [
            [
                [paragraph("Zilly", heading), paragraph("ORDER RECEIPT", white)],
                [paragraph(order.number, white), paragraph(data["date"], white)],
            ]
        ],
        colWidths=[width * 0.56, width * 0.44],
    )
    banner.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), green),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 16),
                ("RIGHTPADDING", (0, 0), (-1, -1), 16),
                ("TOPPADDING", (0, 0), (-1, -1), 16),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 16),
            ]
        )
    )
    story.extend(
        [
            banner,
            Spacer(1, 14),
            paragraph(data["status"]),
            paragraph(data["message"], small),
            Spacer(1, 16),
        ]
    )
    contact, address = order.contact, order.address
    customer = [
        paragraph("CUSTOMER DETAILS", label),
        paragraph(f"{contact.get('first_name', '')} {contact.get('last_name', '')}"),
        paragraph(contact.get("phone", "")),
        paragraph(contact.get("email", "")),
    ]
    address_lines = (
        ["Collect from the store. The store will confirm pickup readiness."]
        if order.delivery_method == "pickup"
        else [
            str(address.get(key, ""))
            for key in ("address", "landmark", "city", "postal_code")
            if address.get(key)
        ]
    )
    address_cell = [
        paragraph("PICKUP" if order.delivery_method == "pickup" else "DELIVERY ADDRESS", label)
    ] + [paragraph(line) for line in address_lines]
    mode = [paragraph("FULFILLMENT", label), paragraph(data["fulfillment"])]
    payment = [
        paragraph("PAYMENT", label),
        paragraph(data["payment"]),
        paragraph(f"Payment status: {data['payment_status']}"),
    ]
    metadata = Table([[customer, address_cell], [mode, payment]], colWidths=[width / 2] * 2)
    metadata.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), pale),
                ("BOX", (0, 0), (-1, -1), 0.5, border),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    story.extend(
        [
            metadata,
            Spacer(1, 18),
            paragraph(
                f"ITEM SUMMARY - {data['product_count']} products / {data['quantity']} items"
            ),
            Spacer(1, 8),
        ]
    )
    rows = [
        [
            paragraph(text, white)
            for text in (
                "Item / SKU",
                "Qty",
                "Original price\nBefore discount",
                "Price after deal\nDiscounted price",
                "Line total\nQty x payable price",
            )
        ]
    ]
    for item in data["items"]:
        rows.append(
            [
                [paragraph(item.name), paragraph(f"SKU: {item.sku or '-'}", label)],
                paragraph(item.quantity, right),
                paragraph(money(item.regular_price), right),
                paragraph(money(item.unit_price), right)
                if item.regular_price > item.unit_price
                else paragraph("-", centered),
                paragraph(money(item.line_total), right),
            ]
        )
    table = LongTable(rows, colWidths=[width - 330, 60, 90, 90, 90], repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), green),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8faf9")]),
                ("LINEBELOW", (0, 1), (-1, -1), 0.4, border),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
            ]
        )
    )
    story.extend([table, Spacer(1, 16)])
    amounts = [
        ("Original item total", money(data["gross_subtotal"])),
        ("Item discount", f"- {money(data['item_discount'])}"),
        ("Net item subtotal", money(order.subtotal)),
        (
            "Pickup fee" if order.delivery_method == "pickup" else "Shipping fee",
            "Free (PKR 0.00)" if order.delivery_fee == 0 else money(order.delivery_fee),
        ),
        ("Tax", money(order.tax)),
        ("Amount payable", money(order.total)),
    ]
    totals = Table(
        [[paragraph(title), paragraph(value, right)] for title, value in amounts],
        colWidths=[width * 0.62, width * 0.38],
    )
    totals.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), pale),
                ("BOX", (0, 0), (-1, -1), 0.5, border),
                ("LINEABOVE", (0, -1), (-1, -1), 1, green),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(
        KeepTogether(
            [
                totals,
                Spacer(1, 10),
                paragraph(f"Payment status: {data['payment_status']}. {data['payment']}.", small),
            ]
        )
    )
    if address.get("notes"):
        story.extend([Spacer(1, 14), paragraph("ORDER NOTES", label), paragraph(address["notes"])])

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(border)
        canvas.line(40, 32, A4[0] - 40, 32)
        canvas.setFont(font_name, 7)
        canvas.setFillColor(colors.HexColor("#68766d"))
        canvas.drawString(40, 20, f"Zilly | Order receipt {order.number}")
        canvas.drawRightString(A4[0] - 40, 20, f"Page {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    output.seek(0)
    return output
