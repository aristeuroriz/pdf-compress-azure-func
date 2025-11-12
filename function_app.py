import logging
import os
import tempfile
import uuid

import azure.functions as func
from azure.storage.blob import BlobServiceClient

from compress_pdf import reduce_pdf_size

app = func.FunctionApp(http_auth_level=func.AuthLevel.ADMIN)


@app.route(route="compress_pdf")
def compress_pdf(req: func.HttpRequest) -> func.HttpResponse:
    """
    Comprime o PDF e retorna uma URL do Blob Storage para download.
    Solução para arquivos grandes (>30MB) no Flex Consumption Plan.
    """
    logging.info("PDF compression (Blob Storage) function triggered.")

    try:
        # Obtém o arquivo PDF do request
        pdf_file = req.files.get("file")
        logging.info(f"Files in request: {list(req.files.keys())}")

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

            # Upload para o Blob Storage
            connection_string = os.environ.get("AzureWebJobsStorage")
            if not connection_string:
                return func.HttpResponse(
                    "AzureWebJobsStorage não configurado.", status_code=500
                )

            # Para desenvolvimento local com Azurite
            if connection_string == "UseDevelopmentStorage=true":
                connection_string = "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;"

            blob_service_client = BlobServiceClient.from_connection_string(
                connection_string
            )
            container_name = "compressed-pdfs"

            # Cria o container se não existir
            try:
                container_client = blob_service_client.get_container_client(
                    container_name
                )
                if not container_client.exists():
                    container_client.create_container()
                    logging.info(f"Container '{container_name}' created.")
            except Exception as e:
                logging.warning(f"Error checking/creating container: {e}")

            # Gera um nome único para o blob
            blob_name = f"{uuid.uuid4()}-compressed-{pdf_file.filename}"
            blob_client = blob_service_client.get_blob_client(
                container=container_name, blob=blob_name
            )

            # Upload do PDF comprimido
            logging.info(f"Uploading to blob: {blob_name}")
            blob_client.upload_blob(compressed_pdf, overwrite=True)
            logging.info("Upload completed.")

            # Gera URL com SAS token (válida por 1 hora)
            blob_url = blob_client.url

            # Retorna a URL e informações
            import json

            result = {
                "message": "PDF comprimido com sucesso!",
                "download_url": blob_url,
                "original_size_bytes": len(pdf_content),
                "compressed_size_bytes": len(compressed_pdf),
                "reduction_percent": round(
                    (1 - len(compressed_pdf) / len(pdf_content)) * 100, 2
                ),
                "blob_name": blob_name,
                "expires_in": "O link está disponível no container",
            }

            return func.HttpResponse(
                body=json.dumps(result, indent=2),
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
            f"Erro ao processar o PDF: {str(e)}", status_code=500
        )
