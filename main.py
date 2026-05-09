from db import criar_tabelas, conectar
from datetime import datetime

def menu():
    print("\n=== Sistema de Regulação de Saúde ===")
    print("1. Cadastrar paciente")
    print("2. Cadastrar solicitação")
    print("3. Consultar histórico do paciente")
    print("4. Filtrar solicitações")
    print("0. Sair")
    return input("Escolha uma opção: ")

def cadastrar_paciente():
    print("\n--- Cadastro de Paciente ---")
    id = input("CPF ou Cartão SUS: ")
    nome = input("Nome completo: ")
    nascimento = input("Data de nascimento (AAAA-MM-DD): ")
    telefone = input("Telefone: ")
    endereco = input("Endereço: ")
    conn = conectar()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO paciente (id, nome, nascimento, telefone, endereco) VALUES (?, ?, ?, ?, ?)",
                  (id, nome, nascimento, telefone, endereco))
        conn.commit()
        print("Paciente cadastrado com sucesso!")
    except sqlite3.IntegrityError:
        print("Já existe um paciente com esse CPF/SUS.")
    conn.close()

def cadastrar_solicitacao():
    print("\n--- Cadastro de Solicitação ---")
    paciente_id = input("CPF ou Cartão SUS do paciente: ")
    data_solicitacao = input("Data da solicitação médica (AAAA-MM-DD): ")
    data_entrada = input("Data de entrada na secretaria (AAAA-MM-DD): ")
    data_insercao = datetime.now().strftime('%Y-%m-%d')
    tipo = input("Tipo (Consulta, Exame, Cirurgia): ")
    especialidade = input("Especialidade ou descrição do exame: ")
    prioridade = input("Prioridade (Eletivo, Urgente): ")
    encaminhamento = input("Programa (Regula RN, Sisreg, etc): ")
    status = input("Status (Em espera, Realizado, Devolvido): ")
    data_realizacao = None
    unidade_realizadora = None
    if status.lower() == 'realizado':
        data_realizacao = input("Data de realização (AAAA-MM-DD): ")
        unidade_realizadora = input("Unidade realizadora: ")
    conn = conectar()
    c = conn.cursor()
    c.execute("INSERT INTO solicitacao (paciente_id, data_solicitacao, data_entrada, data_insercao, data_realizacao, unidade_realizadora, tipo, especialidade, descricao, prioridade, encaminhamento, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
              (paciente_id, data_solicitacao, data_entrada, data_insercao, data_realizacao, unidade_realizadora, tipo, especialidade, especialidade, prioridade, encaminhamento, status))
    conn.commit()
    conn.close()
    print("Solicitação cadastrada com sucesso!")

def consultar_historico():
    print("\n--- Histórico do Paciente ---")
    paciente_id = input("CPF ou Cartão SUS: ")
    conn = conectar()
    c = conn.cursor()

    def filtrar_solicitacoes():
        while True:
            print("\n--- Filtros de Solicitações ---")
            print("1. Por Especialidade")
            print("2. Por Prioridade + Status")
            print("3. Por Data de Entrada (FIFO)")
            print("4. Por Perfil Etário (idade)")
            print("0. Voltar")
            op = input("Escolha um filtro: ")
            conn = conectar()
            c = conn.cursor()
            if op == '1':
                esp = input("Especialidade: ")
                c.execute("SELECT * FROM solicitacao WHERE especialidade LIKE ?", (f"%{esp}%",))
                rows = c.fetchall()
                print(f"\nSolicitações para {esp}:")
                for row in rows:
                    print(row)
            elif op == '2':
                prioridade = input("Prioridade (Eletivo/Urgente): ")
                status = input("Status (Em espera/Realizado/Devolvido): ")
                c.execute("SELECT * FROM solicitacao WHERE prioridade=? AND status=?", (prioridade, status))
                rows = c.fetchall()
                print(f"\nSolicitações {prioridade} + {status}:")
                for row in rows:
                    print(row)
            elif op == '3':
                data = input("Data de entrada (AAAA-MM-DD): ")
                c.execute("SELECT * FROM solicitacao WHERE data_entrada=? ORDER BY data_entrada ASC", (data,))
                rows = c.fetchall()
                print(f"\nSolicitações na data {data}:")
                for row in rows:
                    print(row)
            elif op == '4':
                idade_min = int(input("Idade mínima: "))
                idade_max = int(input("Idade máxima: "))
                hoje = datetime.now().date()
                c.execute("SELECT p.id, p.nome, p.nascimento, s.* FROM paciente p JOIN solicitacao s ON p.id = s.paciente_id")
                rows = c.fetchall()
                print(f"\nSolicitações para pacientes entre {idade_min} e {idade_max} anos:")
                for row in rows:
                    nascimento = datetime.strptime(row[2], '%Y-%m-%d').date()
                    idade = (hoje - nascimento).days // 365
                    if idade_min <= idade <= idade_max:
                        print(row)
            elif op == '0':
                conn.close()
                break
            else:
                print("Opção inválida!")
            conn.close()
    c.execute("SELECT nome FROM paciente WHERE id = ?", (paciente_id,))
    paciente = c.fetchone()
    if not paciente:
        print("Paciente não encontrado.")
        conn.close()
        return
    print(f"Paciente: {paciente[0]}")
    c.execute("SELECT * FROM solicitacao WHERE paciente_id = ?", (paciente_id,))
    rows = c.fetchall()
    if not rows:
        print("Nenhuma solicitação encontrada.")
    else:
        for row in rows:
            print(row)
    conn.close()

def main():
    criar_tabelas()
    while True:
        op = menu()
        if op == '1':
            cadastrar_paciente()
        elif op == '2':
            cadastrar_solicitacao()
        elif op == '3':
            consultar_historico()
            elif op == '4':
                filtrar_solicitacoes()
        elif op == '0':
            print("Saindo...")
            break
        else:
            print("Opção inválida!")

if __name__ == '__main__':
    main()
