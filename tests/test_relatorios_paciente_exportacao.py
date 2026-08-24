from app import formatar_conclusao_relatorio


def test_formatar_conclusao_relatorio_mapeia_labels_para_exportacao():
    assert formatar_conclusao_relatorio('PRESENTE') == 'Presente'
    assert formatar_conclusao_relatorio('AUSENTE') == 'Ausente'
    assert formatar_conclusao_relatorio('CANCELADO') == 'Cancelado'
    assert formatar_conclusao_relatorio('') == '-'
