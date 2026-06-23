"""Cliente de captura via API da Jusbrasil (Etapa 1).

IMPORTANTE: o endpoint, o esquema de autenticação e o formato da resposta da
API da Jusbrasil **não são públicos/estáveis** e devem ser confirmados contra
a documentação oficial / o contrato fornecido junto com a credencial. Por isso:

  * a URL base e o caminho da busca são configuráveis via `.env`
    (`JUSBRASIL_API_BASE_URL`, `JUSBRASIL_SEARCH_PATH`);
  * o mapeamento da resposta para `Publicacao` está isolado em
    `_map_to_publicacao` e a montagem de parâmetros em `_montar_params`,
    de modo que ajustá-los ao contrato real exija mudar um único ponto.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import requests
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from src.config.settings import settings
from src.models import AlvoMonitoramento, FonteCaptura, Publicacao, TipoMonitoramento
from src.services.capture.base import CaptureError, CaptureProvider
from src.utils.dates import parse_date
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _e_retentavel(exc: BaseException) -> bool:
    """Define quais erros justificam retentativa (rede e HTTP 5xx)."""
    if isinstance(exc, (requests.ConnectionError, requests.Timeout)):
        return True
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        return exc.response.status_code >= 500
    return False


class JusbrasilClient(CaptureProvider):
    """Provedor de captura que consulta a API da Jusbrasil."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: int = 30,
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.jusbrasil_api_key
        if not self.api_key:
            raise CaptureError(
                "JUSBRASIL_API_KEY não configurada. Defina-a no .env ou use "
                "CAPTURE_PROVIDER=mock para desenvolver sem credenciais."
            )
        self.base_url = (base_url or settings.jusbrasil_api_base_url).rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
                "User-Agent": "monitor-diarios-oficiais/0.1",
            }
        )

    # ------------------------------------------------------------------ HTTP
    @retry(
        reraise=True,
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=2, max=16),
        retry=retry_if_exception(_e_retentavel),
    )
    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        logger.debug("GET %s params=%s", url, params)
        resp = self._session.get(url, params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    # --------------------------------------------------------------- Captura
    def buscar(
        self,
        alvo: AlvoMonitoramento,
        *,
        data_inicio: date | None = None,
        data_fim: date | None = None,
        max_paginas: int = 10,
    ) -> list[Publicacao]:
        params_base = self._montar_params(alvo)
        if data_inicio:
            params_base["data_inicio"] = data_inicio.isoformat()
        if data_fim:
            params_base["data_fim"] = data_fim.isoformat()

        publicacoes: list[Publicacao] = []
        pagina = 1
        while pagina <= max_paginas:
            params = {**params_base, "pagina": pagina}
            try:
                payload = self._get(settings.jusbrasil_search_path, params)
            except requests.HTTPError as exc:
                status = exc.response.status_code if exc.response is not None else "?"
                raise CaptureError(
                    f"API Jusbrasil retornou erro HTTP {status} para {alvo.rotulo!r}."
                ) from exc
            except requests.RequestException as exc:
                raise CaptureError(
                    f"Erro de rede ao consultar a Jusbrasil ({alvo.rotulo}): {exc}"
                ) from exc

            itens = self._extrair_itens(payload)
            publicacoes.extend(self._map_to_publicacao(item, alvo) for item in itens)

            if not self._tem_proxima_pagina(payload, len(itens)):
                break
            pagina += 1

        logger.info("Jusbrasil: %d publicação(ões) para %s", len(publicacoes), alvo.rotulo)
        return publicacoes

    # ------------------------------------------ Pontos de ajuste ao contrato
    @staticmethod
    def _montar_params(alvo: AlvoMonitoramento) -> dict[str, Any]:
        """Traduz um alvo de monitoramento nos parâmetros de busca da API."""
        if alvo.tipo is TipoMonitoramento.OAB:
            params: dict[str, Any] = {"oab": alvo.valor}
            if alvo.uf:
                params["uf"] = alvo.uf
            return params
        if alvo.tipo is TipoMonitoramento.PROCESSO:
            return {"numero_processo": alvo.valor}
        return {"q": alvo.valor}  # TipoMonitoramento.TERMO

    @staticmethod
    def _extrair_itens(payload: dict[str, Any]) -> list[dict[str, Any]]:
        for chave in ("data", "publicacoes", "results", "items"):
            if isinstance(payload.get(chave), list):
                return payload[chave]
        return []

    @staticmethod
    def _tem_proxima_pagina(payload: dict[str, Any], qtd_itens: int) -> bool:
        if qtd_itens == 0:
            return False
        meta = payload.get("paginacao") or payload.get("meta") or {}
        if "proxima_pagina" in meta:
            return bool(meta["proxima_pagina"])
        if "pagina_atual" in meta and "total_paginas" in meta:
            return meta["pagina_atual"] < meta["total_paginas"]
        return False  # sem sinal explícito de paginação, encerra

    @staticmethod
    def _map_to_publicacao(item: dict[str, Any], alvo: AlvoMonitoramento) -> Publicacao:
        return Publicacao(
            id_externo=str(item.get("id") or item.get("id_publicacao") or ""),
            fonte=FonteCaptura.JUSBRASIL,
            termo_monitorado=alvo.rotulo,
            numero_processo=item.get("numero_processo") or item.get("processo"),
            diario=item.get("diario") or item.get("origem"),
            data_publicacao=parse_date(
                item.get("data_publicacao") or item.get("data")
            ),
            conteudo=item.get("conteudo") or item.get("texto") or "",
        )
