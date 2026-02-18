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

## Deploy no Render (monorepo)
### Backend (FastAPI) - Web Service
1. Crie um **Web Service** no Render conectado ao repo.
2. Configure:
   - Root Directory: `backend`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. Variaveis de ambiente (Render -> Environment):
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_ROLE_KEY`
   - `SUPABASE_INPUTS_BUCKET` (ex: `inputs`)
   - `SUPABASE_OUTPUTS_BUCKET` (ex: `outputs`)
   - `CORS_ORIGIN` (URL do frontend no Render)
4. (Opcional) Health Check Path: `/health`
5. Habilite auto-deploy do branch `main`.

### Frontend (React/Vite) - Static Site
1. Crie um **Static Site** no Render conectado ao mesmo repo.
2. Configure:
   - Root Directory: `frontend`
   - Build Command: `npm install && npm run build`
   - Publish Directory: `dist`
3. Variaveis de ambiente:
   - `VITE_API_BASE` = URL do backend no Render (ex: `https://seu-backend.onrender.com`)
4. Habilite auto-deploy do branch `main`.

### Observacao importante
- Depois de obter as URLs finais do Render, atualize `CORS_ORIGIN` no backend e `VITE_API_BASE` no frontend e force um novo deploy.

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
