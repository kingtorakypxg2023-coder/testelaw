"""Provedor de IA usando a API da OpenAI.

Usa structured outputs (`response_format=PydanticModel`) com o método `parse`.
"""
from __future__ import annotations

from src.config.settings import settings
from src.models import AnaliseExtraida, Publicacao
from src.services.intelligence.base import IntelligenceError, IntelligenceProvider
from src.services.intelligence.prompts import SYSTEM_PROMPT, montar_prompt_usuario
from src.utils.logger import get_logger

logger = get_logger(__name__)


class OpenAIProvider(IntelligenceProvider):
    """Extração de prazos via modelos da OpenAI."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        api_key = api_key if api_key is not None else settings.openai_api_key
        if not api_key:
            raise IntelligenceError(
                "OPENAI_API_KEY não configurada. Defina-a no .env ou use "
                "AI_PROVIDER=mock para desenvolver sem credenciais."
            )
        try:
            from openai import OpenAI
        except ModuleNotFoundError as exc:  # pragma: no cover - depende do ambiente
            raise IntelligenceError(
                "Pacote 'openai' não instalado. Rode: pip install -r requirements.txt"
            ) from exc

        self._client = OpenAI(api_key=api_key)
        self.model = model or settings.openai_model

    def _extrair(self, publicacao: Publicacao) -> AnaliseExtraida:
        # Compatível com SDKs novos (chat.completions.parse) e antigos (beta.*).
        parse = getattr(self._client.chat.completions, "parse", None)
        if parse is None:
            parse = self._client.beta.chat.completions.parse
        try:
            completion = parse(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": montar_prompt_usuario(publicacao)},
                ],
                response_format=AnaliseExtraida,
            )
        except Exception as exc:  # boundary de integração com a API externa
            raise IntelligenceError(f"Falha na API OpenAI: {exc}") from exc

        analise = completion.choices[0].message.parsed
        if analise is None:
            raise IntelligenceError("OpenAI não retornou saída estruturada válida.")
        return analise
