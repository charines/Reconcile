import React, { useEffect, useMemo, useState } from "react";
import {
  createQualification,
  deleteImport,
  deleteQualification,
  fetchImportPreview,
  fetchRequalifiedItems,
  getDownloadUrl,
  getRequalifiedItemsDownloadUrl,
  listImports,
  listQualifications,
  requalifyImports,
  updateQualification,
  uploadImport
} from "./api";

const PAGE_SIZE = 25;
const RULE_TYPES = [
  { value: "financeira", label: "Financeira" },
  { value: "gerencial", label: "Gerencial" }
];
const IMPORT_PAGE_SIZES = [19, 25, 50];

export default function App() {
  const [activeTab, setActiveTab] = useState("importar");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  const [qualifications, setQualifications] = useState([]);
  const [ruleTypeFilter, setRuleTypeFilter] = useState("financeira");
  const [newRule, setNewRule] = useState({
    keyword: "",
    code: "",
    description: "",
    priority: 1,
    rule_type: "financeira"
  });
  const [editingRuleId, setEditingRuleId] = useState(null);

  const [uploadForm, setUploadForm] = useState({
    company: "",
    bank: "",
    agency: "",
    account: "",
    rule_type: "financeira"
  });
  const [file, setFile] = useState(null);
  const [importId, setImportId] = useState("");
  const [importMeta, setImportMeta] = useState(null);
  const [rows, setRows] = useState([]);
  const [page, setPage] = useState(1);
  const [totalRows, setTotalRows] = useState(0);

  const [requalifyRuleType, setRequalifyRuleType] = useState("financeira");
  const [imports, setImports] = useState([]);
  const [importsPage, setImportsPage] = useState(1);
  const [importsPageSize, setImportsPageSize] = useState(25);
  const [importsTotal, setImportsTotal] = useState(0);
  const [importsSortBy, setImportsSortBy] = useState("created_at");
  const [importsSortDir, setImportsSortDir] = useState("desc");
  const [selectedImports, setSelectedImports] = useState(new Set());
  const [requalifyResults, setRequalifyResults] = useState([]);
  const [allRequalifiedItems, setAllRequalifiedItems] = useState([]);
  const [allItemsPage, setAllItemsPage] = useState(1);
  const [allItemsPageSize, setAllItemsPageSize] = useState(25);
  const [allItemsTotal, setAllItemsTotal] = useState(0);
  const [allItemsSortBy, setAllItemsSortBy] = useState("data");
  const [allItemsSortDir, setAllItemsSortDir] = useState("desc");

  useEffect(() => {
    if (activeTab !== "regras") return;
    loadQualifications(ruleTypeFilter);
  }, [activeTab, ruleTypeFilter]);

  useEffect(() => {
    if (!editingRuleId) {
      setNewRule((prev) => ({ ...prev, rule_type: ruleTypeFilter }));
    }
  }, [ruleTypeFilter, editingRuleId]);

  useEffect(() => {
    if (!importId) return;
    loadPreview(importId, page);
  }, [importId, page]);

  useEffect(() => {
    if (activeTab !== "requalificar") return;
    loadImports();
  }, [activeTab, importsPage, importsPageSize, importsSortBy, importsSortDir]);

  useEffect(() => {
    if (activeTab !== "requalificar") return;
    loadAllRequalifiedItems();
  }, [activeTab, allItemsPage, allItemsPageSize, allItemsSortBy, allItemsSortDir]);

  useEffect(() => {
    if (!status && !error) return;
    const timer = setTimeout(() => {
      setStatus("");
      setError("");
    }, 3000);
    return () => clearTimeout(timer);
  }, [status, error]);

  const pageCount = useMemo(() => {
    return Math.max(1, Math.ceil(totalRows / PAGE_SIZE));
  }, [totalRows]);

  const importsPageCount = useMemo(() => {
    return Math.max(1, Math.ceil(importsTotal / importsPageSize));
  }, [importsTotal, importsPageSize]);

  const allItemsPageCount = useMemo(() => {
    return Math.max(1, Math.ceil(allItemsTotal / allItemsPageSize));
  }, [allItemsTotal, allItemsPageSize]);

  async function loadQualifications(ruleType) {
    try {
      const data = await listQualifications(ruleType);
      setQualifications(data);
    } catch (err) {
      setError(err.message || "Falha ao carregar qualificacoes");
    }
  }

  async function handleCreateOrUpdateRule(event) {
    event.preventDefault();
    setError("");
    setStatus(editingRuleId ? "Atualizando qualificacao..." : "Salvando qualificacao...");

    try {
      const payload = {
        ...newRule,
        priority: Number(newRule.priority),
        rule_type: newRule.rule_type || ruleTypeFilter
      };
      if (editingRuleId) {
        await updateQualification(editingRuleId, payload);
      } else {
        await createQualification(payload);
      }
      setNewRule({
        keyword: "",
        code: "",
        description: "",
        priority: 1,
        rule_type: ruleTypeFilter
      });
      setEditingRuleId(null);
      await loadQualifications(ruleTypeFilter);
      setStatus("Qualificacao salva.");
    } catch (err) {
      setError(err.message || "Falha ao salvar qualificacao");
      setStatus("");
    }
  }

  async function handleDeleteRule(id) {
    if (!window.confirm("Deseja remover esta regra?")) return;
    setError("");
    setStatus("Removendo regra...");

    try {
      await deleteQualification(id);
      await loadQualifications(ruleTypeFilter);
      setStatus("Regra removida.");
    } catch (err) {
      setError(err.message || "Falha ao remover regra");
      setStatus("");
    }
  }

  function handleEditRule(rule) {
    setRuleTypeFilter(rule.rule_type || "financeira");
    setNewRule({
      keyword: rule.keyword,
      code: rule.code,
      description: rule.description,
      priority: rule.priority,
      rule_type: rule.rule_type || "financeira"
    });
    setEditingRuleId(rule.id);
  }

  function resetRuleForm() {
    setNewRule({
      keyword: "",
      code: "",
      description: "",
      priority: 1,
      rule_type: ruleTypeFilter
    });
    setEditingRuleId(null);
  }

  async function handleUpload(event) {
    event.preventDefault();
    setError("");
    if (!file) {
      setError("Selecione um arquivo CSV");
      return;
    }

    setStatus("Enviando e processando arquivo...");
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("company", uploadForm.company);
      formData.append("bank", uploadForm.bank);
      formData.append("agency", uploadForm.agency);
      formData.append("account", uploadForm.account);
      formData.append("rule_type", uploadForm.rule_type || "financeira");

      const result = await uploadImport(formData);
      setImportId(result.import_id);
      setPage(1);
      setStatus(`Importacao concluida. ${result.row_count} linhas processadas.`);
    } catch (err) {
      setError(err.message || "Falha ao importar arquivo");
      setStatus("");
    }
  }

  async function loadPreview(id, currentPage) {
    setError("");
    try {
      const data = await fetchImportPreview(id, currentPage, PAGE_SIZE);
      setImportMeta(data.import_data);
      setRows(data.rows || []);
      setTotalRows(data.total_rows || 0);
    } catch (err) {
      setError(err.message || "Falha ao carregar preview");
    }
  }

  async function loadImports() {
    setError("");
    try {
      const data = await listImports({
        page: importsPage,
        pageSize: importsPageSize,
        sortBy: importsSortBy,
        sortDir: importsSortDir
      });
      setImports(data.items || []);
      setImportsTotal(data.total || 0);
      setSelectedImports(new Set());
    } catch (err) {
      setError(err.message || "Falha ao carregar importacoes");
    }
  }

  async function loadAllRequalifiedItems() {
    setError("");
    try {
      const data = await fetchRequalifiedItems(
        allItemsPage,
        allItemsPageSize,
        allItemsSortBy,
        allItemsSortDir
      );
      setAllRequalifiedItems(data.rows || []);
      setAllItemsTotal(data.total_rows || 0);
    } catch (err) {
      setError(err.message || "Falha ao carregar itens requalificados");
    }
  }

  function toggleImportSelection(importIdValue) {
    setSelectedImports((prev) => {
      const next = new Set(prev);
      if (next.has(importIdValue)) {
        next.delete(importIdValue);
      } else {
        next.add(importIdValue);
      }
      return next;
    });
  }

  function handleSort(column) {
    if (importsSortBy === column) {
      setImportsSortDir((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setImportsSortBy(column);
      setImportsSortDir("asc");
    }
  }

  function renderSortLabel(label, column) {
    if (importsSortBy !== column) return label;
    return `${label} ${importsSortDir === "asc" ? "▲" : "▼"}`;
  }

  function handleAllItemsSort(column) {
    if (allItemsSortBy === column) {
      setAllItemsSortDir((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setAllItemsSortBy(column);
      setAllItemsSortDir("asc");
    }
  }

  function renderAllItemsSortLabel(label, column) {
    if (allItemsSortBy !== column) return label;
    return `${label} ${allItemsSortDir === "asc" ? "▲" : "▼"}`;
  }

  async function handleRequalify() {
    if (selectedImports.size === 0) {
      setError("Selecione importacoes para requalificar");
      return;
    }

    setError("");
    setStatus("Requalificando importacoes...");
    try {
      const payload = {
        rule_type: requalifyRuleType,
        import_ids: Array.from(selectedImports)
      };
      const result = await requalifyImports(payload);
      setRequalifyResults(result || []);
      setStatus("Requalificacao concluida.");
      await loadImports();
      await loadAllRequalifiedItems();
    } catch (err) {
      setError(err.message || "Falha ao requalificar importacoes");
      setStatus("");
    }
  }

  async function handleDeleteImport(importIdValue) {
    if (!window.confirm("Deseja remover esta importacao?")) return;
    setError("");
    setStatus("Removendo importacao...");
    try {
      await deleteImport(importIdValue);
      setStatus("Importacao removida.");
      await loadImports();
      await loadAllRequalifiedItems();
    } catch (err) {
      setError(err.message || "Falha ao remover importacao");
      setStatus("");
    }
  }

  return (
    <div className="app">
      {status || error ? (
        <div className={`flash ${error ? "error" : "success"}`}>
          <span>{error || status}</span>
          <button
            type="button"
            className="flash-close"
            onClick={() => {
              setStatus("");
              setError("");
            }}
          >
            Fechar
          </button>
        </div>
      ) : null}
      <header className="hero">
        <div>
          <p className="pill">Reconcile MVP</p>
          <h1>Qualificacao inteligente de extratos</h1>
          <p className="subtitle">
            Faça upload do CSV, aplique regras de palavras-chave e gere um
            arquivo qualificado pronto para analise.
          </p>
        </div>
        <div className="hero-card">
          <h3>Status</h3>
          <p>{status || "Aguardando nova importacao"}</p>
          {error ? <p className="error">{error}</p> : null}
        </div>
      </header>

      <main className="content">
        <div className="tabs">
          <button
            className={`tab ${activeTab === "importar" ? "active" : ""}`}
            onClick={() => setActiveTab("importar")}
            type="button"
          >
            Importar
          </button>
          <button
            className={`tab ${activeTab === "requalificar" ? "active" : ""}`}
            onClick={() => setActiveTab("requalificar")}
            type="button"
          >
            Requalificar
          </button>
          <button
            className={`tab ${activeTab === "regras" ? "active" : ""}`}
            onClick={() => setActiveTab("regras")}
            type="button"
          >
            Cadastrar regras
          </button>
        </div>

        {activeTab === "importar" ? (
          <>
            <section className="grid">
              <form className="card" onSubmit={handleUpload}>
                <h2>Nova importacao</h2>
                <div className="field">
                  <label>Empresa</label>
                  <input
                    value={uploadForm.company}
                    onChange={(event) =>
                      setUploadForm({
                        ...uploadForm,
                        company: event.target.value
                      })
                    }
                    placeholder="Ex: ACME Ltda"
                    required
                  />
                </div>
                <div className="field">
                  <label>Banco</label>
                  <input
                    value={uploadForm.bank}
                    onChange={(event) =>
                      setUploadForm({
                        ...uploadForm,
                        bank: event.target.value
                      })
                    }
                    placeholder="Ex: 341"
                    required
                  />
                </div>
                <div className="field">
                  <label>Agencia</label>
                  <input
                    value={uploadForm.agency}
                    onChange={(event) =>
                      setUploadForm({
                        ...uploadForm,
                        agency: event.target.value
                      })
                    }
                    placeholder="Ex: 0001"
                    required
                  />
                </div>
                <div className="field">
                  <label>Conta</label>
                  <input
                    value={uploadForm.account}
                    onChange={(event) =>
                      setUploadForm({
                        ...uploadForm,
                        account: event.target.value
                      })
                    }
                    placeholder="Ex: 12345-6"
                    required
                  />
                </div>
                <div className="field">
                  <label>Tipo de regra</label>
                  <select
                    value={uploadForm.rule_type}
                    onChange={(event) =>
                      setUploadForm({
                        ...uploadForm,
                        rule_type: event.target.value
                      })
                    }
                  >
                    {RULE_TYPES.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="field">
                  <label>Arquivo CSV</label>
                  <input
                    type="file"
                    accept=".csv,text/csv"
                    onChange={(event) => setFile(event.target.files?.[0] || null)}
                    required
                  />
                </div>
                <button className="primary" type="submit">
                  Processar extrato
                </button>
              </form>
            </section>

            <section className="card table-card">
              <div className="table-header">
                <h2>Resultado da importacao</h2>
                {importId ? (
                  <a className="link" href={getDownloadUrl(importId)}>
                    Baixar CSV
                  </a>
                ) : (
                  <span>Sem importacao</span>
                )}
              </div>
              {importMeta ? (
                <div className="meta">
                  <div>
                    <strong>Empresa:</strong> {importMeta.company}
                  </div>
                  <div>
                    <strong>Banco:</strong> {importMeta.bank}
                  </div>
                  <div>
                    <strong>Agencia:</strong> {importMeta.agency}
                  </div>
                  <div>
                    <strong>Conta:</strong> {importMeta.account}
                  </div>
                  <div>
                    <strong>Tipo:</strong> {importMeta.rule_type || "financeira"}
                  </div>
                </div>
              ) : null}
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Data</th>
                      <th>Valor</th>
                      <th>Historico</th>
                      <th>Codigo</th>
                      <th>Descricao</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row, index) => (
                      <tr key={`${row.data}-${index}`}>
                        <td>{row.data}</td>
                        <td>{row.valor}</td>
                        <td>{row.historico}</td>
                        <td>{row.codigo_qualificacao}</td>
                        <td>{row.descricao_qualificacao}</td>
                      </tr>
                    ))}
                    {rows.length === 0 ? (
                      <tr>
                        <td colSpan="5">Sem dados para exibir.</td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              </div>
              <div className="pagination">
                <button
                  className="ghost"
                  onClick={() => setPage((prev) => Math.max(1, prev - 1))}
                  disabled={page <= 1}
                >
                  Anterior
                </button>
                <span>
                  Pagina {page} de {pageCount}
                </span>
                <button
                  className="ghost"
                  onClick={() => setPage((prev) => Math.min(pageCount, prev + 1))}
                  disabled={page >= pageCount}
                >
                  Proxima
                </button>
              </div>
            </section>
          </>
        ) : null}

        {activeTab === "regras" ? (
          <>
            <section className="grid">
              <form className="card" onSubmit={handleCreateOrUpdateRule}>
                <h2>{editingRuleId ? "Editar regra" : "Nova qualificacao"}</h2>
                <div className="field">
                  <label>Tipo de regra</label>
                  <select
                    value={newRule.rule_type}
                    onChange={(event) =>
                      setNewRule({
                        ...newRule,
                        rule_type: event.target.value
                      })
                    }
                  >
                    {RULE_TYPES.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="field">
                  <label>Palavra-chave</label>
                  <input
                    value={newRule.keyword}
                    onChange={(event) =>
                      setNewRule({ ...newRule, keyword: event.target.value })
                    }
                    placeholder="Ex: TARIFA"
                    required
                  />
                </div>
                <div className="field">
                  <label>Codigo</label>
                  <input
                    value={newRule.code}
                    onChange={(event) =>
                      setNewRule({ ...newRule, code: event.target.value })
                    }
                    placeholder="Ex: DESP"
                    required
                  />
                </div>
                <div className="field">
                  <label>Descricao</label>
                  <input
                    value={newRule.description}
                    onChange={(event) =>
                      setNewRule({
                        ...newRule,
                        description: event.target.value
                      })
                    }
                    placeholder="Ex: Tarifas bancarias"
                    required
                  />
                </div>
                <div className="field">
                  <label>Prioridade</label>
                  <input
                    type="number"
                    min="1"
                    value={newRule.priority}
                    onChange={(event) =>
                      setNewRule({ ...newRule, priority: event.target.value })
                    }
                    required
                  />
                </div>
                <div className="actions">
                  <button className="primary" type="submit">
                    {editingRuleId ? "Salvar alteracoes" : "Salvar regra"}
                  </button>
                  {editingRuleId ? (
                    <button className="ghost" type="button" onClick={resetRuleForm}>
                      Cancelar
                    </button>
                  ) : null}
                </div>
              </form>

              <div className="card">
                <h2>Filtro de regras</h2>
                <div className="field">
                  <label>Tipo</label>
                  <select
                    value={ruleTypeFilter}
                    onChange={(event) => {
                      setRuleTypeFilter(event.target.value);
                      setEditingRuleId(null);
                    }}
                  >
                    {RULE_TYPES.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>
                <p className="muted">
                  {qualifications.length} regras encontradas.
                </p>
              </div>
            </section>

            <section className="card table-card">
              <div className="table-header">
                <h2>Regras cadastradas</h2>
                <span>{qualifications.length} regras</span>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Prioridade</th>
                      <th>Palavra-chave</th>
                      <th>Codigo</th>
                      <th>Descricao</th>
                      <th>Tipo</th>
                      <th>Acoes</th>
                    </tr>
                  </thead>
                  <tbody>
                    {qualifications.map((q) => (
                      <tr key={q.id}>
                        <td>{q.priority}</td>
                        <td>{q.keyword}</td>
                        <td>{q.code}</td>
                        <td>{q.description}</td>
                        <td>{q.rule_type}</td>
                        <td>
                          <div className="table-actions">
                            <button
                              className="ghost small"
                              type="button"
                              onClick={() => handleEditRule(q)}
                            >
                              Editar
                            </button>
                            <button
                              className="danger small"
                              type="button"
                              onClick={() => handleDeleteRule(q.id)}
                            >
                              Excluir
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                    {qualifications.length === 0 ? (
                      <tr>
                        <td colSpan="6">Nenhuma regra cadastrada.</td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              </div>
            </section>
          </>
        ) : null}

        {activeTab === "requalificar" ? (
          <>
            <section className="card">
              <div className="requalify-header">
                <div>
                  <h2>Requalificacao</h2>
                  <p className="muted">
                    Selecione as importacoes e aplique o tipo de regra desejado.
                  </p>
                </div>
                <div className="requalify-controls">
                  <div className="field">
                    <label>Tipo de regra</label>
                    <select
                      value={requalifyRuleType}
                      onChange={(event) => setRequalifyRuleType(event.target.value)}
                    >
                      {RULE_TYPES.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <button className="primary" type="button" onClick={handleRequalify}>
                    Aplicar requalificacao
                  </button>
                </div>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th></th>
                      <th>
                        <button
                          className="sort"
                          type="button"
                          onClick={() => handleSort("company")}
                        >
                          {renderSortLabel("Empresa", "company")}
                        </button>
                      </th>
                      <th>
                        <button
                          className="sort"
                          type="button"
                          onClick={() => handleSort("account")}
                        >
                          {renderSortLabel("Conta", "account")}
                        </button>
                      </th>
                      <th>Banco</th>
                      <th>Agencia</th>
                      <th>
                        <button
                          className="sort"
                          type="button"
                          onClick={() => handleSort("rule_type")}
                        >
                          {renderSortLabel("Tipo", "rule_type")}
                        </button>
                      </th>
                      <th>
                        <button
                          className="sort"
                          type="button"
                          onClick={() => handleSort("row_count")}
                        >
                          {renderSortLabel("Linhas", "row_count")}
                        </button>
                      </th>
                      <th>
                        <button
                          className="sort"
                          type="button"
                          onClick={() => handleSort("created_at")}
                        >
                          {renderSortLabel("Data", "created_at")}
                        </button>
                      </th>
                      <th>Acoes</th>
                    </tr>
                  </thead>
                  <tbody>
                    {imports.map((item) => (
                      <tr key={item.id}>
                        <td>
                          <input
                            type="checkbox"
                            checked={selectedImports.has(item.id)}
                            onChange={() => toggleImportSelection(item.id)}
                          />
                        </td>
                        <td>{item.company}</td>
                        <td>{item.account}</td>
                        <td>{item.bank}</td>
                        <td>{item.agency}</td>
                        <td>{item.rule_type}</td>
                        <td>{item.row_count}</td>
                        <td>
                          {item.created_at
                            ? new Date(item.created_at).toLocaleDateString()
                            : ""}
                        </td>
                        <td>
                          <button
                            className="danger small"
                            type="button"
                            onClick={() => handleDeleteImport(item.id)}
                          >
                            Remover
                          </button>
                        </td>
                      </tr>
                    ))}
                    {imports.length === 0 ? (
                      <tr>
                        <td colSpan="9">Nenhuma importacao encontrada.</td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              </div>
              <div className="pagination">
                <div className="page-size">
                  <label>Registros</label>
                  <select
                    value={importsPageSize}
                    onChange={(event) => {
                      setImportsPageSize(Number(event.target.value));
                      setImportsPage(1);
                    }}
                  >
                    {IMPORT_PAGE_SIZES.map((size) => (
                      <option key={size} value={size}>
                        {size}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="pagination-controls">
                  <button
                    className="ghost"
                    onClick={() =>
                      setImportsPage((prev) => Math.max(1, prev - 1))
                    }
                    disabled={importsPage <= 1}
                  >
                    Anterior
                  </button>
                  <span>
                    Pagina {importsPage} de {importsPageCount}
                  </span>
                  <button
                    className="ghost"
                    onClick={() =>
                      setImportsPage((prev) =>
                        Math.min(importsPageCount, prev + 1)
                      )
                    }
                    disabled={importsPage >= importsPageCount}
                  >
                    Proxima
                  </button>
                </div>
              </div>
            </section>

            <section className="card table-card">
              <div className="table-header">
                <h2>Itens requalificados</h2>
                <span>{requalifyResults.length} itens</span>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Empresa</th>
                      <th>Conta</th>
                      <th>Tipo</th>
                      <th>Linhas</th>
                    </tr>
                  </thead>
                  <tbody>
                    {requalifyResults.map((item) => (
                      <tr key={item.id}>
                        <td>{item.company}</td>
                        <td>{item.account}</td>
                        <td>{item.rule_type}</td>
                        <td>{item.row_count}</td>
                      </tr>
                    ))}
                    {requalifyResults.length === 0 ? (
                      <tr>
                        <td colSpan="4">Nenhuma requalificacao executada.</td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              </div>
            </section>

            <section className="card table-card">
              <div className="table-header">
                <h2>Itens requalificados (todas importacoes)</h2>
                <div className="table-actions">
                  <span>{allItemsTotal} itens</span>
                  <a
                    className="link"
                    href={getRequalifiedItemsDownloadUrl(
                      allItemsSortBy,
                      allItemsSortDir
                    )}
                  >
                    Baixar CSV
                  </a>
                </div>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>
                        <button
                          className="sort"
                          type="button"
                          onClick={() => handleAllItemsSort("empresa")}
                        >
                          {renderAllItemsSortLabel("Empresa", "empresa")}
                        </button>
                      </th>
                      <th>
                        <button
                          className="sort"
                          type="button"
                          onClick={() => handleAllItemsSort("banco")}
                        >
                          {renderAllItemsSortLabel("Banco", "banco")}
                        </button>
                      </th>
                      <th>
                        <button
                          className="sort"
                          type="button"
                          onClick={() => handleAllItemsSort("agencia")}
                        >
                          {renderAllItemsSortLabel("Agencia", "agencia")}
                        </button>
                      </th>
                      <th>
                        <button
                          className="sort"
                          type="button"
                          onClick={() => handleAllItemsSort("conta")}
                        >
                          {renderAllItemsSortLabel("Conta", "conta")}
                        </button>
                      </th>
                      <th>
                        <button
                          className="sort"
                          type="button"
                          onClick={() => handleAllItemsSort("data")}
                        >
                          {renderAllItemsSortLabel("Data", "data")}
                        </button>
                      </th>
                      <th>
                        <button
                          className="sort"
                          type="button"
                          onClick={() => handleAllItemsSort("valor")}
                        >
                          {renderAllItemsSortLabel("Valor", "valor")}
                        </button>
                      </th>
                      <th>
                        <button
                          className="sort"
                          type="button"
                          onClick={() => handleAllItemsSort("historico")}
                        >
                          {renderAllItemsSortLabel("Historico", "historico")}
                        </button>
                      </th>
                      <th>
                        <button
                          className="sort"
                          type="button"
                          onClick={() => handleAllItemsSort("codigo_qualificacao")}
                        >
                          {renderAllItemsSortLabel("Codigo", "codigo_qualificacao")}
                        </button>
                      </th>
                      <th>
                        <button
                          className="sort"
                          type="button"
                          onClick={() => handleAllItemsSort("descricao_qualificacao")}
                        >
                          {renderAllItemsSortLabel(
                            "Descricao",
                            "descricao_qualificacao"
                          )}
                        </button>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {allRequalifiedItems.map((item, index) => (
                      <tr key={`${item.data}-${index}`}>
                        <td>{item.empresa}</td>
                        <td>{item.banco}</td>
                        <td>{item.agencia}</td>
                        <td>{item.conta}</td>
                        <td>{item.data}</td>
                        <td>{item.valor}</td>
                        <td>{item.historico}</td>
                        <td>{item.codigo_qualificacao}</td>
                        <td>{item.descricao_qualificacao}</td>
                      </tr>
                    ))}
                    {allRequalifiedItems.length === 0 ? (
                      <tr>
                        <td colSpan="9">Sem dados para exibir.</td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              </div>
              <div className="pagination">
                <div className="page-size">
                  <label>Registros</label>
                  <select
                    value={allItemsPageSize}
                    onChange={(event) => {
                      setAllItemsPageSize(Number(event.target.value));
                      setAllItemsPage(1);
                    }}
                  >
                    {IMPORT_PAGE_SIZES.map((size) => (
                      <option key={size} value={size}>
                        {size}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="pagination-controls">
                  <button
                    className="ghost"
                    onClick={() =>
                      setAllItemsPage((prev) => Math.max(1, prev - 1))
                    }
                    disabled={allItemsPage <= 1}
                  >
                    Anterior
                  </button>
                  <span>
                    Pagina {allItemsPage} de {allItemsPageCount}
                  </span>
                  <button
                    className="ghost"
                    onClick={() =>
                      setAllItemsPage((prev) =>
                        Math.min(allItemsPageCount, prev + 1)
                      )
                    }
                    disabled={allItemsPage >= allItemsPageCount}
                  >
                    Proxima
                  </button>
                </div>
              </div>
            </section>
          </>
        ) : null}
      </main>
    </div>
  );
}
