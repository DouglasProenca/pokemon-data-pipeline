
import os
import json
import sys

from pathlib import Path
from datetime import datetime, date
from dotenv import load_dotenv
from botocore.config import Config
import boto3

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

GROUP_ID = int(os.environ["TCG_GROUP_ID"])
DATA_DATE = (
    date.fromisoformat(sys.argv[1])
    if len(sys.argv) > 1
    else date.today()
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

bucket = os.environ["S3_BUCKET"]


def ler_json(key):
    response = s3.get_object(
        Bucket=bucket,
        Key=key
    )
    return json.loads(response["Body"].read())


data = DATA_DATE.isoformat()

print(f"\nInspecionando RAW BCB: {data}")

# PTAX
ptax_key = (
    f"raw/bcb_ptax/group_id={GROUP_ID}/"
    f"data={data}/cotacao.json"
)

ptax = ler_json(ptax_key)
registros_ptax = ptax["value"]

fechamentos = [
    item for item in registros_ptax
    if item.get("tipoBoletim", "").strip().casefold()
    in {"fechamento", "fechamento ptax"}
]

print("\n=== PTAX ===")
print(f"Total de boletins: {len(registros_ptax)}")
print(f"Fechamentos: {len(fechamentos)}")

if len(fechamentos) != 1:
    raise RuntimeError("Quantidade inesperada de fechamentos.")

print("Data:", fechamentos[0].get("dataHoraCotacao"))
print("Compra:", fechamentos[0].get("cotacaoCompra"))
print("Venda:", fechamentos[0].get("cotacaoVenda"))

# CDI
cdi_key = (
    f"raw/bcb_cdi/group_id={GROUP_ID}/"
    f"data={data}/cdi.json"
)

cdi = ler_json(cdi_key)

print("\n=== CDI ===")
print(f"Total de observações: {len(cdi)}")

observacoes = sorted(
    cdi,
    key=lambda item: datetime.strptime(
        item["data"], "%d/%m/%Y"
    )
)

for item in observacoes[-3:]:
    print(
        f"Data: {item['data']} | "
        f"Taxa publicada: {item['valor']}"
    )

print("\nInspeção BCB concluída!")
