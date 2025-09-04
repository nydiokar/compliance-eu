from __future__ import annotations

import csv
import hashlib
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from src.core.einvoice.ubl import (
    UBLInvoiceBuilder,
    generate_ubl_invoice,
    Invoice,
    Party,
    InvoiceLine,
    LegalMonetaryTotal,
)
from src.core.intake import load_frame
from src.core.mapping.profiles import load_profile, MappingProfile
from src.logging_conf import get_logger
from src.settings import settings

logger = get_logger("einvoice.batch")


def _sanitize_filename(name: str) -> str:
    name = name.strip().lower()
    name = re.sub(r"[^a-z0-9\-_.]", "_", name)
    return name[:80] if len(name) > 80 else name


def _checksum(file_path: Path) -> str:
    hasher = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _resolve_columns(df: pd.DataFrame, profile: MappingProfile) -> Dict[str, str]:
    """Resolve DataFrame columns to profile targets using sources lists (case-insensitive)."""
    mapping: Dict[str, str] = {}
    lower_cols = {c.lower(): c for c in df.columns}

    for target, spec in profile.columns.items():
        for src in spec.sources:
            src_lower = str(src).lower()
            if src_lower in lower_cols:
                mapping[target] = lower_cols[src_lower]
                break
        # If not found, leave unmapped (may be optional)

    logger.info("einvoice_columns_resolved", mapped=len(mapping), total_targets=len(profile.columns))
    return mapping


def _dec(value: object, default: Decimal = Decimal("0")) -> Decimal:
    try:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return default
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError):
        return default


def _group_by_invoice(df: pd.DataFrame, invoice_id_col: str) -> List[Tuple[str, pd.DataFrame]]:
    if invoice_id_col not in df.columns:
        raise ValueError(f"Required column not found: {invoice_id_col}")
    groups: List[Tuple[str, pd.DataFrame]] = []
    for inv_id, gdf in df.groupby(invoice_id_col):
        groups.append((str(inv_id), gdf.reset_index(drop=True)))
    return groups


def generate_invoices_from_csv(
    input_csv: Path,
    output_dir: Optional[Path] = None,
    org_id: Optional[str] = None,
    xsd_path: Optional[Path] = None,
    profile_name: str = "einvoice_v1",
) -> Dict[str, Path | List[Path]]:
    """Generate UBL invoices from a CSV file and build a registry CSV.

    Returns dict with `registry` and `invoices` list.
    """
    if output_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = settings.output_dir / (org_id or "org") / "einvoice" / timestamp
        output_dir = base
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("einvoice_batch_start", input=str(input_csv), out=str(output_dir))

    # Load data and profile
    df = load_frame(input_csv)
    profile = load_profile(profile_name)
    if not profile:
        raise ValueError(f"Mapping profile not found: {profile_name}")

    # Resolve columns
    colmap = _resolve_columns(df, profile)

    # Required columns for MVP
    required = [
        "invoice_id", "issue_date", "supplier_name", "customer_name",
        "line_description", "quantity", "unit_price"
    ]
    missing = [t for t in required if t not in colmap]
    if missing:
        raise ValueError(f"Missing required columns for e-invoice: {missing}")

    # Group by invoice
    groups = _group_by_invoice(df, colmap["invoice_id"])  # list of (invoice_id, df)

    invoices: List[Path] = []
    registry_rows: List[Dict[str, str]] = []
    currency = "EUR"  # default; could be detected from column later
    builder = UBLInvoiceBuilder()

    for inv_id, gdf in groups:
        try:
            # Parties
            row0 = gdf.iloc[0]
            supplier = Party(
                name=str(row0.get(colmap.get("supplier_name"), "")).strip(),
                tax_id=str(row0.get(colmap.get("supplier_tax_id"), "")).strip() or None,
            )
            customer = Party(
                name=str(row0.get(colmap.get("customer_name"), "")).strip(),
                tax_id=str(row0.get(colmap.get("customer_tax_id"), "")).strip() or None,
            )

            # Lines
            lines: List[InvoiceLine] = []
            total_net = Decimal("0.00")
            total_tax = Decimal("0.00")
            for i, r in gdf.iterrows():
                qty = _dec(r.get(colmap["quantity"]))
                unit_price = _dec(r.get(colmap["unit_price"]))
                line_net = (qty * unit_price).quantize(Decimal("0.01"))
                tax_percent = _dec(r.get(colmap.get("tax_percent"))) if "tax_percent" in colmap else Decimal("0")
                tax_amount = (line_net * tax_percent / Decimal("100")).quantize(Decimal("0.01"))
                total_net += line_net
                total_tax += tax_amount

                lines.append(
                    InvoiceLine(
                        id=str(i + 1),
                        description=str(r.get(colmap["line_description"], "")).strip(),
                        quantity=qty,
                        unit_price=unit_price,
                        line_extension_amount=line_net,
                        tax_percent=tax_percent,
                    )
                )

            totals = LegalMonetaryTotal(
                line_extension_amount=total_net,
                tax_exclusive_amount=total_net,
                tax_inclusive_amount=(total_net + total_tax).quantize(Decimal("0.01")),
                payable_amount=(total_net + total_tax).quantize(Decimal("0.01")),
            )

            inv = Invoice(
                id=inv_id,
                issue_date=str(row0.get(colmap["issue_date"], "")).split(" ")[0],
                currency=currency,
                supplier=supplier,
                customer=customer,
                lines=lines,
                totals=totals,
            )

            # Write XML
            fname = f"inv_{_sanitize_filename(inv_id)}.xml"
            out_file = output_dir / fname
            builder.write(inv, out_file, xsd_path=xsd_path)
            invoices.append(out_file)
            reg = {
                "invoice_id": inv_id,
                "file_path": str(out_file.resolve()),
                "currency": currency,
                "payable_amount": str(totals.payable_amount),
                "checksum": _checksum(out_file),
                "status": "ok",
                "error": "",
            }
        except Exception as e:
            logger.error("einvoice_build_failed", invoice_id=inv_id, error=str(e))
            reg = {
                "invoice_id": inv_id,
                "file_path": "",
                "currency": currency,
                "payable_amount": "0.00",
                "checksum": "",
                "status": "error",
                "error": str(e),
            }
        registry_rows.append(reg)

    # Write registry CSV
    registry_path = output_dir / "registry.csv"
    with open(registry_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "invoice_id",
                "file_path",
                "currency",
                "payable_amount",
                "checksum",
                "status",
                "error",
            ],
        )
        writer.writeheader()
        for row in registry_rows:
            writer.writerow(row)

    logger.info("einvoice_batch_done", invoices=len(invoices), registry=str(registry_path))
    return {"registry": registry_path, "invoices": invoices}

