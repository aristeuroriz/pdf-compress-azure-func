#!/bin/bash

# Teste local
FUNCTION_URL="http://localhost:7071/api/compress_pdf_blob"
INPUT_PDF="enoteca_catarina.pdf"

echo "Testando Azure Function LOCALMENTE com Blob Storage..."
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "$FUNCTION_URL" \
  -F "file=@$INPUT_PDF" \
  --max-time 600)

echo "=== RESPOSTA COMPLETA ==="
echo "$RESPONSE"
echo "========================="

# Separa o código HTTP
HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE:" | cut -d':' -f2)
BODY=$(echo "$RESPONSE" | sed '/HTTP_CODE:/d')

echo ""
echo "Status Code: $HTTP_CODE"
echo ""

if command -v jq &> /dev/null; then
    echo "$BODY" | jq .
else
    echo "$BODY"
fi

# Extrai a URL de download
DOWNLOAD_URL=$(echo "$BODY" | grep -o '"download_url":"[^"]*"' | cut -d'"' -f4)

if [ -n "$DOWNLOAD_URL" ] && [ "$DOWNLOAD_URL" != "null" ]; then
    echo ""
    echo "✓ PDF comprimido com sucesso!"
    echo "Fazendo download..."
    curl -s "$DOWNLOAD_URL" --output compressed_local.pdf
    
    if [ -f "compressed_local.pdf" ]; then
        SIZE=$(ls -lh compressed_local.pdf | awk '{print $5}')
        echo "✓ PDF baixado! Tamanho: $SIZE"
    else
        echo "✗ Erro ao baixar o PDF"
    fi
else
    echo "✗ Erro: Não foi possível obter a URL de download"
    echo "Resposta: $BODY"
fi
