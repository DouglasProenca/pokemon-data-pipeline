
import os
import sys
import json
from pathlib import Path
from collections import Counter

import boto3

from dotenv import load_dotenv
from botocore.config import Config
from botocore.exceptions import ClientError


# =====================================================
# CONFIGURACOES
# =====================================================

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

GROUP_ID = int(os.environ["TCG_GROUP_ID"])

DATA_DATE = (
    sys.argv[1]
    if len(sys.argv) > 1
    else "2026-11-18"
)

bucket = os.environ["S3_BUCKET"]

prefix = (
    f"raw/tcgplayer/group_id={GROUP_ID}/"
    f"data={DATA_DATE}"
)


# =====================================================
# CONEXAO RUSTFS
# =====================================================

s3 = boto3.client(
    "s3",
    endpoint_url=os.environ["S3_ENDPOINT"],
    aws_access_key_id=os.environ["S3_ACCESS_KEY"],
    aws_secret_access_key=os.environ["S3_SECRET_KEY"],
    region_name=os.getenv("S3_REGION", "us-east-1"),
    config=Config(
        signature_version="s3v4",
        s3={"addressing_style": "path"}
    )
)


# =====================================================
# LEITURA RAW
# =====================================================

def carregar_json(nome):

    key = f"{prefix}/{nome}"

    try:
        response = s3.get_object(
            Bucket=bucket,
            Key=key
        )

        return json.loads(response["Body"].read())

    except ClientError as erro:
        raise RuntimeError(
            f"Erro ao ler {key}: "
            f"{erro.response['Error']['Code']}"
        ) from erro


# =====================================================
# DIAGNOSTICO
# =====================================================

def main():

    print("=" * 55)
    print("DIAGNOSTICO DOS DADOS PARA SILVER")
    print("=" * 55)

    print(f"Group ID: {GROUP_ID}")
    print(f"Data: {DATA_DATE}")

    produtos = carregar_json("products.json")["results"]
    precos = carregar_json("prices.json")["results"]

    print("\n=== VOLUME DE DADOS ===")
    print(f"Total de produtos: {len(produtos)}")
    print(f"Total de precos: {len(precos)}")

    # -------------------------------------------------
    # Extended Data
    # -------------------------------------------------

    print("\n=== CAMPOS DO EXTENDED DATA ===")

    campos_extended = Counter()

    for produto in produtos:
        extended = produto.get("extendedData") or []

        if isinstance(extended, list):
            for campo in extended:
                if isinstance(campo, dict):
                    nome = (
                        campo.get("name")
                        or campo.get("displayName")
                        or campo.get("key")
                        or "SEM_NOME"
                    )

                    campos_extended[nome] += 1

        elif isinstance(extended, dict):
            for nome in extended:
                campos_extended[nome] += 1

    for campo, quantidade in campos_extended.most_common():
        print(f"{campo}: {quantidade}")

    # -------------------------------------------------
    # Amostra dos produtos
    # -------------------------------------------------

    print("\n=== AMOSTRA DE PRODUTOS ===")

    for produto in produtos[:5]:

        print("\nProduct ID:", produto.get("productId"))
        print("Nome:", produto.get("name"))
        print("URL:", produto.get("url"))
        print("Extended Data:")

        print(json.dumps(
            produto.get("extendedData"),
            indent=2,
            ensure_ascii=False
        ))

    # -------------------------------------------------
    # Acabamentos dos precos
    # -------------------------------------------------

    print("\n=== ACABAMENTOS ===")

    acabamentos = Counter(
        registro.get("subTypeName") or "<NULO>"
        for registro in precos
    )

    for acabamento, quantidade in acabamentos.items():
        print(f"{acabamento}: {quantidade}")

    # -------------------------------------------------
    # Valores nulos
    # -------------------------------------------------

    campos_preco = [
        "marketPrice",
        "lowPrice",
        "midPrice",
        "highPrice",
        "directLowPrice"
    ]

    print("\n=== VALORES NULOS NOS PRECOS ===")

    for campo in campos_preco:

        quantidade = sum(
            1 for registro in precos
            if registro.get(campo) is None
        )

        print(f"{campo}: {quantidade}")

    # -------------------------------------------------
    # Integridade referencial
    # -------------------------------------------------

    ids_produtos = {
        produto.get("productId")
        for produto in produtos
    }

    ids_precos = {
        preco.get("productId")
        for preco in precos
    }

    print("\n=== INTEGRIDADE REFERENCIAL ===")

    print(
        "Product IDs sem preco:",
        len(ids_produtos - ids_precos)
    )

    print(
        "Precos sem produto correspondente:",
        len(ids_precos - ids_produtos)
    )

    print(
        "Product IDs duplicados:",
        len(produtos) - len(ids_produtos)
    )

    # -------------------------------------------------
    # Amostra dos precos
    # -------------------------------------------------

    print("\n=== AMOSTRA DE PRECOS ===")

    print(json.dumps(
        precos[:5],
        indent=2,
        ensure_ascii=False
    ))

    print("\nDiagnostico concluido!")


if __name__ == "__main__":
    main()
