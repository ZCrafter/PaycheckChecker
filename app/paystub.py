"""Optional: read gross / net / pay date out of a paystub PDF (e.g. downloaded from ADP)."""
import logging
import re
import sys
from datetime import datetime
from pathlib import Path

import pdfplumber

from .config import Config, load

log = logging.getLogger(__name__)


def pdf_text(path: Path) -> str:
    with pdfplumber.open(path) as pdf:
        return "\n".join((page.extract_text() or "") for page in pdf.pages)


def _first(regex: str, text: str):
    m = re.search(regex, text, re.IGNORECASE)
    return m.group(1) if m else None


def parse_stub(path: Path, c: Config):
    """Returns dict(gross, net, pay_date, path) with None for anything not found."""
    text = pdf_text(path)
    gross = _first(c.stub_gross_regex, text)
    net = _first(c.stub_net_regex, text)
    raw_date = _first(c.stub_date_regex, text)
    pay_date = None
    if raw_date:
        try:
            pay_date = datetime.strptime(raw_date, c.stub_date_format).date()
        except ValueError:
            pass
    return {
        "gross": float(gross.replace(",", "")) if gross else None,
        "net": float(net.replace(",", "")) if net else None,
        "pay_date": pay_date,
        "path": path,
    }


def find_stub_for_payday(c: Config, payday):
    """Scans STUB_DIR for a PDF whose pay date equals `payday`."""
    if not c.stub_dir.exists():
        return None
    for pdf in sorted(c.stub_dir.glob("*.pdf")):
        try:
            info = parse_stub(pdf, c)
        except Exception as e:
            log.warning("Could not read %s: %s", pdf, e)
            continue
        if info["pay_date"] == payday:
            return info
    return None


if __name__ == "__main__":
    # Debug tool:  python -m app.paystub path/to/stub.pdf
    if len(sys.argv) < 2:
        sys.exit("usage: python -m app.paystub stub.pdf")
    cfg = load()
    p = Path(sys.argv[1])
    print("----- extracted text -----")
    print(pdf_text(p))
    print("----- parsed -----")
    print(parse_stub(p, cfg))
    print("If a value is None, adjust STUB_*_REGEX in .env to match the text above.")
