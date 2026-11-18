
import os
import json
from pathlib import Path

import boto3

from dotenv import load_dotenv
from botocore.config import Config


# Configuracao
ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

GROUP_ID = int(os.environ["TCG_GROUP_ID"])
DATA_DATE = "2026-11-18"
BUCKET = os.environ["S3_BUCKET"]

PREFIX = (
    f"raw/tcgplayer/group_id={GROUP_ID}/"
    f"data={DATA_DATE}"
)

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


def carregar(nome):
    response = s3.get_object(
        Bucket=BUCKET,
        Key=f"{PREFIX}/{nome}"
    )
    return json.loads(response["Body"].read())["results"]


produtos = carregar("products.json")
precos = carregar("prices.json")


def extrair_atributos(produto):
    extended = produto.get("extendedData") or []

    if isinstance(extended, dict):
        return extended

    return {
        item.get("name"): item.get("value")
        for item in extended
        if isinstance(item, dict) and item.get("name")
    }


ids_com_preco = {
    registro["productId"]
    for registro in precos
}


print("\n=== PRODUTOS SEM CARD TYPE ===")

sem_card_type = []

for produto in produtos:
    atributos = extrair_atributos(produto)

    if not atributos.get("Card Type"):
        sem_card_type.append(produto)

        print(
            f"\nID: {produto['productId']}"
            f"\nNome: {produto['name']}"
            f"\nAtributos: {list(atributos.keys())}"
        )


print("\nTotal sem Card Type:", len(sem_card_type))


print("\n=== PRODUTOS SEM RARIDADE ===")

for produto in produtos:
    atributos = extrair_atributos(produto)

    if not atributos.get("Rarity"):
        print(
            produto["productId"],
            "-",
            produto["name"]
        )


print("\n=== PRODUTOS SEM NUMERACAO ===")

for produto in produtos:
    atributos = extrair_atributos(produto)

    if not atributos.get("Number"):
        print(
            produto["productId"],
            "-",
            produto["name"]
        )


print("\n=== PRODUTOS SEM PRECOS ===")

for produto in produtos:
    if produto["productId"] not in ids_com_preco:
        print(
            produto["productId"],
            "-",
            produto["name"]
        )


print("\nDiagnostico de classificacao concluido!")
