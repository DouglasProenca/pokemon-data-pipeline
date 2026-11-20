
import time
import uuid

import boto3
import pytest

from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from testcontainers.core.container import DockerContainer

from src.coleta.gravador_raw import (
    gravar_objeto,
    gravar_ou_validar_existente,
    ObjetoJaExisteError,
    ConteudoExistenteDivergenteError,
)

SILO_IMAGE = (
    "pgsty/silo:RELEASE.2026-11-12T00-00-00Z"
)

ACCESS_KEY = "silo-test-admin"
SECRET_KEY = "SiloTestPassword123!"

BUCKET = "raw-test-integration"


@pytest.fixture(scope="module")
def s3_client():

    container = DockerContainer(SILO_IMAGE)

    container.with_env(
        "MINIO_ROOT_USER",
        ACCESS_KEY
    )

    container.with_env(
        "MINIO_ROOT_PASSWORD",
        SECRET_KEY
    )

    container.with_exposed_ports(9000)

    container.with_command(
        "server /data --console-address :9001"
    )

    with container as silo:

        host = silo.get_container_host_ip()
        port = silo.get_exposed_port(9000)

        endpoint = f"http://{host}:{port}"

        client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=ACCESS_KEY,
            aws_secret_access_key=SECRET_KEY,
            region_name="us-east-1",
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"}
            )
        )

        # Aguarda o S3 estar pronto
        conectado = False

        for tentativa in range(40):
            try:
                client.list_buckets()
                conectado = True
                break

            except (BotoCoreError, ClientError):
                time.sleep(1)

        if not conectado:
            raise RuntimeError(
                "Silo nao ficou disponivel para testes."
            )

        client.create_bucket(Bucket=BUCKET)

        yield client


def test_grava_objeto_novo(s3_client):

    key = f"raw/tests/{uuid.uuid4()}/products.json"

    conteudo = b'{"success":true,"results":[{"id":1}]}'

    resposta = gravar_objeto(
        s3=s3_client,
        bucket=BUCKET,
        key=key,
        conteudo=conteudo
    )

    assert resposta["ResponseMetadata"]["HTTPStatusCode"] == 200

    # Confirma a leitura do objeto
    objeto = s3_client.get_object(
        Bucket=BUCKET,
        Key=key
    )

    conteudo_lido = objeto["Body"].read()

    assert conteudo_lido == conteudo


def test_recusa_sobrescrever_objeto(s3_client):

    key = f"raw/tests/{uuid.uuid4()}/products.json"

    conteudo_original = b'{"versao":1}'
    conteudo_novo = b'{"versao":2}'

    # Primeira gravacao
    gravar_objeto(
        s3_client,
        BUCKET,
        key,
        conteudo_original
    )

    # Segunda gravacao deve falhar
    with pytest.raises(ObjetoJaExisteError):

        gravar_objeto(
            s3_client,
            BUCKET,
            key,
            conteudo_novo
        )

    # O arquivo original deve continuar intacto
    objeto = s3_client.get_object(
        Bucket=BUCKET,
        Key=key
    )

    conteudo_final = objeto["Body"].read()

    assert conteudo_final == conteudo_original


def test_nao_permite_conteudo_vazio(s3_client):

    with pytest.raises(ValueError):

        gravar_objeto(
            s3=s3_client,
            bucket=BUCKET,
            key="raw/tests/vazio.json",
            conteudo=b""
        )


def test_nao_permite_conteudo_que_nao_seja_bytes(s3_client):

    with pytest.raises(TypeError):

        gravar_objeto(
            s3=s3_client,
            bucket=BUCKET,
            key="raw/tests/invalido.json",
            conteudo='{"teste":true}'
        )


def test_gravacao_repetida_com_conteudo_identico(s3_client):

    key = f"raw/tests/{uuid.uuid4()}/products.json"

    conteudo = b'{"products": 228}'

    primeira = gravar_ou_validar_existente(
        s3_client, BUCKET, key, conteudo
    )

    segunda = gravar_ou_validar_existente(
        s3_client, BUCKET, key, conteudo
    )

    assert primeira is True
    assert segunda is False


def test_gravacao_com_conteudo_diferente_e_rejeitada(s3_client):

    key = f"raw/tests/{uuid.uuid4()}/products.json"

    original = b'{"versao": 1}'
    novo = b'{"versao": 2}'

    gravar_ou_validar_existente(
        s3_client, BUCKET, key, original
    )

    with pytest.raises(ConteudoExistenteDivergenteError):

        gravar_ou_validar_existente(
            s3_client, BUCKET, key, novo
        )

    objeto = s3_client.get_object(
        Bucket=BUCKET,
        Key=key,
    )

    assert objeto["Body"].read() == original
