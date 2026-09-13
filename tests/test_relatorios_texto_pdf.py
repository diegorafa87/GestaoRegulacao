import io

from pypdf import PdfReader

from app import gerar_pdf_relatorio_texto


def _extrair_texto_pdf(pdf_bytes):
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return '\n'.join(page.extract_text() or '' for page in reader.pages)


def test_gerar_pdf_relatorio_texto_inclui_cabecalho_e_conteudo():
    conteudo = "CONSULTA\nULTRASSONOGRAFIA"

    pdf_bytes = gerar_pdf_relatorio_texto(
        conteudo,
        "Relatório Sintético",
        "01/01/2024 a 31/01/2024",
        "Sintético",
    )

    assert pdf_bytes.startswith(b'%PDF')
    texto_pdf = _extrair_texto_pdf(pdf_bytes)
    assert 'Secretaria Municipal de Saúde de Fernando Pedroza' in texto_pdf
    assert 'Relatório Sintético' in texto_pdf
    assert 'CONSULTA' in texto_pdf
    assert 'ULTRASSONOGRAFIA' in texto_pdf
    assert b'/XObject' in pdf_bytes or b'/Subtype /Image' in pdf_bytes


def test_gerar_pdf_relatorio_texto_usa_tabela_para_especialidades_e_quantidades():
    conteudo = "CONSULTA (3)\nULTRASSONOGRAFIA (2)"

    pdf_bytes = gerar_pdf_relatorio_texto(
        conteudo,
        "Relatório Sintético",
        "01/01/2024 a 31/01/2024",
        "Sintético",
    )

    assert pdf_bytes.startswith(b'%PDF')
    texto_pdf = _extrair_texto_pdf(pdf_bytes)
    assert 'Especialidade' in texto_pdf
    assert 'Quantidade' in texto_pdf
    assert 'CONSULTA' in texto_pdf
    assert '3' in texto_pdf
