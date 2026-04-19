<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { api } from "../api/client";
import { colIndexToLetters, quoteSheetName } from "../utils/sheetsA1";

const sheetTitle = ref("Анкеты");
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

/** Баллы по строке: индекс строки карточки → значения по порядку колонок баллов */
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
    sheetTitle.value = names.ankety;
    const data = await api.getSheet(names.ankety);
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
    layout.value = await api.anketyColumnLayout();
  } catch (e) {
    layoutErr.value = e instanceof Error ? e.message : "";
    layout.value = null;
  }
  initEditors();
}

async function saveRow(cardIndex: number) {
  if (!layout.value?.score_column_indices?.length) {
    saveMsg.value = "Нет разметки колонок — откройте раздел после синхронизации.";
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
  <div class="ankety-page">
    <header class="page-head">
      <h1 class="page-head__title">Анкеты</h1>
    </header>

    <p v-if="layoutErr" class="msg-muted msg-compact">{{ layoutErr }}</p>
    <p v-if="err" class="msg-error">{{ err }}</p>
    <p v-if="saveMsg" class="msg-muted msg-compact">{{ saveMsg }}</p>

    <div v-if="!dataRows.length && !err" class="card muted empty-hint">Нет строк — назначьте анкеты или синхронизируйте таблицу.</div>

    <article
      v-for="(row, cardIndex) in dataRows"
      :key="dataRowIndices[cardIndex] ?? cardIndex"
      class="anketa-card card"
    >
      <div class="anketa-card__head">
        <span class="anketa-card__title">
          {{ cell(row, 0) }} {{ cell(row, 1) }} {{ cell(row, 2) }}
          <span v-if="cell(row, 4)" class="muted">· {{ cell(row, 4) }}</span>
        </span>
        <span class="muted anketa-card__meta">Строка {{ (dataRowIndices[cardIndex] ?? 0) + 1 }}</span>
      </div>

      <div class="anketa-card__grid">
        <div class="anketa-card__col anketa-card__col--answers">
          <details class="anketa-details">
            <summary>Ответы респондента</summary>
            <div class="anketa-qa">
              <div v-for="ac in answerColumns" :key="ac.i" class="anketa-qa__row">
                <div class="anketa-qa__q">{{ ac.label }}</div>
                <div class="anketa-qa__a">{{ cell(row, ac.i) || "—" }}</div>
              </div>
            </div>
          </details>
        </div>

        <div class="anketa-card__col anketa-card__col--grading">
          <section v-if="layout?.score_column_indices?.length" class="anketa-scores">
            <h4>Баллы</h4>
            <div class="anketa-scores__grid">
              <label v-for="(sc, sk) in layout.score_column_indices" :key="sk" class="score-field">
                <span class="score-field__label">{{ sc.header?.replace(/\n/g, " ") || `Балл ${sk + 1}` }}</span>
                <input v-model="rowScores[cardIndex][sk]" type="text" inputmode="decimal" class="score-field__input" />
              </label>
            </div>
            <div
              v-if="layout.sum_column.index != null || layout.level_column.index != null"
              class="anketa-readonly muted"
            >
              <span v-if="layout.sum_column.index != null"
                >{{ layout.sum_column.header?.trim() || "Сумма" }}: {{ cellOpt(row, layout.sum_column.index) }}</span
              >
              <span v-if="layout.level_column.index != null">
                · {{ layout.level_column.header?.trim() || "Уровень" }}:
                {{ cellOpt(row, layout.level_column.index) }}</span
              >
            </div>
          </section>

          <section v-if="layout?.reviewer_questions_column?.index != null" class="anketa-reviewer">
            <label class="field">
              <span>Вопросы по анкете</span>
              <textarea v-model="rowQuestions[cardIndex]" rows="2" class="anketa-textarea" />
            </label>
            <label v-if="layout?.reviewer_comment_column?.index != null" class="field">
              <span>Комментарий по анкете</span>
              <textarea v-model="rowComments[cardIndex]" rows="3" class="anketa-textarea" />
            </label>
          </section>

          <footer class="anketa-card__foot">
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
.ankety-page {
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
.anketa-card {
  margin-bottom: 1.25rem;
  padding: 1rem 1.35rem 1.25rem;
}
.anketa-card__head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 1rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid var(--border);
}
.anketa-card__title {
  font-weight: 600;
  font-size: clamp(1rem, 1.2vw, 1.15rem);
}
.anketa-card__meta {
  font-size: 0.8rem;
}
.anketa-card__grid {
  display: grid;
  gap: 1.25rem 1.75rem;
  grid-template-columns: 1fr;
  align-items: start;
}
@media (min-width: 1040px) {
  .anketa-card__grid {
    grid-template-columns: minmax(0, 1.15fr) minmax(320px, 1fr);
  }
}
.anketa-details {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 0.4rem 0.85rem;
  background: #121620;
}
.anketa-details summary {
  cursor: pointer;
  font-weight: 500;
  padding: 0.35rem 0;
}
.anketa-details[open] summary {
  margin-bottom: 0.5rem;
}
.anketa-qa {
  max-height: min(52vh, 640px);
  overflow-y: auto;
  padding-right: 0.35rem;
}
.anketa-qa__row {
  margin-bottom: 0.65rem;
  font-size: 0.9rem;
}
.anketa-qa__q {
  color: var(--muted);
  font-size: 0.78rem;
  margin-bottom: 0.15rem;
}
.anketa-qa__a {
  white-space: pre-wrap;
  word-break: break-word;
}
.anketa-scores h4 {
  margin: 0 0 0.5rem;
  font-size: 0.9rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--muted);
}
.anketa-scores__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(108px, 1fr));
  gap: 0.65rem 0.85rem;
}
@media (min-width: 1400px) {
  .anketa-scores__grid {
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
.anketa-readonly {
  margin-top: 0.5rem;
  font-size: 0.85rem;
}
.anketa-reviewer .field span {
  display: block;
  font-size: 0.85rem;
  color: var(--muted);
  margin-bottom: 0.25rem;
}
.anketa-textarea {
  width: 100%;
  padding: 0.5rem;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: #0f1219;
  color: var(--text);
  font: inherit;
  resize: vertical;
}
.anketa-card__foot {
  margin-top: 0.75rem;
  padding-top: 0.75rem;
  border-top: 1px solid var(--border);
}
</style>
