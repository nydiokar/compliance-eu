from pathlib import Path

from src.core.einvoice import generate_invoices_from_csv


def test_einvoice_batch_from_minimal_csv(tmp_path: Path):
    # Create a minimal CSV with two invoice lines under the same invoice
    csv_path = tmp_path / "invoices.csv"
    csv_path.write_text(
        """Invoice ID,Issue Date,Supplier,Customer,Description,Qty,Unit Price,VAT %
INV-1,2025-01-10,Supplier Ltd,Customer LLC,Service A,1,100,20
INV-1,2025-01-10,Supplier Ltd,Customer LLC,Service B,2,50,20
""",
        encoding="utf-8",
    )

    result = generate_invoices_from_csv(csv_path, org_id="test_org")
    registry = result["registry"]
    invoices = result["invoices"]

    assert registry.exists()
    assert len(invoices) == 1
    xml = invoices[0].read_text(encoding="utf-8")
    assert "<cbc:ID>INV-1</cbc:ID>" in xml

