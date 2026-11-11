"""Optional Gemini embeddings and the local cosine-similarity calculation."""

import math
from collections.abc import Sequence


EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIMENSIONS = 3072


def build_embedder(api_key: str):
    # Import the provider integration only when embeddings are actually enabled.
    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    return GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL,
        api_key=api_key,
        task_type="RETRIEVAL_DOCUMENT",
        output_dimensionality=EMBEDDING_DIMENSIONS,
    )


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        raise ValueError("Stored recipe embeddings do not match the query embedding dimensions.")
    # A zero-length vector has no direction, so it cannot be similar to a query.
    denominator = math.sqrt(sum(value * value for value in left)) * math.sqrt(
        sum(value * value for value in right)
    )
    if denominator == 0:
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True)) / denominator
