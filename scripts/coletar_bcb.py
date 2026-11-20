
import os
import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from src.coleta.gravador_raw import (
    gravar_ou_validar_existente,
)

import boto3
import requests

from dotenv import load_dotenv
from botocore.config import Config
from botocore.exceptions import ClientError
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# =====================================================
# CONFIGURACOES
# =====================================================

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

GROUP_ID = int(os.getenv("TCG_GROUP_ID", "0"))

if GROUP_ID <= 0:
    raise RuntimeError("TCG_GROUP_ID nao configurado.")

BUCKET = os.getenv("S3_BUCKET")
ENDPOINT = os.getenv("S3_ENDPOINT")
ACCESS_KEY = os.getenv("S3_ACCESS_KEY")
SECRET_KEY = os.getenv("S3_SECRET_KEY")
REGION = os.getenv("S3_REGION", "us-east-1")

TIMEOUT = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "30"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "5"))
USER_AGENT = os.getenv(
    "TCG_USER_AGENT",
    "pokemon-data-pipeline/1.0"
)

LOOKBACK_DAYS = int(
    os.getenv("BCB_CDI_LOOKBACK_DAYS", "15")
)

TZ_BR = ZoneInfo("America/Sao_Paulo")


# =====================================================
# CLIENTE HTTP
# =====================================================

def criar_sessao():

    retry = Retry(
        total=MAX_RETRIES,
        connect=MAX_RETRIES,
        read=MAX_RETRIES,
        status=MAX_RETRIES,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["GET"]),
        respect_retry_after_header=True
    )

    adapter = HTTPAdapter(max_retries=retry)

    session = requests.Session()
    session.mount("https://", adapter)

    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "application/json"
    })

    return session


def requisitar_json(session, url, params):

    response = session.get(
        url,
        params=params,
        timeout=TIMEOUT
    )

    response.raise_for_status()

    try:
        json.loads(response.content)
    except ValueError as erro:
        raise RuntimeError(
            f"Resposta invalida da fonte: {url}"
        ) from erro

    # Retorna os bytes originais, sem reserializar
    return response.content


# =====================================================
# COLETA PTAX
# =====================================================

def coletar_ptax(session, data_coleta):

    url = (
        "https://olinda.bcb.gov.br/olinda/servico/"
        "PTAX/versao/v1/odata/"
        "CotacaoMoedaDia(moeda=@moeda,"
        "dataCotacao=@dataCotacao)"
    )

    data_formatada = data_coleta.strftime("%m-%d-%Y")

    params = {
        "@moeda": "'USD'",
        "@dataCotacao": f"'{data_formatada}'",
        "$format": "json"
    }

    print("\nConsultando PTAX...")

    conteudo = requisitar_json(
        session,
        url,
        params
    )

    payload = json.loads(conteudo)
    registros = payload.get("value")

    if not isinstance(registros, list):
        raise RuntimeError(
            "Formato inesperado na resposta PTAX."
        )

    tipos_boletim = sorted({
        str(item.get("tipoBoletim"))
        for item in registros
    })

    print("\nTipos de boletim retornados pelo BCB:")
    for tipo in tipos_boletim:
        print(f"- {tipo}")

    fechamentos = [
        item for item in registros
        if str(item.get("tipoBoletim", "")).strip().casefold()
        in {"fechamento", "fechamento ptax"}
    ]

    if registros and not fechamentos:
        raise RuntimeError(
            "PTAX retornou cotacoes, mas nao encontrou "
            "o boletim de Fechamento."
        )

    print(f"Boletins encontrados: {len(registros)}")
    print(f"Boletins de fechamento: {len(fechamentos)}")

    if not registros:
        print(
            "Nenhuma cotacao no dia consultado "
            "(possivel fim de semana ou feriado)."
        )

    return conteudo


# =====================================================
# COLETA CDI
# =====================================================

def coletar_cdi(session, data_coleta):

    url = (
        "https://api.bcb.gov.br/dados/serie/"
        "bcdata.sgs.12/dados"
    )

    data_inicial = data_coleta - timedelta(
        days=LOOKBACK_DAYS
    )

    params = {
        "formato": "json",
        "dataInicial": data_inicial.strftime("%d/%m/%Y"),
        "dataFinal": data_coleta.strftime("%d/%m/%Y")
    }

    print("\nConsultando CDI...")

    conteudo = requisitar_json(
        session,
        url,
        params
    )

    registros = json.loads(conteudo)

    if not isinstance(registros, list):
        raise RuntimeError(
            "Formato inesperado na resposta CDI."
        )

    if not registros:
        raise RuntimeError(
            "Nenhuma taxa CDI encontrada na janela consultada."
        )

    print(f"Registros CDI encontrados: {len(registros)}")
    print(f"Inicio da janela: {data_inicial}")
    print(f"Final da janela: {data_coleta}")

    print(
        "Ultima observacao retornada:",
        registros[-1]
    )

    return conteudo


# =====================================================
# CLIENTE RUSTFS
# =====================================================

def criar_cliente_s3():

    configuracoes = [
        BUCKET, ENDPOINT, ACCESS_KEY, SECRET_KEY
    ]

    if not all(configuracoes):
        raise RuntimeError(
            "Configuracoes incompletas do RustFS."
        )

    return boto3.client(
        "s3",
        endpoint_url=ENDPOINT,
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        region_name=REGION,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"}
        )
    )


def objeto_existe(s3, key):

    try:
        s3.head_object(
            Bucket=BUCKET,
            Key=key
        )

        return True

    except ClientError as erro:

        status = erro.response.get(
            "ResponseMetadata", {}
        ).get("HTTPStatusCode")

        codigo = erro.response.get(
            "Error", {}
        ).get("Code")

        if status == 404 or codigo in (
            "404", "NoSuchKey", "NotFound"
        ):
            return False

        raise


def gravar_arquivos(arquivos):

    s3 = criar_cliente_s3()

    gravados = 0

    for key, conteudo in arquivos:

        novo = gravar_ou_validar_existente(
            s3=s3,
            bucket=BUCKET,
            key=key,
            conteudo=conteudo,
        )

        if novo:
            print(f"Arquivo gravado e validado: {key}")
            gravados += 1
        else:
            print(f"Arquivo identico ja existente: {key}")

    return gravados


# =====================================================
# EXECUCAO
# =====================================================

def main():

    hoje = datetime.now(TZ_BR).date()
    data_particao = hoje.isoformat()

    print("=" * 55)
    print("COLETA BANCO CENTRAL - PTAX E CDI")
    print("=" * 55)

    print(f"Group ID: {GROUP_ID}")
    print(f"Data da coleta: {data_particao}")

    session = criar_sessao()

    # Coleta das duas fontes
    ptax_raw = coletar_ptax(session, hoje)
    cdi_raw = coletar_cdi(session, hoje)

    # Prefixos individuais da colecao
    prefixo_ptax = (
        f"raw/bcb_ptax/group_id={GROUP_ID}/"
        f"data={data_particao}"
    )

    prefixo_cdi = (
        f"raw/bcb_cdi/group_id={GROUP_ID}/"
        f"data={data_particao}"
    )

    arquivos = [
        (
            f"{prefixo_ptax}/cotacao.json",
            ptax_raw
        ),
        (
            f"{prefixo_cdi}/cdi.json",
            cdi_raw
        )
    ]

    print("\nGravando no RustFS...")

    gravar_arquivos(arquivos)

    print("\nColeta BCB finalizada com sucesso!")
    print(f"Arquivos gravados: {len(arquivos)}")


if __name__ == "__main__":
    main()
