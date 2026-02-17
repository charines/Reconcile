# Reconcile

MVP para qualificacao de extratos bancarios com React + FastAPI + Supabase.

## Visao geral
- Upload de CSV padronizado com colunas `data,valor,historico`
- Aplicacao de regras por palavras-chave
- Resultado em tabela paginada e download do CSV qualificado

## Estrutura do repo
- `backend/` FastAPI (Python)
- `frontend/` React (Vite)
- `supabase/schema.sql` SQL para tabelas

## Requisitos
- Python 3.11+
- Node 18+
- Conta no Supabase

## Configuracao do Supabase
1. Crie um projeto no Supabase.
2. Rode o SQL em `supabase/schema.sql`.
3. Crie os buckets `inputs` e `outputs` (Storage).
4. Copie o `SUPABASE_URL` e o `SUPABASE_SERVICE_ROLE_KEY`.

## Backend (FastAPI)
1. Copie `backend/.env.example` para `backend/.env` e preencha as chaves.
2. Instale dependencias:
   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. Suba a API:
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

## Frontend (React)
1. Copie `frontend/.env.example` para `frontend/.env` e ajuste se necessario.
2. Instale dependencias:
   ```bash
   cd frontend
   npm install
   ```
3. Inicie o frontend:
   ```bash
   npm run dev
   ```

## Formato do CSV de entrada
- Colunas obrigatorias: `data,valor,historico`
- Separador `,` ou `;` (detectado automaticamente)
- Datas: `dd/mm/yyyy` ou `yyyy-mm-dd`
- Valores: `1.234,56` ou `1234.56`

## Endpoints principais
- `GET /health`
- `GET /qualifications`
- `POST /qualifications`
- `POST /imports`
- `GET /imports/{id}`
- `GET /imports/{id}/download`

## Observacoes
- Sem autenticacao no MVP.
- Sem IA/N8N no processamento.
- Para volumes maiores, adicionar processamento assincrono.
