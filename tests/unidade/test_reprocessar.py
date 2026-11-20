
import io
import json

from datetime import date

from src.lakehouse import reprocessar
from src.silver import transformer


class FakePaginator:
    """Simula a listagem de objetos S3."""

    def __init__(self, keys):
        self.keys = keys

    def paginate(self, **kwargs):
        return [{
            "Contents": [
                {"Key": key}
                for key in self.keys
            ]
        }]


class FakeS3:
    """Simula leitura e listagem do S3 sem rede."""

    def __init__(self, objetos):
        self.objetos = objetos

    def get_paginator(self, nome):
        assert nome == "list_objects_v2"
        return FakePaginator(list(self.objetos.keys()))

    def get_object(self, Bucket, Key):
        conteudo = json.dumps(
            self.objetos[Key]
        ).encode("utf-8")

        return {
            "Body": io.BytesIO(conteudo)
        }


def produto_exemplo(nome="Mega Gardevoir ex"):

    return {
        "productId": 644352,
        "groupId": transformer.GROUP_ID,
        "name": nome,
        "imageUrl": "https://example.com/image.jpg",
        "url": "https://example.com/product",
        "extendedData": [
            {"name": "Number", "value": "001/132"},
            {"name": "Rarity", "value": "Double Rare"},
            {"name": "Card Type", "value": "Pokémon"},
        ]
    }


def resposta_tcg(registros):
    return {
        "success": True,
        "results": registros
    }


def setup_function():
    transformer.quarentena.clear()


def test_listar_particoes_encontra_datas():

    s3 = FakeS3({
        "raw/tcgplayer/group_id=24380/data=2026-11-17/products.json": {},
        "raw/tcgplayer/group_id=24380/data=2026-11-17/prices.json": {},
        "raw/tcgplayer/group_id=24380/data=2026-11-18/products.json": {},
        "raw/tcgplayer/group_id=24380/data=2026-11-18/prices.json": {},
    })

    resultado = reprocessar.listar_particoes(
        s3,
        "raw/tcgplayer/group_id=24380/"
    )

    assert len(resultado) == 2

    assert date(2026, 11, 17) in resultado
    assert date(2026, 11, 18) in resultado

    assert "products.json" in resultado[date(2026, 11, 17)]


def test_reconstruir_produtos_prioriza_snapshot_recente():

    produtos_antigos = [
        produto_exemplo("Nome antigo")
    ]

    produtos_recentes = [
        produto_exemplo("Nome atualizado")
    ]

    objetos = {
        "products_17": resposta_tcg(produtos_antigos),
        "products_18": resposta_tcg(produtos_recentes),
    }

    s3 = FakeS3(objetos)

    particoes = {
        date(2026, 11, 17): {
            "products.json": "products_17"
        },
        date(2026, 11, 18): {
            "products.json": "products_18"
        }
    }

    resultado = reprocessar.reconstruir_produtos(
        s3,
        particoes
    )

    assert len(resultado) == 1
    assert resultado[0].nome == "Nome atualizado"


def test_reconstruir_precos_preserva_historico():

    produto = transformer.transformar_produtos(
        [produto_exemplo()],
        "raw/products.json"
    )

    preco_17 = {
        "productId": 644352,
        "marketPrice": 8.50,
        "lowPrice": 7.00,
        "midPrice": 8.50,
        "highPrice": 10.00,
        "subTypeName": "Normal"
    }

    preco_18 = {
        "productId": 644352,
        "marketPrice": 8.96,
        "lowPrice": 6.99,
        "midPrice": 9.18,
        "highPrice": 99.99,
        "subTypeName": "Normal"
    }

    s3 = FakeS3({
        "prices_17": resposta_tcg([preco_17]),
        "prices_18": resposta_tcg([preco_18]),
    })

    particoes = {
        date(2026, 11, 17): {
            "prices.json": "prices_17"
        },
        date(2026, 11, 18): {
            "prices.json": "prices_18"
        }
    }

    resultado = reprocessar.reconstruir_precos(
        s3,
        particoes,
        produto
    )

    assert len(resultado) == 2

    assert len(
        resultado[date(2026, 11, 17)]
    ) == 1

    assert len(
        resultado[date(2026, 11, 18)]
    ) == 1

    assert (
        resultado[date(2026, 11, 17)][0].market_price
        == 8.50
    )

    assert (
        resultado[date(2026, 11, 18)][0].market_price
        == 8.96
    )


def test_reconstruir_cdi_remove_repeticoes_entre_snapshots():

    cdi_17 = [
        {"data": "17/11/2026", "valor": "0.050788"}
    ]

    cdi_18 = [
        {"data": "17/11/2026", "valor": "0.050788"},
        {"data": "18/11/2026", "valor": "0.050788"}
    ]

    s3 = FakeS3({
        "cdi_17": cdi_17,
        "cdi_18": cdi_18,
    })

    particoes = {
        date(2026, 11, 17): {
            "cdi.json": "cdi_17"
        },
        date(2026, 11, 18): {
            "cdi.json": "cdi_18"
        }
    }

    resultado = reprocessar.reconstruir_cdi(
        s3,
        particoes
    )

    datas = [item.data for item in resultado]

    assert datas == [
        date(2026, 11, 17),
        date(2026, 11, 18)
    ]

    assert len(resultado) == 2
    assert len(transformer.quarentena["cdi_diario"]) == 0


def test_reconstruir_cdi_prioriza_observacao_corrigida():

    s3 = FakeS3({
        "cdi_antigo": [
            {"data": "17/11/2026", "valor": "0.050788"}
        ],
        "cdi_recente": [
            {"data": "17/11/2026", "valor": "0.051000"}
        ],
    })

    particoes = {
        date(2026, 11, 18): {
            "cdi.json": "cdi_antigo"
        },
        date(2026, 11, 19): {
            "cdi.json": "cdi_recente"
        }
    }

    resultado = reprocessar.reconstruir_cdi(
        s3,
        particoes
    )

    assert len(resultado) == 1
    assert resultado[0].taxa_dia == 0.051000

    # Registra a divergencia entre snapshots
    assert len(transformer.quarentena["cdi_diario"]) == 1


def test_publicar_preview_substitui_geracao_anterior(
    tmp_path,
    monkeypatch
):

    root = tmp_path / "projeto"
    data_dir = root / "data"

    output = data_dir / "silver_preview"
    staging = data_dir / "silver_rebuild_tmp"

    monkeypatch.setattr(reprocessar, "ROOT", root)
    monkeypatch.setattr(reprocessar, "OUTPUT", output)
    monkeypatch.setattr(reprocessar, "STAGING", staging)

    # Simula uma versao antiga
    output.mkdir(parents=True)
    (output / "versao.txt").write_text(
        "antiga",
        encoding="utf-8"
    )

    # Nova geracao
    staging.mkdir(parents=True)
    (staging / "versao.txt").write_text(
        "nova",
        encoding="utf-8"
    )

    reprocessar.publicar_preview()

    assert (
        output / "versao.txt"
    ).read_text(encoding="utf-8") == "nova"

    assert not staging.exists()

    backup = data_dir / "silver_preview_backup"
    assert not backup.exists()


def test_publicar_preview_pode_ser_reexecutado(
    tmp_path,
    monkeypatch
):

    root = tmp_path / "projeto"
    data_dir = root / "data"

    output = data_dir / "silver_preview"
    staging = data_dir / "silver_rebuild_tmp"

    monkeypatch.setattr(reprocessar, "ROOT", root)
    monkeypatch.setattr(reprocessar, "OUTPUT", output)
    monkeypatch.setattr(reprocessar, "STAGING", staging)

    for numero in range(2):

        staging.mkdir(parents=True)

        (staging / "resultado.txt").write_text(
            str(numero),
            encoding="utf-8"
        )

        reprocessar.publicar_preview()

    assert (
        output / "resultado.txt"
    ).read_text(encoding="utf-8") == "1"

    assert not staging.exists()
