import pymupdf as fitz

def extract_text_from_pdf(file_path: str):
    """
    Extracts text from a PDF, page by page, keeping track of
    which page each block of text came from (needed later for citations).
    Returns a list of dicts: [{"text": ..., "page": ..., "source": ...}]
    """
    doc = fitz.open(file_path)
    filename = file_path.split("\\")[-1].split("/")[-1]  # works on Windows and Unix paths

    extracted_pages = []

    for page_number, page in enumerate(doc, start=1):
        text = page.get_text()
        if text.strip():  # skip blank pages
            extracted_pages.append({
                "text": text,
                "page": page_number,
                "source": filename
            })

    doc.close()
    return extracted_pages


if __name__ == "__main__":
    # Quick manual test — run this file directly to check it works
    import sys
    test_file = sys.argv[1] if len(sys.argv) > 1 else None
    if not test_file:
        print("Usage: python pdf_parser.py <path_to_pdf>")
    else:
        pages = extract_text_from_pdf(test_file)
        print(f"Extracted {len(pages)} pages with text.")
        print("--- Preview of page 1 ---")
        print(pages[0]["text"][:500] if pages else "No text found")