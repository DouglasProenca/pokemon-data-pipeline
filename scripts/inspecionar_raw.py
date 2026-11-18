
import os
import json
import boto3

from pathlib import Path
from dotenv import load_dotenv
from botocore.config import Config

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env", override=True)

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

bucket = os.environ["S3_BUCKET"]
prefix = "raw/tcgplayer/group_id=24380/data=2026-11-17"

for filename in ["products.json", "prices.json"]:
    key = f"{prefix}/{filename}"

    response = s3.get_object(Bucket=bucket, Key=key)
    content = response["Body"].read()
    data = json.loads(content)

    results = data.get("results", [])

    print(f"\nArquivo: {filename}")
    print(f"Tamanho: {len(content):,} bytes")
    print(f"Sucesso da API: {data.get('success')}")
    print(f"Quantidade de registros: {len(results)}")

    if results:
        print(
            "Campos disponíveis:",
            ", ".join(sorted(results[0].keys()))
        )

print("\nInspeção RAW concluída!")
