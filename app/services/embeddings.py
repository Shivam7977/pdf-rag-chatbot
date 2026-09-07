from sentence_transformers import SentenceTransformer

# Loaded once and reused — loading this model is slow, so we don't want
# to reload it on every function call.
_model = None

def get_embedding_model():
    global _model
    if _model is None:
        # all-MiniLM-L6-v2 is small, fast, and runs well on CPU —
        # a solid default for a local-first project like ours.
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def embed_texts(texts: list):
    """
    Takes a list of strings, returns a list of embedding vectors
    (one vector per input string).
    """
    model = get_embedding_model()
    embeddings = model.encode(texts, show_progress_bar=False)
    return embeddings.tolist()  # convert numpy array to plain lists for storage


if __name__ == "__main__":
    # Quick sanity check
    sample_texts = ["What is overfitting?", "The cat sat on the mat."]
    vectors = embed_texts(sample_texts)
    print(f"Generated {len(vectors)} embeddings")
    print(f"Each embedding has {len(vectors[0])} dimensions")
    print("First 5 values of first embedding:", vectors[0][:5])