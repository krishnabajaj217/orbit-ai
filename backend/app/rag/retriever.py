import math

from app.rag.memory_store import load_memories
from app.rag.ollama_embeddings import create_embedding


def cosine_similarity(
    vector_a: list[float],
    vector_b: list[float],
) -> float:
    """
    Calculate cosine similarity between
    two vectors.
    """

    if not vector_a or not vector_b:
        return 0.0

    if len(vector_a) != len(vector_b):
        return 0.0

    dot_product = sum(
        a * b
        for a, b in zip(
            vector_a,
            vector_b,
        )
    )

    magnitude_a = math.sqrt(
        sum(
            value * value
            for value in vector_a
        )
    )

    magnitude_b = math.sqrt(
        sum(
            value * value
            for value in vector_b
        )
    )

    if (
        magnitude_a == 0
        or magnitude_b == 0
    ):
        return 0.0

    return dot_product / (
        magnitude_a * magnitude_b
    )


async def retrieve_memories(
    user_id: str,
    query: str,
    top_k: int = 5,
) -> list[dict]:
    """
    Retrieve the most relevant memories
    belonging to one user.
    """

    if not query or not query.strip():
        return []

    memories = load_memories(user_id)

    if not memories:
        return []

    query_embedding = await create_embedding(
        query
    )

    results = []

    for memory in memories:

        embedding = memory.get(
            "embedding"
        )

        if not embedding:
            continue

        similarity = cosine_similarity(
            query_embedding,
            embedding,
        )

        results.append(
            {
                **memory,
                "similarity": similarity,
            }
        )

    results.sort(
        key=lambda item: (
            item.get(
                "similarity",
                0.0,
            ),
            item.get(
                "importance",
                0.0,
            ),
        ),
        reverse=True,
    )

    return results[:top_k]