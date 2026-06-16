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

## Configurar API do Google (Gemini)

Para ativar o chat IA usando o modelo Gemini (Google Generative AI):

- Crie um arquivo `.env` na raiz (ou edite o existente) com a variável `GEMINI_API_KEY` contendo sua chave.
- Se quiser forçar o modo de desenvolvimento sem chamar a API, ajuste `USE_MOCK_IA=true` no `.env`.
- Reinicie a aplicação e acesse a rota `/ia_chat` (é necessário login) para testar o chat.

Dependências relevantes já incluídas em `requirements.txt`: `google-generativeai`, `python-dotenv`.
