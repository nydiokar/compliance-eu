from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

from lxml import etree

from src.logging_conf import get_logger

logger = get_logger("einvoice.ubl")


NSMAP = {
    None: "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",  # default namespace
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
}


def _cbc(tag: str) -> str:
    return f"{{{NSMAP['cbc']}}}{tag}"


def _cac(tag: str) -> str:
    return f"{{{NSMAP['cac']}}}{tag}"


@dataclass
class Party:
    name: str
    tax_id: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    street: Optional[str] = None


@dataclass
class InvoiceLine:
    id: str
    description: str
    quantity: Decimal
    unit_price: Decimal
    line_extension_amount: Decimal
    tax_percent: Decimal = Decimal("0")


@dataclass
class LegalMonetaryTotal:
    line_extension_amount: Decimal
    tax_exclusive_amount: Decimal
    tax_inclusive_amount: Decimal
    payable_amount: Decimal


@dataclass
class Invoice:
    id: str
    issue_date: str  # ISO date YYYY-MM-DD
    currency: str
    supplier: Party
    customer: Party
    lines: List[InvoiceLine] = field(default_factory=list)
    totals: Optional[LegalMonetaryTotal] = None


class UBLInvoiceBuilder:
    """Minimal UBL 2.1 Invoice XML builder (MVP scope)."""

    def __init__(self, profile_id: str = "bii04", customization_id: str = "1.0"):
        self.profile_id = profile_id
        self.customization_id = customization_id

    def build_tree(self, invoice: Invoice) -> etree._ElementTree:
        root = etree.Element("{urn:oasis:names:specification:ubl:schema:xsd:Invoice-2}Invoice", nsmap=NSMAP)

        # Identifiers
        etree.SubElement(root, _cbc("CustomizationID")).text = self.customization_id
        etree.SubElement(root, _cbc("ProfileID")).text = self.profile_id
        etree.SubElement(root, _cbc("ID")).text = invoice.id
        etree.SubElement(root, _cbc("IssueDate")).text = invoice.issue_date
        etree.SubElement(root, _cbc("DocumentCurrencyCode")).text = invoice.currency

        # Supplier
        acc_supplier = etree.SubElement(root, _cac("AccountingSupplierParty"))
        party = etree.SubElement(acc_supplier, _cac("Party"))
        etree.SubElement(party, _cbc("Name")).text = invoice.supplier.name
        if invoice.supplier.tax_id:
            party_tax = etree.SubElement(party, _cac("PartyTaxScheme"))
            etree.SubElement(party_tax, _cbc("CompanyID")).text = invoice.supplier.tax_id
        self._append_address(party, invoice.supplier)

        # Customer
        acc_customer = etree.SubElement(root, _cac("AccountingCustomerParty"))
        party = etree.SubElement(acc_customer, _cac("Party"))
        etree.SubElement(party, _cbc("Name")).text = invoice.customer.name
        if invoice.customer.tax_id:
            party_tax = etree.SubElement(party, _cac("PartyTaxScheme"))
            etree.SubElement(party_tax, _cbc("CompanyID")).text = invoice.customer.tax_id
        self._append_address(party, invoice.customer)

        # Lines
        for line in invoice.lines:
            self._append_line(root, line, invoice.currency)

        # Totals
        if invoice.totals:
            self._append_totals(root, invoice.totals, invoice.currency)

        return etree.ElementTree(root)

    def _append_address(self, party_el: etree._Element, party: Party) -> None:
        if not (party.country or party.city or party.street or party.postal_code):
            return
        postal = etree.SubElement(party_el, _cac("PostalAddress"))
        if party.street:
            etree.SubElement(postal, _cbc("StreetName")).text = party.street
        if party.city:
            etree.SubElement(postal, _cbc("CityName")).text = party.city
        if party.postal_code:
            etree.SubElement(postal, _cbc("PostalZone")).text = party.postal_code
        if party.country:
            country = etree.SubElement(postal, _cac("Country"))
            etree.SubElement(country, _cbc("IdentificationCode")).text = party.country

    def _append_line(self, root: etree._Element, line: InvoiceLine, currency: str) -> None:
        line_el = etree.SubElement(root, _cac("InvoiceLine"))
        etree.SubElement(line_el, _cbc("ID")).text = str(line.id)
        etree.SubElement(line_el, _cbc("InvoicedQuantity"), unitCode="EA").text = f"{line.quantity}"
        etree.SubElement(
            line_el, _cbc("LineExtensionAmount"), currencyID=currency
        ).text = f"{line.line_extension_amount:.2f}"

        item = etree.SubElement(line_el, _cac("Item"))
        etree.SubElement(item, _cbc("Description")).text = line.description

        price = etree.SubElement(line_el, _cac("Price"))
        etree.SubElement(price, _cbc("PriceAmount"), currencyID=currency).text = f"{line.unit_price:.2f}"

        if line.tax_percent and Decimal(line.tax_percent) > 0:
            tax_total = etree.SubElement(line_el, _cac("TaxTotal"))
            tax_sub = etree.SubElement(tax_total, _cac("TaxSubtotal"))
            etree.SubElement(tax_sub, _cbc("Percent")).text = f"{line.tax_percent:.2f}"

    def _append_totals(self, root: etree._Element, totals: LegalMonetaryTotal, currency: str) -> None:
        lmt = etree.SubElement(root, _cac("LegalMonetaryTotal"))
        etree.SubElement(lmt, _cbc("LineExtensionAmount"), currencyID=currency).text = f"{totals.line_extension_amount:.2f}"
        etree.SubElement(lmt, _cbc("TaxExclusiveAmount"), currencyID=currency).text = f"{totals.tax_exclusive_amount:.2f}"
        etree.SubElement(lmt, _cbc("TaxInclusiveAmount"), currencyID=currency).text = f"{totals.tax_inclusive_amount:.2f}"
        etree.SubElement(lmt, _cbc("PayableAmount"), currencyID=currency).text = f"{totals.payable_amount:.2f}"

    def write(
        self,
        invoice: Invoice,
        output_path: Path,
        xsd_path: Optional[Path] = None,
        pretty_print: bool = True,
    ) -> Path:
        """Write UBL Invoice XML to file. Optionally validate against XSD if provided."""
        tree = self.build_tree(invoice)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        tree.write(str(output_path), encoding="utf-8", xml_declaration=True, pretty_print=pretty_print)

        if xsd_path and xsd_path.exists():
            try:
                schema_doc = etree.parse(str(xsd_path))
                schema = etree.XMLSchema(schema_doc)
                schema.assertValid(tree)
                logger.info("UBL invoice validated against XSD", file=str(output_path))
            except Exception as e:
                logger.error("UBL XSD validation failed", error=str(e), file=str(output_path))
                # Surface but do not crash in MVP
        return output_path


def generate_ubl_invoice(payload: Dict[str, Any], output_path: Path, xsd_path: Optional[Path] = None) -> Path:
    """Generate a minimal UBL invoice XML from a dict payload and write to disk.

    Expected payload keys: id, issue_date, currency, supplier{}, customer{}, lines[], totals{}
    """
    inv = Invoice(
        id=str(payload["id"]),
        issue_date=str(payload["issue_date"]),
        currency=str(payload.get("currency", "EUR")),
        supplier=Party(**payload["supplier"]),
        customer=Party(**payload["customer"]),
        lines=[InvoiceLine(**l) for l in payload.get("lines", [])],
        totals=LegalMonetaryTotal(**payload["totals"]) if payload.get("totals") else None,
    )
    builder = UBLInvoiceBuilder()
    return builder.write(inv, output_path=output_path, xsd_path=xsd_path)
