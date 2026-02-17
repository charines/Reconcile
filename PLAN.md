# Plano de Implementação do MVP — Qualificação de Extratos

**Summary**
- Construir um MVP local com **React (frontend)** + **FastAPI (backend Python)** usando **Supabase DB + Storage**.
- Entrada via upload de **CSV padronizado** com colunas `data, valor, historico`.
- Qualificação por **substring (case-insensitive)**, escolhendo a **primeira regra válida por prioridade**.
- Saída em **HTML paginado** com opção de download do **CSV qualificado**.

---

## Assumptions & Defaults
- Sem autenticação no MVP (uso interno único).
- Tabela de qualificação **global** (não por empresa/banco/conta).
- Volume pequeno (até ~50k linhas), então paginação client-side é aceitável.
- Não usar IA no MVP; só regras determinísticas.
- CSV de entrada contém apenas `data, valor, historico`; empresa/banco/agencia/conta vêm de um formulário no upload.

---

## Public APIs / Interfaces / Types (Principais Adições)

### Supabase DB (tabelas)
1. **qualifications**
   - `id` (uuid, PK)
   - `keyword` (text, obrigatório)
   - `code` (text, obrigatório)
   - `description` (text, obrigatório)
   - `priority` (int, obrigatório; menor = mais prioritário)
   - `created_at`

2. **imports**
   - `id` (uuid, PK)
   - `company` (text)
   - `bank` (text)
   - `agency` (text)
   - `account` (text)
   - `input_file_path` (text, path no Storage)
   - `output_file_path` (text, path no Storage)
   - `row_count` (int)
   - `created_at`

3. **import_rows** (opcional no MVP; pode pular e gerar só CSV de saída)
   - `id` (uuid, PK)
   - `import_id` (uuid, FK -> imports)
   - `date` (date)
   - `value` (numeric)
   - `history` (text)
   - `qualification_code` (text)
   - `qualification_description` (text)

### Storage Buckets
- `inputs/` para arquivos originais
- `outputs/` para CSV qualificado gerado

### Backend (FastAPI) — endpoints
- `POST /imports`
  - multipart: `file` + `company` + `bank` + `agency` + `account`
  - processa, armazena no Supabase, devolve `import_id`

- `GET /imports/:id`
  - retorna metadados, preview paginado (se não usar `import_rows`, devolve do CSV de saída)

- `GET /imports/:id/download`
  - retorna CSV de saída (stream ou URL assinada do Supabase)

- `GET /qualifications`
  - lista regras de qualificação

- `POST /qualifications`
  - cria regra (keyword, code, description, priority)

---

## Plano de Implementação (Decisão Completa)

### 1. Setup Base
1. Criar projeto React (Vite).
2. Criar backend FastAPI (poetry ou pip + requirements).
3. Configurar Supabase: projeto, DB, buckets e chaves.

### 2. Schema Supabase
1. Criar tabelas `qualifications` e `imports`.
2. (Opcional) Criar `import_rows` se quiser preview com paginação sem ler CSV inteiro.
3. Criar buckets `inputs` e `outputs`.

### 3. Backend FastAPI
1. Endpoint de upload:
   - Recebe CSV + metadados
   - Armazena arquivo original no bucket `inputs/`
   - Lê CSV, normaliza `data` e `valor`
   - Carrega regras `qualifications` ordenadas por `priority ASC`
   - Aplica regra: primeiro `keyword` contido em `historico` (case-insensitive)
   - Gera CSV de saída com:
     `empresa, banco, agencia, conta, data, valor, historico, codigo_qualificacao, descricao_qualificacao`
   - Salva CSV no bucket `outputs/`
   - Registra em `imports` com paths e contagem
2. Endpoint para listar/baixar CSV de saída.
3. Endpoint CRUD básico de `qualifications` (listar + criar é suficiente no MVP).

### 4. Frontend React
1. Tela de upload:
   - Form com `empresa`, `banco`, `agencia`, `conta`
   - Upload do arquivo CSV
2. Tela de resultado:
   - Tabela HTML paginada (client-side para pequeno volume)
   - Botão para download do CSV
3. Tela de cadastro/listagem de qualificações:
   - Form simples para criar regra
   - Tabela de regras existentes

### 5. Processamento e Regras (Detalhe)
- Matching:
  - `if keyword in historico` (case-insensitive)
  - primeira regra por `priority` vence
- Se não houver match:
  - `codigo_qualificacao` e `descricao_qualificacao` vazios (ou `NULL`)
- Parsing CSV:
  - aceitar separador `,` ou `;` (detectar pela 1ª linha)
  - normalizar data `dd/mm/yyyy` e `yyyy-mm-dd`

---

## Testes e Cenários
1. **Upload simples**
   - CSV com 3 linhas, 1 regra => 1 match correto
2. **Sem match**
   - Linha sem palavra-chave => campos de qualificação vazios
3. **Prioridade**
   - Dois keywords presentes => vence o de menor `priority`
4. **Normalização de data/valor**
   - `10/02/2026` e `2026-02-10` devem virar mesma data
   - `1.234,56` e `1234.56` devem virar mesmo valor
5. **Download**
   - CSV gerado com colunas corretas e metadados no início

---

## Out of Scope (MVP)
- IA/N8N na qualificação
- Autenticação e multi-tenant
- Formatos além de CSV (OFX/XLSX)
- Processamento assíncrono para volumes grandes

---

Se quiser, posso evoluir o plano para:
1. IA opcional como fallback
2. Formatos OFX/XLSX
3. Multiempresa e autenticação
4. Paginação server-side para grandes volumes
