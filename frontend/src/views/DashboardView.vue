<script setup lang="ts">
import { onMounted, ref } from "vue";
import { api } from "../api/client";

const stats = ref<{
  meta: Record<string, unknown>;
  row_counts: Record<string, number>;
  cached_sheets: string[];
} | null>(null);

type MasterRow = {
  email: string;
  label: string;
  ankety: { total: number; reviewed: number; pending: number };
  domashki: { total: number; reviewed: number; pending: number };
  interviews: { total: number; conducted: number; pending: number };
};

const master = ref<{
  masters: MasterRow[];
  cache_loaded: boolean;
  note: string | null;
} | null>(null);

const syncResult = ref<string | null>(null);
const err = ref("");
const loading = ref(false);

async function load() {
  err.value = "";
  try {
    const [s, m] = await Promise.all([api.dashboardStats(), api.masterDashboard()]);
    stats.value = s;
    master.value = m;
  } catch (e) {
    err.value = e instanceof Error ? e.message : "Ошибка";
  }
}

async function sync() {
  syncResult.value = null;
  loading.value = true;
  err.value = "";
  try {
    const r = await api.syncSheets();
    syncResult.value = `Ок: ${r.sheets.join(", ")}`;
    await load();
  } catch (e) {
    err.value = e instanceof Error ? e.message : "Только супер-админ может синхронизировать";
  } finally {
    loading.value = false;
  }
}

function cellClass(n: number) {
  if (n === 0) return "cell-ok";
  return "cell-warn";
}

onMounted(load);
</script>

<template>
  <div class="dash">
    <h1>Дашборд</h1>
    <p class="muted">
      Назначения и пользователи хранятся в БД приложения; цифры по проверкам считаются по кэшу Google Sheets
      (после синхронизации).
    </p>
    <p v-if="err" class="msg-error">{{ err }}</p>
    <p v-if="syncResult" class="muted">{{ syncResult }}</p>
    <div class="card card--actions">
      <button type="button" class="btn btn-primary" :disabled="loading" @click="sync">
        {{ loading ? "…" : "Синхронизировать с Google" }}
      </button>
    </div>

    <div v-if="master" class="card">
      <h3 class="card-title">Мастера отбора</h3>
      <p v-if="master.note" class="muted">{{ master.note }}</p>
      <div class="table-wrap">
        <table class="dash-table">
          <thead>
            <tr>
              <th>MO</th>
              <th>Всего анкет</th>
              <th>Проверено анкет</th>
              <th>Непроверено анкет</th>
              <th>Всего ИДЗ</th>
              <th>Проверено ИДЗ</th>
              <th>Непроверено ИДЗ</th>
              <th>Проведено собесов</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="m in master.masters" :key="m.email">
              <td>
                <span class="dash-mo">{{ m.label }}</span>
                <span class="muted dash-email">{{ m.email }}</span>
              </td>
              <td>{{ m.ankety.total }}</td>
              <td>{{ m.ankety.reviewed }}</td>
              <td :class="cellClass(m.ankety.pending)">{{ m.ankety.pending }}</td>
              <td>{{ m.domashki.total }}</td>
              <td>{{ m.domashki.reviewed }}</td>
              <td :class="cellClass(m.domashki.pending)">{{ m.domashki.pending }}</td>
              <td>{{ m.interviews.conducted }} / {{ m.interviews.total }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-if="master.masters.length === 0" class="muted">Нет пользователей с ролью «user» (мастеров).</p>
    </div>

    <div v-if="stats" class="card">
      <h3 class="card-title">Строк по листам (кэш Redis)</h3>
      <ul class="dash-list">
        <li v-for="(n, name) in stats.row_counts" :key="name">
          <strong>{{ name }}</strong
          >: {{ n }}
        </li>
      </ul>
      <p v-if="!stats.cached_sheets.length" class="muted">Кэш пуст — нажмите синхронизацию.</p>
    </div>
  </div>
</template>

<style scoped>
.dash {
  width: 100%;
}
.card-title {
  margin-top: 0;
}
.card--actions {
  margin-bottom: 1rem;
}
.msg-error {
  color: #f88;
}
.dash-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.88rem;
}
.dash-table th,
.dash-table td {
  border: 1px solid var(--border);
  padding: 0.45rem 0.55rem;
  text-align: left;
}
.dash-table th {
  background: #1a1f2a;
  color: var(--muted);
  font-weight: 600;
}
.dash-mo {
  font-weight: 600;
  display: block;
}
.dash-email {
  font-size: 0.75rem;
  display: block;
  word-break: break-all;
}
.cell-ok {
  background: rgba(46, 160, 67, 0.15);
}
.cell-warn {
  background: rgba(220, 80, 80, 0.18);
}
.dash-list {
  margin: 0;
  padding-left: 1.2rem;
}
</style>
