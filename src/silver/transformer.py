
import json
import os
import argparse
from zoneinfo import ZoneInfo

from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

import boto3
import pyarrow as pa
import pyarrow.parquet as pq

from botocore.config import Config
from dotenv import load_dotenv
from pydantic import ValidationError

from src.silver.models import (
    ColecaoSilver,
    ProdutoSilver,
    PrecoDiarioSilver,
    CambioDiarioSilver,
    CdiDiarioSilver,
)


# =====================================================
# CONFIGURACOES
# =====================================================

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env", override=True)

GROUP_ID = int(os.environ["TCG_GROUP_ID"])
BUCKET = os.environ["S3_BUCKET"]



OUTPUT_ROOT = ROOT / "data" / "silver_preview"
QUARANTINE_ROOT = ROOT / "data" / "quarentena"


# =====================================================
# SCHEMAS PARQUET
# Tipos alinhados ao contrato do professor
# =====================================================

SCHEMAS = {
    "colecao": pa.schema([
        ("group_id", pa.int32()),
        ("nome", pa.string()),
        ("sigla", pa.string()),
        ("data_lancamento", pa.date32()),
        ("responsavel", pa.string()),
    ]),

    "produto": pa.schema([
        ("product_id", pa.int32()),
        ("group_id", pa.int32()),
        ("nome", pa.string()),
        ("tipo_produto", pa.string()),
        ("raridade", pa.string()),
        ("numero", pa.string()),
        ("image_url", pa.string()),
        ("url", pa.string()),
    ]),

    "preco_diario": pa.schema([
        ("data", pa.date32()),
        ("product_id", pa.int32()),
        ("group_id", pa.int32()),
        ("acabamento", pa.string()),
        ("market_price", pa.float64()),
        ("low_price", pa.float64()),
        ("mid_price", pa.float64()),
        ("high_price", pa.float64()),
        ("moeda", pa.string()),
        ("fonte", pa.string()),
        ("chave_raw", pa.string()),
    ]),

    "cambio_diario": pa.schema([
        ("data", pa.date32()),
        ("cotacao_compra", pa.float64()),
        ("cotacao_venda", pa.float64()),
        ("data_hora_cotacao", pa.timestamp("us")),
        ("boletim", pa.string()),
        ("chave_raw", pa.string()),
    ]),

    "cdi_diario": pa.schema([
        ("data", pa.date32()),
        ("taxa_dia", pa.float64()),
        ("chave_raw", pa.string()),
    ]),
}


# =====================================================
# CONEXAO COM RUSTFS
# =====================================================

def criar_cliente_s3():

    return boto3.client(
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


def ler_json(s3, key):

    response = s3.get_object(
        Bucket=BUCKET,
        Key=key
    )

    conteudo = response["Body"].read()

    return json.loads(conteudo), key


# =====================================================
# UTILITARIOS
# =====================================================

def texto_opcional(valor):

    if valor is None:
        return None

    resultado = str(valor).strip()

    return resultado or None


def extrair_extended_data(produto):

    dados = produto.get("extendedData") or []

    if isinstance(dados, dict):
        return dados

    resultado = {}

    for item in dados:

        if not isinstance(item, dict):
            continue

        nome = item.get("name")

        if nome:
            resultado[nome] = item.get("value")

    return resultado


def classificar_produto(atributos):

    numero = texto_opcional(atributos.get("Number"))
    card_type = texto_opcional(atributos.get("Card Type"))
    raridade = texto_opcional(atributos.get("Rarity"))

    eh_code_card = (
        raridade is not None
        and raridade.casefold() == "code card"
    )

    if numero or card_type or eh_code_card:
        return "carta"

    return "selado"


# =====================================================
# QUARENTENA
# =====================================================

quarentena = defaultdict(list)


def adicionar_quarentena(tabela, registro, origem, motivo):

    quarentena[tabela].append({
        "tabela": tabela,
        "origem": origem,
        "motivo": motivo,
        "registro": registro
    })


def validar(modelo, registro, tabela, origem):

    try:
        return modelo.model_validate(registro)

    except (ValidationError, ValueError, TypeError) as erro:

        adicionar_quarentena(
            tabela=tabela,
            registro=registro,
            origem=origem,
            motivo=str(erro)
        )

        return None


# =====================================================
# TRANSFORMACAO DA COLECAO
# =====================================================

def transformar_colecao():

    registro = {
        "group_id": GROUP_ID,
        "nome": os.environ["TCG_COLLECTION_NAME"],
        "sigla": os.environ["TCG_COLLECTION_SIGLA"],
        "data_lancamento": date.fromisoformat(
            os.environ["TCG_COLLECTION_RELEASE_DATE"]
        ),
        "responsavel": os.environ["PROJECT_RESPONSIBLE"],
    }

    modelo = validar(
        ColecaoSilver,
        registro,
        "colecao",
        "configuracao"
    )

    return [modelo] if modelo else []


# =====================================================
# TRANSFORMACAO DOS PRODUTOS
# =====================================================

def transformar_produtos(registros, origem):

    resultado = []

    for produto in registros:

        atributos = extrair_extended_data(produto)

        raridade = texto_opcional(
            atributos.get("Rarity")
        )

        numero = texto_opcional(
            atributos.get("Number")
        )

        registro = {
            "product_id": produto.get("productId"),
            "group_id": produto.get("groupId"),
            "nome": produto.get("name"),
            "tipo_produto": classificar_produto(atributos),
            "raridade": raridade,
            "numero": numero,
            "image_url": texto_opcional(
                produto.get("imageUrl")
            ),
            "url": texto_opcional(
                produto.get("url")
            ),
        }

        if registro["group_id"] != GROUP_ID:

            adicionar_quarentena(
                "produto",
                registro,
                origem,
                "Produto pertence a outro group_id"
            )
            continue

        modelo = validar(
            ProdutoSilver,
            registro,
            "produto",
            origem
        )

        if modelo:
            resultado.append(modelo)

    return resultado


# =====================================================
# TRANSFORMACAO DOS PRECOS
# =====================================================

def transformar_precos(
    registros,
    produtos,
    data_referencia,
    origem
):

    resultado = []

    ids_produtos = {
        produto.product_id for produto in produtos
    }

    chaves_processadas = set()

    for preco in registros:

        product_id = preco.get("productId")

        if product_id not in ids_produtos:

            adicionar_quarentena(
                "preco_diario",
                preco,
                origem,
                "Product ID sem produto correspondente"
            )
            continue

        acabamento = texto_opcional(
            preco.get("subTypeName")
        )

        chave = (
            data_referencia,
            product_id,
            acabamento
        )

        if chave in chaves_processadas:

            adicionar_quarentena(
                "preco_diario",
                preco,
                origem,
                "Registro duplicado para produto, acabamento e data"
            )
            continue

        chaves_processadas.add(chave)

        registro = {
            "data": data_referencia,
            "product_id": product_id,
            "group_id": GROUP_ID,
            "acabamento": acabamento,
            "market_price": preco.get("marketPrice"),
            "low_price": preco.get("lowPrice"),
            "mid_price": preco.get("midPrice"),
            "high_price": preco.get("highPrice"),
            "moeda": "USD",
            "fonte": "TCGCSV",
            "chave_raw": origem,
        }

        modelo = validar(
            PrecoDiarioSilver,
            registro,
            "preco_diario",
            origem
        )

        if modelo:
            resultado.append(modelo)

    return resultado


# =====================================================
# TRANSFORMACAO DA PTAX
# =====================================================

def transformar_ptax(registros, origem, data_referencia):

    fechamentos = [
        item for item in registros
        if str(item.get("tipoBoletim", "")).strip().casefold()
        in {"fechamento", "fechamento ptax"}
    ]

    if not fechamentos:
        print(
            "PTAX: nenhum fechamento neste dia. "
            "Nenhuma linha será criada."
        )
        return []

    if len(fechamentos) > 1:
        raise RuntimeError(
            "Mais de um boletim de fechamento encontrado."
        )

    item = fechamentos[0]

    registro = {
        "data": data_referencia,
        "cotacao_compra": item.get("cotacaoCompra"),
        "cotacao_venda": item.get("cotacaoVenda"),
        "data_hora_cotacao": item.get("dataHoraCotacao"),
        "boletim": "Fechamento",
        "chave_raw": origem,
    }

    modelo = validar(
        CambioDiarioSilver,
        registro,
        "cambio_diario",
        origem
    )

    return [modelo] if modelo else []


# =====================================================
# TRANSFORMACAO DO CDI
# =====================================================

def transformar_cdi(registros, origem):

    resultado = []
    datas_processadas = set()

    for item in registros:

        data_observacao = datetime.strptime(
            item["data"],
            "%d/%m/%Y"
        ).date()

        if data_observacao in datas_processadas:

            adicionar_quarentena(
                "cdi_diario",
                item,
                origem,
                "Data duplicada na resposta CDI"
            )
            continue

        datas_processadas.add(data_observacao)

        registro = {
            "data": data_observacao,
            "taxa_dia": item.get("valor"),
            "chave_raw": origem,
        }

        modelo = validar(
            CdiDiarioSilver,
            registro,
            "cdi_diario",
            origem
        )

        if modelo:
            resultado.append(modelo)

    return resultado


# =====================================================
# PERSISTENCIA PARQUET LOCAL
# =====================================================

def salvar_parquet(tabela, modelos, caminho):

    caminho.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    registros = [
        modelo.model_dump()
        for modelo in modelos
    ]

    arrow_table = pa.Table.from_pylist(
        registros,
        schema=SCHEMAS[tabela]
    )

    pq.write_table(
        arrow_table,
        caminho,
        compression="snappy"
    )

    print(
        f"{tabela}: {len(modelos)} registros "
        f"-> {caminho.relative_to(ROOT)}"
    )


# =====================================================
# PERSISTENCIA DA QUARENTENA
# =====================================================

def salvar_quarentena(data_referencia):

    for tabela, registros in quarentena.items():

        caminho = (
            QUARANTINE_ROOT
            / f"{tabela}_{data_referencia.isoformat()}.jsonl"
        )

        caminho.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        with caminho.open(
            "w",
            encoding="utf-8"
        ) as arquivo:

            for registro in registros:
                arquivo.write(
                    json.dumps(
                        registro,
                        ensure_ascii=False,
                        default=str
                    ) + "\n"
                )

        print(
            f"Quarentena {tabela}: "
            f"{len(registros)} registros"
        )


# =====================================================
# EXECUCAO PRINCIPAL
# =====================================================

def main(data_referencia=None):

    if data_referencia is None:
        parser = argparse.ArgumentParser()
        parser.add_argument("data", nargs="?")
        args = parser.parse_args()

        if args.data:
            data_referencia = date.fromisoformat(args.data)
        else:
            data_referencia = datetime.now(
                ZoneInfo("America/Sao_Paulo")
            ).date()

    raw_prefix = (
        f"raw/tcgplayer/group_id={GROUP_ID}/"
        f"data={data_referencia.isoformat()}"
    )

    print("=" * 60)
    print("PROCESSAMENTO DA CAMADA SILVER")
    print("=" * 60)

    print(f"Group ID: {GROUP_ID}")
    print(f"Data: {data_referencia}")

    s3 = criar_cliente_s3()

    # Lê os dados originais do RustFS
    produtos_raw, chave_produtos = ler_json(
        s3,
        f"{raw_prefix}/products.json"
    )

    precos_raw, chave_precos = ler_json(
        s3,
        f"{raw_prefix}/prices.json"
    )

    ptax_prefix = (
        f"raw/bcb_ptax/group_id={GROUP_ID}/"
        f"data={data_referencia.isoformat()}"
    )

    cdi_prefix = (
        f"raw/bcb_cdi/group_id={GROUP_ID}/"
        f"data={data_referencia.isoformat()}"
    )

    ptax_raw, chave_ptax = ler_json(
        s3,
        f"{ptax_prefix}/cotacao.json"
    )

    cdi_raw, chave_cdi = ler_json(
        s3,
        f"{cdi_prefix}/cdi.json"
    )

    # Transforma cada tabela
    colecoes = transformar_colecao()

    produtos = transformar_produtos(
        produtos_raw["results"],
        chave_produtos
    )

    precos = transformar_precos(
        precos_raw["results"],
        produtos,
        data_referencia,
        chave_precos
    )

    cambios = transformar_ptax(
        ptax_raw["value"],
        chave_ptax,
        data_referencia
    )

    cdis = transformar_cdi(
        cdi_raw,
        chave_cdi
    )

    # Caminhos locais espelham a estrutura do Data Lake
    base = OUTPUT_ROOT

    salvar_parquet(
        "colecao",
        colecoes,
        base / "colecao"
        / f"group_id={GROUP_ID}"
        / "colecao.parquet"
    )

    salvar_parquet(
        "produto",
        produtos,
        base / "produto"
        / f"group_id={GROUP_ID}"
        / "produto.parquet"
    )

    salvar_parquet(
        "preco_diario",
        precos,
        base / "preco_diario"
        / f"group_id={GROUP_ID}"
        / f"data={data_referencia.isoformat()}"
        / "preco.parquet"
    )

    salvar_parquet(
        "cambio_diario",
        cambios,
        base / "cambio_diario"
        / f"group_id={GROUP_ID}"
        / "cambio.parquet"
    )

    salvar_parquet(
        "cdi_diario",
        cdis,
        base / "cdi_diario"
        / f"group_id={GROUP_ID}"
        / "cdi.parquet"
    )

    salvar_quarentena(data_referencia)

    print("\nResumo da execução:")
    print(f"Produtos válidos: {len(produtos)}")
    print(f"Preços válidos: {len(precos)}")
    print(f"PTAX válidas: {len(cambios)}")
    print(f"CDI válidos: {len(cdis)}")
    print(
        "Registros em quarentena:",
        sum(len(v) for v in quarentena.values())
    )

    print("\nSilver local gerada com sucesso!")


if __name__ == "__main__":
    main()
