
import os
from pathlib import Path

import duckdb
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

GROUP_ID = int(os.environ["TCG_GROUP_ID"])

BASE = ROOT / "data" / "silver_preview"

ARQUIVOS = {
    "colecao": BASE / "colecao" / f"group_id={GROUP_ID}" / "colecao.parquet",
    "produto": BASE / "produto" / f"group_id={GROUP_ID}" / "produto.parquet",
    "preco_diario": BASE / "preco_diario" / f"group_id={GROUP_ID}" / "data=2026-11-18" / "preco.parquet",
    "cambio_diario": BASE / "cambio_diario" / f"group_id={GROUP_ID}" / "cambio.parquet",
    "cdi_diario": BASE / "cdi_diario" / f"group_id={GROUP_ID}" / "cdi.parquet",
}


def tabela_sql(caminho):
    caminho = str(caminho).replace("'", "''")
    return f"read_parquet('{caminho}')"


def main():

    print("=" * 60)
    print("VALIDACAO DA CAMADA SILVER")
    print("=" * 60)

    con = duckdb.connect()

    # Verifica existencia e estrutura dos arquivos
    for nome, caminho in ARQUIVOS.items():

        if not caminho.exists():
            raise FileNotFoundError(
                f"Arquivo nao encontrado: {caminho}"
            )

        tabela = tabela_sql(caminho)

        quantidade = con.execute(
            f"SELECT COUNT(*) FROM {tabela}"
        ).fetchone()[0]

        print(f"\n=== {nome.upper()} ===")
        print(f"Registros: {quantidade}")

        schema = con.execute(
            f"DESCRIBE SELECT * FROM {tabela}"
        ).fetchall()

        for coluna in schema:
            print(f"{coluna[0]}: {coluna[1]}")

    produto = tabela_sql(ARQUIVOS["produto"])
    preco = tabela_sql(ARQUIVOS["preco_diario"])
    cdi = tabela_sql(ARQUIVOS["cdi_diario"])

    # Classificacao dos produtos
    print("\n=== CLASSIFICACAO DOS PRODUTOS ===")

    resultados = con.execute(f"""
        SELECT
            tipo_produto,
            COUNT(*) AS quantidade
        FROM {produto}
        GROUP BY tipo_produto
        ORDER BY tipo_produto
    """).fetchall()

    for tipo, quantidade in resultados:
        print(f"{tipo}: {quantidade}")

    # Produtos sem precos
    print("\n=== PRODUTOS SEM PRECOS ===")

    sem_preco = con.execute(f"""
        SELECT COUNT(*)
        FROM {produto} p
        WHERE NOT EXISTS (
            SELECT 1
            FROM {preco} pr
            WHERE pr.product_id = p.product_id
        )
    """).fetchone()[0]

    print(f"Produtos sem preco: {sem_preco}")

    # Precos sem produtos correspondentes
    orfaos = con.execute(f"""
        SELECT COUNT(*)
        FROM {preco} pr
        WHERE NOT EXISTS (
            SELECT 1
            FROM {produto} p
            WHERE p.product_id = pr.product_id
        )
    """).fetchone()[0]

    print(f"Precos sem produto: {orfaos}")

    # Produtos duplicados
    duplicados = con.execute(f"""
        SELECT COUNT(*) - COUNT(DISTINCT product_id)
        FROM {produto}
    """).fetchone()[0]

    print(f"Produtos duplicados: {duplicados}")

    # Precos duplicados pela chave logica
    duplicados_preco = con.execute(f"""
        SELECT COUNT(*)
        FROM (
            SELECT data, product_id, acabamento
            FROM {preco}
            GROUP BY data, product_id, acabamento
            HAVING COUNT(*) > 1
        ) d
    """).fetchone()[0]

    print(f"Chaves de preco duplicadas: {duplicados_preco}")

    # CDI: verificar se as datas estao duplicadas
    cdi_duplicado = con.execute(f"""
        SELECT COUNT(*)
        FROM (
            SELECT data
            FROM {cdi}
            GROUP BY data
            HAVING COUNT(*) > 1
        ) d
    """).fetchone()[0]

    print(f"Datas CDI duplicadas: {cdi_duplicado}")

    print("\nValidacao concluida!")

    con.close()


if __name__ == "__main__":
    main()
