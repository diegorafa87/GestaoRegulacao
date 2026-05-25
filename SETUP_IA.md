## 🤖 Configuração da IA com Google Gemini

A IA foi integrada com sucesso ao sistema! Para funcionar, você precisa configurar a API key do Google Gemini.

### Passo 1: Obter a API Key do Google Gemini

1. Acesse: https://aistudio.google.com/app/apikey
2. Clique em "Create API Key"
3. Copie a chave gerada

### Passo 2: Adicionar ao arquivo .env

1. Abra o arquivo `.env` na raiz do projeto
2. Adicione a seguinte linha:
```
GEMINI_API_KEY=sua_chave_aqui
```

3. Substitua `sua_chave_aqui` pela API key que você copiou

### Passo 3: Reiniciar a aplicação

1. Pare o servidor Flask (Ctrl+C)
2. Reinicie: `python app.py`

### 🎯 Funcionalidades da IA

Agora você pode acessar a IA através do menu "🤖 IA Chat" e:

✅ **Fazer perguntas em linguagem natural** como:
- "Quantos pacientes temos?"
- "Qual é o status das solicitações?"
- "Quais as especialidades mais solicitadas?"
- "Gere um relatório completo"

✅ **Gerar relatórios automáticos** sobre:
- Pacientes cadastrados
- Solicitações e seus status
- Especialidades mais solicitadas
- Tendências dos últimos 7 dias

✅ **Baixar relatórios como PDF**
- Clique em "📥 Baixar como PDF" após receber a resposta

### 📊 Dados que a IA pode acessar

A IA tem acesso a:
- Total de pacientes e solicitações
- Status das solicitações (ELETIVO, URGENTE, RETORNO, EXECUTADO)
- Tipos de requisição (CONSULTA, EXAME, CIRURGIA)
- Especialidades cadastradas
- Datas de inserção e realização

### 🔒 Privacidade

- As perguntas são enviadas para o servidor Gemini
- Apenas dados agregados são consultados (sem informações sensíveis individuais)
- Cada pergunta gera um novo contexto independente

### ⚠️ Troubleshooting

**Erro: "API key do Gemini não configurada"**
- Verifique se adicionou a chave no arquivo `.env`
- Verifique se a chave está correta
- Reinicie a aplicação

**Erro: "Quota excedida"**
- A API do Gemini tem limite de requisições
- Aguarde alguns minutos e tente novamente

**Resposta muito lenta**
- A primeira requisição pode ser mais lenta (inicialização)
- Requisições subsequentes são mais rápidas

---

Aproveite o power da IA para extrair insights do seu sistema de regulação! 🚀
