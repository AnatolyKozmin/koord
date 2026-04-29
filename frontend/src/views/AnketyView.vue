<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { api, getRole } from "../api/client";
import { colIndexToLetters, quoteSheetName } from "../utils/sheetsA1";

const sheetTitle = ref("Анкеты");
const currentUserLabel = ref<string | null>(null);
const header = ref<string[]>([]);
const dataRows = ref<string[][]>([]);
const dataRowIndices = ref<number[]>([]);
const err = ref("");
const layoutErr = ref("");
const saveMsg = ref("");
const saving = ref(false);

const layout = ref<{
  score_column_indices: { index: number; header: string | null; options: string[] }[];
  sum_column: { index: number | null; header: string | null };
  level_column: { index: number | null; header: string | null };
  reviewer_questions_column: { index: number | null; header: string | null };
  reviewer_comment_column: { index: number | null; header: string | null };
} | null>(null);

/** Баллы по строке: индекс строки карточки → значения по порядку колонок баллов */
const rowScores = ref<string[][]>([]);
const rowQuestions = ref<string[]>([]);
const rowComments = ref<string[]>([]);

/** Снимки сохранённых значений — для сравнения с текущими */
const savedScores = ref<string[][]>([]);
const savedQuestions = ref<string[]>([]);
const savedComments = ref<string[]>([]);
/**
 * null  = только загрузили, ещё ничего не меняли
 * true  = успешно сохранено в эту сессию
 * false = (не используется)
 */
const savedOnce = ref<(boolean | null)[]>([]);

/** Карточка считается заполненной если хотя бы один балл непустой */
function hasAnyScore(i: number): boolean {
  return (rowScores.value[i] ?? []).some((v) => v !== "");
}

function isDirty(i: number): boolean {
  if (savedOnce.value[i] === null) return false; // ещё не трогали
  const scoresChanged = (rowScores.value[i] ?? []).some(
    (v, k) => v !== (savedScores.value[i]?.[k] ?? ""),
  );
  const qChanged = (rowQuestions.value[i] ?? "") !== (savedQuestions.value[i] ?? "");
  const cChanged = (rowComments.value[i] ?? "") !== (savedComments.value[i] ?? "");
  return scoresChanged || qChanged || cChanged;
}

/** Пометить карточку как «изменённую» при любом вводе */
function markDirty(i: number) {
  if (savedOnce.value[i] === null) savedOnce.value[i] = false;
}

const firstAnswerColEnd = computed(() => {
  const sc = layout.value?.score_column_indices;
  if (!sc?.length) return header.value.length;
  return sc[0].index;
});

// Колонки A (0) и B (1) — служебные: «Проверяющий» и «Сумма баллов»; не показываем.
const SKIP_COLS = 2;

const answerColumns = computed(() => {
  const h = header.value;
  const end = firstAnswerColEnd.value;
  return h.slice(SKIP_COLS, end).map((label, idx) => ({
    i: idx + SKIP_COLS,
    label: label || `Колонка ${idx + SKIP_COLS + 1}`,
  }));
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
  // Сохраняем «baseline» — то что пришло из кэша
  savedScores.value = rowScores.value.map((r) => [...r]);
  savedQuestions.value = [...rowQuestions.value];
  savedComments.value = [...rowComments.value];
  // null = ещё не трогали; если из кэша уже есть баллы — считаем «ранее сохранено»
  savedOnce.value = rowScores.value.map((scores) =>
    scores.some((v) => v !== "") ? true : null,
  );
}

watch([dataRows, layout], initEditors, { deep: true });

async function load() {
  err.value = "";
  saveMsg.value = "";
  layoutErr.value = "";
  try {
    const me = await api.me().catch(() => null);
    if (me) currentUserLabel.value = (me as { master_label?: string | null }).master_label ?? null;
  } catch { /* ignore */ }
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
    await api.queueWriteBatch(updates);
    saveMsg.value = "Сохранено в очередь.";
    // Патчим локальный dataRows чтобы перезагрузка кэша не потеряла новые значения
    const row = dataRows.value[cardIndex];
    if (row) {
      layout.value?.score_column_indices.forEach((sc, k) => {
        row[sc.index] = rowScores.value[cardIndex]?.[k] ?? "";
      });
      const rq = layout.value?.reviewer_questions_column?.index;
      if (rq != null) row[rq] = rowQuestions.value[cardIndex] ?? "";
      const rc = layout.value?.reviewer_comment_column?.index;
      if (rc != null) row[rc] = rowComments.value[cardIndex] ?? "";
    }
    // Обновляем baseline — карточка считается сохранённой
    savedScores.value[cardIndex] = [...(rowScores.value[cardIndex] ?? [])];
    savedQuestions.value[cardIndex] = rowQuestions.value[cardIndex] ?? "";
    savedComments.value[cardIndex] = rowComments.value[cardIndex] ?? "";
    savedOnce.value[cardIndex] = true;
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
      <div v-if="currentUserLabel" class="reviewer-banner">
        Личный кабинет · <strong>{{ currentUserLabel }}</strong>
      </div>
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
          {{ cell(row, 2) }} {{ cell(row, 3) }}
          <span v-if="cell(row, 4)" class="muted">· {{ cell(row, 4) }}</span>
        </span>
        <div class="anketa-card__head-right">
          <span v-if="isDirty(cardIndex)" class="status-badge status-badge--dirty">● Не сохранено</span>
          <span v-else-if="savedOnce[cardIndex] === true" class="status-badge status-badge--saved">✓ Сохранено</span>
          <span v-else-if="hasAnyScore(cardIndex)" class="status-badge status-badge--saved">✓ Ответ в таблице</span>
          <span class="muted anketa-card__meta">Строка {{ (dataRowIndices[cardIndex] ?? 0) + 1 }}</span>
        </div>
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
                <select
                  v-model="rowScores[cardIndex][sk]"
                  class="score-field__select"
                  :data-score="rowScores[cardIndex][sk]"
                  @change="markDirty(cardIndex)"
                >
                  <option value="">—</option>
                  <option v-for="opt in sc.options" :key="opt" :value="opt">{{ opt }}</option>
                </select>
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
              <textarea v-model="rowQuestions[cardIndex]" rows="2" class="anketa-textarea" @input="markDirty(cardIndex)" />
            </label>
            <label v-if="layout?.reviewer_comment_column?.index != null" class="field">
              <span>Комментарий по анкете</span>
              <textarea v-model="rowComments[cardIndex]" rows="3" class="anketa-textarea" @input="markDirty(cardIndex)" />
            </label>
          </section>

          <footer class="anketa-card__foot">
            <button
              type="button"
              class="btn btn-primary"
              :class="{ 'btn--pulse': isDirty(cardIndex) }"
              :disabled="saving"
              @click="saveRow(cardIndex)"
            >
              {{ saving ? "…" : "Сохранить" }}
            </button>
            <span v-if="(savedOnce[cardIndex] === true || hasAnyScore(cardIndex)) && !isDirty(cardIndex)" class="foot-saved-hint">✓ Ответ загружен</span>
          </footer>
        </div>
      </div>
    </article>
  </div>
</template>

<style scoped>
/* ── Page layout ── */
.ankety-page { width: 100%; }

.page-head { margin-bottom: 1.25rem; }

.reviewer-banner {
  display: inline-block;
  margin-top: 0.4rem;
  font-size: 0.85rem;
  color: var(--c-purple-light);
  background: rgba(153, 102, 255, 0.12);
  border: 1px solid rgba(153, 102, 255, 0.25);
  border-radius: 20px;
  padding: 0.2rem 0.75rem;
}

.page-head__title {
  margin: 0;
  font-size: clamp(1.5rem, 2.5vw, 2rem);
  font-weight: 700;
  letter-spacing: -0.02em;
  background: var(--grad-accent);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.msg-compact { font-size: 0.85rem; margin: 0 0 0.5rem; }
.msg-muted   { color: rgba(243,242,242,0.45); }
.msg-error   { color: var(--c-pink); margin: 0 0 0.5rem; }

.empty-hint {
  padding: 1.25rem 1.5rem;
  margin-bottom: 1rem;
  color: rgba(243,242,242,0.45);
}

/* ── Card ── */
.anketa-card {
  margin-bottom: 1.5rem;
  padding: 1.25rem 1.5rem 1.25rem;
  border-color: var(--c-border);
  background: var(--c-bg-2);
  transition: border-color 0.2s;
}
.anketa-card:hover { border-color: var(--c-border-bright); }

.anketa-card__head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 1rem;
  padding-bottom: 0.9rem;
  border-bottom: 1px solid var(--c-border);
}

.anketa-card__title {
  font-weight: 700;
  font-size: clamp(1rem, 1.3vw, 1.15rem);
  color: var(--c-white);
}

.anketa-card__meta {
  font-size: 0.78rem;
  color: rgba(243,242,242,0.35);
  background: var(--c-bg-3);
  padding: 0.2rem 0.6rem;
  border-radius: 20px;
  border: 1px solid var(--c-border);
}

/* ── Two-column grid ── */
.anketa-card__grid {
  display: grid;
  gap: 1.25rem 2rem;
  grid-template-columns: 1fr;
  align-items: start;
}
@media (min-width: 1040px) {
  .anketa-card__grid {
    grid-template-columns: minmax(0, 1.2fr) minmax(300px, 1fr);
  }
}

/* ── Answers block (collapsible) ── */
.anketa-details {
  border: 1px solid var(--c-border);
  border-radius: 10px;
  padding: 0 1rem;
  background: var(--c-bg-3);
}
.anketa-details summary {
  cursor: pointer;
  font-weight: 600;
  font-size: 0.88rem;
  padding: 0.65rem 0;
  color: var(--c-lavender);
  letter-spacing: 0.02em;
  list-style: none;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.anketa-details summary::before {
  content: "▶";
  font-size: 0.6rem;
  transition: transform 0.2s;
  color: var(--c-purple-mid);
}
.anketa-details[open] summary::before { transform: rotate(90deg); }
.anketa-details[open] summary { padding-bottom: 0.5rem; border-bottom: 1px solid var(--c-border); margin-bottom: 0.75rem; }

.anketa-qa {
  max-height: min(52vh, 640px);
  overflow-y: auto;
  padding-bottom: 0.75rem;
  scrollbar-width: thin;
  scrollbar-color: var(--c-purple) transparent;
}
.anketa-qa__row {
  margin-bottom: 0.85rem;
  font-size: 0.875rem;
}
.anketa-qa__q {
  color: var(--c-lavender);
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.25rem;
}
.anketa-qa__a {
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--c-white);
  line-height: 1.5;
}

/* ── Scores block ── */
.anketa-scores h4 {
  margin: 0 0 0.75rem;
  font-size: 0.78rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: var(--c-lavender);
}

.anketa-scores__grid {
  display: flex;
  flex-wrap: nowrap;
  gap: 0.6rem;
  overflow-x: auto;
  padding-bottom: 0.25rem;
  scrollbar-width: thin;
  scrollbar-color: var(--c-purple) transparent;
}

.score-field {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  flex: 1 1 0;
  min-width: 90px;
}
.score-field__label {
  font-size: 0.7rem;
  color: rgba(243,242,242,0.45);
  line-height: 1.25;
  max-height: 2.5em;
  overflow: hidden;
}
.score-field__select {
  padding: 0.45rem 0.5rem;
  border-radius: 8px;
  border: 1px solid var(--c-border-bright);
  background: var(--c-bg);
  color: var(--c-white);
  font: inherit;
  font-size: 1rem;
  font-weight: 600;
  width: 100%;
  text-align: center;
  cursor: pointer;
  appearance: none;
  -webkit-appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'%3E%3Cpath d='M1 1l4 4 4-4' stroke='%23A486EC' stroke-width='1.5' fill='none' stroke-linecap='round'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 0.5rem center;
  padding-right: 1.5rem;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.score-field__select:focus {
  outline: none;
  border-color: var(--c-purple-mid);
  box-shadow: 0 0 0 3px rgba(164,134,236,0.2);
}
.score-field__select option {
  background: var(--c-bg-2);
  color: var(--c-white);
}
/* Цветовая индикация выбранного балла */
.score-field__select[data-score="0"] { border-color: rgba(255,135,171,0.5); color: var(--c-pink); }
.score-field__select[data-score="1"] { border-color: rgba(245,132,20,0.5); color: var(--c-orange); }
.score-field__select[data-score="2"] { border-color: rgba(177,170,255,0.5); color: var(--c-purple-light); }
.score-field__select[data-score="3"] { border-color: rgba(252,207,80,0.5); color: var(--c-yellow); }

.anketa-readonly {
  margin-top: 0.65rem;
  font-size: 0.82rem;
  color: rgba(243,242,242,0.45);
  padding: 0.4rem 0.75rem;
  background: var(--c-bg-3);
  border-radius: 8px;
  border: 1px solid var(--c-border);
}

/* ── Reviewer section ── */
.anketa-reviewer { margin-top: 0.75rem; }

.anketa-reviewer .field span {
  display: block;
  font-size: 0.78rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--c-lavender);
  margin-bottom: 0.3rem;
}
.anketa-textarea {
  width: 100%;
  padding: 0.6rem 0.8rem;
  border-radius: 10px;
  border: 1px solid var(--c-border-bright);
  background: var(--c-bg);
  color: var(--c-white);
  font: inherit;
  resize: vertical;
  line-height: 1.5;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.anketa-textarea:focus {
  outline: none;
  border-color: var(--c-purple-mid);
  box-shadow: 0 0 0 3px rgba(164,134,236,0.2);
}

/* ── Head right ── */
.anketa-card__head-right {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex-wrap: wrap;
}

.status-badge {
  font-size: 0.75rem;
  font-weight: 600;
  padding: 0.2rem 0.65rem;
  border-radius: 20px;
  letter-spacing: 0.02em;
  white-space: nowrap;
}
.status-badge--dirty {
  background: rgba(255, 135, 171, 0.15);
  border: 1px solid rgba(255, 135, 171, 0.4);
  color: var(--c-pink);
  animation: badge-pulse 1.8s ease-in-out infinite;
}
.status-badge--saved {
  background: rgba(124, 232, 162, 0.12);
  border: 1px solid rgba(124, 232, 162, 0.35);
  color: #7ee8a2;
}

@keyframes badge-pulse {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0.6; }
}

/* ── Footer ── */
.anketa-card__foot {
  margin-top: 1rem;
  padding-top: 0.9rem;
  border-top: 1px solid var(--c-border);
  display: flex;
  align-items: center;
  gap: 1rem;
}

.foot-saved-hint {
  font-size: 0.82rem;
  color: #7ee8a2;
  font-weight: 500;
}

/* Кнопка мигает, если есть несохранённые изменения */
.btn--pulse {
  animation: btn-glow 1.4s ease-in-out infinite;
}
@keyframes btn-glow {
  0%, 100% { box-shadow: 0 0 0 0 rgba(164, 134, 236, 0); }
  50%       { box-shadow: 0 0 0 6px rgba(164, 134, 236, 0.3); }
}
</style>
