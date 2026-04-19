<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { api } from "../api/client";
import { colIndexToLetters, quoteSheetName } from "../utils/sheetsA1";

const sheetTitle = ref("Domashki");
const header = ref<string[]>([]);
const dataRows = ref<string[][]>([]);
const dataRowIndices = ref<number[]>([]);
const err = ref("");
const layoutErr = ref("");
const saveMsg = ref("");
const saving = ref(false);

const layout = ref<{
  score_column_indices: { index: number; header: string | null }[];
  sum_column: { index: number | null; header: string | null };
  level_column: { index: number | null; header: string | null };
  reviewer_questions_column: { index: number | null; header: string | null };
  reviewer_comment_column: { index: number | null; header: string | null };
} | null>(null);

const rowScores = ref<string[][]>([]);
const rowQuestions = ref<string[]>([]);
const rowComments = ref<string[]>([]);

const firstAnswerColEnd = computed(() => {
  const sc = layout.value?.score_column_indices;
  if (!sc?.length) return header.value.length;
  return sc[0].index;
});

const answerColumns = computed(() => {
  const h = header.value;
  const end = firstAnswerColEnd.value;
  return h.slice(0, end).map((label, i) => ({ i, label: label || `Колонка ${i + 1}` }));
});

function cell(row: string[], i: number): string {
  return row[i] != null && row[i] !== undefined ? String(row[i]) : "";
}

function cellOpt(row: string[], ix: number | null | undefined): string {
  if (ix == null || ix < 0) return "—";
  return cell(row, ix) || "—";
}

function initEditors() {
  rowScores.value = dataRows.value.map((row) =>
    (layout.value?.score_column_indices ?? []).map((c) => cell(row, c.index)),
  );
  rowQuestions.value = dataRows.value.map((row) =>
    layout.value?.reviewer_questions_column?.index != null
      ? cell(row, layout.value.reviewer_questions_column.index)
      : "",
  );
  rowComments.value = dataRows.value.map((row) =>
    layout.value?.reviewer_comment_column?.index != null ? cell(row, layout.value.reviewer_comment_column.index) : "",
  );
}

watch([dataRows, layout], initEditors, { deep: true });

async function load() {
  err.value = "";
  saveMsg.value = "";
  layoutErr.value = "";
  try {
    const names = await api.sheetTabNames();
    sheetTitle.value = names.domashki;
    const data = await api.getSheet(names.domashki);
    const vals = data.values || [];
    header.value = vals[0] ? vals[0].map((x) => String(x)) : [];
    dataRows.value = vals.slice(1).map((r) => r.map((x) => (x != null ? String(x) : "")));
    dataRowIndices.value =
      Array.isArray(data.data_row_indices) && data.data_row_indices.length === dataRows.value.length
        ? data.data_row_indices
        : dataRows.value.map((_, i) => i + 1);
  } catch (e) {
    err.value = e instanceof Error ? e.message : "Ошибка загрузки";
  }
  try {
    layout.value = await api.domashkiColumnLayout();
  } catch (e) {
    layoutErr.value = e instanceof Error ? e.message : "";
    layout.value = null;
  }
  initEditors();
}

async function saveRow(cardIndex: number) {
  if (!layout.value?.score_column_indices?.length) {
    saveMsg.value = "Нет разметки колонок — выполните синхронизацию таблицы.";
    return;
  }
  const ri = dataRowIndices.value[cardIndex];
  if (ri === undefined) return;
  const rowNum = ri + 1;
  const q = quoteSheetName(sheetTitle.value);
  const updates: { range_a1: string; values: string[][] }[] = [];

  layout.value.score_column_indices.forEach((sc, k) => {
    const v = rowScores.value[cardIndex]?.[k] ?? "";
    const col = colIndexToLetters(sc.index);
    updates.push({ range_a1: `${q}!${col}${rowNum}`, values: [[v]] });
  });

  const rq = layout.value.reviewer_questions_column?.index;
  if (rq != null) {
    updates.push({
      range_a1: `${q}!${colIndexToLetters(rq)}${rowNum}`,
      values: [[rowQuestions.value[cardIndex] ?? ""]],
    });
  }
  const rc = layout.value.reviewer_comment_column?.index;
  if (rc != null) {
    updates.push({
      range_a1: `${q}!${colIndexToLetters(rc)}${rowNum}`,
      values: [[rowComments.value[cardIndex] ?? ""]],
    });
  }

  saving.value = true;
  saveMsg.value = "";
  try {
    const res = await api.queueWriteBatch(updates);
    saveMsg.value = "Сохранено в очередь. Через несколько секунд обновите страницу.";
  } catch (e) {
    saveMsg.value = e instanceof Error ? e.message : "Ошибка сохранения";
  } finally {
    saving.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div class="hw-page">
    <header class="page-head">
      <h1 class="page-head__title">Домашки (ИДЗ)</h1>
    </header>

    <p v-if="layoutErr" class="msg-muted msg-compact">{{ layoutErr }}</p>
    <p v-if="err" class="msg-error">{{ err }}</p>
    <p v-if="saveMsg" class="msg-muted msg-compact">{{ saveMsg }}</p>

    <div v-if="!dataRows.length && !err" class="card muted empty-hint">
      Нет строк — назначьте проверку или синхронизируйте таблицу (супер-админ).
    </div>

    <article v-for="(row, cardIndex) in dataRows" :key="dataRowIndices[cardIndex] ?? cardIndex" class="hw-card card">
      <div class="hw-card__head">
        <span class="hw-card__title">
          <template v-if="cell(row, 1)">{{ cell(row, 1) }}</template>
          <template v-else>Строка {{ (dataRowIndices[cardIndex] ?? 0) + 1 }}</template>
          <span v-if="cell(row, 0)" class="muted"> · МО: {{ cell(row, 0) }}</span>
        </span>
        <span v-if="cell(row, 2)" class="muted hw-card__email">{{ cell(row, 2) }}</span>
        <span class="muted hw-card__meta">Строка {{ (dataRowIndices[cardIndex] ?? 0) + 1 }}</span>
      </div>

      <div class="hw-card__grid">
        <div class="hw-card__col">
          <details class="hw-details">
            <summary>Данные по ИДЗ</summary>
            <div class="hw-qa">
              <div v-for="ac in answerColumns" :key="ac.i" class="hw-qa__row">
                <div class="hw-qa__q">{{ ac.label }}</div>
                <div class="hw-qa__a">{{ cell(row, ac.i) || "—" }}</div>
              </div>
            </div>
          </details>
        </div>

        <div class="hw-card__col hw-card__col--grading">
          <section v-if="layout?.score_column_indices?.length" class="hw-scores">
            <h4>Баллы</h4>
            <div class="hw-scores__grid">
              <label v-for="(sc, sk) in layout.score_column_indices" :key="sk" class="score-field">
                <span class="score-field__label">{{ sc.header?.replace(/\n/g, " ") || `Балл ${sk + 1}` }}</span>
                <input v-model="rowScores[cardIndex][sk]" type="text" inputmode="decimal" class="score-field__input" />
              </label>
            </div>
            <div v-if="layout.sum_column.index != null || layout.level_column.index != null" class="hw-readonly muted">
              <span v-if="layout.sum_column.index != null"
                >{{ layout.sum_column.header?.trim() || "Оценка" }}: {{ cellOpt(row, layout.sum_column.index) }}</span
              >
              <span v-if="layout.level_column.index != null">
                · {{ layout.level_column.header?.trim() || "Уровень" }}:
                {{ cellOpt(row, layout.level_column.index) }}</span
              >
            </div>
          </section>

          <section v-if="layout?.reviewer_questions_column?.index != null" class="hw-reviewer">
            <label class="field">
              <span>Вопросы по ИДЗ</span>
              <textarea v-model="rowQuestions[cardIndex]" rows="2" class="hw-textarea" />
            </label>
            <label v-if="layout?.reviewer_comment_column?.index != null" class="field">
              <span>Комментарий по ИДЗ</span>
              <textarea v-model="rowComments[cardIndex]" rows="3" class="hw-textarea" />
            </label>
          </section>

          <footer class="hw-card__foot">
            <button type="button" class="btn btn-primary" :disabled="saving" @click="saveRow(cardIndex)">
              {{ saving ? "…" : "Сохранить" }}
            </button>
          </footer>
        </div>
      </div>
    </article>
  </div>
</template>

<style scoped>
.hw-page {
  width: 100%;
}
.page-head {
  margin-bottom: 0.75rem;
}
.page-head__title {
  margin: 0;
  font-size: clamp(1.35rem, 2vw, 1.65rem);
  font-weight: 700;
  letter-spacing: -0.02em;
}
.msg-compact {
  font-size: 0.85rem;
  margin: 0 0 0.5rem;
}
.msg-muted {
  color: var(--muted);
}
.msg-error {
  color: #f88;
  margin: 0 0 0.5rem;
}
.empty-hint {
  padding: 1rem 1.25rem;
  margin-bottom: 1rem;
}
.hw-card {
  margin-bottom: 1.25rem;
  padding: 1rem 1.35rem 1.25rem;
}
.hw-card__head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 1rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid var(--border);
}
.hw-card__title {
  font-weight: 600;
  font-size: clamp(1rem, 1.2vw, 1.15rem);
}
.hw-card__email {
  font-size: 0.85rem;
}
.hw-card__meta {
  font-size: 0.8rem;
  width: 100%;
  text-align: right;
}
.hw-card__grid {
  display: grid;
  gap: 1.25rem 1.75rem;
  grid-template-columns: 1fr;
  align-items: start;
}
@media (min-width: 1040px) {
  .hw-card__grid {
    grid-template-columns: minmax(0, 1.15fr) minmax(320px, 1fr);
  }
}
.hw-details {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 0.4rem 0.85rem;
  background: #121620;
}
.hw-details summary {
  cursor: pointer;
  font-weight: 500;
  padding: 0.35rem 0;
}
.hw-details[open] summary {
  margin-bottom: 0.5rem;
}
.hw-qa {
  max-height: min(52vh, 640px);
  overflow-y: auto;
  padding-right: 0.35rem;
}
.hw-qa__row {
  margin-bottom: 0.65rem;
  font-size: 0.9rem;
}
.hw-qa__q {
  color: var(--muted);
  font-size: 0.78rem;
  margin-bottom: 0.15rem;
}
.hw-qa__a {
  white-space: pre-wrap;
  word-break: break-word;
}
.hw-scores h4 {
  margin: 0 0 0.5rem;
  font-size: 0.9rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--muted);
}
.hw-scores__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(108px, 1fr));
  gap: 0.65rem 0.85rem;
}
@media (min-width: 1400px) {
  .hw-scores__grid {
    grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
  }
}
.score-field {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}
.score-field__label {
  font-size: 0.72rem;
  color: var(--muted);
  line-height: 1.2;
  max-height: 2.4em;
  overflow: hidden;
}
.score-field__input {
  padding: 0.35rem 0.5rem;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: #0f1219;
  color: var(--text);
  font: inherit;
  width: 100%;
}
.hw-readonly {
  margin-top: 0.5rem;
  font-size: 0.85rem;
}
.hw-reviewer .field span {
  display: block;
  font-size: 0.85rem;
  color: var(--muted);
  margin-bottom: 0.25rem;
}
.hw-textarea {
  width: 100%;
  padding: 0.5rem;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: #0f1219;
  color: var(--text);
  font: inherit;
  resize: vertical;
}
.hw-card__foot {
  margin-top: 0.75rem;
  padding-top: 0.75rem;
  border-top: 1px solid var(--border);
}
</style>
