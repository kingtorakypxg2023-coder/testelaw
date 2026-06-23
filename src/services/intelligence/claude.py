"""Provedor de IA usando a API da Anthropic (Claude) — provedor padrão.

Usa saída estruturada nativa via `client.messages.parse(..., output_format=...)`,
que valida a resposta contra o schema Pydantic `AnaliseExtraida`.
"""
from __future__ import annotations

from src.config.settings import settings
from src.models import AnaliseExtraida, Publicacao
from src.services.intelligence.base import IntelligenceError, IntelligenceProvider
from src.services.intelligence.prompts import SYSTEM_PROMPT, montar_prompt_usuario
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ClaudeProvider(IntelligenceProvider):
    """Extração de prazos via modelos Claude (Anthropic)."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        api_key = api_key if api_key is not None else settings.anthropic_api_key
        if not api_key:
            raise IntelligenceError(
                "ANTHROPIC_API_KEY não configurada. Defina-a no .env ou use "
                "AI_PROVIDER=mock para desenvolver sem credenciais."
            )
        try:
            import anthropic
        except ModuleNotFoundError as exc:  # pragma: no cover - depende do ambiente
            raise IntelligenceError(
                "Pacote 'anthropic' não instalado. Rode: pip install -r requirements.txt"
            ) from exc

        self._anthropic = anthropic
        self._client = anthropic.Anthropic(api_key=api_key)
        self.model = model or settings.claude_model

    def _extrair(self, publicacao: Publicacao) -> AnaliseExtraida:
        try:
            response = self._client.messages.parse(
                model=self.model,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                messages=[
                    {"role": "user", "content": montar_prompt_usuario(publicacao)}
                ],
                output_format=AnaliseExtraida,
            )
        except self._anthropic.APIError as exc:
            raise IntelligenceError(f"Falha na API Anthropic: {exc}") from exc

        if response.stop_reason == "refusal":
            raise IntelligenceError(
                "A IA recusou a análise da publicação (stop_reason=refusal)."
            )
        analise = response.parsed_output
        if analise is None:
            raise IntelligenceError("A IA não retornou saída estruturada válida.")
        return analise
