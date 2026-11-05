# utils/receipt.py
# Robinsons Supermarket Sales Invoice Receipt Generator for SmartRetail Final Revision

from datetime import datetime
from decimal import Decimal
import os

def generate_receipt(sale: dict, items: list[dict], store_config: dict = None) -> str:
    """
    Generates exact Robinsons Supermarket style Sales Invoice text format.
    EXCLUDES customer loyalty info per client directive.
    """
    if store_config is None:
        store_config = {
            "store_name": "O!KIE GROCERY CORPORATION",
            "tin_no": "000-405-340-010",
            "store_address": "Main Branch, Lopez Ave., Batong Malake, Los Banos, Laguna",
            "serial_no": "4CE423DOMF",
            "machine_id": "24103116151605407",
            "terminal_no": "0017",
            "store_no": "0202"
        }

    width = 44
    line_star = "*" * width
    line_dash = "-" * width

    def center(text: str) -> str:
        return text.center(width)

    def row(label: str, value: str) -> str:
        space = width - len(label) - len(value)
        return label + " " * max(space, 1) + value

    # Header section
    lines = [
        center(store_config.get("store_name", "O!KIE GROCERY CORPORATION")),
        center(f"VAT REG TIN {store_config.get('tin_no', '000-405-340-010')}"),
    ]

    # Format multi-line address cleanly to fit within 44-character line width
    raw_address = store_config.get("store_address", "Main Branch, Lopez Ave., Batong Malake, Los Banos, Laguna")
    if "\n" in raw_address:
        addr_parts = raw_address.split("\n")
    else:
        addr_parts = []
        words = raw_address.split(", ")
        current = ""
        for w in words:
            if current:
                test = current + ", " + w
                if len(test) <= width:
                    current = test
                else:
                    addr_parts.append(current)
                    current = w
            else:
                current = w
        if current:
            addr_parts.append(current)

    for addr_line in addr_parts:
        lines.append(center(addr_line))

    lines += [
        center(f"SN: {store_config.get('serial_no', '4CE423DOMF')}"),
        center(f"MIN: {store_config.get('machine_id', '24103116151605407')}"),
        line_star,
        center("SALES INVOICE"),
        line_star,
        "Name:    ___________________________________",
        "TIN:     ___________________________________",
        "ID No:   ___________________________________",
        "Address: ___________________________________",
        "Signature:__________________________________",
    ]

    total_items_qty = 0
    total_promo_savings = Decimal("0.00")

    # Purchased Items
    for item in items:
        name = str(item.get("item_name", "Item"))[:28]
        barcode = str(item.get("barcode", ""))[:14]
        qty = int(item.get("quantity", 1))
        unit_price = Decimal(str(item.get("unit_price", 0)))
        raw_total = Decimal(str(item.get("raw_line_total", unit_price * qty)))
        net_total = Decimal(str(item.get("line_total", raw_total)))
        is_vatable = item.get("is_vatable", 1)
        vat_tag = " V" if is_vatable else " E"
        total_items_qty += qty

        lines.append(f"{name:<26} {barcode:>17}")
        qty_price_str = f"  {qty} x P{float(unit_price):,.2f}"
        total_str = f"P{float(raw_total):,.2f}{vat_tag}"
        space_len = width - len(qty_price_str) - len(total_str)
        lines.append(f"{qty_price_str}{' ' * max(space_len, 1)}{total_str}")

        promo_disc = Decimal(str(item.get("line_promo_discount", 0)))
        promo_tag = item.get("promo_tag", "")

        # Fallback for historical transactions created before promo column addition
        if promo_disc == 0 and len(items) == 1 and sale and Decimal(str(sale.get("discount_amount", 0))) > 0:
            promo_disc = Decimal(str(sale["discount_amount"]))
            promo_tag = "[PROMO DISCOUNT]"
            raw_total = net_total + promo_disc

        if promo_disc > 0:
            total_promo_savings += promo_disc
            disc_label = f"  Less Promo {promo_tag}"[:28]
            disc_val_str = f"-P{float(promo_disc):,.2f}"
            space_disc = width - len(disc_label) - len(disc_val_str)
            lines.append(f"{disc_label}{' ' * max(space_disc, 1)}{disc_val_str}")

    # Totals & Payments
    total = Decimal(str(sale.get("total_amount", 0)))
    payment_method = sale.get("payment_method", "cash").upper()
    cash_received = Decimal(str(sale.get("cash_received", total))) if sale.get("cash_received") is not None else total
    change = Decimal(str(sale.get("change_amount", 0))) if sale.get("change_amount") is not None else Decimal("0.00")

    lines += [
        row("TOTAL", f"P{float(total):,.2f}"),
    ]
    if total_promo_savings > 0:
        lines.append(row("  (Saved via Promos)", f"-P{float(total_promo_savings):,.2f}"))

    lines += [
        row(payment_method, f"P{float(cash_received):,.2f}"),
        row("Change", f"P{float(change):,.2f}"),
        line_star,
    ]

    # Tax Audit Breakdown Box (Philippine Tax Regulations)
    vatable_sales = Decimal(str(sale.get("vatable_sales", 0)))
    vat_exempt_sales = Decimal(str(sale.get("vat_exempt_sales", 0)))
    zero_rated_sales = Decimal(str(sale.get("zero_rated_sales", 0)))
    tax_amount = Decimal(str(sale.get("tax_amount", 0)))

    lines += [
        row("  Vatable Sales", f"{float(vatable_sales):>12.2f}"),
        row("  VAT Exempt Sales", f"{float(vat_exempt_sales):>12.2f}"),
        row("  Zero Rated Sales", f"{float(zero_rated_sales):>12.2f}"),
        row("  VAT (12%)", f"{float(tax_amount):>12.2f}"),
        row("  Total", f"{float(total):>12.2f}"),
        line_star,
    ]

    # Footer Transaction Audit Info
    sale_dt = sale.get("sale_date")
    if isinstance(sale_dt, datetime):
        dt_str = sale_dt.strftime("%m/%d/%Y Time:%H:%M:%S")
    else:
        dt_str = datetime.now().strftime("%m/%d/%Y Time:%H:%M:%S")

    cashier_code = sale.get("cashier_code", "CSH-101")
    cashier_name = sale.get("cashier_name", "Cashier")
    si_no = sale.get("si_number", "SI-0000141533")
    trans_id = sale.get("sale_id", "1881")

    lines += [
        f"Total Items: {total_items_qty}",
        f"Cashier: {cashier_code} {cashier_name}",
        f"Str No: {store_config.get('store_no', '0202')} Date:{dt_str}",
        f"Terminal No: {store_config.get('terminal_no', '0017')}     Trans ID: {trans_id}",
        "This serves as your Sales Invoice",
        f"SI No: {si_no}",
        line_dash,
        center("Tell us how we're doing:"),
        center("customercare@okiegrocery.com"),
        center(f"PN: FP102024-116-0478932-{trans_id:0>5}"),
        center(f"SPM: SP102024-116-0242071-{trans_id:0>5}"),
        "",
    ]

    return "\n".join(lines)


def save_receipt(receipt_text: str, si_number: str) -> str:
    """Save formatted receipt to a text file in assets/receipts."""
    folder = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "receipts")
    os.makedirs(folder, exist_ok=True)
    filename = f"receipt_{si_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    filepath = os.path.join(folder, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(receipt_text)
    return filepath

# Alias
generate_receipt_text = generate_receipt
