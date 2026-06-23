"""Etapa 1 - CAPTURA.

Integração com APIs de diários oficiais (Jusbrasil / Escavador) para buscar
publicações por termos, números de OAB e números de processo monitorados.
Saída: objetos `Publicacao`.

Uso típico::

    from src.services.capture import get_capture_provider, carregar_alvos

    provider = get_capture_provider()           # conforme CAPTURE_PROVIDER
    publicacoes = provider.buscar_varios(carregar_alvos())
"""
from src.services.capture.base import CaptureError, CaptureProvider
from src.services.capture.factory import get_capture_provider
from src.services.capture.targets import carregar_alvos

__all__ = [
    "CaptureError",
    "CaptureProvider",
    "get_capture_provider",
    "carregar_alvos",
]
