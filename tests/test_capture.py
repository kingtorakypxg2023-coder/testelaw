"""Testes do módulo de captura (Etapa 1)."""
from __future__ import annotations

from typing import Any

import pytest
import requests

from src.config.settings import Settings
from src.models import AlvoMonitoramento, FonteCaptura, TipoMonitoramento
from src.services.capture import carregar_alvos, get_capture_provider
from src.services.capture.base import CaptureError
from src.services.capture.jusbrasil import JusbrasilClient
from src.services.capture.mock import MockCaptureProvider


class _FakeResponse:
    """Resposta HTTP falsa para simular chamadas à API nos testes."""

    def __init__(self, json_data: dict[str, Any], status: int = 200) -> None:
        self._json = json_data
        self.status_code = status

    def json(self) -> dict[str, Any]:
        return self._json

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(response=self)  # type: ignore[arg-type]


# --------------------------------------------------------------- Mock provider
def test_mock_retorna_publicacoes() -> None:
    provider = MockCaptureProvider()
    alvo = AlvoMonitoramento(tipo=TipoMonitoramento.TERMO, valor="ACME Advogados")

    pubs = provider.buscar(alvo)

    assert pubs, "o mock deve retornar publicações"
    assert all(p.termo_monitorado == "ACME Advogados" for p in pubs)
    assert all(p.conteudo for p in pubs)
    assert all(p.data_publicacao is not None for p in pubs)


def test_buscar_varios_agrega_resultados() -> None:
    provider = MockCaptureProvider()
    alvos = [
        AlvoMonitoramento(tipo=TipoMonitoramento.TERMO, valor="A"),
        AlvoMonitoramento(tipo=TipoMonitoramento.OAB, valor="123456", uf="SP"),
    ]

    pubs = provider.buscar_varios(alvos)

    assert {p.termo_monitorado for p in pubs} == {"A", "OAB 123456/SP"}


# ------------------------------------------------------------------ Factory
def test_factory_retorna_mock() -> None:
    assert isinstance(get_capture_provider("mock"), MockCaptureProvider)


def test_factory_provedor_desconhecido() -> None:
    with pytest.raises(ValueError):
        get_capture_provider("provedor_inexistente")


# --------------------------------------------------------------- Jusbrasil
def test_jusbrasil_sem_chave_falha() -> None:
    with pytest.raises(CaptureError):
        JusbrasilClient(api_key=None)


def test_jusbrasil_montar_params_por_tipo() -> None:
    client = JusbrasilClient(api_key="fake")

    termo = AlvoMonitoramento(tipo=TipoMonitoramento.TERMO, valor="Fulano")
    oab = AlvoMonitoramento(tipo=TipoMonitoramento.OAB, valor="123456", uf="SP")
    proc = AlvoMonitoramento(tipo=TipoMonitoramento.PROCESSO, valor="0001")

    assert client._montar_params(termo) == {"q": "Fulano"}
    assert client._montar_params(oab) == {"oab": "123456", "uf": "SP"}
    assert client._montar_params(proc) == {"numero_processo": "0001"}


def test_jusbrasil_mapeia_resposta(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "data": [
            {
                "id": 42,
                "numero_processo": "1001234-56.2024.8.26.0100",
                "diario": "DJe TJSP",
                "data_publicacao": "2024-05-10",
                "conteudo": "Intimação para contestação em 15 dias.",
            }
        ],
        "paginacao": {"pagina_atual": 1, "total_paginas": 1},
    }
    client = JusbrasilClient(api_key="fake")
    monkeypatch.setattr(
        client._session, "get", lambda *a, **k: _FakeResponse(payload)
    )

    alvo = AlvoMonitoramento(tipo=TipoMonitoramento.OAB, valor="123456", uf="SP")
    pubs = client.buscar(alvo)

    assert len(pubs) == 1
    pub = pubs[0]
    assert pub.id_externo == "42"
    assert pub.fonte == FonteCaptura.JUSBRASIL
    assert pub.termo_monitorado == "OAB 123456/SP"
    assert pub.numero_processo == "1001234-56.2024.8.26.0100"
    assert pub.data_publicacao is not None and pub.data_publicacao.year == 2024


def test_jusbrasil_paginacao(monkeypatch: pytest.MonkeyPatch) -> None:
    paginas = {
        1: {"data": [{"id": 1, "conteudo": "p1"}], "paginacao": {"pagina_atual": 1, "total_paginas": 2}},
        2: {"data": [{"id": 2, "conteudo": "p2"}], "paginacao": {"pagina_atual": 2, "total_paginas": 2}},
    }
    client = JusbrasilClient(api_key="fake")

    def fake_get(url: str, params: dict[str, Any] | None = None, timeout: int | None = None):
        return _FakeResponse(paginas[params["pagina"]])

    monkeypatch.setattr(client._session, "get", fake_get)

    alvo = AlvoMonitoramento(tipo=TipoMonitoramento.TERMO, valor="X")
    pubs = client.buscar(alvo)

    assert [p.id_externo for p in pubs] == ["1", "2"]


# ------------------------------------------------------------------ Targets
def test_carregar_alvos_combina_criterios() -> None:
    config = Settings(
        monitor_terms="Fulano Advogados, Maria",
        monitor_oab="123456/SP, 98765/RJ",
        monitor_processos="1001234-56.2024.8.26.0100",
    )

    alvos = carregar_alvos(config)

    tipos = [a.tipo for a in alvos]
    assert tipos.count(TipoMonitoramento.TERMO) == 2
    assert tipos.count(TipoMonitoramento.OAB) == 2
    assert tipos.count(TipoMonitoramento.PROCESSO) == 1

    oab = next(a for a in alvos if a.tipo is TipoMonitoramento.OAB)
    assert oab.valor == "123456" and oab.uf == "SP"
