"""Provedor de captura *mock* para desenvolvimento e testes.

Gera publicações fictícias, porém realistas (com prazos, audiências e
recursos), permitindo desenvolver e testar todo o pipeline — inclusive a
Etapa 2 (IA) — sem credenciais e sem consumir cota de API.
"""
from __future__ import annotations

from datetime import date, timedelta

from src.models import AlvoMonitoramento, FonteCaptura, Publicacao
from src.services.capture.base import CaptureProvider
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Modelos de publicações realistas (texto bruto típico de diários oficiais).
_TEMPLATES: list[dict[str, object]] = [
    {
        "numero_processo": "1001234-56.2024.8.26.0100",
        "diario": "DJe TJSP",
        "dias_atras": 1,
        "cliente": "João da Silva",
        "parte_contraria": "Banco XYZ S.A.",
        "conteudo": (
            "INTIMAÇÃO - Processo nº 1001234-56.2024.8.26.0100. Fica a parte "
            "requerida, na pessoa de seu advogado, INTIMADA para, no prazo de "
            "15 (quinze) dias, apresentar contestação, sob pena de revelia e "
            "presunção de veracidade dos fatos alegados (art. 344 do CPC)."
        ),
    },
    {
        "numero_processo": "5005678-90.2023.4.03.6100",
        "diario": "DJe TRF3",
        "dias_atras": 2,
        "cliente": "Maria Oliveira",
        "parte_contraria": "Instituto Nacional do Seguro Social - INSS",
        "conteudo": (
            "DESPACHO - Processo nº 5005678-90.2023.4.03.6100. Designo audiência "
            "de conciliação para o dia 15/07/2026, às 14h00, a ser realizada por "
            "videoconferência. Intimem-se as partes e seus patronos."
        ),
    },
    {
        "numero_processo": "0009876-54.2022.8.26.0224",
        "diario": "DJe TJSP",
        "dias_atras": 3,
        "cliente": "Construtora Alfa Ltda.",
        "parte_contraria": "Município de São Paulo",
        "conteudo": (
            "SENTENÇA - Processo nº 0009876-54.2022.8.26.0224. Ante o exposto, "
            "JULGO PROCEDENTE o pedido. Publique-se. Registre-se. Intimem-se. "
            "Da presente sentença cabe recurso de apelação no prazo de 15 dias."
        ),
    },
]


class MockCaptureProvider(CaptureProvider):
    """Provedor de captura que retorna publicações fictícias e determinísticas."""

    def buscar(
        self,
        alvo: AlvoMonitoramento,
        *,
        data_inicio: date | None = None,
        data_fim: date | None = None,
        **_: object,
    ) -> list[Publicacao]:
        logger.info("[MOCK] Gerando publicações de exemplo para %s", alvo.rotulo)
        hoje = date.today()
        publicacoes: list[Publicacao] = []
        for i, tpl in enumerate(_TEMPLATES):
            publicacoes.append(
                Publicacao(
                    id_externo=f"mock-{alvo.tipo.value}-{i}",
                    fonte=FonteCaptura.OUTRA,
                    termo_monitorado=alvo.rotulo,
                    numero_processo=str(tpl["numero_processo"]),
                    cliente=str(tpl["cliente"]),
                    parte_contraria=str(tpl["parte_contraria"]),
                    diario=str(tpl["diario"]),
                    data_publicacao=hoje - timedelta(days=int(tpl["dias_atras"])),
                    conteudo=str(tpl["conteudo"]),
                )
            )
        return publicacoes
