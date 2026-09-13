import httpx

from app.config import get_settings


settings = get_settings()

OLLAMA_URL = settings.ollama_base_url
EMBEDDING_MODEL = settings.ollama_embedding_model


async def create_embedding(
    text: str,
) -> list[float]:
    """
    Create an embedding using a local Ollama
    embedding model.
    """

    if not text or not text.strip():
        raise ValueError(
            "Cannot create embedding from empty text."
        )

    payload = {
        "model": EMBEDDING_MODEL,
        "input": text.strip(),
    }

    try:

        async with httpx.AsyncClient(
            timeout=60.0
        ) as client:

            response = await client.post(
                f"{OLLAMA_URL}/api/embed",
                json=payload,
            )

            response.raise_for_status()

            data = response.json()

    except httpx.HTTPError as error:

        raise RuntimeError(
            f"Failed to connect to Ollama "
            f"embedding service: {error}"
        ) from error

    embeddings = data.get("embeddings")

    if not embeddings:
        raise RuntimeError(
            f"Ollama returned no embeddings. "
            f"Make sure '{EMBEDDING_MODEL}' "
            f"is installed."
        )

    return embeddings[0]