# Imagem da API do repositório de endereços.
#
# A versão anterior instalava as dependências no arranque do container, o que
# tornava o tempo de subida dependente da rede e a versão dos pacotes variável a
# cada reinício. Aqui as dependências entram na imagem, com versões fixadas em
# requirements-api.txt, e o container sobe direto no servidor.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements-api.txt ./
RUN pip install --no-cache-dir -r requirements-api.txt

COPY src ./src

# Tabela do teste independente (NB17, 02/10/2026). Só produz estado calibrada
# quando a versão dos dados e a da política coincidem com as medidas no teste.
COPY dados_replicacao/calibracao_bh.csv ./dados_replicacao/

# Usuário sem privilégios: o serviço não precisa de root para responder consultas
RUN useradd --create-home --shell /usr/sbin/nologin api && chown -R api:api /app
USER api

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health', timeout=4).status == 200 else 1)"

# UVICORN_WORKERS ajusta o paralelismo conforme o hospedeiro
CMD ["sh", "-c", "uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS:-2}"]
