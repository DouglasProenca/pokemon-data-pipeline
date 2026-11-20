
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SilverModel(BaseModel):
    """Configuracoes comuns dos modelos Silver."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid"
    )


class ColecaoSilver(SilverModel):
    group_id: int = Field(gt=0)
    nome: str = Field(min_length=1)
    sigla: str = Field(min_length=1)
    data_lancamento: date
    responsavel: str = Field(min_length=1)


class ProdutoSilver(SilverModel):
    product_id: int = Field(gt=0)
    group_id: int = Field(gt=0)
    nome: str = Field(min_length=1)

    tipo_produto: Literal["carta", "selado"]

    raridade: str | None = None
    numero: str | None = None
    image_url: str | None = None
    url: str | None = None


class PrecoDiarioSilver(SilverModel):
    data: date
    product_id: int = Field(gt=0)
    group_id: int = Field(gt=0)

    acabamento: str = Field(min_length=1)

    # Precos podem ser nulos.
    # Nulo nao significa zero.
    market_price: float | None = Field(default=None, ge=0)
    low_price: float | None = Field(default=None, ge=0)
    mid_price: float | None = Field(default=None, ge=0)
    high_price: float | None = Field(default=None, ge=0)

    moeda: str = "USD"
    fonte: str = "TCGCSV"
    chave_raw: str = Field(min_length=1)


class CambioDiarioSilver(SilverModel):
    data: date

    cotacao_compra: float = Field(gt=0)
    cotacao_venda: float = Field(gt=0)

    data_hora_cotacao: datetime

    boletim: Literal["Fechamento"] = "Fechamento"

    chave_raw: str = Field(min_length=1)


class CdiDiarioSilver(SilverModel):
    data: date

    # Taxa preservada no formato publicado pelo BCB,
    # em percentual ao dia.
    taxa_dia: float = Field(ge=0)

    chave_raw: str = Field(min_length=1)
