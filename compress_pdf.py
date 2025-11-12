# Requer: PyMuPDF (pip install pymupdf)

from typing import List

import fitz  # PyMuPDF


def reduce_pdf_size(
    input_pdf: str,
    ignore_pages: List[int] = None,
    skip_first: bool = True,
    skip_last: bool = True,
):
    """
    Adiciona um retângulo branco em cada página (por baixo do conteúdo),
    cobrindo fundos/arte de background comuns.

    Parâmetros:
      - input_pdf: caminho do PDF de entrada
      - ignore_pages: lista de páginas (1-based) a ignorar (ex.: [2,3])
      - skip_first: se True, ignora a primeira página
      - skip_last: se True, ignora a última página
      - fill_color: cor de preenchimento (R,G,B) em 0..1

    Retorna:
      - bytes do PDF comprimido
    """
    if ignore_pages is None:
        ignore_pages = []

    doc = fitz.open(input_pdf)
    total = len(doc)

    for i in range(total):
        page_number = i + 1  # 1-based para o usuário
        if (
            (skip_first and page_number == 1)
            or (skip_last and page_number == total)
            or (page_number in ignore_pages)
        ):
            print(f"[skip] Página {page_number}")
            continue

    # Remove metadados e faz garbage collection
    doc.set_metadata({})

    # Otimiza e retorna os bytes do PDF
    pdf_bytes = doc.tobytes(garbage=4, deflate=True)
    doc.close()
    return pdf_bytes
