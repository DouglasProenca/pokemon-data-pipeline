
from botocore.exceptions import ClientError


class ObjetoJaExisteError(Exception):
    """Indica tentativa de sobrescrever um objeto RAW."""


class ConflitoGravacaoError(Exception):
    """Indica conflito durante uma gravacao condicional."""


def gravar_objeto(
    s3,
    bucket: str,
    key: str,
    conteudo: bytes,
    content_type: str = "application/json",
):
    """
    Grava um objeto somente se a chave ainda nao existir.

    Utiliza IfNoneMatch para impedir sobrescritas
    de forma atomica no servico S3.
    """

    if not bucket:
        raise ValueError("Bucket obrigatorio.")

    if not key:
        raise ValueError("Chave do objeto obrigatoria.")

    if not isinstance(conteudo, bytes):
        raise TypeError("O conteudo deve ser bytes.")

    if not conteudo:
        raise ValueError("Nao e permitido gravar arquivo vazio.")

    try:
        return s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=conteudo,
            ContentType=content_type,
            IfNoneMatch="*",
        )

    except ClientError as erro:

        status = erro.response.get(
            "ResponseMetadata", {}
        ).get("HTTPStatusCode")

        codigo = erro.response.get(
            "Error", {}
        ).get("Code")

        if status == 412 or codigo in (
            "412",
            "PreconditionFailed",
        ):
            raise ObjetoJaExisteError(
                f"O objeto RAW ja existe: {key}"
            ) from erro

        if status == 409 or codigo in (
            "409",
            "ConditionalRequestConflict",
        ):
            raise ConflitoGravacaoError(
                f"Conflito durante a gravacao: {key}"
            ) from erro

        raise


class ConteudoExistenteDivergenteError(RuntimeError):
    """A chave ja existe, mas seu conteudo e diferente."""


def gravar_ou_validar_existente(
    s3,
    bucket: str,
    key: str,
    conteudo: bytes,
    content_type: str = "application/json",
) -> bool:
    """
    Grava somente se o objeto nao existir.

    Retorna:
      True: objeto novo gravado.
      False: objeto ja existia com conteudo identico.

    Se o conteudo existente for diferente, falha sem sobrescrever.
    """

    try:
        gravar_objeto(
            s3=s3,
            bucket=bucket,
            key=key,
            conteudo=conteudo,
            content_type=content_type,
        )
        novo = True

    except ObjetoJaExisteError:
        novo = False

    # Confirma o conteudo diretamente no armazenamento.
    response = s3.get_object(
        Bucket=bucket,
        Key=key,
    )

    conteudo_remoto = response["Body"].read()

    if conteudo_remoto != conteudo:
        raise ConteudoExistenteDivergenteError(
            f"A chave {key} ja existe com conteudo diferente. "
            "O objeto original foi preservado."
        )

    return novo
