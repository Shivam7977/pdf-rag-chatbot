"""
Vision provider abstraction for describing images/charts extracted from
PDFs. Two implementations share one interface so the rest of the pipeline
never cares which one is active:

  - OllamaVisionProvider — local (llava via Ollama), used in dev
  - MistralVisionProvider — hosted (Pixtral), used in production

Selected via the VISION_PROVIDER env var ("ollama" | "mistral"), the same
pattern already used for the text-LLM provider switch.
"""
import os
import base64
from abc import ABC, abstractmethod

DESCRIPTION_PROMPT_TEMPLATE = """You are describing an image or chart extracted from a PDF document, for use in a \
retrieval system. Write a concise, factual description (3-5 sentences) that \
would let someone answer questions about this image WITHOUT seeing it.

- If it's a chart/graph: describe what is plotted, the overall trend, and \
preserve specific labels/numbers/axis values that are readable.
- If it's a photo/diagram: describe the key visual content and any labels.
- Do not speculate about anything not visibly present.
- Do not start with phrases like "This image shows" — just describe it directly.

{context_block}"""


class VisionProvider(ABC):
    @abstractmethod
    def describe(self, image_bytes: bytes, context: str | None = None) -> str:
        """Returns a text description of the given image."""
        raise NotImplementedError

    def describe_batch(self, images: list[bytes], contexts: list[str | None]) -> list[str]:
        """
        Default: sequential. Hosted providers that can safely handle
        concurrent requests (e.g. MistralVisionProvider) override this for
        better throughput; a local model (Ollama) should NOT be hit
        concurrently — one model instance, one request at a time.
        """
        return [self.describe(img, ctx) for img, ctx in zip(images, contexts)]

    def _build_prompt(self, context: str | None) -> str:
        context_block = f"Nearby caption/text on the page: \"{context}\"" if context else ""
        return DESCRIPTION_PROMPT_TEMPLATE.format(context_block=context_block)


class OllamaVisionProvider(VisionProvider):
    def __init__(self, model: str | None = None):
        import ollama
        self._ollama = ollama
        self.model = model or os.getenv("OLLAMA_VISION_MODEL", "llava")

    def describe(self, image_bytes: bytes, context: str | None = None) -> str:
        response = self._ollama.chat(
            model=self.model,
            messages=[{
                "role": "user",
                "content": self._build_prompt(context),
                "images": [image_bytes],
            }],
        )
        return response["message"]["content"].strip()


class MistralVisionProvider(VisionProvider):
    def __init__(self, model: str | None = None, api_key: str | None = None):
        from mistralai import Mistral
        self.model = model or os.getenv("MISTRAL_VISION_MODEL", "pixtral-12b-2409")
        key = api_key or os.getenv("MISTRAL_API_KEY")
        if not key:
            raise RuntimeError("MISTRAL_API_KEY is not set.")
        self._client = Mistral(api_key=key)

    def _to_data_url(self, image_bytes: bytes) -> str:
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        return f"data:image/png;base64,{b64}"

    def describe(self, image_bytes: bytes, context: str | None = None) -> str:
        response = self._client.chat.complete(
            model=self.model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": self._build_prompt(context)},
                    {"type": "image_url", "image_url": self._to_data_url(image_bytes)},
                ],
            }],
        )
        return response.choices[0].message.content.strip()

    def describe_batch(self, images: list[bytes], contexts: list[str | None]) -> list[str]:
        # Hosted API — safe to fan requests out concurrently rather than
        # waiting on each one sequentially, since Mistral's endpoint handles
        # concurrent requests fine (unlike a single local Ollama instance).
        import concurrent.futures

        def _call(args):
            img, ctx = args
            return self.describe(img, ctx)

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            return list(pool.map(_call, zip(images, contexts)))


_PROVIDER_REGISTRY = {
    "ollama": OllamaVisionProvider,
    "mistral": MistralVisionProvider,
}


def get_vision_provider() -> VisionProvider:
    name = os.getenv("VISION_PROVIDER", "ollama").lower()
    if name not in _PROVIDER_REGISTRY:
        raise ValueError(f"Unknown VISION_PROVIDER '{name}'. Expected one of {list(_PROVIDER_REGISTRY)}.")
    return _PROVIDER_REGISTRY[name]()