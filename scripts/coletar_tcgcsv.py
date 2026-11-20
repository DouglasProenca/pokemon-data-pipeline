
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from src.coleta.gravador_raw import (
    gravar_ou_validar_existente,
)

import boto3
import requests

from botocore.config import Config
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# ---------------------------------------------------------
# CONFIGURACAO
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env", override=True)

BASE_URL = "https://tcgcsv.com/tcgplayer"
CATEGORY_ID = 3
TIMEZONE_BR = ZoneInfo("America/Sao_Paulo")


def required_env(name):
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Variavel obrigatoria ausente: {name}")
    return value


GROUP_ID = int(required_env("TCG_GROUP_ID"))
USER_AGENT = required_env("TCG_USER_AGENT")

TIMEOUT = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "30"))
DELAY = max(float(os.getenv("REQUEST_DELAY_SECONDS", "0.15")), 0.1)
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "5"))


# ---------------------------------------------------------
# CLIENTE HTTP
# ---------------------------------------------------------

def criar_sessao_http():
    retry_config = Retry(
        total=MAX_RETRIES,
        connect=MAX_RETRIES,
        read=MAX_RETRIES,
        status=MAX_RETRIES,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["GET"]),
        respect_retry_after_header=True,
    )

    adapter = HTTPAdapter(max_retries=retry_config)

    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    })

    session.mount("https://", adapter)

    return session


class TCGCSVClient:

    def __init__(self):
        self.session = criar_sessao_http()
        self.ultima_requisicao = None

    def get(self, url):
        # Respeita o intervalo minimo entre chamadas
        if self.ultima_requisicao is not None:
            elapsed = time.monotonic() - self.ultima_requisicao
            wait = DELAY - elapsed

            if wait > 0:
                time.sleep(wait)

        response = self.session.get(url, timeout=TIMEOUT)
        self.ultima_requisicao = time.monotonic()

        response.raise_for_status()

        return response

    def obter_ultima_atualizacao(self):
        response = self.get("https://tcgcsv.com/last-updated.txt")
        timestamp = response.text.strip()

        atualizado_em = datetime.fromisoformat(
            timestamp.replace("Z", "+00:00")
        )

        if atualizado_em.tzinfo is None:
            atualizado_em = atualizado_em.replace(tzinfo=timezone.utc)

        return atualizado_em

    def obter_json(self, url):
        response = self.get(url)

        try:
            payload = response.json()
        except ValueError as erro:
            raise RuntimeError(
                f"Resposta nao e um JSON valido: {url}"
            ) from erro

        if not isinstance(payload, dict):
            raise RuntimeError("Formato inesperado de resposta TCGCSV")

        if payload.get("success") is not True:
            raise RuntimeError(
                f"TCGCSV retornou erro: {payload.get('errors')}"
            )

        if not isinstance(payload.get("results"), list):
            raise RuntimeError("A resposta nao possui uma lista results")

        # Retorna o corpo original, sem converter novamente para JSON
        return response.content, payload

    def obter_produtos(self, group_id):
        url = f"{BASE_URL}/{CATEGORY_ID}/{group_id}/products"
        return self.obter_json(url)

    def obter_precos(self, group_id):
        url = f"{BASE_URL}/{CATEGORY_ID}/{group_id}/prices"
        return self.obter_json(url)


# ---------------------------------------------------------
# CLIENTE RUSTFS
# ---------------------------------------------------------

def criar_cliente_s3():

    return boto3.client(
        "s3",
        endpoint_url=required_env("S3_ENDPOINT"),
        aws_access_key_id=required_env("S3_ACCESS_KEY"),
        aws_secret_access_key=required_env("S3_SECRET_KEY"),
        region_name=os.getenv("S3_REGION", "us-east-1"),
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"}
        )
    )


def objeto_existe(s3, bucket, key):
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True

    except ClientError as erro:
        status = erro.response.get(
            "ResponseMetadata", {}
        ).get("HTTPStatusCode")

        codigo = erro.response.get(
            "Error", {}
        ).get("Code")

        if status == 404 or codigo in ("404", "NoSuchKey", "NotFound"):
            return False

        raise


def gravar_raw_imutavel(s3, bucket, key, conteudo):

    novo = gravar_ou_validar_existente(
        s3=s3,
        bucket=bucket,
        key=key,
        conteudo=conteudo,
    )

    if novo:
        print(f"Arquivo gravado e validado: {key}")
    else:
        print(f"Arquivo identico ja existente: {key}")

    return novo


# ---------------------------------------------------------
# EXECUCAO
# ---------------------------------------------------------

def main():

    hoje = datetime.now(TIMEZONE_BR).date()
    prefixo = f"raw/tcgplayer/group_id={GROUP_ID}/data={hoje}"

    print("Iniciando coleta TCGCSV...")
    print(f"Group ID: {GROUP_ID}")
    print(f"Data de coleta: {hoje}")

    client = TCGCSVClient()

    # Verifica se a fonte ja publicou a atualizacao de hoje
    atualizado_em = client.obter_ultima_atualizacao()
    atualizado_em_br = atualizado_em.astimezone(TIMEZONE_BR)

    if atualizado_em_br.date() != hoje:
        raise RuntimeError(
            "O TCGCSV ainda nao publicou a atualizacao de hoje. "
            f"Ultima atualizacao: {atualizado_em.isoformat()}"
        )

    print(f"Fonte atualizada em: {atualizado_em.isoformat()}")

    # Coleta produtos
    print("\nConsultando produtos...")

    produtos_raw, produtos = client.obter_produtos(GROUP_ID)
    lista_produtos = produtos["results"]

    if not lista_produtos:
        raise RuntimeError("A colecao nao retornou produtos.")

    group_ids = {
        produto.get("groupId") for produto in lista_produtos
    }

    if group_ids != {GROUP_ID}:
        raise RuntimeError(
            f"Group IDs inesperados na resposta: {group_ids}"
        )

    # Coleta precos
    print("Consultando precos...")

    precos_raw, precos = client.obter_precos(GROUP_ID)
    lista_precos = precos["results"]

    if not lista_precos:
        raise RuntimeError("A colecao nao retornou precos.")

    print(f"\nProdutos encontrados: {len(lista_produtos)}")
    print(f"Linhas de precos: {len(lista_precos)}")

    # Prepara as chaves do Data Lake
    bucket = required_env("S3_BUCKET")
    s3 = criar_cliente_s3()

    arquivos = [
        (f"{prefixo}/products.json", produtos_raw),
        (f"{prefixo}/prices.json", precos_raw),
    ]

    # Cada arquivo e tratado individualmente:
    # nunca substitui um objeto que ja existe.
    gravados = 0

    for key, conteudo in arquivos:
        try:
            gravar_raw_imutavel(
                s3=s3,
                bucket=bucket,
                key=key,
                conteudo=conteudo
            )
            gravados += 1

        except FileExistsError as erro:
            print(f"Preservado: {erro}")

    print("\nColeta finalizada.")
    print(f"Novos arquivos gravados: {gravados}")


if __name__ == "__main__":
    main()
