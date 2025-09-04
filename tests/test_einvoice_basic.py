from pathlib import Path

from src.core.einvoice import generate_ubl_invoice


def test_generate_minimal_ubl_invoice(tmp_path: Path):
    payload = {
        "id": "INV-001",
        "issue_date": "2025-01-15",
        "currency": "EUR",
        "supplier": {
            "name": "Supplier Ltd",
            "tax_id": "BG123456789",
            "country": "BG",
            "city": "Sofia",
            "postal_code": "1000",
            "street": "1 Main St",
        },
        "customer": {
            "name": "Customer LLC",
            "tax_id": "BG987654321",
            "country": "BG",
            "city": "Sofia",
            "postal_code": "1000",
            "street": "2 Oak Ave",
        },
        "lines": [
            {
                "id": "1",
                "description": "Service fee",
                "quantity": 1,
                "unit_price": 100,
                "line_extension_amount": 100,
                "tax_percent": 20,
            }
        ],
        "totals": {
            "line_extension_amount": 100,
            "tax_exclusive_amount": 100,
            "tax_inclusive_amount": 120,
            "payable_amount": 120,
        },
    }

    out = tmp_path / "invoice.xml"
    result_path = generate_ubl_invoice(payload, out)
    assert result_path.exists()
    xml = result_path.read_text(encoding="utf-8")
    assert "<cbc:ID>INV-001</cbc:ID>" in xml
    assert "<cbc:DocumentCurrencyCode>EUR</cbc:DocumentCurrencyCode>" in xml
    assert "<cbc:Name>Supplier Ltd</cbc:Name>" in xml

