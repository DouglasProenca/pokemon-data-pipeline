
import sys

from scripts.coletar_tcgcsv import main as coletar_tcgcsv
from scripts.coletar_bcb import main as coletar_bcb


def executar_coleta(nome, funcao, erros):

    print(f"\n{'=' * 60}")
    print(f"INICIANDO: {nome}")
    print("=" * 60)

    try:
        funcao()
        print(f"\nSUCESSO: {nome}")

    except Exception as erro:
        mensagem = f"{nome}: {type(erro).__name__}: {erro}"
        erros.append(mensagem)
        print(f"\nFALHA: {mensagem}", file=sys.stderr)


def main():

    print("=" * 60)
    print("PIPELINE DIARIO - POKEMON DATA")
    print("=" * 60)

    erros = []

    executar_coleta(
        "TCGCSV - Produtos e precos",
        coletar_tcgcsv,
        erros
    )

    executar_coleta(
        "BCB - PTAX e CDI",
        coletar_bcb,
        erros
    )

    print("\n" + "=" * 60)
    print("RESUMO DA EXECUCAO")
    print("=" * 60)

    if erros:
        for erro in erros:
            print(f"- {erro}")

        print("\nPipeline finalizado com falhas.")
        raise SystemExit(1)

    print("Todas as fontes foram processadas com sucesso.")


if __name__ == "__main__":
    main()
