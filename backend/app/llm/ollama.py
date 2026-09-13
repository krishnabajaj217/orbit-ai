import json
from collections.abc import AsyncIterator

import httpx

from ..config import get_settings


class OllamaError(RuntimeError):
    pass


async def is_reachable() -> bool:
    settings = get_settings()

    try:
        async with httpx.AsyncClient(timeout=3) as client:
            response = await client.get(
                f"{settings.ollama_base_url.rstrip('/')}/api/tags"
            )

            return response.is_success

    except httpx.HTTPError:
        return False


async def stream_chat(
    messages: list[dict[str, str]],
) -> AsyncIterator[str]:

    settings = get_settings()

    payload = {
        "model": settings.ollama_model,

        "messages": messages,

        "stream": True,

        # Keep Gemma loaded in memory.
        # This avoids repeatedly loading the model.
        "keep_alive": "10m",

        "options": {
            # Smaller context = less work for your RTX 2050.
            "num_ctx": 2048,

            # More deterministic responses.
            "temperature": 0.2,
        },
    }

    try:

        timeout = httpx.Timeout(
            120.0,
            connect=5.0,
        )

        async with httpx.AsyncClient(
            timeout=timeout,
        ) as client:

            async with client.stream(
                "POST",
                f"{settings.ollama_base_url.rstrip('/')}/api/chat",
                json=payload,
            ) as response:

                if response.status_code == 404:

                    raise OllamaError(
                        f"The configured model "
                        f"'{settings.ollama_model}' "
                        "is unavailable."
                    )

                response.raise_for_status()

                async for line in response.aiter_lines():

                    if not line:
                        continue

                    try:
                        data = json.loads(line)

                    except json.JSONDecodeError:
                        continue

                    if data.get("error"):

                        raise OllamaError(
                            "Ollama returned an error while "
                            "generating the response."
                        )

                    chunk = (
                        data
                        .get("message", {})
                        .get("content", "")
                    )

                    if chunk:
                        yield chunk

    except OllamaError:
        raise

    except httpx.ConnectError as error:

        raise OllamaError(
            "Ollama is not running. "
            "Start it with `ollama serve`."
        ) from error

    except httpx.TimeoutException as error:

        raise OllamaError(
            "Ollama took too long to respond. "
            "Please try again."
        ) from error

    except httpx.HTTPError as error:

        raise OllamaError(
            "Could not connect to Ollama. "
            "Please check its status and try again."
        ) from error