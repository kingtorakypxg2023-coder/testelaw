"""Prompts usados na extração de prazos pela IA (Etapa 2)."""
from __future__ import annotations

from src.models import Publicacao

SYSTEM_PROMPT = """\
Você é um assistente jurídico especializado em interpretar publicações de \
diários oficiais brasileiros e extrair prazos e ações processuais de forma \
estruturada.

Regras importantes:
- Identifique se a publicação contém prazos processuais ou ações a cumprir.
- Para cada prazo, quando o texto indicar uma quantidade de dias (ex.: "15 \
dias", "no prazo de 5 (cinco) dias"), preencha `prazo_dias` com esse número \
inteiro.
- NÃO calcule datas. O cálculo da data fatal é feito pelo sistema. Limite-se a \
extrair `prazo_dias`.
- Quando o texto citar uma DATA específica de um evento (ex.: audiência \
designada para 15/07/2026), preencha `data_referencia` no formato AAAA-MM-DD.
- Classifique `tipo` entre: recurso, contestacao, manifestacao, audiencia, \
pagamento, cumprimento, outro.
- Marque `urgente=true` para prazos curtos/peremptórios ou audiências próximas.
- Escreva um `resumo` objetivo do teor da publicação, em português.
- Identifique o `cliente` (nome do autor do processo / parte representada). Se \
não for possível identificar com clareza, deixe nulo.
- Se não houver prazo nem ação a cumprir, retorne `possui_prazo=false` e \
`prazos=[]`.
"""


def montar_prompt_usuario(publicacao: Publicacao) -> str:
    """Monta o prompt de usuário com os dados da publicação a analisar."""
    partes = [
        "Analise a publicação de diário oficial abaixo e extraia os prazos/ações."
    ]
    if publicacao.numero_processo:
        partes.append(f"Número do processo: {publicacao.numero_processo}")
    if publicacao.data_publicacao:
        partes.append(f"Data da publicação: {publicacao.data_publicacao.isoformat()}")
    partes.append("---- TEXTO DA PUBLICAÇÃO ----")
    partes.append(publicacao.conteudo)
    return "\n".join(partes)
