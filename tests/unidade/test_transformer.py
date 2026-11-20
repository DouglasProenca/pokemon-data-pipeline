
from datetime import date

from src.silver import transformer


def setup_function():
    # Evita que a quarentena de um teste
    # contamine o resultado do seguinte.
    transformer.quarentena.clear()


def produto_exemplo(
    product_id=644352,
    nome="Mega Evolution Booster Pack",
    group_id=24380,
    extended_data=None,
):
    return {
        "productId": product_id,
        "groupId": group_id,
        "name": nome,
        "imageUrl": "https://example.com/image.jpg",
        "url": "https://example.com/product",
        "extendedData": extended_data or [],
    }


def test_classifica_carta_convencional():

    atributos = {
        "Number": "001/132",
        "Rarity": "Double Rare",
        "Card Type": "Pokémon",
    }

    assert transformer.classificar_produto(atributos) == "carta"


def test_classifica_code_card_como_carta():

    atributos = {
        "Rarity": "Code Card",
    }

    assert transformer.classificar_produto(atributos) == "carta"


def test_classifica_booster_box_como_selado():

    atributos = {
        "CardText": "Each box contains 36 booster packs."
    }

    assert transformer.classificar_produto(atributos) == "selado"


def test_transforma_produto_corretamente():

    registro = produto_exemplo(
        extended_data=[
            {"name": "Number", "value": "001/132"},
            {"name": "Rarity", "value": "Double Rare"},
            {"name": "Card Type", "value": "Pokémon"},
        ]
    )

    resultado = transformer.transformar_produtos(
        [registro],
        "raw/products.json"
    )

    assert len(resultado) == 1
    assert resultado[0].product_id == 644352
    assert resultado[0].tipo_produto == "carta"
    assert resultado[0].raridade == "Double Rare"


def test_produto_de_outro_group_id_vai_para_quarentena():

    registro = produto_exemplo(
        group_id=99999
    )

    resultado = transformer.transformar_produtos(
        [registro],
        "raw/products.json"
    )

    assert resultado == []
    assert len(transformer.quarentena["produto"]) == 1


def test_associa_preco_por_product_id():

    produto = produto_exemplo(
        extended_data=[
            {"name": "Number", "value": "001/132"},
            {"name": "Rarity", "value": "Double Rare"},
        ]
    )

    produtos = transformer.transformar_produtos(
        [produto],
        "raw/products.json"
    )

    precos_raw = [{
        "productId": 644352,
        "marketPrice": 8.96,
        "lowPrice": 6.99,
        "midPrice": 9.18,
        "highPrice": 99.99,
        "directLowPrice": None,
        "subTypeName": "Normal",
    }]

    resultado = transformer.transformar_precos(
        precos_raw,
        produtos,
        date(2026, 11, 18),
        "raw/prices.json"
    )

    assert len(resultado) == 1
    assert resultado[0].product_id == 644352
    assert resultado[0].market_price == 8.96
    assert resultado[0].moeda == "USD"


def test_preco_sem_produto_vai_para_quarentena():

    precos_raw = [{
        "productId": 999999,
        "marketPrice": 10.0,
        "lowPrice": 8.0,
        "midPrice": 10.0,
        "highPrice": 12.0,
        "subTypeName": "Normal",
    }]

    resultado = transformer.transformar_precos(
        precos_raw,
        [],
        date(2026, 11, 18),
        "raw/prices.json"
    )

    assert resultado == []
    assert len(transformer.quarentena["preco_diario"]) == 1


def test_preco_duplicado_vai_para_quarentena():

    produto = produto_exemplo(
        extended_data=[
            {"name": "Number", "value": "001/132"},
            {"name": "Rarity", "value": "Double Rare"},
        ]
    )

    produtos = transformer.transformar_produtos(
        [produto],
        "raw/products.json"
    )

    preco = {
        "productId": 644352,
        "marketPrice": 8.96,
        "lowPrice": 6.99,
        "midPrice": 9.18,
        "highPrice": 99.99,
        "subTypeName": "Normal",
    }

    resultado = transformer.transformar_precos(
        [preco, preco],
        produtos,
        date(2026, 11, 18),
        "raw/prices.json"
    )

    assert len(resultado) == 1
    assert len(transformer.quarentena["preco_diario"]) == 1
