"""Per-order label settings and a single renderer for preview and download."""

from decimal import Decimal
from io import BytesIO
from xml.sax.saxutils import escape

from django import forms
from reportlab.graphics.barcode import createBarcodeDrawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, TableStyle

from checkout.receipts import receipt_details, receipt_font

LABEL_FORMATS = {"4x6": (4 * inch, 6 * inch), "4x4": (4 * inch, 4 * inch), "a4": A4}


class LabelForm(forms.Form):
    courier = forms.CharField(required=False, max_length=80, label="Courier")
    service = forms.CharField(required=False, max_length=60, label="Booked service")
    tracking = forms.RegexField(
        r"\A[A-Za-z0-9][A-Za-z0-9 /_.-]{0,99}\Z",
        required=False,
        max_length=100,
        label="Tracking / waybill number",
        help_text="Use your courier's number, or leave blank for the order reference. Long numbers may need A4 for barcode scanning.",
    )
    hub_code = forms.CharField(required=False, max_length=20, label="Destination hub")
    weight_kg = forms.DecimalField(
        required=False,
        min_value=Decimal("0.001"),
        max_digits=8,
        decimal_places=3,
        label="Weight (kg)",
    )
    dimensions = forms.CharField(required=False, max_length=80, label="Dimensions (L x W x H, cm)")
    pieces = forms.IntegerField(required=False, min_value=1, max_value=999, label="Parcel count")
    instructions = forms.CharField(
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Delivery instructions",
    )
    return_address = forms.CharField(
        required=False,
        max_length=1000,
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Return address for this order",
        help_text="Starts with the address in Settings > Order settings; saved with this order.",
    )
    format = forms.ChoiceField(
        choices=[
            ("4x6", "4 x 6 inch label"),
            ("4x4", "4 x 4 inch compact label"),
            ("a4", "A4 packing slip"),
        ],
        label="Paper format",
    )
    palette = forms.ChoiceField(
        choices=[("branded", "Branded green"), ("thermal", "Thermal black & white")],
        label="Print style",
    )
    contents = forms.ChoiceField(
        choices=[
            ("full", "Full item list"),
            ("summary", "Quantity summary"),
            ("hidden", "Hide package contents"),
        ],
        label="Package contents",
    )
    show_skus = forms.BooleanField(required=False, label="Show SKU codes")
    show_prices = forms.BooleanField(required=False, label="Show item prices")
    expected_revision = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, order, default_return_address="", **kwargs):
        super().__init__(*args, **kwargs)
        self.initial = {
            "format": "4x6",
            "palette": "branded",
            "contents": "full",
            "show_skus": True,
            "show_prices": False,
            "instructions": order.address.get("notes", ""),
            "return_address": default_return_address,
            **order.shipping_details,
            "expected_revision": order.shipping_updated_at.isoformat()
            if order.shipping_updated_at
            else "",
        }

    def shipping_data(self):
        data = {
            key: value for key, value in self.cleaned_data.items() if key != "expected_revision"
        }
        if data["weight_kg"] is not None:
            data["weight_kg"] = str(data["weight_kg"])
        return data


def label_pdf(order, settings):
    """Render only the selected format from immutable order snapshots."""
    receipt = receipt_details(order)
    paper = LABEL_FORMATS[settings["format"]]
    compact = settings["format"] == "4x4"
    margin = 12 if settings["format"] != "a4" else 32
    width = paper[0] - 2 * margin - 12
    accent = colors.black if settings["palette"] == "thermal" else colors.HexColor("#047857")
    font = receipt_font()
    body = ParagraphStyle(
        "LabelBody",
        fontName=font,
        fontSize=7 if compact else 9,
        leading=10 if compact else 13,
        textColor=colors.black,
        spaceAfter=4,
    )
    heading = ParagraphStyle("LabelHeading", parent=body, fontSize=12, leading=16, textColor=accent)

    def paragraph(text, style=body):
        return Paragraph(escape(str(text)).replace("\n", "<br/>"), style)

    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=paper,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin,
        bottomMargin=margin + 14,
        title=f"Delivery label {order.number}",
        author="Retail",
    )
    story = [
        paragraph("retail. / " + receipt["fulfillment"], heading),
        paragraph(f"{order.number} | {receipt['date']}"),
    ]
    if order.status in {"cancelled", "failed"}:
        story.append(paragraph("DO NOT DISPATCH - " + order.status.upper(), heading))
    elif order.status == "delivery_review":
        story.append(paragraph("ADDRESS / DISTANCE REVIEW REQUIRED"))
    if settings.get("return_address"):
        story.append(paragraph("RETURN IF UNDELIVERED\n" + settings["return_address"]))
    story.append(
        paragraph(
            "COLLECTING CUSTOMER" if order.delivery_method == "pickup" else "SHIP TO", heading
        )
    )
    story.append(
        paragraph(
            f"{order.contact.get('first_name', '')} {order.contact.get('last_name', '')}\n"
            + str(order.contact.get("phone", ""))
        )
    )
    if order.delivery_method == "pickup":
        story.append(paragraph("Collect from store"))
    else:
        for key in ("address", "landmark", "city", "postal_code"):
            if order.address.get(key):
                story.append(paragraph(order.address[key]))
    if order.payment_status == "paid":
        payment = "PAID - DO NOT COLLECT"
    elif order.payment_method == "cod" and order.status not in {"cancelled", "failed"}:
        payment = f"CASH TO COLLECT: PKR {order.total:.2f}"
    else:
        payment = "PAYMENT NOT VERIFIED - CHECK ORDER"
    story.append(paragraph(payment, heading))
    story.append(paragraph(f"Order total: PKR {order.total:.2f} | Payment: {order.payment_status}"))
    for key, title in (
        ("courier", "Courier"),
        ("service", "Service"),
        ("hub_code", "Hub"),
        ("weight_kg", "Weight (kg)"),
        ("dimensions", "Dimensions (cm)"),
        ("pieces", "Parcels"),
    ):
        if settings.get(key):
            story.append(paragraph(f"{title}: {settings[key]}"))
    tracking = settings.get("tracking") or order.number
    story.append(paragraph("COURIER TRACKING" if settings.get("tracking") else "ORDER REFERENCE"))
    barcode = createBarcodeDrawing("Code128", value=tracking, barHeight=26, humanReadable=False)
    scale = min(1, width / barcode.width)
    barcode.scale(scale, 1)
    barcode.width *= scale
    story.extend([barcode, paragraph(tracking), Spacer(1, 3)])
    if settings.get("instructions"):
        story.append(paragraph("INSTRUCTIONS\n" + settings["instructions"]))
    if settings["contents"] != "hidden":
        story.append(paragraph(f"PACKAGE CONTENTS / {receipt['quantity']} items", heading))
        if settings["contents"] == "full":
            headers = ["Item", "Qty"] + (["Line total"] if settings["show_prices"] else [])
            rows = [[paragraph(value) for value in headers]]
            for item in receipt["items"]:
                name = item.name
                if settings["show_skus"] and item.sku:
                    name += "\nSKU: " + item.sku
                row = [paragraph(name), paragraph(item.quantity)]
                if settings["show_prices"]:
                    row.append(paragraph(f"PKR {item.line_total:.2f}"))
                rows.append(row)
            columns = [width - 90, 24, 66] if settings["show_prices"] else [width - 30, 30]
            table = LongTable(rows, colWidths=columns, repeatRows=1, splitInRow=1)
            table.setStyle(
                TableStyle(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LINEBELOW", (0, 0), (-1, -1), 0.4, accent),
                        ("LEFTPADDING", (0, 0), (-1, -1), 2),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]
                )
            )
            story.append(table)

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont(font, 6)
        canvas.setFillColor(colors.black)
        canvas.drawString(margin, 10, f"{order.number} | Page {doc.page}")
        if doc.page > 1:
            canvas.drawRightString(paper[0] - margin, 10, "CONTINUATION - SAME PARCEL")
        canvas.restoreState()

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    output.seek(0)
    return output
