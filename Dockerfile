# Imagem do Monitor de Diários Oficiais & Prazos Jurídicos
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Dependências primeiro (melhor cache de camadas)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código da aplicação
COPY src/ ./src/

# Diretório de dados persistentes (SQLite)
VOLUME ["/app/data"]

# Por padrão, executa o scheduler (ciclos periódicos).
# Configuração via variáveis de ambiente (--env-file .env).
CMD ["python", "-m", "src.scheduler"]
