# Sistema de Regulação de Saúde

Este projeto é um sistema simples de regulação para secretarias de saúde, feito em Python com SQLite e interface de linha de comando (CLI).

## Funcionalidades
- Cadastro de pacientes
- Cadastro de solicitações (consultas, exames, cirurgias)
- Filtros e relatórios por paciente, especialidade, prioridade, status, cronologia e perfil etário

## Como rodar
1. Certifique-se de ter Python 3 instalado.
2. Execute o arquivo `main.py`:
   ```bash
   python main.py
   ```

## Estrutura dos dados
- Paciente: CPF/SUS, nome, nascimento, telefone, endereço
- Solicitação: datas, tipo, especialidade/descrição, prioridade, encaminhamento, status, unidade realizadora

---

Este projeto é um ponto de partida e pode ser expandido conforme a necessidade da secretaria.

## Observação sobre IA

O recurso de chat IA foi removido desta versão. Se precisar reativá-lo no futuro, as dependências e endpoints relacionados estão localizados nos arquivos do projeto.
