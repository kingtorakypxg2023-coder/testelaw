"""Provedor de IA usando a API do Google Gemini.

Usa saída estruturada via `response_schema` (Pydantic) do SDK `google-genai`.
"""
from __future__ import annotations

from src.config.settings import settings
from src.models import AnaliseExtraida, Publicacao
from src.services.intelligence.base import IntelligenceError, IntelligenceProvider
from src.services.intelligence.prompts import SYSTEM_PROMPT, montar_prompt_usuario
from src.utils.logger import get_logger

logger = get_logger(__name__)


class GeminiProvider(IntelligenceProvider):
    """Extração de prazos via modelos Gemini (Google)."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        api_key = api_key if api_key is not None else settings.gemini_api_key
        if not api_key:
            raise IntelligenceError(
                "GEMINI_API_KEY não configurada. Defina-a no .env ou use "
                "AI_PROVIDER=mock para desenvolver sem credenciais."
            )
        try:
            from google import genai
            from google.genai import types as genai_types
        except ModuleNotFoundError as exc:  # pragma: no cover - depende do ambiente
            raise IntelligenceError(
                "Pacote 'google-genai' não instalado. Rode: pip install -r requirements.txt"
            ) from exc

        self._types = genai_types
        self._client = genai.Client(api_key=api_key)
        self.model = model or settings.gemini_model

    def _extrair(self, publicacao: Publicacao) -> AnaliseExtraida:
        try:
            response = self._client.models.generate_content(
                model=self.model,
                contents=montar_prompt_usuario(publicacao),
                config=self._types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_schema=AnaliseExtraida,
                ),
            )
        except Exception as exc:  # SDK do Gemini não expõe uma base estável de erros
            raise IntelligenceError(f"Falha na API Gemini: {exc}") from exc

        analise = response.parsed
        if analise is None:
            if not response.text:
                raise IntelligenceError("Gemini não retornou conteúdo.")
            analise = AnaliseExtraida.model_validate_json(response.text)
        return analise
