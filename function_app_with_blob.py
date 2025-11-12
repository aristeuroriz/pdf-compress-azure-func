import io
import logging
import os
import tempfile
import uuid
from datetime import datetime, timedelta

import azure.functions as func
from azure.storage.blob import (
    BlobSasPermissions,
    BlobServiceClient,
    generate_blob_sas,
)

from compress_pdf import reduce_pdf_size

app = func.FunctionApp(http_auth_level=func.AuthLevel.ADMIN)


@app.route(route="compress_pdf_blob")
def compress_pdf_blob(req: func.HttpRequest) -> func.HttpResponse:
    """
    Comprime o PDF e salva no Blob Storage, retornando uma URL de download.
    Melhor para arquivos grandes (>30MB).
    """
    logging.info("PDF compression (Blob) function triggered.")

    try:
        # Obtém o arquivo PDF do request
        pdf_file = req.files.get("file")

        if not pdf_file:
            return func.HttpResponse(
                '{"error": "Por favor, envie um arquivo PDF usando o campo \'file\'."}',
                mimetype="application/json",
                status_code=400,
            )

        # Lê o conteúdo do arquivo
        pdf_content = pdf_file.read()
        logging.info(f"PDF size: {len(pdf_content)} bytes")

        # Verifica o tamanho (100MB = 104857600 bytes)
        if len(pdf_content) > 104857600:
            return func.HttpResponse(
                '{"error": "O arquivo excede o tamanho máximo de 100MB."}',
                mimetype="application/json",
                status_code=400,
            )

        # Cria um arquivo temporário para o PyMuPDF processar
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".pdf"
        ) as temp_file:
            temp_file.write(pdf_content)
            temp_path = temp_file.name

        logging.info(f"Temp file created: {temp_path}")

        try:
            # Executa a compressão
            logging.info("Starting compression...")
            compressed_pdf = reduce_pdf_size(
                input_pdf=temp_path,
                skip_first=req.params.get("skip_first", "true").lower()
                == "true",
                skip_last=req.params.get("skip_last", "true").lower() == "true",
            )

            logging.info(
                f"Compression completed. Size: {len(compressed_pdf)} bytes"
            )

            # Upload para Blob Storage
            connection_string = os.environ.get("AzureWebJobsStorage")
            if not connection_string:
                raise ValueError("AzureWebJobsStorage não configurado")

            blob_service_client = BlobServiceClient.from_connection_string(
                connection_string
            )
            container_name = "compressed-pdfs"

            # Cria o container se não existir
            try:
                blob_service_client.create_container(container_name)
            except Exception:
                pass  # Container já existe

            # Nome único para o blob
            blob_name = f"{uuid.uuid4()}_compressed_{pdf_file.filename}"
            blob_client = blob_service_client.get_blob_client(
                container=container_name, blob=blob_name
            )

            # Upload do PDF comprimido
            blob_client.upload_blob(compressed_pdf, overwrite=True)
            logging.info(f"PDF uploaded to blob: {blob_name}")

            # Gera SAS token com validade de 1 hora
            sas_token = generate_blob_sas(
                account_name=blob_service_client.account_name,
                container_name=container_name,
                blob_name=blob_name,
                account_key=blob_service_client.credential.account_key,
                permission=BlobSasPermissions(read=True),
                expiry=datetime.utcnow() + timedelta(hours=1),
            )

            download_url = f"{blob_client.url}?{sas_token}"

            return func.HttpResponse(
                body=f'{{"download_url": "{download_url}", "filename": "compressed_{pdf_file.filename}", "size": {len(compressed_pdf)}, "expires_in": "1 hour"}}',
                mimetype="application/json",
                status_code=200,
            )

        finally:
            # Remove o arquivo temporário
            if os.path.exists(temp_path):
                os.remove(temp_path)
                logging.info(f"Temp file removed: {temp_path}")

    except Exception as e:
        logging.error(f"Erro ao processar PDF: {str(e)}", exc_info=True)
        return func.HttpResponse(
            f'{{"error": "Erro ao processar o PDF: {str(e)}"}}',
            mimetype="application/json",
            status_code=500,
        )


@app.route(route="compress_pdf")
def compress_pdf(req: func.HttpRequest) -> func.HttpResponse:
    """
    Comprime o PDF e retorna diretamente no response.
    Melhor para arquivos pequenos (<30MB).
    """
    logging.info("PDF compression (direct) function triggered.")

    try:
        # Obtém o arquivo PDF do request
        pdf_file = req.files.get("file")

        if not pdf_file:
            return func.HttpResponse(
                "Por favor, envie um arquivo PDF usando o campo 'file'.",
                status_code=400,
            )

        # Lê o conteúdo do arquivo
        pdf_content = pdf_file.read()
        logging.info(f"PDF size: {len(pdf_content)} bytes")

        # Verifica o tamanho (100MB = 104857600 bytes)
        if len(pdf_content) > 104857600:
            return func.HttpResponse(
                "O arquivo excede o tamanho máximo de 100MB.", status_code=400
            )

        # Cria um arquivo temporário para o PyMuPDF processar
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".pdf"
        ) as temp_file:
            temp_file.write(pdf_content)
            temp_path = temp_file.name

        logging.info(f"Temp file created: {temp_path}")

        try:
            # Executa a compressão
            logging.info("Starting compression...")
            compressed_pdf = reduce_pdf_size(
                input_pdf=temp_path,
                skip_first=req.params.get("skip_first", "true").lower()
                == "true",
                skip_last=req.params.get("skip_last", "true").lower() == "true",
            )

            logging.info(
                f"Compression completed. Size: {len(compressed_pdf)} bytes"
            )

            # Retorna o PDF comprimido
            response = func.HttpResponse(
                body=compressed_pdf,
                mimetype="application/pdf",
                status_code=200,
                headers={
                    "Content-Disposition": f"attachment; filename=compressed_{pdf_file.filename}",
                    "Content-Length": str(len(compressed_pdf)),
                },
            )
            logging.info("Response created successfully")
            return response

        finally:
            # Remove o arquivo temporário
            if os.path.exists(temp_path):
                os.remove(temp_path)
                logging.info(f"Temp file removed: {temp_path}")

    except Exception as e:
        logging.error(f"Erro ao processar PDF: {str(e)}", exc_info=True)
        return func.HttpResponse(
            f"Erro ao processar o PDF: {str(e)}", status_code=500
        )
