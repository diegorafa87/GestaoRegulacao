import os
import sys
from datetime import date

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import mapear_dados_cadsus, calcular_idade, separar_endereco_em_campos, montar_endereco, formatar_endereco_lista


def test_mapear_dados_cadsus_extrai_campos_basicos():
    payload = {
        'nomeCompleto': 'MARIA DA SILVA',
        'sus': '123456789012345',
        'nomeMae': 'JOANA SILVA',
        'endereco': {
            'logradouro': 'RUA DAS FLORES',
            'numero': '100',
            'bairro': 'CENTRO'
        }
    }

    resultado = mapear_dados_cadsus(payload)

    assert resultado['nome'] == 'MARIA DA SILVA'
    assert resultado['sus'] == '123456789012345'
    assert resultado['nome_mae'] == 'JOANA SILVA'
    assert resultado['endereco'] == 'RUA DAS FLORES, Nº 100, BAIRRO CENTRO'


def test_separar_endereco_em_campos_reconhece_rua_numero_e_bairro():
    resultado = separar_endereco_em_campos('RUA DAS FLORES, Nº 100, BAIRRO CENTRO')

    assert resultado == {
        'rua': 'RUA DAS FLORES',
        'numero': '100',
        'bairro': 'CENTRO',
        'sem_numero': False,
    }


def test_montar_endereco_com_sem_numero_retorna_sn():
    resultado = montar_endereco('RUA DAS FLORES', '', 'CENTRO', sem_numero=True)

    assert resultado == 'RUA DAS FLORES, S/N, BAIRRO CENTRO'


def test_formatar_endereco_lista_preserva_bairro_completo():
    resultado = formatar_endereco_lista('RUA DAS FLORES, S/N, BAIRRO CENTRO')

    assert resultado == 'RUA DAS FLORES, S/N, CENTRO, FERNANDO PEDROZA, RN.'


def test_calcular_idade_para_datas_validas():
    hoje = date.today()
    idade_2000 = hoje.year - 2000 - ((hoje.month, hoje.day) < (1, 15))
    idade_2010 = hoje.year - 2010 - ((hoje.month, hoje.day) < (12, 31))

    assert calcular_idade('2000-01-15') == f'{idade_2000} anos'
    assert calcular_idade('2010-12-31') == f'{idade_2010} anos'
    assert calcular_idade(None) == ''
