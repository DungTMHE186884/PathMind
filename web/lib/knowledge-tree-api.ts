import { apiFetch, apiUrl } from "@/lib/api";

const BASE = "/api/knowledge-tree";

export interface Rights {
  role: string;
  can_edit: boolean;
}
export interface DomainSummary {
  id: string;
  slug: string;
  name: string;
  description: string;
  kb_name: string | null;
  nodes: number;
}
export interface TreeNode {
  id: string;
  parent_id: string | null;
  title: string;
  summary: string;
  version: number;
  refs: { source_id: string; start: number; end: number }[];
  children: TreeNode[];
}
export interface TreeData {
  domain: { id: string; slug: string; name: string; description: string; kb_name: string | null };
  nodes: TreeNode[];
  sources: { id: string; filename: string; size: number }[];
}
export interface NodeDetail {
  id: string;
  domain_id: string;
  title: string;
  summary: string;
  version: number;
  excerpts: { source_id: string; filename: string; text: string }[];
}
async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await apiFetch(apiUrl(`${BASE}${path}`), init);
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = (await res.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      /* keep the status text */
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const getRights = () => call<Rights>("/me");
export const listDomains = () =>
  call<{ domains: DomainSummary[] }>("/domains").then((r) => r.domains);
export const getTree = (id: string) => call<TreeData>(`/domains/${id}/tree`);
export const getNode = (id: string) => call<NodeDetail>(`/nodes/${id}`);
export const createDomain = (name: string, description: string) =>
  call<{ id: string }>("/domains", json("POST", { name, description }));
export const deleteDomain = (id: string) =>
  call<{ ok: boolean }>(`/domains/${id}`, { method: "DELETE" });
export const addNode = (
  domainId: string,
  parentId: string | null,
  title: string,
  summary: string,
) =>
  call<{ id: string }>(
    `/domains/${domainId}/nodes`,
    json("POST", { parent_id: parentId, title, summary }),
  );
export const patchNode = (
  id: string,
  patch: { title?: string; summary?: string },
) => call<{ id: string }>(`/nodes/${id}`, json("PATCH", patch));
export const deleteNode = (id: string) =>
  call<{ deleted: number }>(`/nodes/${id}`, { method: "DELETE" });

export function importFile(file: File, domainId: string | null, name = "") {
  const form = new FormData();
  form.append("file", file);
  if (!domainId) form.append("name", name);
  return call<{ domain_id: string; nodes_created: number }>(
    domainId ? `/domains/${domainId}/import` : "/domains/import",
    { method: "POST", body: form },
  );
}

export const listKbOptions = () =>
  call<{ knowledge_bases: string[] }>("/kb-options").then((r) => r.knowledge_bases);
export const patchDomain = (
  id: string,
  patch: { name?: string; description?: string; kb_name?: string | null },
) => call<{ id: string; kb_name: string | null }>(`/domains/${id}`, json("PATCH", patch));

export interface AskResult {
  query: string;
  content: string;
  scope: { title: string; path: string; domain: string; score: number }[];
  sources: unknown[];
  notes: string[];
}
export const askKnowledge = (query: string, domainId?: string | null) =>
  call<AskResult>("/ask", json("POST", { query, domain_id: domainId ?? null }));
