import React, { useEffect, useMemo, useState } from "react";
import {
  createQualification,
  fetchImportPreview,
  getDownloadUrl,
  listQualifications,
  uploadImport
} from "./api";

const PAGE_SIZE = 25;

export default function App() {
  const [qualifications, setQualifications] = useState([]);
  const [newRule, setNewRule] = useState({
    keyword: "",
    code: "",
    description: "",
    priority: 1
  });
  const [uploadForm, setUploadForm] = useState({
    company: "",
    bank: "",
    agency: "",
    account: ""
  });
  const [file, setFile] = useState(null);
  const [importId, setImportId] = useState("");
  const [importMeta, setImportMeta] = useState(null);
  const [rows, setRows] = useState([]);
  const [page, setPage] = useState(1);
  const [totalRows, setTotalRows] = useState(0);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    loadQualifications();
  }, []);

  useEffect(() => {
    if (!importId) return;
    loadPreview(importId, page);
  }, [importId, page]);

  const pageCount = useMemo(() => {
    return Math.max(1, Math.ceil(totalRows / PAGE_SIZE));
  }, [totalRows]);

  async function loadQualifications() {
    try {
      const data = await listQualifications();
      setQualifications(data);
    } catch (err) {
      setError(err.message || "Falha ao carregar qualificacoes");
    }
  }

  async function handleCreateRule(event) {
    event.preventDefault();
    setError("");
    setStatus("Salvando qualificacao...");

    try {
      const payload = {
        ...newRule,
        priority: Number(newRule.priority)
      };
      await createQualification(payload);
      setNewRule({ keyword: "", code: "", description: "", priority: 1 });
      await loadQualifications();
      setStatus("Qualificacao salva.");
    } catch (err) {
      setError(err.message || "Falha ao salvar qualificacao");
      setStatus("");
    }
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

  return (
    <div className="app">
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
        <section className="grid">
          <form className="card" onSubmit={handleUpload}>
            <h2>Nova importacao</h2>
            <div className="field">
              <label>Empresa</label>
              <input
                value={uploadForm.company}
                onChange={(event) =>
                  setUploadForm({ ...uploadForm, company: event.target.value })
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
                  setUploadForm({ ...uploadForm, bank: event.target.value })
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
                  setUploadForm({ ...uploadForm, agency: event.target.value })
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
                  setUploadForm({ ...uploadForm, account: event.target.value })
                }
                placeholder="Ex: 12345-6"
                required
              />
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

          <form className="card" onSubmit={handleCreateRule}>
            <h2>Nova qualificacao</h2>
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
                  setNewRule({ ...newRule, description: event.target.value })
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
            <button className="primary" type="submit">
              Salvar regra
            </button>
          </form>
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
                </tr>
              </thead>
              <tbody>
                {qualifications.map((q) => (
                  <tr key={q.id}>
                    <td>{q.priority}</td>
                    <td>{q.keyword}</td>
                    <td>{q.code}</td>
                    <td>{q.description}</td>
                  </tr>
                ))}
                {qualifications.length === 0 ? (
                  <tr>
                    <td colSpan="4">Nenhuma regra cadastrada.</td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
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
      </main>
    </div>
  );
}
