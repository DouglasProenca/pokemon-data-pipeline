
from datetime import date, datetime

import pytest
from pydantic import ValidationError

from src.silver.models import (
    ColecaoSilver,
    ProdutoSilver,
    PrecoDiarioSilver,
    CambioDiarioSilver,
    CdiDiarioSilver,
)


def test_criar_colecao():
    colecao = ColecaoSilver(
        group_id=24380,
        nome="ME01: Mega Evolution",
        sigla="MEG",
        data_lancamento=date(2025, 9, 26),
        responsavel="Douglas Proenca"
    )

    assert colecao.group_id == 24380
    assert colecao.sigla == "MEG"


def test_produto_pode_ser_carta():
    produto = ProdutoSilver(
        product_id=644352,
        group_id=24380,
        nome="Mega Evolution Booster Pack",
        tipo_produto="carta"
    )

    assert produto.tipo_produto == "carta"


def test_produto_pode_ser_selado():
    produto = ProdutoSilver(
        product_id=644298,
        group_id=24380,
        nome="Mega Evolution Booster Box",
        tipo_produto="selado"
    )

    assert produto.tipo_produto == "selado"


def test_preco_permite_valores_nulos():
    preco = PrecoDiarioSilver(
        data=date(2026, 11, 18),
        product_id=644279,
        group_id=24380,
        acabamento="Normal",
        market_price=None,
        low_price=None,
        chave_raw="raw/tcgplayer/group_id=24380/data=2026-11-18/prices.json"
    )

    assert preco.market_price is None
    assert preco.low_price is None


def test_preco_nao_permite_valor_negativo():
    with pytest.raises(ValidationError):
        PrecoDiarioSilver(
            data=date(2026, 11, 18),
            product_id=644279,
            group_id=24380,
            acabamento="Normal",
            market_price=-10,
            chave_raw="raw/prices.json"
        )


def test_cambio_exige_fechamento():
    cambio = CambioDiarioSilver(
        data=date(2026, 11, 18),
        cotacao_compra=5.8096,
        cotacao_venda=5.8102,
        data_hora_cotacao=datetime(2026, 11, 18, 13, 8, 44),
        boletim="Fechamento",
        chave_raw="raw/bcb_ptax/cotacao.json"
    )

    assert cambio.boletim == "Fechamento"

    with pytest.raises(ValidationError):
        CambioDiarioSilver(
            data=date(2026, 11, 18),
            cotacao_compra=5.8096,
            cotacao_venda=5.8102,
            data_hora_cotacao=datetime(2026, 11, 18, 13, 8, 44),
            boletim="Abertura",
            chave_raw="raw/bcb_ptax/cotacao.json"
        )


def test_cdi_preserva_percentual_diario():
    cdi = CdiDiarioSilver(
        data=date(2026, 11, 17),
        taxa_dia=0.050788,
        chave_raw="raw/bcb_cdi/cdi.json"
    )

    assert cdi.taxa_dia == 0.050788
