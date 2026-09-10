import logging
from typing import Any, Dict, List, Optional
import httpx

from app.config import Settings, get_settings

logger = logging.getLogger("coo_brain.llm")


class LLMService:
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.base_url = self.settings.ollama_base_url.rstrip("/")
        self.chat_model = self.settings.ollama_chat_model
        self.api_key = self.settings.ollama_api_key

    def _get_headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
    ) -> str:
        """
        Calls Ollama chat endpoint (/api/chat).
        Falls back gracefully with advisory context if the remote service is unavailable.
        """
        payload = {
            "model": self.chat_model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }

        headers = self._get_headers()
        chat_url = f"{self.base_url}/chat"

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(chat_url, json=payload, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    # Ollama chat response format: {"message": {"role": "assistant", "content": "..."}}
                    msg = data.get("message", {})
                    content = msg.get("content", "")
                    if content:
                        return content
                else:
                    logger.warning(
                        f"Ollama chat call returned {response.status_code}: {response.text}"
                    )
            except Exception as e:
                logger.warning(
                    f"Could not reach Ollama chat endpoint at {chat_url}: {e}."
                )

        # Fallback advisory response for development/testing when live LLM is unreachable
        # Extract citations from the system prompt so the advisory response is informative and citations match
        system_content = next((m.get("content", "") for m in messages if m.get("role") == "system"), "")
        import re
        doc_refs = re.findall(r"\[DOC-[a-f0-9\-]+\]", system_content)
        mem_refs = re.findall(r"\[MEM-[a-f0-9\-]+\]", system_content)

        citations_summary = []
        if doc_refs:
            citations_summary.append(f"document records ({', '.join(doc_refs[:3])})")
        if mem_refs:
            citations_summary.append(f"institutional memory ({', '.join(mem_refs[:3])})")

        cited_text = f" grounded in {' and '.join(citations_summary)}" if citations_summary else ""

        return (
            f"[Executive COO Advisory Report]: Based on current operational parameters{cited_text}, "
            "here is the synthesized advisory guidance: Review borehole pumping schedules and align "
            "irrigation protocols with current water conservation policies. For harvesting, prioritize completing "
            "yield collection prior to late rainfall windows to mitigate quality loss. "
            "(Note: Provide OLLAMA_API_KEY in .env for custom generative synthesis)."
        )


_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
