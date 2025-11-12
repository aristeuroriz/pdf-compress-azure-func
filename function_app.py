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

        if not pdf_file:
            return func.HttpResponse(
                "Por favor, envie um arquivo PDF usando o campo 'file'."
                "status_code=400",
            )

        # Lê o conteúdo do arquivo
        pdf_content = pdf_file.read()

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

        try:
            # Executa a compressão
            compressed_pdf = reduce_pdf_size(
                input_pdf=temp_path,
                skip_first=req.params.get("skip_first", "true").lower()
                == "true",
                skip_last=req.params.get("skip_last", "true").lower() == "true",
            )

            # Retorna o PDF comprimido
            return func.HttpResponse(
                body=compressed_pdf,
                mimetype="application/pdf",
                status_code=200,
                headers={
                    "Content-Disposition": f"attachment; filename=compressed_{pdf_file.filename}"
                },
            )
        finally:
            # Remove o arquivo temporário
            if os.path.exists(temp_path):
                os.remove(temp_path)

    except Exception as e:
        logging.error(f"Erro ao processar PDF: {str(e)}")
        return func.HttpResponse(
            f"Erro ao processar o PDF: {str(e)}", status_code=500
        )
