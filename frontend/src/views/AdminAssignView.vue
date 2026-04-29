<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { api } from "../api/client";

type Reviewer = { email: string; role: string; master_label: string | null };
type MasterStat = {
  email: string;
  label: string;
  ankety: { total: number; reviewed: number; pending: number };
  domashki: { total: number; reviewed: number; pending: number };
  interviews: { total: number; conducted: number; pending: number };
};

const tab = ref<"users" | "assign" | "rows" | "stats">("stats");

const users = ref<Reviewer[]>([]);
const assignments = ref<Record<string, Record<string, number[]>>>({});
const stats = ref<MasterStat[]>([]);
const cacheLoaded = ref(false);

const tabNames = ref<{
  subs: string; enquiries: string; domashki: string; ankety: string; interviews: string;
} | null>(null);

const loading = ref(false);
const globalMsg = ref("");
const globalErr = ref("");

/* ── Новый пользователь ── */
const newEmail = ref("");
const newPassword = ref("");
const newLabel = ref("");
const createMsg = ref("");
const createErr = ref("");

/* ── Смена пароля ── */
const pwdInputs = ref<Record<string, string>>({});
const pwdMsg = ref<Record<string, string>>({});
const pwdErr = ref<Record<string, string>>({});

/* ── Равномерное распределение ── */
const sheetForDist = ref("");
const perUser = ref(10);
const distributeByColumns = ref(false);
const selectedEmails = ref<string[]>([]);
const distMsg = ref("");
const distErr = ref("");

/* ── Вкладка «По строкам» ── */
const rowsSheet = ref("");
const sheetHeader = ref<string[]>([]);
const sheetRows = ref<{ index: number; preview: string[]; reviewer: string | null }[]>([]);
const rowsLoading = ref(false);
const rowsErr = ref("");
const rowSearch = ref("");
const savingRow = ref<number | null>(null);

const reviewers = computed(() => users.value.filter((u) => u.role === "user"));

function displayName(u: Reviewer) {
  return u.master_label || u.email;
}

function assignCount(email: string): number {
  const a = assignments.value[email];
  if (!a) return 0;
  return Object.values(a).reduce((s, arr) => s + arr.length, 0);
}

function assignCountForSheet(email: string, sheet: string): number {
  return assignments.value[email]?.[sheet]?.length ?? 0;
}

async function refresh() {
  loading.value = true;
  globalErr.value = "";
  try {
    const [u, a, n, s] = await Promise.all([
      api.adminUsers(),
      api.adminAssignments(),
      api.sheetTabNames(),
      api.masterDashboard().catch(() => ({ masters: [], cache_loaded: false, note: null })),
    ]);
    users.value = u;
    assignments.value = a;
    tabNames.value = n;
    stats.value = s.masters;
    cacheLoaded.value = s.cache_loaded;
    if (!sheetForDist.value && n.ankety) sheetForDist.value = n.ankety;
    if (!rowsSheet.value && n.ankety) rowsSheet.value = n.ankety;
  } catch (e) {
    globalErr.value = e instanceof Error ? e.message : "Ошибка загрузки";
  } finally {
    loading.value = false;
  }
}

watch(sheetForDist, () => {
  if (!tabNames.value) return;
  distributeByColumns.value = sheetForDist.value === tabNames.value.interviews;
});

onMounted(refresh);

async function createUser() {
  createMsg.value = "";
  createErr.value = "";
  if (!newEmail.value.trim() || !newPassword.value.trim()) {
    createErr.value = "Email и пароль обязательны";
    return;
  }
  try {
    await api.adminCreateUser(newEmail.value.trim(), newPassword.value.trim());
    createMsg.value = `Создан: ${newEmail.value.trim()}`;
    newEmail.value = "";
    newPassword.value = "";
    newLabel.value = "";
    await refresh();
  } catch (e) {
    createErr.value = e instanceof Error ? e.message : "Ошибка";
  }
}

function toggleAll() {
  if (selectedEmails.value.length === reviewers.value.length) {
    selectedEmails.value = [];
  } else {
    selectedEmails.value = reviewers.value.map((r) => r.email);
  }
}

async function distribute() {
  distMsg.value = "";
  distErr.value = "";
  if (!selectedEmails.value.length) { distErr.value = "Выберите хотя бы одного"; return; }
  try {
    const res = await api.adminDistribute(sheetForDist.value, perUser.value, selectedEmails.value, distributeByColumns.value);
    const what = distributeByColumns.value ? "колонок" : "строк";
    distMsg.value = `Готово. ${what}: ${JSON.stringify(res.assigned_rows)}`;
    await refresh();
  } catch (e) {
    distErr.value = e instanceof Error ? e.message : "Ошибка";
  }
}

const filteredRows = computed(() => {
  const q = rowSearch.value.trim().toLowerCase();
  if (!q) return sheetRows.value;
  return sheetRows.value.filter((r) => r.preview.some((v) => v.toLowerCase().includes(q)));
});

async function loadSheetRows() {
  rowsErr.value = "";
  rowsLoading.value = true;
  sheetRows.value = [];
  try {
    const res = await api.adminSheetRows(rowsSheet.value);
    sheetHeader.value = res.header;
    sheetRows.value = res.rows;
  } catch (e) {
    rowsErr.value = e instanceof Error ? e.message : "Ошибка";
  } finally {
    rowsLoading.value = false;
  }
}

async function assignRow(rowIndex: number, email: string | null) {
  savingRow.value = rowIndex;
  try {
    await api.adminAssignRow(rowsSheet.value, rowIndex, email);
    const r = sheetRows.value.find((x) => x.index === rowIndex);
    if (r) r.reviewer = email;
    // обновляем сводную таблицу назначений
    assignments.value = await api.adminAssignments();
  } catch (e) {
    rowsErr.value = e instanceof Error ? e.message : "Ошибка назначения";
  } finally {
    savingRow.value = null;
  }
}

async function setPassword(email: string) {
  pwdMsg.value[email] = "";
  pwdErr.value[email] = "";
  const pwd = (pwdInputs.value[email] ?? "").trim();
  if (pwd.length < 4) { pwdErr.value[email] = "Минимум 4 символа"; return; }
  try {
    await api.adminSetPassword(email, pwd);
    pwdMsg.value[email] = "Пароль обновлён";
    pwdInputs.value[email] = "";
  } catch (e) {
    pwdErr.value[email] = e instanceof Error ? e.message : "Ошибка";
  }
}

async function clearAssignment(email: string) {
  if (!confirm(`Удалить все назначения для ${email}?`)) return;
  try {
    await api.adminClearAssignment(email);
    await refresh();
  } catch (e) {
    globalErr.value = e instanceof Error ? e.message : "Ошибка сброса";
  }
}

function totalStat(field: "ankety" | "domashki", key: "total" | "reviewed" | "pending") {
  return stats.value.reduce((s, m) => s + (m[field]?.[key] ?? 0), 0);
}
function totalInterviews(key: "total" | "conducted" | "pending") {
  return stats.value.reduce((s, m) => s + (m.interviews?.[key] ?? 0), 0);
}

function pct(done: number, total: number) {
  if (!total) return 0;
  return Math.round((done / total) * 100);
}
</script>

<template>
  <div class="admin-wrap">
    <div class="admin-header">
      <h1>Супер-админ</h1>
      <p class="muted">Управление проверяющими, назначениями и статистикой.</p>
      <p v-if="globalErr" class="err-banner">{{ globalErr }}</p>
    </div>

    <!-- Tabs -->
    <div class="tab-bar">
      <button :class="['tab-btn', tab === 'stats' && 'tab-btn--active']" @click="tab = 'stats'">📊 Статистика</button>
      <button :class="['tab-btn', tab === 'rows' && 'tab-btn--active']" @click="tab = 'rows'">📋 По строкам</button>
      <button :class="['tab-btn', tab === 'assign' && 'tab-btn--active']" @click="tab = 'assign'">⚡ Авто</button>
      <button :class="['tab-btn', tab === 'users' && 'tab-btn--active']" @click="tab = 'users'">👥 Пользователи</button>
      <span class="spacer" />
      <button class="btn btn-sm" :disabled="loading" @click="refresh">{{ loading ? '…' : '↻ Обновить' }}</button>
    </div>

    <!-- ═══════════════════ STATISTICS ═══════════════════ -->
    <div v-if="tab === 'stats'" class="tab-content">
      <p v-if="!cacheLoaded" class="warn-banner">
        Кэш листов пуст — данные показаны только по назначениям. Синхронизируйте Google Таблицу на
        <RouterLink to="/dashboard">дашборде</RouterLink>.
      </p>

      <!-- Сводная строка -->
      <div class="summary-row">
        <div class="summary-card">
          <div class="summary-val">{{ reviewers.length }}</div>
          <div class="summary-lbl">Проверяющих</div>
        </div>
        <div class="summary-card">
          <div class="summary-val">{{ totalStat('ankety', 'total') }}</div>
          <div class="summary-lbl">Анкет назначено</div>
        </div>
        <div class="summary-card">
          <div class="summary-val">{{ totalStat('ankety', 'reviewed') }}</div>
          <div class="summary-lbl">Анкет проверено</div>
        </div>
        <div class="summary-card">
          <div class="summary-val">{{ totalStat('domashki', 'total') }}</div>
          <div class="summary-lbl">Домашек назначено</div>
        </div>
        <div class="summary-card">
          <div class="summary-val">{{ totalStat('domashki', 'reviewed') }}</div>
          <div class="summary-lbl">Домашек проверено</div>
        </div>
        <div class="summary-card">
          <div class="summary-val">{{ totalInterviews('total') }}</div>
          <div class="summary-lbl">Собеседований</div>
        </div>
      </div>

      <!-- Таблица по проверяющим -->
      <div class="card" style="padding: 0; overflow: hidden;">
        <table class="stats-table">
          <thead>
            <tr>
              <th>Проверяющий</th>
              <th colspan="2">Анкеты</th>
              <th colspan="2">Домашки</th>
              <th colspan="2">Собеседования</th>
            </tr>
            <tr class="subhead">
              <th></th>
              <th>Назначено</th><th>Проверено</th>
              <th>Назначено</th><th>Проверено</th>
              <th>Назначено</th><th>Проведено</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!stats.length">
              <td colspan="7" class="empty-row">Нет данных</td>
            </tr>
            <tr v-for="m in stats" :key="m.email">
              <td class="reviewer-cell">
                <div class="reviewer-name">{{ m.label }}</div>
                <div class="reviewer-email">{{ m.email }}</div>
              </td>
              <!-- Анкеты -->
              <td class="num-cell">{{ m.ankety.total }}</td>
              <td class="num-cell">
                <span :class="m.ankety.pending === 0 && m.ankety.total > 0 ? 'done' : ''">
                  {{ m.ankety.reviewed }}
                </span>
                <span v-if="m.ankety.total" class="pct"> ({{ pct(m.ankety.reviewed, m.ankety.total) }}%)</span>
              </td>
              <!-- Домашки -->
              <td class="num-cell">{{ m.domashki.total }}</td>
              <td class="num-cell">
                <span :class="m.domashki.pending === 0 && m.domashki.total > 0 ? 'done' : ''">
                  {{ m.domashki.reviewed }}
                </span>
                <span v-if="m.domashki.total" class="pct"> ({{ pct(m.domashki.reviewed, m.domashki.total) }}%)</span>
              </td>
              <!-- Собеседования -->
              <td class="num-cell">{{ m.interviews.total }}</td>
              <td class="num-cell">
                <span :class="m.interviews.pending === 0 && m.interviews.total > 0 ? 'done' : ''">
                  {{ m.interviews.conducted }}
                </span>
                <span v-if="m.interviews.total" class="pct"> ({{ pct(m.interviews.conducted, m.interviews.total) }}%)</span>
              </td>
            </tr>
          </tbody>
          <!-- Итого -->
          <tfoot v-if="stats.length">
            <tr>
              <td><strong>Итого</strong></td>
              <td class="num-cell"><strong>{{ totalStat('ankety', 'total') }}</strong></td>
              <td class="num-cell"><strong>{{ totalStat('ankety', 'reviewed') }}</strong></td>
              <td class="num-cell"><strong>{{ totalStat('domashki', 'total') }}</strong></td>
              <td class="num-cell"><strong>{{ totalStat('domashki', 'reviewed') }}</strong></td>
              <td class="num-cell"><strong>{{ totalInterviews('total') }}</strong></td>
              <td class="num-cell"><strong>{{ totalInterviews('conducted') }}</strong></td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>

    <!-- ═══════════════════ ROWS ═══════════════════ -->
    <div v-if="tab === 'rows'" class="tab-content">
      <div class="card">
        <h3>Назначение по строкам</h3>
        <p class="muted">Выберите лист, загрузите строки и назначьте проверяющего каждой через выпадающий список.</p>
        <div class="form-row" style="align-items: flex-end">
          <div class="field">
            <label>Лист</label>
            <select v-if="tabNames" v-model="rowsSheet" class="select-like">
              <option :value="tabNames.ankety">Анкеты</option>
              <option :value="tabNames.domashki">Домашки</option>
              <option :value="tabNames.enquiries">Enquiries</option>
            </select>
          </div>
          <button class="btn btn-primary" :disabled="rowsLoading" @click="loadSheetRows">
            {{ rowsLoading ? '…' : 'Загрузить строки' }}
          </button>
        </div>
        <p v-if="rowsErr" class="err-msg">{{ rowsErr }}</p>
      </div>

      <div v-if="sheetRows.length" class="card" style="margin-top: 1rem; padding: 0.75rem 1rem;">
        <div class="rows-toolbar">
          <span class="muted" style="font-size:0.85rem">{{ sheetRows.length }} строк · {{ sheetRows.filter(r => r.reviewer).length }} назначено</span>
          <input v-model="rowSearch" type="search" placeholder="Поиск по содержимому…" class="search-input" />
        </div>

        <div class="rows-table-wrap">
          <table class="rows-table">
            <thead>
              <tr>
                <th class="col-num">#</th>
                <th v-for="(h, hi) in sheetHeader.slice(2)" :key="hi">{{ h || `Кол. ${hi + 3}` }}</th>
                <th class="col-reviewer">Проверяющий</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in filteredRows"
                :key="row.index"
                :class="{ 'row--assigned': !!row.reviewer, 'row--saving': savingRow === row.index }"
              >
                <td class="col-num muted">{{ row.index }}</td>
                <td v-for="(val, vi) in row.preview.slice(2)" :key="vi" class="cell-preview">{{ val || '—' }}</td>
                <td class="col-reviewer">
                  <select
                    :value="row.reviewer ?? ''"
                    class="reviewer-select"
                    :disabled="savingRow === row.index"
                    @change="(e) => assignRow(row.index, (e.target as HTMLSelectElement).value || null)"
                  >
                    <option value="">— не назначен —</option>
                    <option v-for="r in reviewers" :key="r.email" :value="r.email">
                      {{ r.master_label || r.email }}
                    </option>
                  </select>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- ═══════════════════ ASSIGNMENTS ═══════════════════ -->
    <div v-if="tab === 'assign'" class="tab-content">

      <!-- Равномерное распределение -->
      <div class="card">
        <h3>Равномерное распределение</h3>
        <p class="muted">Каждый выбранный проверяющий получит одинаковое кол-во строк по порядку из листа.</p>
        <div class="form-row">
          <div class="field">
            <label>Лист</label>
            <select v-if="tabNames" v-model="sheetForDist" class="select-like">
              <option :value="tabNames.ankety">Анкеты</option>
              <option :value="tabNames.domashki">Домашки</option>
              <option :value="tabNames.enquiries">Enquiries</option>
              <option :value="tabNames.interviews">Собеседования (по колонкам)</option>
            </select>
          </div>
          <div class="field field--sm">
            <label>Строк на человека</label>
            <input v-model.number="perUser" type="number" min="1" max="5000" />
          </div>
        </div>

        <p class="muted" style="margin-bottom: 0.5rem">Выберите проверяющих:</p>
        <div class="user-chips">
          <label class="chip chip--all">
            <input type="checkbox" :checked="selectedEmails.length === reviewers.length" @change="toggleAll" />
            Все
          </label>
          <label v-for="u in reviewers" :key="u.email" class="chip">
            <input type="checkbox" :checked="selectedEmails.includes(u.email)" @change="() => {
              const i = selectedEmails.indexOf(u.email);
              if (i >= 0) selectedEmails.splice(i, 1); else selectedEmails.push(u.email);
            }" />
            {{ displayName(u) }}
          </label>
        </div>
        <div style="margin-top: 0.75rem; display: flex; gap: 1rem; align-items: center;">
          <button class="btn btn-primary" @click="distribute">Раздать по {{ perUser }}</button>
          <span v-if="distMsg" class="ok-msg">{{ distMsg }}</span>
          <span v-if="distErr" class="err-msg">{{ distErr }}</span>
        </div>
      </div>

      <!-- Текущие назначения -->
      <div class="card" style="margin-top: 1rem">
        <h3>Текущие назначения</h3>
        <table class="assign-table">
          <thead>
            <tr>
              <th>Проверяющий</th>
              <th v-if="tabNames">Анкеты</th>
              <th v-if="tabNames">Домашки</th>
              <th v-if="tabNames">Собеседования</th>
              <th>Итого</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="u in reviewers" :key="u.email">
              <td class="reviewer-cell">
                <div class="reviewer-name">{{ displayName(u) }}</div>
                <div class="reviewer-email">{{ u.email }}</div>
              </td>
              <td v-if="tabNames" class="num-cell">{{ assignCountForSheet(u.email, tabNames.ankety) }}</td>
              <td v-if="tabNames" class="num-cell">{{ assignCountForSheet(u.email, tabNames.domashki) }}</td>
              <td v-if="tabNames" class="num-cell">{{ assignCountForSheet(u.email, tabNames.interviews) }}</td>
              <td class="num-cell">{{ assignCount(u.email) }}</td>
              <td>
                <button class="btn btn-sm btn-danger" @click="clearAssignment(u.email)">Сбросить</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- ═══════════════════ USERS ═══════════════════ -->
    <div v-if="tab === 'users'" class="tab-content">
      <!-- Создать -->
      <div class="card">
        <h3>Новый пользователь</h3>
        <div class="form-row">
          <div class="field">
            <label>Email</label>
            <input v-model="newEmail" type="email" autocomplete="off" placeholder="ivan@koord.local" />
          </div>
          <div class="field">
            <label>Пароль</label>
            <input v-model="newPassword" type="password" autocomplete="new-password" />
          </div>
        </div>
        <button class="btn btn-primary" @click="createUser">Создать</button>
        <span v-if="createMsg" class="ok-msg" style="margin-left: 1rem">{{ createMsg }}</span>
        <span v-if="createErr" class="err-msg" style="margin-left: 1rem">{{ createErr }}</span>
      </div>

      <!-- Список -->
      <div class="card" style="margin-top: 1rem;">
        <table class="stats-table">
          <thead>
            <tr>
              <th>Имя</th>
              <th>Email</th>
              <th>Роль</th>
              <th>Назначений</th>
              <th>Новый пароль</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="u in users" :key="u.email">
              <td>{{ u.master_label || '—' }}</td>
              <td class="mono">{{ u.email }}</td>
              <td><span :class="['role-badge', u.role === 'super_admin' ? 'role-badge--super' : 'role-badge--user']">{{ u.role }}</span></td>
              <td class="num-cell">{{ assignCount(u.email) }}</td>
              <td>
                <div class="pwd-row">
                  <input
                    v-model="pwdInputs[u.email]"
                    type="password"
                    placeholder="новый пароль"
                    class="pwd-input"
                    @keyup.enter="setPassword(u.email)"
                  />
                  <button class="btn btn-sm" @click="setPassword(u.email)">Сохранить</button>
                </div>
                <span v-if="pwdMsg[u.email]" class="ok-msg" style="font-size:0.78rem">{{ pwdMsg[u.email] }}</span>
                <span v-if="pwdErr[u.email]" class="err-msg" style="font-size:0.78rem">{{ pwdErr[u.email] }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<style scoped>
.admin-wrap {
  max-width: 1100px;
  margin: 0 auto;
  padding: 1.5rem 1rem 3rem;
}
.admin-header h1 {
  margin: 0 0 0.25rem;
}
.tab-bar {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin: 1.25rem 0 1rem;
  border-bottom: 1px solid var(--border);
  padding-bottom: 0.5rem;
}
.tab-btn {
  background: none;
  border: none;
  color: var(--muted);
  font: inherit;
  font-size: 0.95rem;
  cursor: pointer;
  padding: 0.4rem 0.75rem;
  border-radius: 6px;
  transition: color 0.15s, background 0.15s;
}
.tab-btn:hover { color: var(--text); background: rgba(255,255,255,0.05); }
.tab-btn--active { color: var(--c-purple-light); background: rgba(153,102,255,0.12); }
.spacer { flex: 1; }
.btn-sm { font-size: 0.82rem; padding: 0.3rem 0.7rem; }

.tab-content { animation: fadein 0.18s ease; }
@keyframes fadein { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: none; } }

/* Summary cards */
.summary-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-bottom: 1.25rem;
}
.summary-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 0.9rem 1.25rem;
  min-width: 110px;
  text-align: center;
  flex: 1 1 110px;
}
.summary-val { font-size: 1.8rem; font-weight: 700; color: var(--c-purple-light); }
.summary-lbl { font-size: 0.78rem; color: var(--muted); margin-top: 0.15rem; }

/* Stats table */
.stats-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.88rem;
}
.stats-table th {
  text-align: center;
  padding: 0.6rem 0.75rem;
  color: var(--muted);
  font-weight: 600;
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}
.stats-table th:first-child { text-align: left; }
.stats-table td {
  padding: 0.6rem 0.75rem;
  border-bottom: 1px solid rgba(255,255,255,0.05);
  vertical-align: middle;
}
.stats-table tfoot td {
  border-top: 1px solid var(--border);
  border-bottom: none;
}
.subhead th { font-size: 0.75rem; color: rgba(255,255,255,0.35); padding-top: 0; }
.reviewer-cell { min-width: 160px; }
.reviewer-name { font-weight: 500; }
.reviewer-email { font-size: 0.75rem; color: var(--muted); }
.num-cell { text-align: center; font-variant-numeric: tabular-nums; }
.pct { color: var(--muted); font-size: 0.78rem; }
.done { color: #4ade80; }
.empty-row { text-align: center; color: var(--muted); padding: 2rem; }
.mono { font-family: monospace; font-size: 0.82rem; }

/* Assign section */
.form-row { display: flex; flex-wrap: wrap; gap: 1rem; align-items: flex-end; margin-bottom: 1rem; }
.field { display: flex; flex-direction: column; gap: 0.35rem; flex: 1 1 200px; }
.field--sm { flex: 0 0 130px; }
.field label { font-size: 0.82rem; color: var(--muted); }
.field input, .select-like {
  padding: 0.5rem 0.65rem;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: rgba(255,255,255,0.04);
  color: var(--text);
  font: inherit;
}
.field input:focus, .select-like:focus { outline: 1px solid var(--c-purple); }

/* Chips */
.user-chips { display: flex; flex-wrap: wrap; gap: 0.4rem; }
.chip {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.3rem 0.6rem;
  border: 1px solid var(--border);
  border-radius: 20px;
  cursor: pointer;
  font-size: 0.82rem;
  transition: border-color 0.15s, background 0.15s;
}
.chip:hover { border-color: var(--c-purple); background: rgba(153,102,255,0.1); }
.chip--all { border-style: dashed; }

/* Custom counts grid */
.custom-grid { display: flex; flex-direction: column; gap: 0.5rem; max-height: 55vh; overflow-y: auto; padding-right: 0.25rem; }
.custom-row { display: flex; align-items: center; gap: 0.75rem; }
.custom-name { flex: 1; font-size: 0.9rem; }
.custom-input { width: 80px; padding: 0.35rem 0.5rem; border-radius: 6px; border: 1px solid var(--border); background: rgba(255,255,255,0.04); color: var(--text); font: inherit; text-align: center; }
.custom-input:focus { outline: 1px solid var(--c-purple); }

/* Assign table */
.assign-table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
.assign-table th { text-align: center; padding: 0.6rem 0.75rem; color: var(--muted); font-weight: 600; border-bottom: 1px solid var(--border); }
.assign-table th:first-child { text-align: left; }
.assign-table td { padding: 0.55rem 0.75rem; border-bottom: 1px solid rgba(255,255,255,0.05); vertical-align: middle; }

/* Rows tab */
.rows-toolbar {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 0.75rem;
  flex-wrap: wrap;
}
.search-input {
  padding: 0.35rem 0.65rem;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: rgba(255,255,255,0.04);
  color: var(--text);
  font: inherit;
  font-size: 0.85rem;
  width: 220px;
}
.search-input:focus { outline: 1px solid var(--c-purple); }
.rows-table-wrap {
  overflow: auto;
  max-height: 68vh;
  border: 1px solid var(--border);
  border-radius: 8px;
}
.rows-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.83rem;
  min-width: 700px;
}
.rows-table thead {
  position: sticky;
  top: 0;
  z-index: 1;
  background: var(--c-bg-2, #1a1228);
}
.rows-table th {
  padding: 0.5rem 0.6rem;
  text-align: left;
  color: var(--muted);
  font-weight: 600;
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}
.rows-table td {
  padding: 0.4rem 0.6rem;
  border-bottom: 1px solid rgba(255,255,255,0.04);
  vertical-align: middle;
}
.col-num { width: 42px; text-align: center; }
.col-reviewer { width: 200px; }
.cell-preview {
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.row--assigned td { background: rgba(74, 222, 128, 0.04); }
.row--saving td { opacity: 0.5; }
.reviewer-select {
  width: 100%;
  padding: 0.3rem 0.5rem;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: rgba(255,255,255,0.04);
  color: var(--text);
  font: inherit;
  font-size: 0.82rem;
  cursor: pointer;
}
.reviewer-select:focus { outline: 1px solid var(--c-purple); }
.reviewer-select:not([value=""]):not(:invalid) { border-color: rgba(74,222,128,0.3); }

/* Password row */
.pwd-row { display: flex; gap: 0.4rem; align-items: center; }
.pwd-input {
  width: 140px;
  padding: 0.3rem 0.5rem;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: rgba(255,255,255,0.04);
  color: var(--text);
  font: inherit;
  font-size: 0.82rem;
}
.pwd-input:focus { outline: 1px solid var(--c-purple); }

/* Role badges */
.role-badge { display: inline-block; padding: 0.2rem 0.5rem; border-radius: 20px; font-size: 0.75rem; font-weight: 600; }
.role-badge--super { background: rgba(255, 180, 50, 0.15); color: #fbbf24; }
.role-badge--user { background: rgba(153,102,255,0.15); color: var(--c-purple-light); }

/* Messages */
.ok-msg { color: #4ade80; font-size: 0.85rem; }
.err-msg { color: #f87171; font-size: 0.85rem; }
.err-banner { background: rgba(248,113,113,0.15); border: 1px solid #f87171; color: #f87171; border-radius: 8px; padding: 0.6rem 0.9rem; }
.warn-banner { background: rgba(251,191,36,0.12); border: 1px solid #fbbf24; color: #fbbf24; border-radius: 8px; padding: 0.6rem 0.9rem; margin-bottom: 1rem; font-size: 0.88rem; }
.btn-danger { background: rgba(248,113,113,0.15); color: #f87171; border-color: rgba(248,113,113,0.3); }
.btn-danger:hover { background: rgba(248,113,113,0.25); }
</style>
