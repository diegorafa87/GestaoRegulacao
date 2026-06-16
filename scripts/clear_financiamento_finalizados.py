from db import conectar

"""
Script one-off para limpar o campo financiamento de todas as solicitações
cuja conclusão seja CANCELADO ou RETIRADO.

Uso:
    python scripts/clear_financiamento_finalizados.py

Faça backup do banco antes de executar.
"""

if __name__ == '__main__':
    conn = conectar()
    c = conn.cursor()
    try:
        c.execute("UPDATE solicitacao SET financiamento = NULL WHERE UPPER(COALESCE(conclusao, '')) IN ('CANCELADO', 'RETIRADO')")
        updated = c.rowcount
        conn.commit()
        print(f'Atualizado(s) {updated} registro(s).')
    except Exception as e:
        conn.rollback()
        print('Erro ao atualizar registros:', e)
    finally:
        conn.close()
