
from pathlib import Path
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data" / "silver_preview"

arquivos = {
    "colecao": BASE / "colecao/group_id=24380/colecao.parquet",
    "produto": BASE / "produto/group_id=24380/produto.parquet",
    "preco_diario": BASE / "preco_diario/group_id=24380/data=2026-11-18/preco.parquet",
    "cambio_diario": BASE / "cambio_diario/group_id=24380/cambio.parquet",
    "cdi_diario": BASE / "cdi_diario/group_id=24380/cdi.parquet",
}

for nome, caminho in arquivos.items():

    print(f"\n=== {nome.upper()} ===")

    if not caminho.exists():
        print("Arquivo nao encontrado:", caminho)
        continue

    schema = pq.read_schema(caminho)

    for campo in schema:
        print(f"{campo.name}: {campo.type}")

print("\nInspecao fisica concluida!")
