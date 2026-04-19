<script setup lang="ts">
import { onMounted, ref } from "vue";
import { api } from "../api/client";

const users = ref<{ email: string; role: string }[]>([]);
const assignments = ref<Record<string, Record<string, number[]>>>({});
const newEmail = ref("");
const newPassword = ref("");
const createMsg = ref("");
const createErr = ref("");

const tabNames = ref<{
  subs: string;
  enquiries: string;
  domashki: string;
  ankety: string;
  interviews: string;
} | null>(null);
const sheetForDist = ref("");
const perUser = ref(10);
const distributeByColumns = ref(false);
const selectedEmails = ref<string[]>([]);
const distMsg = ref("");
const distErr = ref("");

async function refresh() {
  createErr.value = "";
  distErr.value = "";
  users.value = await api.adminUsers();
  assignments.value = await api.adminAssignments();
  const names = await api.sheetTabNames();
  tabNames.value = names;
  if (!sheetForDist.value) sheetForDist.value = names.ankety;
}

function onDistributeSheetChange() {
  if (!tabNames.value) return;
  distributeByColumns.value = sheetForDist.value === tabNames.value.interviews;
}

onMounted(refresh);

async function createUser() {
  createMsg.value = "";
  createErr.value = "";
  try {
    await api.adminCreateUser(newEmail.value.trim(), newPassword.value, "user");
    createMsg.value = "Пользователь создан";
    newEmail.value = "";
    newPassword.value = "";
    await refresh();
  } catch (e) {
    createErr.value = e instanceof Error ? e.message : "Ошибка";
  }
}

function toggleUser(email: string) {
  const i = selectedEmails.value.indexOf(email);
  if (i >= 0) selectedEmails.value.splice(i, 1);
  else selectedEmails.value.push(email);
}

async function distribute() {
  distMsg.value = "";
  distErr.value = "";
  if (!selectedEmails.value.length) {
    distErr.value = "Выберите хотя бы одного пользователя";
    return;
  }
  try {
    const res = await api.adminDistribute(
      sheetForDist.value,
      perUser.value,
      selectedEmails.value,
      distributeByColumns.value,
    );
    const what = distributeByColumns.value ? "колонок" : "строк";
    distMsg.value = `Готово. Распределены индексы ${what}: ${JSON.stringify(res.assigned_rows)}`;
    await refresh();
  } catch (e) {
    distErr.value = e instanceof Error ? e.message : "Ошибка";
  }
}
</script>

<template>
  <div>
    <h1>Назначения (супер-админ)</h1>
    <p class="muted">
      Создайте логины для проверяющих, затем выберите лист и раздайте по N строк каждому. Индексы строк — как в
      таблице после синхронизации (строка 0 — заголовок).
    </p>

    <div class="card" style="margin-bottom: 1.25rem">
      <h3 style="margin-top: 0">Новый пользователь</h3>
      <div class="field">
        <label>Email (логин)</label>
        <input v-model="newEmail" type="email" autocomplete="off" />
      </div>
      <div class="field">
        <label>Пароль</label>
        <input v-model="newPassword" type="password" autocomplete="new-password" />
      </div>
      <button type="button" class="btn btn-primary" @click="createUser">Создать</button>
      <p v-if="createMsg" class="muted">{{ createMsg }}</p>
      <p v-if="createErr" style="color: #f88">{{ createErr }}</p>
    </div>

    <div class="card" style="margin-bottom: 1.25rem">
      <h3 style="margin-top: 0">Распределить строки листа</h3>
      <div class="field">
        <label>Лист</label>
        <select v-if="tabNames" v-model="sheetForDist" class="select-like" @change="onDistributeSheetChange">
          <option :value="tabNames.ankety">Анкеты ({{ tabNames.ankety }})</option>
          <option :value="tabNames.domashki">Домашки ({{ tabNames.domashki }})</option>
          <option :value="tabNames.enquiries">Enquiries ({{ tabNames.enquiries }})</option>
          <option :value="tabNames.interviews">Собеседования ({{ tabNames.interviews }})</option>
        </select>
      </div>
      <p v-if="tabNames && sheetForDist === tabNames.interviews" class="muted">
        Для «Собеседования» распределяются <strong>колонки</strong> кандидатов (с D по ширине листа), не строки.
        При необходимости снимите галочку ниже.
      </p>
      <div v-if="tabNames && sheetForDist === tabNames.interviews" class="field">
        <label>
          <input v-model="distributeByColumns" type="checkbox" />
          Распределять по колонкам (рекомендуется)
        </label>
      </div>
      <div class="field">
        <label>Сколько строк на человека</label>
        <input v-model.number="perUser" type="number" min="1" max="5000" />
      </div>
      <p class="muted">Отметьте проверяющих (только существующие учётные записи):</p>
      <div class="user-chips">
        <label v-for="u in users.filter((x) => x.role === 'user')" :key="u.email" class="chip">
          <input type="checkbox" :checked="selectedEmails.includes(u.email)" @change="toggleUser(u.email)" />
          {{ u.email }}
        </label>
      </div>
      <button type="button" class="btn btn-primary" style="margin-top: 0.75rem" @click="distribute">
        Раздать по {{ perUser }} строк
      </button>
      <p v-if="distMsg" class="muted" style="word-break: break-all">{{ distMsg }}</p>
      <p v-if="distErr" style="color: #f88">{{ distErr }}</p>
    </div>

    <div class="card">
      <h3 style="margin-top: 0">Текущие назначения (индексы строк в кэше)</h3>
      <pre class="pre-json">{{ JSON.stringify(assignments, null, 2) }}</pre>
    </div>
  </div>
</template>

<style scoped>
.pre-json {
  margin: 0;
  font-size: 0.8rem;
  overflow: auto;
  max-height: 40vh;
  color: var(--muted);
}
.user-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}
.chip {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.35rem 0.6rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.9rem;
}
.select-like {
  padding: 0.5rem 0.65rem;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: #121620;
  color: var(--text);
  font: inherit;
  max-width: 100%;
}
</style>
