# evaluation/verify_pages.py
import sys
sys.path.append(".")
from app.db.chroma import get_collection

def verify_dataset(dataset):
    collection = get_collection()
    all_data = collection.get(include=["documents", "metadatas"])

    for item in dataset:
        keywords = item["expected_keywords"]
        source = item["expected_source"]
        claimed_page = item["expected_page"]

        # Find chunks from the right document that contain the keywords
        matches = []
        for doc, meta in zip(all_data["documents"], all_data["metadatas"]):
            if meta["source"] != source:
                continue
            # check if most keywords appear in this chunk
            hits = sum(1 for kw in keywords if kw.lower() in doc.lower())
            if hits >= len(keywords) // 2 + 1:  # majority of keywords match
                matches.append((meta["page"], hits))

        actual_pages = sorted(set(p for p, h in matches))
        status = "OK" if claimed_page in actual_pages else "MISMATCH"

        print(f"[{status}] \"{item['question'][:50]}...\"")
        print(f"    claimed page: {claimed_page} | found on pages: {actual_pages}")


if __name__ == "__main__":
    import json
    with open("evaluation/dataset.json", "r", encoding="utf-8") as f:
        dataset = json.load(f)
    verify_dataset(dataset)