import { ref } from "vue";

/** Пустая база = запросы на тот же origin (Vite в dev проксирует /api → backend). Иначе полный URL из VITE_API_URL. */
function apiBase(): string {
  const url = import.meta.env.VITE_API_URL;
  if (url != null && String(url).trim() !== "") {
    return String(url).replace(/\/$/, "");
  }
  return "";
}

const base = apiBase();

const TOKEN_KEY = "token";
const ROLE_KEY = "role";

const tokenRef = ref<string | null>(sessionStorage.getItem(TOKEN_KEY));
const roleRef = ref<string | null>(sessionStorage.getItem(ROLE_KEY));

export function getToken(): string | null {
  return tokenRef.value;
}

export function setToken(t: string | null) {
  tokenRef.value = t;
  if (t) sessionStorage.setItem(TOKEN_KEY, t);
  else sessionStorage.removeItem(TOKEN_KEY);
}

export function setRole(r: string | null) {
  roleRef.value = r;
  if (r) sessionStorage.setItem(ROLE_KEY, r);
  else sessionStorage.removeItem(ROLE_KEY);
}

export function getRole(): string | null {
  return roleRef.value;
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
  me: () =>
    request<{ email: string; role: string; master_label: string | null; faculty: string | null }>("/api/auth/me"),
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
        faculty: string | null;
        ankety: { total: number; reviewed: number; pending: number };
        domashki: { total: number; reviewed: number; pending: number };
        interviews: { total: number; conducted: number; pending: number };
      }[];
      sheets_summary?: {
        ankety: {
          sheet: string;
          total_rows: number;
          assigned: number;
          unassigned_count: number;
          unassigned_indices: number[];
        };
        domashki: {
          sheet: string;
          total_rows: number;
          assigned: number;
          unassigned_count: number;
          unassigned_indices: number[];
          no_student_id_match: number;
        };
      };
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
  adminUsers: () =>
    request<
      {
        email: string;
        role: string;
        master_label: string | null;
        faculty: string | null;
        reviewer_faculties: string[];
      }[]
    >("/api/admin/users"),
  adminCreateUser: (
    email: string,
    password: string,
    role: "user" | "super_admin" = "user",
    faculty?: string | null,
  ) =>
    request<{
      email: string;
      role: string;
      master_label: string | null;
      faculty: string | null;
      reviewer_faculties: string[];
    }>("/api/admin/users", {
      method: "POST",
      json: { email, password, role, faculty: faculty ?? null },
    }),
  adminAssignments: () => request<Record<string, Record<string, number[]>>>("/api/admin/assignments"),
  adminDistribute: (sheet_name: string, per_user: number, user_emails: string[], by_columns?: boolean) =>
    request<{ ok: boolean; assigned_rows: Record<string, number[]> }>("/api/admin/assignments/distribute", {
      method: "POST",
      json: { sheet_name, per_user, user_emails, by_columns: !!by_columns },
    }),
  adminDistributeCustom: (sheet_name: string, user_counts: Record<string, number>, by_columns?: boolean) =>
    request<{ ok: boolean; assigned_rows: Record<string, number[]> }>("/api/admin/assignments/distribute-custom", {
      method: "POST",
      json: { sheet_name, user_counts, by_columns: !!by_columns },
    }),
  adminDistributeBalanced: (sheet_name: string, user_emails: string[]) =>
    request<{
      ok: boolean;
      assigned: Record<string, number[]>;
      unassigned: number[];
    }>("/api/admin/assignments/distribute-balanced", {
      method: "POST",
      json: { sheet_name, user_emails },
    }),
  adminDistributeDomashki: (sheet_name: string, user_emails: string[]) =>
    request<{
      ok: boolean;
      newly_assigned: Record<string, number[]>;
      unassigned: number[];
      already_assigned: number;
    }>("/api/admin/assignments/distribute-domashki", {
      method: "POST",
      json: { sheet_name, user_emails },
    }),
  adminSheetRows: (sheet_name: string) =>
    request<{
      sheet: string;
      header: string[];
      rows: { index: number; preview: string[]; reviewer: string | null }[];
    }>(`/api/admin/sheet-rows/${encodeURIComponent(sheet_name)}`),
  adminAssignRow: (sheet_name: string, row_index: number, email: string | null) =>
    request<{ ok: boolean }>("/api/admin/assignments/assign-row", {
      method: "POST",
      json: { sheet_name, row_index, email },
    }),
  adminPatchUserFaculty: (email: string, faculty: string | null) =>
    request<{ ok: boolean; email: string; faculty: string | null }>(
      `/api/admin/users/${encodeURIComponent(email)}/faculty`,
      { method: "PATCH", json: { faculty } },
    ),
  adminPatchReviewerFaculties: (email: string, faculties: string[]) =>
    request<{ ok: boolean; email: string; reviewer_faculties: string[] }>(
      `/api/admin/users/${encodeURIComponent(email)}/reviewer-faculties`,
      { method: "PATCH", json: { faculties } },
    ),
  adminSetPassword: (email: string, password: string) =>
    request<{ ok: boolean }>(`/api/admin/users/${encodeURIComponent(email)}/password`, {
      method: "PATCH",
      json: { password },
    }),
  adminClearAssignment: (email: string) =>
    request<{ ok: boolean }>(`/api/admin/assignments/${encodeURIComponent(email)}`, { method: "DELETE" }),
  adminPutAssignment: (email: string, rows_by_sheet: Record<string, number[]>) =>
    request<{ ok: boolean }>(`/api/admin/assignments/${encodeURIComponent(email)}`, {
      method: "PUT",
      json: { rows_by_sheet },
    }),
  anketyColumnLayout: () =>
    request<{
      sheet: string;
      score_column_indices: { index: number; header: string | null; options: string[] }[];
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
