import sys
sys.path.append(".")
from app.services.pdf_parser import extract_text_from_pdf
from app.services.chunker import chunk_pages
from app.db.chroma import add_chunks
from app.services.bm25_retriever import build_bm25_index

PDF_FILES = [
    "data/uploads/22744iied.pdf",
    "data/uploads/paper1.pdf",
    "data/uploads/paper2.pdf",
]

def ingest_all():
    total_chunks = 0
    for pdf_path in PDF_FILES:
        print(f"Processing: {pdf_path}")
        pages = extract_text_from_pdf(pdf_path)
        chunks = chunk_pages(pages)
        count = add_chunks(chunks)
        print(f"  -> {count} chunks added")
        total_chunks += count
    print(f"\nTotal chunks across all documents: {total_chunks}")

if __name__ == "__main__":
    ingest_all()
    
# Ingestion ke baad BM25 index ko force-rebuild karo
build_bm25_index(force_rebuild=True)
print("BM25 index rebuilt.")    