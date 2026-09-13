r"""
Temporary debug script — dumps the full parsed output of a PDF to a text file
so it can be reviewed properly instead of squinting at truncated terminal output.
Not part of the production pipeline; delete after use.

Usage:
    python dump_pdf.py data\uploads\paper1.pdf paper1_output.txt
"""
import sys
from app.services.pdf_parser import extract_text_from_pdf

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python dump_pdf.py <path_to_pdf> <output_txt_path>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    output_path = sys.argv[2]

    pages = extract_text_from_pdf(pdf_path)

    with open(output_path, "w", encoding="utf-8") as f:
        for p in pages:
            f.write(f"--- Page {p['page']} ---\n")
            f.write(p["text"])
            f.write("\n\n")

    print(f"Wrote {len(pages)} pages to {output_path}")