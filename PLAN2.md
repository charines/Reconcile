**Plano de Melhoria — Tela Administrativa + Requalificação + Tipos de Regras**

## **Resumo**
Vamos evoluir o MVP para uma **tela administrativa** com 3 opções: **Importar**, **Requalificar** e **Cadastrar Regras**.  
As regras passam a ter **tipo** (`financeira` ou `gerencial`).  
A importação passa a usar um **tipo de regra selecionado** (padrão: `financeira`).  
A requalificação reprocessa imports selecionados, **atualiza o mesmo registro** e mostra um **resumo** do que foi requalificado.  
Também adicionamos **CRUD completo** de regras e **remoção de importações** (apagando arquivos no Storage).

---

## **Mudanças de Dados (Supabase)**
### **Tabela `qualifications`**
Adicionar coluna `rule_type` com valores permitidos:
- `financeira`
- `gerencial`

```sql
alter table public.qualifications
add column if not exists rule_type text not null default 'financeira';

alter table public.qualifications
add constraint qualifications_rule_type_check
check (rule_type in ('financeira', 'gerencial'));
```

### **Tabela `imports`**
Adicionar coluna `rule_type` usada na importação/requalificação:

```sql
alter table public.imports
add column if not exists rule_type text not null default 'financeira';

alter table public.imports
add constraint imports_rule_type_check
check (rule_type in ('financeira', 'gerencial'));
```

**Decisão:** A requalificação **atualiza o registro existente** (mesmo `id`), criando novo output e atualizando `output_file_path`, `row_count` e `rule_type`.

---

## **Mudanças de API (Backend FastAPI)**

### **Qualificações**
- `GET /qualifications?rule_type=financeira|gerencial`
  - Lista filtrada por tipo
- `POST /qualifications`
  - Novo campo obrigatório: `rule_type`
- `PUT /qualifications/{id}`
  - Atualiza `keyword, code, description, priority, rule_type`
- `DELETE /qualifications/{id}`

### **Importações**
- `POST /imports`
  - Novo campo `rule_type` no `Form` (default `financeira`)
  - Usa apenas regras do tipo escolhido
  - Grava `rule_type` no registro

- `GET /imports`
  - Lista importações com paginação e ordenação
  - Parâmetros: `page`, `page_size`, `sort_by`, `sort_dir`
  - Colunas para sort: `created_at`, `company`, `account`, `row_count`, `rule_type`

- `POST /imports/requalify`
  - Body:
    ```json
    {
      "rule_type": "financeira",
      "import_ids": ["uuid1", "uuid2"]
    }
    ```
  - Reprocessa cada import:
    - Baixa input original
    - Aplica regras do tipo escolhido
    - Gera novo output e **atualiza a importação existente**
  - Retorna lista de resultados por import:
    ```json
    [
      { "id": "...", "company": "...", "account": "...", "row_count": 123, "rule_type": "financeira" }
    ]
    ```

- `DELETE /imports/{id}`
  - Remove registro do banco **e arquivos input/output no Storage**
  - Se arquivos não existirem, ignora erro

---

## **Mudanças no Frontend (React)**

### **Tela Administrativa**
Adicionar um seletor principal (tabs/segmented control):
- **Importar**
- **Requalificar**
- **Cadastrar Regras**

### **1. Importar**
- Reaproveitar formulário atual
- Adicionar seletor de tipo de regra (`financeira` padrão)
- Enviar `rule_type` junto no upload

### **2. Cadastrar Regras (CRUD)**
- Campo select para tipo: `financeira` ou `gerencial`
- Form de criação/edição
- Tabela filtrada pelo tipo selecionado
- Ações por linha: **Editar** / **Excluir**
- Editar preenche o form e muda botão para “Salvar alterações”

### **3. Requalificar**
- Select para tipo (`financeira` default)
- Lista de importações com checkbox
- Ações:
  - **Aplicar requalificação** (bulk)
  - **Remover importação** (por linha)
- Tabela de importações:
  - Colunas: checkbox, empresa, conta, banco, agência, tipo, data, linhas
  - Ordenação por clique na coluna
- Paginação com `page_size` selecionável: **19, 25, 50**
- Após requalificar: tabela abaixo com **resumo das importações requalificadas** (empresa, conta, tipo, linhas)

---

## **Regras de Processamento**
- Filtrar regras por `rule_type`
- Matching permanece igual:
  - `keyword` contida no `historico` (case-insensitive)
  - menor `priority` vence
- `rule_type` gravado em `imports`

---

## **Testes / Cenários**
1. **CRUD de Regras**
   - Criar regra `financeira` e `gerencial`
   - Editar prioridade
   - Excluir regra
   - Listagem filtrada por tipo

2. **Importação por Tipo**
   - Importar com tipo `financeira`
   - Importar com tipo `gerencial`
   - Confirmar `rule_type` gravado em `imports`

3. **Requalificação**
   - Selecionar 2 imports, aplicar tipo `gerencial`
   - Confirmar output atualizado e `rule_type` alterado
   - Tabela de requalificados mostrando empresa/conta

4. **Paginação e Ordenação**
   - Alternar page size 19 / 25 / 50
   - Ordenar por empresa/conta/data e verificar mudança

5. **Remoção**
   - Excluir importação e validar remoção dos arquivos no Storage

---

## **Assunções e Defaults**
- `rule_type` tem apenas `financeira` e `gerencial`
- Requalificação atualiza a importação existente (não cria nova)
- Remoção de importação apaga arquivos no Storage
- Paginação/ordenação da lista de importações é **server-side**
