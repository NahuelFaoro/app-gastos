"""Comprueba OCR real de imagen y PDF escaneado con un comprobante sintético."""
import tempfile
from pathlib import Path


def main():
    import fitz
    from app.scanner import extract_text
    with tempfile.TemporaryDirectory(prefix="appgastos_test_ocr_") as folder:
        image = Path(folder) / "ticket.png"
        pdf = Path(folder) / "ticket.pdf"
        document = fitz.open()
        page = document.new_page(width=400, height=260)
        page.insert_text((30, 50), "TEST RECEIPT", fontsize=24)
        page.insert_text((30, 100), "TOTAL 1234.50", fontsize=24)
        page.insert_text((30, 150), "DATE 2026-09-13", fontsize=22)
        page.get_pixmap(matrix=fitz.Matrix(2, 2)).save(image)
        document.close()
        scanned = fitz.open()
        page = scanned.new_page(width=400, height=260)
        page.insert_image(page.rect, filename=str(image))
        scanned.save(pdf)
        scanned.close()
        for path in (image, pdf):
            text = " ".join(extract_text(path)).upper()
            assert "TOTAL" in text and "1234" in text, (path.suffix, text)
            print(path.suffix, "OCR_OK", text)
    print("APP_GASTOS_PACKAGED_OCR_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
