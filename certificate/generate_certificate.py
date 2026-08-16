#!/usr/bin/env python3
"""
generate_certificate.py — iCorporate certificate generator

Fills the certificate-template.svg with a recipient's details, embeds a
QR code linking to the verification page, outputs a print-ready PDF,
and appends the new certificate to certificates.json.

SETUP (run once):
    pip install cairosvg qrcode[pil] --break-system-packages

USAGE:
    python3 generate_certificate.py \
        --id ICORP-INT-0009 \
        --name "Kwame Mensah" \
        --track DevOps \
        --start "1 June 2026" \
        --end "31 August 2026" \
        --issued "31 August 2026"

    --track accepts: DevOps | "IT Infrastructure" | or any custom text

This will produce:
    output/ICORP-INT-0009-Kwame-Mensah.pdf
and add a matching entry to certificates.json in the same folder.
"""

import argparse
import base64
import json
import os
import re
import sys
from datetime import date


def today_formatted():
    """Returns today's date as e.g. 'Aug 16, 2026'."""
    return date.today().strftime("%b %d, %Y")

TEMPLATE_SVG = "certificate-template.svg"
CERT_JSON = "certificates.json"
OUTPUT_DIR = "output"


def build_qr(cert_id):
    import qrcode
    from qrcode.constants import ERROR_CORRECT_M
    from io import BytesIO

    url = f"https://icorporate.net/verify?id={cert_id}"
    qr = qrcode.QRCode(border=1, error_correction=ERROR_CORRECT_M)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0B1220", back_color="#FAF9F6")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def fill_template(args):
    with open(TEMPLATE_SVG, "r", encoding="utf-8") as f:
        svg = f.read()

    svg = svg.replace("[Recipient Full Name]", args.name)
    svg = svg.replace("[Internship Track]", args.track)
    svg = svg.replace("[Start Date]", args.start)
    svg = svg.replace("[End Date]", args.end)
    svg = svg.replace("[Date Issued]", args.issued)
    svg = svg.replace("[ICORP-INT-0000]", args.id)

    # swap in a QR code specific to this certificate's ID — only touch the
    # image tagged id="qrImage", never the signature image
    qr_b64 = build_qr(args.id)
    pattern = re.compile(
        r'(<image id="qrImage" href=")data:image/png;base64,[A-Za-z0-9+/=]+(")'
    )
    if not pattern.search(svg):
        raise RuntimeError(
            'Could not find <image id="qrImage" ...> in the template. '
            "Make sure certificate-template.svg has the id=\"qrImage\" tag."
        )
    svg = pattern.sub(lambda m: f'{m.group(1)}data:image/png;base64,{qr_b64}{m.group(2)}', svg)
    return svg


def write_pdf(svg_content, out_path):
    import cairosvg
    cairosvg.svg2pdf(bytestring=svg_content.encode("utf-8"), write_to=out_path)


def update_registry(args):
    entry = {
        "id": args.id,
        "name": args.name,
        "track": f"{args.track} Internship Program" if "Internship" not in args.track else args.track,
        "start": args.start,
        "end": args.end,
        "issued": args.issued,
        "status": "valid",
    }

    if os.path.exists(CERT_JSON):
        with open(CERT_JSON, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                print(f"WARNING: {CERT_JSON} is not valid JSON. Fix it before running this script, "
                      f"or a fresh certificates.json will be created and overwrite it.")
                data = []
    else:
        data = []

    # avoid duplicate IDs — update in place if it already exists
    data = [c for c in data if c.get("id") != args.id]
    data.append(entry)

    with open(CERT_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")

    print(f"Updated {CERT_JSON} ({len(data)} certificates on record)")


def main():
    parser = argparse.ArgumentParser(description="Generate an iCorporate certificate PDF.")
    parser.add_argument("--id", required=True, help="Certificate number, e.g. ICORP-INT-0009")
    parser.add_argument("--name", required=True, help="Recipient full name")
    parser.add_argument("--track", required=True, help='e.g. "DevOps" or "IT Infrastructure"')
    parser.add_argument("--start", required=True, help='e.g. "1 June 2026"')
    parser.add_argument("--end", required=True, help='e.g. "31 August 2026"')
    parser.add_argument("--issued", default=None,
                         help='e.g. "31 August 2026" — defaults to today\'s date if omitted')
    parser.add_argument("--skip-registry", action="store_true",
                         help="Generate the PDF only, don't touch certificates.json")
    args = parser.parse_args()

    if args.issued is None:
        args.issued = today_formatted()
        print(f"No --issued given, using today's date: {args.issued}")

    if not os.path.exists(TEMPLATE_SVG):
        sys.exit(f"ERROR: {TEMPLATE_SVG} not found in this folder. "
                  f"Make sure it's saved alongside this script.")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    svg_content = fill_template(args)

    safe_name = re.sub(r"[^A-Za-z0-9]+", "-", args.name).strip("-")
    out_path = os.path.join(OUTPUT_DIR, f"{args.id}-{safe_name}.pdf")
    write_pdf(svg_content, out_path)
    print(f"Certificate created: {out_path}")

    if not args.skip_registry:
        update_registry(args)
        print("Don't forget to git add/commit/push certificates.json so verification goes live.")


if __name__ == "__main__":
    main()
