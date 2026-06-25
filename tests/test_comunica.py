"""Testes do provedor de captura DJEN/Comunica (CNJ)."""
from __future__ import annotations

from typing import Any

import pytest
import requests

from src.models import AlvoMonitoramento, FonteCaptura, TipoMonitoramento
from src.services.capture import get_capture_provider
from src.services.capture.comunica import ComunicaProvider, _limpar_html


class _FakeResponse:
    def __init__(self, json_data: Any, status: int = 200) -> None:
        self._json = json_data
        self.status_code = status

    def json(self) -> Any:
        return self._json

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(response=self)  # type: ignore[arg-type]


def test_nao_exige_credencial() -> None:
    # O provedor do DJEN é gratuito e não recebe nenhuma chave de API.
    assert isinstance(ComunicaProvider(), ComunicaProvider)


def test_montar_params_por_tipo() -> None:
    client = ComunicaProvider()
    oab = AlvoMonitoramento(tipo=TipoMonitoramento.OAB, valor="123456", uf="SP")
    proc = AlvoMonitoramento(tipo=TipoMonitoramento.PROCESSO, valor="0001")
    termo = AlvoMonitoramento(tipo=TipoMonitoramento.TERMO, valor="Fulano")

    assert client._montar_params(oab) == {"numeroOab": "123456", "ufOab": "SP"}
    assert client._montar_params(proc) == {"numeroProcesso": "0001"}
    assert client._montar_params(termo) == {"nomeAdvogado": "Fulano"}


def test_limpar_html() -> None:
    assert _limpar_html("<p>Intimação em <b>15</b> dias.</p>") == "Intimação em 15 dias."


def test_extrai_partes_dos_destinatarios() -> None:
    item = {
        "destinatarios": [
            {"nome": "João da Silva", "polo": "A"},
            {"nome": "Banco XYZ S.A.", "polo": "P"},
            {"nome": "Maria Litisconsorte", "polo": "A"},
        ]
    }
    cliente, reu = ComunicaProvider._extrair_partes(item)
    assert cliente == "João da Silva / Maria Litisconsorte"  # autores (polo ativo)
    assert reu == "Banco XYZ S.A."  # réu (polo passivo)


def test_extrai_partes_sem_dados() -> None:
    assert ComunicaProvider._extrair_partes({"texto": "x"}) == (None, None)


def test_mapeia_resposta(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "status": "success",
        "count": 1,
        "items": [
            {
                "id": 99,
                "numero_processo": "1001234-56.2024.8.26.0100",
                "siglaTribunal": "TJSP",
                "nomeOrgao": "1ª Vara Cível",
                "data_disponibilizacao": "2026-06-10",
                "texto": "<p>Fica intimada para contestação em 15 dias.</p>",
                "destinatarios": [
                    {"nome": "Fulano de Tal", "polo": "A"},
                    {"nome": "Empresa Ré Ltda.", "polo": "P"},
                ],
            }
        ],
    }
    client = ComunicaProvider()
    monkeypatch.setattr(client._session, "get", lambda *a, **k: _FakeResponse(payload))

    alvo = AlvoMonitoramento(tipo=TipoMonitoramento.OAB, valor="123456", uf="SP")
    pubs = client.buscar(alvo)

    assert len(pubs) == 1
    pub = pubs[0]
    assert pub.id_externo == "99"
    assert pub.fonte == FonteCaptura.COMUNICA
    assert pub.termo_monitorado == "OAB 123456/SP"
    assert pub.numero_processo == "1001234-56.2024.8.26.0100"
    assert pub.cliente == "Fulano de Tal"
    assert pub.parte_contraria == "Empresa Ré Ltda."
    assert pub.diario == "1ª Vara Cível"
    assert "Fica intimada para contestação em 15 dias." == pub.conteudo  # HTML removido
    assert pub.data_publicacao is not None and pub.data_publicacao.year == 2026


def test_paginacao(monkeypatch: pytest.MonkeyPatch) -> None:
    client = ComunicaProvider()
    client.page_size = 1  # força paginação
    paginas = {
        1: {"items": [{"id": 1, "texto": "a"}]},
        2: {"items": [{"id": 2, "texto": "b"}]},
        3: {"items": []},
    }

    def fake_get(url: str, params: dict | None = None, timeout: int | None = None):
        return _FakeResponse(paginas[params["pagina"]])

    monkeypatch.setattr(client._session, "get", fake_get)

    alvo = AlvoMonitoramento(tipo=TipoMonitoramento.TERMO, valor="X")
    pubs = client.buscar(alvo)
    assert [p.id_externo for p in pubs] == ["1", "2"]


def test_factory_comunica() -> None:
    assert isinstance(get_capture_provider("comunica"), ComunicaProvider)
