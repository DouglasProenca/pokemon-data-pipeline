import os
import boto3

from dotenv import load_dotenv
from botocore.config import Config
from botocore.exceptions import ClientError, BotoCoreError

load_dotenv()

endpoint = os.getenv("S3_ENDPOINT")
bucket = os.getenv("S3_BUCKET")
access_key = os.getenv("S3_ACCESS_KEY")
secret_key = os.getenv("S3_SECRET_KEY")
region = os.getenv("S3_REGION", "us-east-1")

if not all([endpoint, bucket, access_key, secret_key]):
    raise RuntimeError("Existem configurações obrigatórias ausentes no .env")

s3 = boto3.client(
    "s3",
    endpoint_url=endpoint,
    aws_access_key_id=access_key,
    aws_secret_access_key=secret_key,
    region_name=region,
    config=Config(
        signature_version="s3v4",
        s3={"addressing_style": "path"}
    )
)

try:
    print("Conectando ao RustFS...")

    paginator = s3.get_paginator("list_objects_v2")

    prefixos = []

    for page in paginator.paginate(
        Bucket=bucket,
        Prefix="raw/tcgplayer/",
        Delimiter="/"
    ):
        for item in page.get("CommonPrefixes", []):
            prefixos.append(item["Prefix"])

    print("\nConexão realizada com sucesso!")
    print(f"Bucket: {bucket}")
    print("\nColeções encontradas:")

    if prefixos:
        for prefixo in prefixos:
            print(f"- {prefixo}")
    else:
        print("Nenhum prefixo encontrado.")

except (ClientError, BotoCoreError) as erro:
    print(f"Erro ao acessar o RustFS: {erro}")