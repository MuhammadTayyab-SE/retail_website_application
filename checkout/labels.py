"""Per-order label settings with shared data for HTML previews and PDF output."""

from base64 import b64encode
from decimal import Decimal
from io import BytesIO
from xml.sax.saxutils import escape

from django import forms
from reportlab.graphics.barcode import createBarcodeDrawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    LongTable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    TableStyle,
)

from checkout.forms import CheckoutForm
from checkout.receipts import receipt_details, receipt_font

LABEL_FORMATS = {"4x6": (4 * inch, 6 * inch), "4x4": (4 * inch, 4 * inch), "a4": A4}
ADDRESS_FIELDS = ("address", "landmark", "city", "postal_code")


class LabelForm(forms.Form):
    correct_address = forms.BooleanField(required=False, label="Edit delivery address")
    address = CheckoutForm.base_fields["address"]
    landmark = CheckoutForm.base_fields["landmark"]
    city = CheckoutForm.base_fields["city"]
    postal_code = CheckoutForm.base_fields["postal_code"]
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
        max_length=2000,
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
            ("a4", "A4 slip + label"),
        ],
        label="Paper format",
        widget=forms.RadioSelect(attrs={"form": "label-settings-form"}),
    )
    palette = forms.ChoiceField(
        choices=[("branded", "Branded green"), ("thermal", "Thermal black & white")],
        label="Print style",
        widget=forms.RadioSelect(attrs={"form": "label-settings-form"}),
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
        self.allowed_cities = order.policy_snapshot.get("allowed_cities", [])
        self.fields["correct_address"].disabled = order.delivery_method == "pickup"
        correcting = (
            self.is_bound and self["correct_address"].value() and order.delivery_method != "pickup"
        )
        for name in ADDRESS_FIELDS:
            self.initial[name] = order.address.get(name, "")
            self.fields[name].disabled = not correcting
            self.fields[name].required = correcting and name in {"address", "city"}

    def clean_city(self):
        city = self.cleaned_data["city"]
        if (
            self.cleaned_data.get("correct_address")
            and self.allowed_cities
            and city.casefold() not in {value.strip().casefold() for value in self.allowed_cities}
        ):
            raise forms.ValidationError("Use a city within this order's delivery area.")
        return city

    def corrected_address(self):
        return (
            {name: self.cleaned_data[name] for name in ADDRESS_FIELDS}
            if self.cleaned_data.get("correct_address")
            else {}
        )

    def shipping_data(self):
        data = {
            key: value
            for key, value in self.cleaned_data.items()
            if key not in {"expected_revision", "correct_address", *ADDRESS_FIELDS}
        }
        if data["weight_kg"] is not None:
            data["weight_kg"] = str(data["weight_kg"])
        return data


def label_preview(order, settings):
    data = label_details(order, settings)
    barcode = createBarcodeDrawing(
        "Code128", value=data["tracking"], barHeight=36, humanReadable=False
    )
    qr = createBarcodeDrawing("QR", value=order.number, width=64, height=64, barBorder=2)
    data["barcode_image"] = "data:image/svg+xml;base64," + b64encode(
        barcode.asString("svg").encode("utf-8")
    ).decode("ascii")
    data["qr_image"] = "data:image/svg+xml;base64," + b64encode(
        qr.asString("svg").encode("utf-8")
    ).decode("ascii")
    data["template"] = {
        "4x6": "retail_admin/labels/4x6.html",
        "4x4": "retail_admin/labels/4x4.html",
        "a4": "retail_admin/labels/a4.html",
    }[settings["format"]]
    return data


def label_details(order, settings):
    """Shared authoritative content for browser previews and PDF labels."""
    receipt = receipt_details(order)
    customer = f"{order.contact.get('first_name', '')} {order.contact.get('last_name', '')}".strip()
    phone = str(order.contact.get("phone", ""))
    pickup = order.delivery_method == "pickup"
    destination = (
        "Collect from store"
        if pickup
        else "\n".join(
            str(order.address[key]) for key in ("address", "landmark") if order.address.get(key)
        )
    )
    city = "STORE PICKUP" if pickup else str(order.address.get("city", "")).upper()
    postal = str(order.address.get("postal_code", "")) if not pickup else ""
    ship_caption = "COLLECTING CUSTOMER" if pickup else "SHIP TO / CONSIGNEE"
    tracking = settings.get("tracking") or order.number
    tracking_caption = "AWB / TRACKING NUMBER" if settings.get("tracking") else "ORDER REFERENCE"
    service = settings.get("service") or receipt["fulfillment"]
    courier = settings.get("courier") or "Courier not assigned"
    hub = settings.get("hub_code") or "-"
    specs = (
        " | ".join(
            str(value)
            for value in (
                f"{settings['weight_kg']} kg" if settings.get("weight_kg") else "",
                f"{settings['pieces']} parcels" if settings.get("pieces") else "",
            )
            if value
        )
        or "Parcel details not set"
    )
    return_address = settings.get("return_address") or "Return address not set"
    cash_due = (
        order.payment_method == "cod"
        and order.payment_status == "unpaid"
        and order.status not in {"cancelled", "failed"}
    )
    if order.payment_status == "paid":
        payment = "PAID - DO NOT COLLECT"
        payment_badge = "PAID"
    elif cash_due:
        payment = f"CASH TO COLLECT: PKR {order.total:.2f}"
        payment_badge = "COD"
    else:
        payment = "PAYMENT NOT VERIFIED - CHECK ORDER"
        payment_badge = "CHECK"

    warning = ""
    if order.status in {"cancelled", "failed"}:
        warning = "DO NOT DISPATCH - " + order.status.upper()
    elif order.status == "delivery_review":
        warning = "ADDRESS / DISTANCE REVIEW REQUIRED"
    return {
        "order": order,
        "settings": settings,
        "receipt": receipt,
        "customer": customer,
        "phone": phone,
        "pickup": pickup,
        "destination": destination,
        "city": city,
        "postal": postal,
        "ship_caption": ship_caption,
        "tracking": tracking,
        "tracking_caption": tracking_caption,
        "service": service,
        "courier": courier,
        "hub": hub,
        "specs": specs,
        "return_address": return_address,
        "cash_due": cash_due,
        "payment": payment,
        "payment_badge": payment_badge,
        "warning": warning,
    }


def label_pdf(order, settings):
    """Build the selected printable PDF from shared label data."""
    data = label_details(order, settings)
    selected = settings["format"]
    compact = selected == "4x4"
    thermal = settings["palette"] == "thermal"
    paper = LABEL_FORMATS[selected]
    margin = 8 if selected != "a4" else 28
    width = paper[0] - 2 * margin - 12
    font = receipt_font()
    ink = colors.black
    brand = ink if thermal else colors.HexColor("#064e3b")
    pale = colors.white if thermal else colors.HexColor("#ecfdf5")
    body = ParagraphStyle(
        "LabelBody",
        fontName=font,
        fontSize=7 if compact else 9 if selected == "a4" else 7.5,
        leading=8 if compact else 12 if selected == "a4" else 10,
        textColor=ink,
    )
    small = ParagraphStyle("LabelSmall", parent=body, fontSize=6, leading=7)
    large = ParagraphStyle(
        "LabelLarge", parent=body, fontSize=10 if compact else 12, leading=12 if compact else 14
    )
    white = ParagraphStyle("LabelWhite", parent=body, textColor=colors.white)
    white_small = ParagraphStyle("LabelWhiteSmall", parent=small, textColor=colors.white)
    white_large = ParagraphStyle("LabelWhiteLarge", parent=large, textColor=colors.white)
    center = ParagraphStyle("LabelCenter", parent=body, alignment=TA_CENTER)
    right = ParagraphStyle("LabelRight", parent=body, alignment=TA_RIGHT)

    def paragraph(value, style=body):
        return Paragraph(escape(str(value)).replace("\n", "<br/>"), style)

    def panel(rows, columns, background=colors.white, commands=()):
        table = LongTable(rows, colWidths=columns, hAlign="LEFT", splitInRow=1)
        table.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 1, ink),
                    ("BACKGROUND", (0, 0), (-1, -1), background),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 3 if not compact else 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3 if not compact else 2),
                    *commands,
                ]
            )
        )
        return table

    def payment_panel(panel_width):
        background = ink if thermal else colors.HexColor("#022c22")
        style = white_large if data["cash_due"] else large
        return panel(
            [
                [
                    [
                        paragraph(
                            "CASH ON COLLECTION"
                            if data["pickup"] and data["cash_due"]
                            else "PAYMENT STATUS",
                            white_small if data["cash_due"] else small,
                        ),
                        paragraph(data["payment"], style),
                    ],
                    paragraph(data["payment_badge"], white if data["cash_due"] else body),
                ]
            ],
            [panel_width - 42, 42],
            background if data["cash_due"] else pale,
        )

    def barcode_panel(panel_width):
        barcode = createBarcodeDrawing(
            "Code128", value=data["tracking"], barHeight=20 if compact else 28, humanReadable=False
        )
        scale = min(1, (panel_width - 20) / barcode.width)
        barcode.scale(scale, 1)
        barcode.width *= scale
        return panel(
            [
                [paragraph(data["tracking_caption"], small)],
                [barcode],
                [paragraph(data["tracking"], center)],
            ],
            [panel_width],
            commands=[
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ],
        )

    def qr_code(size):
        # The QR identifies the order; it does not imply a courier tracking service.
        return createBarcodeDrawing("QR", value=order.number, width=size, height=size, barBorder=2)

    def ship_panel(panel_width, include_qr=False):
        lines = [
            paragraph(data["ship_caption"], small),
            paragraph(data["customer"], large),
            paragraph("TEL: " + data["phone"]),
            paragraph(data["destination"]),
        ]
        if include_qr or selected == "a4":
            lines.append(
                paragraph(data["city"] + (" / " + data["postal"] if data["postal"] else ""), large)
            )
        elif data["postal"]:
            lines.append(paragraph("POSTAL: " + data["postal"], small))
        if include_qr:
            return panel(
                [
                    [
                        lines,
                        [
                            qr_code(42),
                            paragraph("ORDER QR", small),
                            paragraph(data["specs"], small),
                        ],
                    ]
                ],
                [panel_width - 66, 66],
            )
        return panel([[lines]], [panel_width])

    def header(panel_width):
        return panel(
            [
                [
                    [
                        paragraph("retail.", white_large),
                        paragraph("ORDER FULFILLMENT", white_small),
                    ],
                    [paragraph(data["courier"], small), paragraph(data["service"], right)],
                    [paragraph("HUB", white), paragraph(data["hub"], white_large)],
                ]
            ],
            [panel_width * 0.35, panel_width * 0.46, panel_width * 0.19],
            commands=[
                ("BACKGROUND", (0, 0), (0, 0), brand),
                ("BACKGROUND", (2, 0), (2, 0), ink),
                ("LINEBEFORE", (2, 0), (2, 0), 1, ink),
            ],
        )

    def contents_table(panel_width):
        heading = f"PACKAGE CONTENTS / {data['receipt']['quantity']} items"
        if settings["contents"] == "hidden":
            return [
                panel([[paragraph("CONTENTS OMITTED / " + order.number, small)]], [panel_width])
            ]
        if settings["contents"] == "summary":
            return [
                panel(
                    [
                        [
                            paragraph(heading),
                            paragraph(f"{data['receipt']['product_count']} products", right),
                        ]
                    ],
                    [panel_width * 0.68, panel_width * 0.32],
                    pale,
                )
            ]
        rows = [[paragraph(heading, white), paragraph("QTY", white)]]
        if settings["show_prices"]:
            rows[0].append(paragraph("LINE TOTAL", white))
        for item in data["receipt"]["items"]:
            name = item.name + ("\nSKU: " + item.sku if settings["show_skus"] and item.sku else "")
            row = [paragraph(name), paragraph(item.quantity, center)]
            if settings["show_prices"]:
                row.append(paragraph(f"PKR {item.line_total:.2f}", right))
            rows.append(row)
        columns = [panel_width - 94, 28, 66] if settings["show_prices"] else [panel_width - 30, 30]
        table = panel(
            rows,
            columns,
            commands=[
                ("BACKGROUND", (0, 0), (-1, 0), ink),
                ("LINEBELOW", (0, 0), (-1, -1), 0.4, ink),
            ],
        )
        table.repeatRows = 1
        return [table]

    story = [panel([[paragraph(data["warning"])]], [width], pale)] if data["warning"] else []
    if selected == "a4":
        story.extend(
            [
                panel(
                    [
                        [
                            [
                                paragraph("retail.", large),
                                paragraph("PACKING SLIP & DISPATCH MANIFEST", small),
                            ],
                            [
                                paragraph(order.number, right),
                                paragraph(data["receipt"]["date"], right),
                            ],
                        ]
                    ],
                    [width * 0.52, width * 0.48],
                    commands=[("LINEBELOW", (0, 0), (-1, 0), 2, ink)],
                ),
                Spacer(1, 10),
                panel(
                    [
                        [
                            [
                                paragraph("DELIVER TO CUSTOMER", small),
                                paragraph(data["customer"], large),
                                paragraph(data["phone"]),
                                paragraph(data["destination"]),
                                paragraph(data["city"] + " " + data["postal"]),
                            ],
                            [
                                paragraph("SHIPMENT METADATA", small),
                                paragraph(data["courier"] + " / " + data["service"]),
                                paragraph("Tracking: " + data["tracking"]),
                                paragraph(data["specs"]),
                                paragraph(
                                    "Dimensions: " + (settings.get("dimensions") or "Not set")
                                ),
                                paragraph("Payment: " + order.payment_status),
                            ],
                        ]
                    ],
                    [width * 0.5, width * 0.5],
                    pale,
                    commands=[("LINEBEFORE", (1, 0), (1, 0), 1, ink)],
                ),
                Spacer(1, 10),
                *contents_table(width),
                panel(
                    [
                        [
                            paragraph(
                                "PACKER CHECK: [ ] Items verified   [ ] Security seal applied",
                                small,
                            ),
                            paragraph(f"Total units: {data['receipt']['quantity']}", right),
                        ]
                    ],
                    [width * 0.75, width * 0.25],
                ),
                Spacer(1, 18),
                paragraph(
                    "DETACH ALONG DOTTED LINE & AFFIX SHIPPING LABEL TO PARCEL EXTERIOR", small
                ),
                HRFlowable(width="100%", thickness=0.7, dash=3, color=ink),
                Spacer(1, 12),
            ]
        )
        left_width, right_width = width * 0.59 - 12, width * 0.41 - 12
        story.append(
            panel(
                [
                    [
                        [
                            panel(
                                [
                                    [
                                        paragraph("retail.", white_large),
                                        paragraph(
                                            data["service"] + " / HUB: " + data["hub"], white
                                        ),
                                    ]
                                ],
                                [left_width * 0.35, left_width * 0.65],
                                brand,
                            ),
                            ship_panel(left_width),
                            payment_panel(left_width),
                        ],
                        [
                            barcode_panel(right_width),
                            Spacer(1, 7),
                            qr_code(64),
                            paragraph("ORDER QR: " + order.number, small),
                            paragraph(data["receipt"]["date"], small),
                            paragraph(data["specs"], small),
                        ],
                    ]
                ],
                [width * 0.59, width * 0.41],
                commands=[("LINEBEFORE", (1, 0), (1, 0), 1, ink)],
            )
        )
        story.append(
            panel(
                [[paragraph("RETURN IF UNDELIVERED: " + data["return_address"], small)]],
                [width],
                pale,
            )
        )
        if settings.get("instructions"):
            story.append(
                panel([[paragraph("INSTRUCTIONS: " + settings["instructions"], small)]], [width])
            )
    elif compact:
        story.extend(
            [
                panel(
                    [
                        [
                            paragraph("retail.", white_large),
                            paragraph(data["service"] + " / HUB: " + data["hub"], white),
                        ]
                    ],
                    [width * 0.35, width * 0.65],
                    brand,
                ),
                ship_panel(width, include_qr=True),
                payment_panel(width),
                barcode_panel(width),
                panel(
                    [[paragraph(order.number, small), paragraph(data["receipt"]["date"], small)]],
                    [width * 0.5, width * 0.5],
                ),
                panel([[paragraph("RETURN: " + data["return_address"], small)]], [width], pale),
            ]
        )
        if settings.get("instructions"):
            story.append(panel([[paragraph("NOTE: " + settings["instructions"], small)]], [width]))
        story.extend(contents_table(width))
    else:
        story.extend(
            [
                header(width),
                panel(
                    [[paragraph("RETURN IF UNDELIVERED: " + data["return_address"], small)]],
                    [width],
                    pale,
                ),
                ship_panel(width),
                panel(
                    [
                        [
                            paragraph("DESTINATION CITY\n" + data["city"]),
                            paragraph("PARCEL SPECS\n" + data["specs"], right),
                        ]
                    ],
                    [width * 0.5, width * 0.5],
                ),
                payment_panel(width),
                barcode_panel(width),
                panel(
                    [
                        [
                            [
                                paragraph("ORDER ID: " + order.number),
                                paragraph("ORDER DATE: " + data["receipt"]["date"], small),
                                paragraph(
                                    "DIMENSIONS: " + (settings.get("dimensions") or "Not set"),
                                    small,
                                ),
                                paragraph(
                                    "NOTE: " + (settings.get("instructions") or "None"), small
                                ),
                            ],
                            [qr_code(50), paragraph("ORDER QR", small)],
                        ]
                    ],
                    [width - 68, 68],
                ),
                *contents_table(width),
            ]
        )

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

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont(font, 5)
        canvas.setFillColor(ink)
        canvas.drawString(margin, 9, f"{order.number} | Page {doc.page}")
        if doc.page > 1:
            canvas.drawRightString(paper[0] - margin, 9, "CONTINUATION - SAME PARCEL")
        canvas.restoreState()

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    output.seek(0)
    return output
