<script setup lang="ts">
import { onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { api, getRole } from "../api/client";

const sheetName = ref("sub-bass");
const rows = ref<string[][]>([]);
const note = ref<string | null>(null);
const err = ref("");
const loading = ref(false);
const isSuperAdmin = () => getRole() === "super_admin";

async function loadTabNames() {
  try {
    const names = await api.sheetTabNames();
    sheetName.value = names.subs;
  } catch {
    /* оставим дефолт */
  }
}

async function load() {
  err.value = "";
  note.value = null;
  try {
    const data = await api.getSheet(sheetName.value);
    rows.value = data.values || [];
    note.value = data.note || null;
  } catch (e) {
    err.value = e instanceof Error ? e.message : "Ошибка загрузки";
  }
}

async function sync() {
  loading.value = true;
  err.value = "";
  try {
    await api.syncSheets();
    await load();
  } catch (e) {
    err.value = e instanceof Error ? e.message : "Не удалось синхронизировать";
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  await loadTabNames();
  await load();
});
</script>

<template>
  <div>
    <div class="subs-hero">
      <img src="/brand/kg.svg" alt="КГ" class="subs-hero-img" />
      <p class="subs-hero-caption">КГ И ЛЮБИМЫЙ СТП</p>
    </div>
    <h1>Сабы</h1>
    <p class="muted">
      Лист «{{ sheetName }}» — для всех пользователей целиком (без разбивки по проверяющим). Имя вкладки в Google
      задаётся в <code>.env</code> как <code>SHEET_NAME_SUBS</code>.
    </p>

    <div v-if="isSuperAdmin()" class="card" style="margin-bottom: 1rem">
      <p class="muted" style="margin-top: 0">
        Подгрузите данные из таблицы в кэш (нужно один раз после запуска и при обновлении листов):
      </p>
      <button type="button" class="btn btn-primary" :disabled="loading" @click="sync">
        {{ loading ? "…" : "Синхронизировать с Google" }}
      </button>
    </div>
    <p v-else-if="note || !rows.length" class="muted">
      Синхронизацию с Google может выполнить
      <RouterLink to="/dashboard">супер-админ на дашборде</RouterLink>.
    </p>

    <div v-if="note" class="card" style="margin-bottom: 1rem; border-color: var(--accent-dim)">
      {{ note }}
    </div>
    <p v-if="err" style="color: #f88">{{ err }}</p>

    <div class="card table-wrap">
      <table v-if="rows.length">
        <tbody>
          <tr v-for="(r, i) in rows" :key="i">
            <td v-for="(c, j) in r" :key="j">{{ c }}</td>
          </tr>
        </tbody>
      </table>
      <p v-else class="muted">
        Пока нет строк в кэше. Супер-админ нажмите «Синхронизировать с Google» выше или на дашборде.
      </p>
    </div>
  </div>
</template>

<style scoped>
.subs-hero {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
  margin-bottom: 2rem;
}

.subs-hero-img {
  width: 100%;
  max-width: 560px;
  height: auto;
  border-radius: 16px;
}

.subs-hero-caption {
  font-family: var(--font-heading);
  font-size: clamp(1.4rem, 4vw, 2.2rem);
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin: 0;
  background: var(--grad-accent);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  text-align: center;
}
</style>
