/** Пустая база = запросы на тот же origin (Vite в dev проксирует /api → backend). Иначе полный URL из VITE_API_URL. */
function apiBase(): string {
  const url = import.meta.env.VITE_API_URL;
  if (url != null && String(url).trim() !== "") {
    return String(url).replace(/\/$/, "");
  }
  return "";
}

const base = apiBase();

export function getToken(): string | null {
  return sessionStorage.getItem("token");
}

export function setToken(t: string | null) {
  if (t) sessionStorage.setItem("token", t);
  else sessionStorage.removeItem("token");
}

const ROLE_KEY = "role";

export function setRole(r: string | null) {
  if (r) sessionStorage.setItem(ROLE_KEY, r);
  else sessionStorage.removeItem(ROLE_KEY);
}

export function getRole(): string | null {
  return sessionStorage.getItem(ROLE_KEY);
}

async function request<T>(
  path: string,
  options: RequestInit & { json?: unknown } = {},
): Promise<T> {
  const headers: HeadersInit = {
    ...(options.json !== undefined ? { "Content-Type": "application/json" } : {}),
    ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}),
    ...((options.headers as Record<string, string>) || {}),
  };
  const body = options.json !== undefined ? JSON.stringify(options.json) : options.body;
  const res = await fetch(`${base}${path}`, { ...options, headers, body });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  login: (email: string, password: string) =>
    request<{ access_token: string }>("/api/auth/login", {
      method: "POST",
      json: { email, password },
    }),
  me: () => request<{ email: string; role: string }>("/api/auth/me"),
  syncSheets: () =>
    request<{ ok: boolean; sheets: string[]; rows: Record<string, number> }>("/api/sheets/sync", {
      method: "POST",
    }),
  getSheet: (name: string) =>
    request<{
      sheet: string;
      values: string[][];
      note?: string;
      data_row_indices?: number[];
    }>(`/api/sheets/${encodeURIComponent(name)}`),
  dashboardStats: () =>
    request<{ meta: Record<string, unknown>; row_counts: Record<string, number>; cached_sheets: string[] }>(
      "/api/stats/dashboard",
    ),
  masterDashboard: () =>
    request<{
      masters: {
        email: string;
        label: string;
        ankety: { total: number; reviewed: number; pending: number };
        domashki: { total: number; reviewed: number; pending: number };
        interviews: { total: number; conducted: number; pending: number };
      }[];
      cache_loaded: boolean;
      note: string | null;
    }>("/api/stats/master-dashboard"),
  sheetTabNames: () =>
    request<{ subs: string; enquiries: string; domashki: string; ankety: string; interviews: string }>(
      "/api/stats/sheet-names",
    ),
  queueWrite: (range_a1: string, values: unknown[][]) =>
    request<{ job_id: string; status: string; poll_url?: string }>("/api/sheets/write-queue", {
      method: "POST",
      json: { range_a1, values },
    }),
  queueWriteBatch: (updates: { range_a1: string; values: unknown[][] }[]) =>
    request<{ job_id: string; status: string; poll_url?: string }>("/api/sheets/write-queue-batch", {
      method: "POST",
      json: { updates },
    }),
  sheetsQueueStatus: (jobId: string) =>
    request<{
      job_id: string;
      status: string;
      enqueued_at: string | null;
      ended_at: string | null;
      result?: unknown;
      error?: string | null;
    }>(`/api/sheets/queue/status/${encodeURIComponent(jobId)}`),
  adminUsers: () => request<{ email: string; role: string }[]>("/api/admin/users"),
  adminCreateUser: (email: string, password: string, role: "user" | "super_admin" = "user") =>
    request<{ email: string; role: string }>("/api/admin/users", {
      method: "POST",
      json: { email, password, role },
    }),
  adminAssignments: () => request<Record<string, Record<string, number[]>>>("/api/admin/assignments"),
  adminDistribute: (sheet_name: string, per_user: number, user_emails: string[], by_columns?: boolean) =>
    request<{ ok: boolean; assigned_rows: Record<string, number[]> }>("/api/admin/assignments/distribute", {
      method: "POST",
      json: { sheet_name, per_user, user_emails, by_columns: !!by_columns },
    }),
  anketyColumnLayout: () =>
    request<{
      sheet: string;
      score_column_indices: { index: number; header: string | null }[];
      sum_column: { index: number | null; header: string | null };
      level_column: { index: number | null; header: string | null };
      reviewer_questions_column: { index: number | null; header: string | null };
      reviewer_comment_column: { index: number | null; header: string | null };
    }>("/api/ankety/column-layout"),
  domashkiColumnLayout: () =>
    request<{
      sheet: string;
      score_column_indices: { index: number; header: string | null }[];
      sum_column: { index: number | null; header: string | null };
      level_column: { index: number | null; header: string | null };
      reviewer_questions_column: { index: number | null; header: string | null };
      reviewer_comment_column: { index: number | null; header: string | null };
    }>("/api/domashki/column-layout"),
  interviewsPayload: () =>
    request<{
      sheet: string;
      first_candidate_col_index: number;
      candidates: {
        column_index: number;
        parse_ok: boolean;
        error?: string;
        questions_header_row?: number;
        score_block_start_row?: number;
        meta: { row: number; label: string; value: string }[];
        questions: {
          row: number;
          key_characteristic: string;
          extra_characteristic: string;
          question: string;
          answer: string;
        }[];
        scores: { row: number; label: string; value: string }[];
        external: {
          candidate_email: string | null;
          ankety: {
            matched: boolean;
            sheet?: string;
            reason?: string;
            row_index?: number;
            reviewer_questions?: string;
            reviewer_comment?: string;
          };
          domashki: {
            matched: boolean;
            sheet?: string;
            reason?: string;
            row_index?: number;
            reviewer_questions?: string;
            reviewer_comment?: string;
          };
        };
      }[];
    }>("/api/interviews/payload"),
  interviewsSave: (body: { column_index: number; cells: { row: number; value: string }[] }) =>
    request<{ job_id: string; status: string; poll_url?: string }>("/api/interviews/save", {
      method: "POST",
      json: body,
    }),
};
