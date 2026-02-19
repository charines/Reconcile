const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

async function handleResponse(response) {
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || "Erro na requisicao");
  }
  return response.json();
}

export async function listQualifications(ruleType) {
  const params = ruleType ? `?rule_type=${encodeURIComponent(ruleType)}` : "";
  const response = await fetch(`${API_BASE}/qualifications${params}`);
  return handleResponse(response);
}

export async function createQualification(payload) {
  const response = await fetch(`${API_BASE}/qualifications`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  return handleResponse(response);
}

export async function updateQualification(id, payload) {
  const response = await fetch(`${API_BASE}/qualifications/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  return handleResponse(response);
}

export async function deleteQualification(id) {
  const response = await fetch(`${API_BASE}/qualifications/${id}`, {
    method: "DELETE"
  });
  return handleResponse(response);
}

export async function uploadImport(formData) {
  const response = await fetch(`${API_BASE}/imports`, {
    method: "POST",
    body: formData
  });
  return handleResponse(response);
}

export async function listImports({ page, pageSize, sortBy, sortDir }) {
  const params = new URLSearchParams();
  params.set("page", String(page));
  params.set("page_size", String(pageSize));
  params.set("sort_by", sortBy);
  params.set("sort_dir", sortDir);
  const response = await fetch(`${API_BASE}/imports?${params.toString()}`);
  return handleResponse(response);
}

export async function requalifyImports(payload) {
  const response = await fetch(`${API_BASE}/imports/requalify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  return handleResponse(response);
}

export async function deleteImport(id) {
  const response = await fetch(`${API_BASE}/imports/${id}`, {
    method: "DELETE"
  });
  return handleResponse(response);
}

export async function fetchImportPreview(importId, page, pageSize) {
  const response = await fetch(
    `${API_BASE}/imports/${importId}?page=${page}&page_size=${pageSize}`
  );
  return handleResponse(response);
}

export function getDownloadUrl(importId) {
  return `${API_BASE}/imports/${importId}/download`;
}

export async function fetchRequalifiedItems(
  page,
  pageSize,
  sortBy,
  sortDir,
  search
) {
  const params = new URLSearchParams();
  params.set("page", String(page));
  params.set("page_size", String(pageSize));
  if (sortBy) params.set("sort_by", sortBy);
  if (sortDir) params.set("sort_dir", sortDir);
  if (search) params.set("search", search);
  const response = await fetch(
    `${API_BASE}/requalified-items?${params.toString()}`
  );
  return handleResponse(response);
}

export function getRequalifiedItemsDownloadUrl(sortBy, sortDir, search) {
  const params = new URLSearchParams();
  if (sortBy) params.set("sort_by", sortBy);
  if (sortDir) params.set("sort_dir", sortDir);
  if (search) params.set("search", search);
  const query = params.toString();
  return `${API_BASE}/requalified-items/download${query ? `?${query}` : ""}`;
}

export async function fetchDashboard() {
  const response = await fetch(`${API_BASE}/dashboard`);
  return handleResponse(response);
}
