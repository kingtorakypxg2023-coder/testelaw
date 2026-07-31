"""Cliente de captura via API pública do DJEN/Comunica (CNJ) — gratuito.

A consulta de comunicações processuais do CNJ é **pública e não exige
credencial**. Como os servidores do CNJ bloqueiam acesso automatizado externo,
o contrato exato (parâmetros e campos da resposta) deve ser confirmado no
Swagger oficial (https://comunicaapi.pje.jus.br/). Por isso o endpoint é
configurável e o mapeamento para `Publicacao` fica centralizado/defensivo,
bastando ajustar um ponto caso algum nome de campo difira.
"""
from __future__ import annotations

import re
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

_RE_TAG = re.compile(r"<[^>]+>")


def _e_retentavel(exc: BaseException) -> bool:
    if isinstance(exc, (requests.ConnectionError, requests.Timeout)):
        return True
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        return exc.response.status_code >= 500
    return False


def _limpar_html(texto: str) -> str:
    """Remove tags HTML e normaliza espaços do corpo da comunicação."""
    return " ".join(_RE_TAG.sub(" ", texto).split())


class ComunicaProvider(CaptureProvider):
    """Captura publicações/intimações do DJEN (CNJ) — fonte oficial e gratuita."""

    def __init__(self, base_url: str | None = None, timeout: int = 30) -> None:
        self.base_url = (base_url or settings.comunica_api_base_url).rstrip("/")
        self.timeout = timeout
        self.page_size = settings.comunica_page_size
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": "monitor-diarios-oficiais/0.1",
            }
        )

    @retry(
        reraise=True,
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=2, max=16),
        retry=retry_if_exception(_e_retentavel),
    )
    def _get(self, params: dict[str, Any]) -> Any:
        url = f"{self.base_url}{settings.comunica_search_path}"
        logger.debug("GET %s params=%s", url, params)
        resp = self._session.get(url, params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

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
            params_base["dataDisponibilizacaoInicio"] = data_inicio.isoformat()
        if data_fim:
            params_base["dataDisponibilizacaoFim"] = data_fim.isoformat()

        publicacoes: list[Publicacao] = []
        pagina = 1
        while pagina <= max_paginas:
            params = {**params_base, "pagina": pagina, "itensPorPagina": self.page_size}
            try:
                payload = self._get(params)
            except requests.HTTPError as exc:
                status = exc.response.status_code if exc.response is not None else "?"
                raise CaptureError(
                    f"API Comunica/DJEN retornou erro HTTP {status} para {alvo.rotulo!r}."
                ) from exc
            except requests.RequestException as exc:
                raise CaptureError(
                    f"Erro de rede ao consultar o DJEN ({alvo.rotulo}): {exc}"
                ) from exc

            itens = self._extrair_itens(payload)
            publicacoes.extend(self._map_to_publicacao(item, alvo) for item in itens)

            if len(itens) < self.page_size:  # última página
                break
            pagina += 1

        logger.info(
            "DJEN/Comunica: %d publicação(ões) para %s", len(publicacoes), alvo.rotulo
        )
        return publicacoes

    # ------------------------------------------ Pontos de ajuste ao contrato
    @staticmethod
    def _montar_params(alvo: AlvoMonitoramento) -> dict[str, Any]:
        if alvo.tipo is TipoMonitoramento.OAB:
            params: dict[str, Any] = {"numeroOab": alvo.valor}
            if alvo.uf:
                params["ufOab"] = alvo.uf
            return params
        if alvo.tipo is TipoMonitoramento.PROCESSO:
            return {"numeroProcesso": alvo.valor}
        return {"nomeAdvogado": alvo.valor}  # TipoMonitoramento.TERMO

    @staticmethod
    def _extrair_itens(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            for chave in ("items", "content", "data", "comunicacoes"):
                if isinstance(payload.get(chave), list):
                    return payload[chave]
        return []

    @staticmethod
    def _extrair_partes(item: dict[str, Any]) -> tuple[str | None, str | None]:
        """Extrai autor (polo ativo) e réu (polo passivo) da comunicação.

        O DJEN costuma trazer as partes numa lista (`destinatarios`/`partes`),
        cada uma com `nome` e `polo` ("A"=ativo/autor, "P"=passivo/réu). Os
        advogados ficam em outra chave, então não são confundidos com as partes.
        """
        lista: Any = None
        for chave in ("destinatarios", "partes", "destinatario", "polos"):
            if isinstance(item.get(chave), list):
                lista = item[chave]
                break
        autores: list[str] = []
        reus: list[str] = []
        for ent in lista or []:
            if not isinstance(ent, dict):
                continue
            nome = str(
                ent.get("nome")
                or ent.get("nomeParte")
                or ent.get("nome_parte")
                or ent.get("nomePessoa")
                or ""
            ).strip()
            if not nome:
                continue
            polo = str(
                ent.get("polo") or ent.get("poloParte") or ent.get("tipoParte") or ""
            ).strip().upper()
            if polo.startswith("P"):
                reus.append(nome)
            else:  # "A"/ativo ou sem polo definido -> assume autor
                autores.append(nome)
        if not autores:
            esc = item.get("nomeAutor") or item.get("autor") or item.get("poloAtivo")
            if esc:
                autores.append(str(esc).strip())
        if not reus:
            esc = item.get("nomeReu") or item.get("reu") or item.get("poloPassivo")
            if esc:
                reus.append(str(esc).strip())
        # dict.fromkeys remove duplicados preservando a ordem.
        cliente = " / ".join(dict.fromkeys(filter(None, autores))) or None
        parte_contraria = " / ".join(dict.fromkeys(filter(None, reus))) or None
        return cliente, parte_contraria

    @staticmethod
    def _extrair_advogados(item: dict[str, Any]) -> str | None:
        """Extrai os advogados/procuradores citados na comunicação.

        No DJEN costumam vir numa lista (`destinatarioadvogados`/`advogados`),
        cada item com o nome e, quando disponível, número/UF da OAB.
        """
        nomes: list[str] = []
        for chave in ("destinatarioadvogados", "advogados", "advogado", "procuradores"):
            lista = item.get(chave)
            if not isinstance(lista, list):
                continue
            for ent in lista:
                if not isinstance(ent, dict):
                    continue
                adv = ent.get("advogado") if isinstance(ent.get("advogado"), dict) else ent
                nome = str(adv.get("nome") or adv.get("nomeAdvogado") or "").strip()
                if not nome:
                    continue
                oab = adv.get("numero_oab") or adv.get("numeroOab") or adv.get("oab")
                uf = adv.get("uf_oab") or adv.get("ufOab") or adv.get("uf")
                if oab:
                    nome = f"{nome} (OAB {oab}{'/' + str(uf) if uf else ''})"
                nomes.append(nome)
            if nomes:
                break
        return " / ".join(dict.fromkeys(nomes)) or None

    @staticmethod
    def _map_to_publicacao(item: dict[str, Any], alvo: AlvoMonitoramento) -> Publicacao:
        texto = item.get("texto") or item.get("conteudo") or item.get("corpo") or ""
        data_raw = (
            item.get("data_disponibilizacao")
            or item.get("datadisponibilizacao")
            or item.get("dataDisponibilizacao")
            or item.get("data")
        )
        ident = item.get("id") or item.get("hash") or item.get("numeroComunicacao") or ""
        cliente, parte_contraria = ComunicaProvider._extrair_partes(item)
        return Publicacao(
            id_externo=str(ident),
            fonte=FonteCaptura.COMUNICA,
            termo_monitorado=alvo.rotulo,
            numero_processo=(
                item.get("numero_processo")
                or item.get("numeroprocessocommascara")
                or item.get("numeroProcesso")
            ),
            cliente=cliente,
            parte_contraria=parte_contraria,
            advogados=ComunicaProvider._extrair_advogados(item),
            diario=item.get("nomeOrgao") or item.get("siglaTribunal"),
            data_publicacao=parse_date(data_raw),
            conteudo=_limpar_html(str(texto)),
        )
