import io
import logging
import os
import tempfile

import azure.functions as func

from compress_pdf import reduce_pdf_size

app = func.FunctionApp(http_auth_level=func.AuthLevel.ADMIN)


@app.route(route="compress_pdf")
def compress_pdf(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("PDF compression function triggered.")

    try:
        # Obtém o arquivo PDF do request
        pdf_file = req.files.get("file")
        logging.info(f"Files in request: {list(req.files.keys())}")

        if not pdf_file:
            return func.HttpResponse(
                "Por favor, envie um arquivo PDF usando o campo 'file'."
                "status_code=400",
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

            # Verifica o tamanho antes de retornar
            if len(compressed_pdf) > 50000000:  # 50MB
                logging.warning(
                    f"PDF comprimido é grande: {len(compressed_pdf) / 1024 / 1024:.2f}MB"
                )

            # Retorna o PDF comprimido com headers otimizados
            response = func.HttpResponse(
                body=compressed_pdf,
                mimetype="application/pdf",
                status_code=200,
                headers={
                    "Content-Disposition": f"attachment; filename=compressed_{pdf_file.filename}",
                    "Content-Length": str(len(compressed_pdf)),
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                },
            )
            logging.info(
                f"Response created successfully. Sending {len(compressed_pdf)} bytes"
            )
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
