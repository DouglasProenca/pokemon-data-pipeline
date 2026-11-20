
import json
import re
import shutil

from collections import defaultdict
from datetime import date
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from src.silver import transformer as silver


# =====================================================
# CONFIGURACOES
# =====================================================

ROOT = Path(__file__).resolve().parents[2]

GROUP_ID = silver.GROUP_ID
BUCKET = silver.BUCKET

OUTPUT = ROOT / "data" / "silver_preview"
STAGING = ROOT / "data" / "silver_rebuild_tmp"

QUARANTINE_FILENAME = "registros.jsonl"


# =====================================================
# LEITURA DO DATA LAKE
# =====================================================

def listar_particoes(s3, prefix):

    paginator = s3.get_paginator("list_objects_v2")

    particoes = defaultdict(dict)

    for page in paginator.paginate(
        Bucket=BUCKET,
        Prefix=prefix
    ):

        for objeto in page.get("Contents", []):

            key = objeto["Key"]

            match = re.search(
                r"/data=(\d{4}-\d{2}-\d{2})/([^/]+)$",
                key
            )

            if not match:
                continue

            data = date.fromisoformat(match.group(1))
            nome = match.group(2)

            particoes[data][nome] = key

    return dict(particoes)


def carregar_json(s3, key):

    response = s3.get_object(
        Bucket=BUCKET,
        Key=key
    )

    return json.loads(response["Body"].read())


def validar_tcg(payload, key):

    if payload.get("success") is not True:
        raise RuntimeError(
            f"Resposta TCGCSV invalida: {key}"
        )

    if not isinstance(payload.get("results"), list):
        raise RuntimeError(
            f"Campo results invalido: {key}"
        )

    return payload["results"]


# =====================================================
# LEVANTAMENTO DAS PARTICOES
# =====================================================

def descobrir_fontes(s3):

    prefixos = {
        "tcgplayer": f"raw/tcgplayer/group_id={GROUP_ID}/",
        "ptax": f"raw/bcb_ptax/group_id={GROUP_ID}/",
        "cdi": f"raw/bcb_cdi/group_id={GROUP_ID}/",
    }

    fontes = {
        nome: listar_particoes(s3, prefixo)
        for nome, prefixo in prefixos.items()
    }

    if not fontes["tcgplayer"]:
        raise RuntimeError("Nenhum RAW TCGCSV encontrado.")

    if not fontes["ptax"]:
        raise RuntimeError("Nenhum RAW PTAX encontrado.")

    if not fontes["cdi"]:
        raise RuntimeError("Nenhum RAW CDI encontrado.")

    for data, arquivos in fontes["tcgplayer"].items():

        obrigatorios = {"products.json", "prices.json"}
        ausentes = obrigatorios - arquivos.keys()

        if ausentes:
            raise RuntimeError(
                f"Particao TCGCSV incompleta em {data}: {ausentes}"
            )

    print("\nParticoes encontradas:")

    for nome, particoes in fontes.items():

        print(
            f"{nome}: {len(particoes)} particoes "
            f"({', '.join(str(d) for d in sorted(particoes))})"
        )

    return fontes


# =====================================================
# TRANSFORMACAO HISTORICA
# =====================================================

def reconstruir_produtos(s3, particoes):

    produtos_por_id = {}

    print("\nReconstruindo cadastro de produtos...")

    # A ultima fotografia disponivel atualiza o cadastro.
    for data in sorted(particoes):

        key = particoes[data]["products.json"]

        payload = carregar_json(s3, key)

        registros = validar_tcg(payload, key)

        modelos = silver.transformar_produtos(
            registros,
            key
        )

        for produto in modelos:
            produtos_por_id[produto.product_id] = produto

        print(
            f"{data}: {len(modelos)} produtos processados"
        )

    return sorted(
        produtos_por_id.values(),
        key=lambda produto: produto.product_id
    )


def reconstruir_precos(s3, particoes, produtos):

    resultado = {}

    print("\nReconstruindo historico de precos...")

    for data in sorted(particoes):

        key = particoes[data]["prices.json"]

        payload = carregar_json(s3, key)

        registros = validar_tcg(payload, key)

        modelos = silver.transformar_precos(
            registros,
            produtos,
            data,
            key
        )

        resultado[data] = modelos

        print(
            f"{data}: {len(modelos)} precos validos"
        )

    return resultado


def reconstruir_ptax(s3, particoes):

    resultado = {}

    print("\nReconstruindo historico PTAX...")

    for data in sorted(particoes):

        key = particoes[data]["cotacao.json"]

        payload = carregar_json(s3, key)

        registros = payload.get("value")

        if not isinstance(registros, list):
            raise RuntimeError(
                f"Formato PTAX invalido: {key}"
            )

        modelos = silver.transformar_ptax(
            registros,
            key,
            data
        )

        if modelos:
            resultado[data] = modelos[0]

        print(
            f"{data}: {len(modelos)} fechamento(s)"
        )

    return resultado


def reconstruir_cdi(s3, particoes):

    observacoes = {}

    print("\nReconstruindo historico CDI...")

    for data_coleta in sorted(particoes):

        key = particoes[data_coleta]["cdi.json"]

        registros = carregar_json(s3, key)

        if not isinstance(registros, list):
            raise RuntimeError(
                f"Formato CDI invalido: {key}"
            )

        modelos = silver.transformar_cdi(
            registros,
            key
        )

        for modelo in modelos:

            anterior = observacoes.get(modelo.data)

            if anterior is not None:

                if anterior.taxa_dia != modelo.taxa_dia:

                    silver.quarentena["cdi_diario"].append({
                        "tabela": "cdi_diario",
                        "origem": modelo.chave_raw,
                        "motivo": (
                            "Taxa divergente entre snapshots. "
                            "Mantida a observacao da coleta mais recente."
                        ),
                        "registro": {
                            "anterior": anterior.model_dump(),
                            "novo": modelo.model_dump()
                        }
                    })

                # Os snapshots sao percorridos em ordem crescente.
                # Portanto, a ultima copia disponivel prevalece.
                observacoes[modelo.data] = modelo

            else:
                observacoes[modelo.data] = modelo

    resultado = [
        observacoes[data]
        for data in sorted(observacoes)
    ]

    print(f"Observacoes CDI unicas: {len(resultado)}")

    return resultado


# =====================================================
# GRAVACAO PARQUET
# =====================================================

def gravar_parquet(nome, modelos, caminho):

    registros = [
        modelo.model_dump()
        for modelo in modelos
    ]

    schema = silver.SCHEMAS[nome]

    tabela = pa.Table.from_pylist(
        registros,
        schema=schema
    )

    caminho.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    pq.write_table(
        tabela,
        caminho,
        compression="snappy"
    )

    print(
        f"{nome}: {len(modelos)} registros gravados"
    )


def gravar_quarentena():

    registros = []

    for itens in silver.quarentena.values():
        registros.extend(itens)

    if not registros:
        print("\nQuarentena: nenhum registro.")
        return

    caminho = (
        STAGING
        / "quarentena"
        / QUARANTINE_FILENAME
    )

    caminho.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with caminho.open("w", encoding="utf-8") as arquivo:

        for registro in registros:

            arquivo.write(
                json.dumps(
                    registro,
                    ensure_ascii=False,
                    default=str
                ) + "\n"
            )

    print(
        f"\nQuarentena: {len(registros)} registros"
    )


# =====================================================
# PUBLICACAO LOCAL ATOMICA
# =====================================================

def publicar_preview():

    backup = ROOT / "data" / "silver_preview_backup"

    if backup.exists():
        shutil.rmtree(backup)

    if OUTPUT.exists():
        OUTPUT.rename(backup)

    try:
        STAGING.rename(OUTPUT)

    except Exception:

        if backup.exists():
            backup.rename(OUTPUT)

        raise

    if backup.exists():
        shutil.rmtree(backup)


# =====================================================
# ORQUESTRACAO
# =====================================================

def main():

    print("=" * 65)
    print("REPROCESSAMENTO HISTORICO DA CAMADA SILVER")
    print("=" * 65)

    print(f"Group ID: {GROUP_ID}")
    print("Origem: RustFS RAW")
    print("Destino: Silver local")

    # Limpa apenas o estado temporario de validacao.
    # Nenhum arquivo RAW ou objeto remoto e removido.
    silver.quarentena.clear()

    if STAGING.exists():
        shutil.rmtree(STAGING)

    STAGING.mkdir(parents=True)

    s3 = silver.criar_cliente_s3()

    fontes = descobrir_fontes(s3)

    # Cadastro historico
    colecao = silver.transformar_colecao()

    produtos = reconstruir_produtos(
        s3,
        fontes["tcgplayer"]
    )

    # Todas as datas de precos
    precos_por_data = reconstruir_precos(
        s3,
        fontes["tcgplayer"],
        produtos
    )

    # Todos os fechamentos PTAX disponiveis
    cambios = reconstruir_ptax(
        s3,
        fontes["ptax"]
    )

    # CDI com deduplicacao pela data da observacao
    cdis = reconstruir_cdi(
        s3,
        fontes["cdi"]
    )

    # Arquivos nao particionados
    base = STAGING

    gravar_parquet(
        "colecao",
        colecao,
        base
        / "colecao"
        / f"group_id={GROUP_ID}"
        / "colecao.parquet"
    )

    gravar_parquet(
        "produto",
        produtos,
        base
        / "produto"
        / f"group_id={GROUP_ID}"
        / "produto.parquet"
    )

    gravar_parquet(
        "cambio_diario",
        [cambios[d] for d in sorted(cambios)],
        base
        / "cambio_diario"
        / f"group_id={GROUP_ID}"
        / "cambio.parquet"
    )

    gravar_parquet(
        "cdi_diario",
        cdis,
        base
        / "cdi_diario"
        / f"group_id={GROUP_ID}"
        / "cdi.parquet"
    )

    # Um arquivo por data de preco
    for data in sorted(precos_por_data):

        gravar_parquet(
            "preco_diario",
            precos_por_data[data],
            base
            / "preco_diario"
            / f"group_id={GROUP_ID}"
            / f"data={data.isoformat()}"
            / "preco.parquet"
        )

    gravar_quarentena()

    # Apenas substitui a previa local depois
    # que todos os arquivos foram gerados.
    publicar_preview()

    print("\n" + "=" * 65)
    print("REPROCESSAMENTO SILVER CONCLUIDO")
    print("=" * 65)

    print(f"Produtos: {len(produtos)}")

    print(
        "Particoes de preco:",
        len(precos_por_data)
    )

    print(
        "Total de precos:",
        sum(len(v) for v in precos_por_data.values())
    )

    print("Fechamentos PTAX:", len(cambios))
    print("Observacoes CDI:", len(cdis))

    print(
        "Registros em quarentena:",
        sum(len(v) for v in silver.quarentena.values())
    )

    print(f"Destino: {OUTPUT}")


if __name__ == "__main__":
    main()
