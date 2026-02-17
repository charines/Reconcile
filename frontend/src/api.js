const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

async function handleResponse(response) {
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || "Erro na requisicao");
  }
  return response.json();
}

export async function listQualifications() {
  const response = await fetch(`${API_BASE}/qualifications`);
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

export async function uploadImport(formData) {
  const response = await fetch(`${API_BASE}/imports`, {
    method: "POST",
    body: formData
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
