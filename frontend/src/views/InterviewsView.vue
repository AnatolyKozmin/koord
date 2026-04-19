<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { api } from "../api/client";
import { colIndexToLetters } from "../utils/sheetsA1";

type ExternalSheet = {
  matched: boolean;
  sheet?: string;
  reason?: string;
  row_index?: number;
  reviewer_questions?: string;
  reviewer_comment?: string;
};

type Candidate = {
  column_index: number;
  parse_ok: boolean;
  error?: string;
  meta: { row: number; label: string; value: string }[];
  questions: {
    row: number;
    key_characteristic: string;
    extra_characteristic: string;
    question: string;
    answer: string;
  }[];
  scores: { row: number; label: string; value: string }[];
  external?: {
    candidate_email: string | null;
    ankety: ExternalSheet;
    domashki: ExternalSheet;
  };
};

const sheetTitle = ref("");
const firstCol = ref(3);
const candidates = ref<Candidate[]>([]);
const err = ref("");
const saveMsg = ref("");
const savingCol = ref<number | null>(null);

const drafts = reactive<Record<number, Record<number, string>>>({});

function initDrafts(list: Candidate[]) {
  for (const k of Object.keys(drafts)) delete drafts[Number(k)];
  for (const c of list) {
    const d: Record<number, string> = {};
    for (const m of c.meta) d[m.row] = m.value;
    for (const q of c.questions) d[q.row] = q.answer;
    for (const s of c.scores) d[s.row] = s.value;
    drafts[c.column_index] = d;
  }
}

/** Короткий заголовок карточки: ФИО / почта из меты или колонка */
function cardSubtitle(c: Candidate): string {
  const bits: string[] = [];
  for (const m of c.meta) {
    const L = m.label.toLowerCase();
    const v = (m.value || "").trim();
    if (!v) continue;
    if (
      L.includes("фио") ||
      L.includes("gmail") ||
      L.includes("почт") ||
      L.includes("vk") ||
      L.includes("@")
    ) {
      bits.push(v);
    }
  }
  const s = bits.filter(Boolean).join(" · ");
  return s || `Колонка ${colIndexToLetters(c.column_index)}`;
}

function isItogoRow(label: string): boolean {
  return label.replace(/\s+/g, " ").trim().toLowerCase().startsWith("итого");
}

function isCommentMoRow(label: string): boolean {
  const t = label.toLowerCase();
  return t.includes("комментарий");
}

function initDraftsIfMissing(col: number) {
  if (!drafts[col]) drafts[col] = {};
  return drafts[col];
}

const extReasonText: Record<string, string> = {
  no_email_in_meta:
    "В ячейке меты нет почты кандидата — укажите gmail в столбце кандидата на листе «Собес», чтобы подтянуть строки анкеты и ИДЗ.",
  no_cache: "Лист не в кэше — выполните синхронизацию с Google.",
  row_not_found: "Строка с таким email не найдена на листе.",
  no_email_column: "В шапке листа не найдена колонка с почтой.",
};

function externalHint(x: ExternalSheet): string {
  if (x.matched) return "";
  return extReasonText[x.reason || ""] || x.reason || "Нет данных.";
}

async function load() {
  err.value = "";
  saveMsg.value = "";
  try {
    const names = await api.sheetTabNames();
    sheetTitle.value = names.interviews;
    const data = await api.interviewsPayload();
    firstCol.value = data.first_candidate_col_index;
    candidates.value = data.candidates as Candidate[];
    initDrafts(candidates.value);
  } catch (e) {
    err.value = e instanceof Error ? e.message : "Ошибка загрузки";
  }
}

function collectCells(col: number, c: Candidate): { row: number; value: string }[] {
  const d = drafts[col];
  if (!d) return [];
  const rows = new Set<number>();
  for (const m of c.meta) rows.add(m.row);
  for (const q of c.questions) rows.add(q.row);
  for (const s of c.scores) rows.add(s.row);
  return [...rows]
    .sort((a, b) => a - b)
    .map((row) => ({ row, value: d[row] ?? "" }));
}

async function saveColumn(c: Candidate) {
  if (!c.parse_ok) return;
  savingCol.value = c.column_index;
  saveMsg.value = "";
  try {
    const cells = collectCells(c.column_index, c);
    await api.interviewsSave({ column_index: c.column_index, cells });
    saveMsg.value = "Сохранено в очередь. Через несколько секунд обновите страницу.";
  } catch (e) {
    saveMsg.value = e instanceof Error ? e.message : "Ошибка сохранения";
  } finally {
    savingCol.value = null;
  }
}

const firstColLetter = computed(() => colIndexToLetters(firstCol.value));

onMounted(load);
</script>

<template>
  <div class="interviews-page">
    <header class="page-head">
      <h1 class="page-head__title">Собеседования</h1>
    </header>

    <p class="msg-muted msg-compact">
      Лист «{{ sheetTitle }}». Шаблон вопросов в колонках A–C; ответы и оценки по кандидату — в колонке
      <strong>{{ firstColLetter }}</strong> (и далее). Видны только назначенные вам столбцы.
    </p>
    <p v-if="err" class="msg-error">{{ err }}</p>
    <p v-if="saveMsg" class="msg-muted msg-compact">{{ saveMsg }}</p>

    <div v-if="!candidates.length && !err" class="card muted empty-hint">
      Нет назначенных колонок кандидатов. Супер-админ: синхронизируйте таблицу и в «Назначениях» раздайте лист
      «{{ sheetTitle }}» по колонкам. При необходимости проверьте в .env:
      <code class="code-inline">SHEET_NAME_INTERVIEWS</code> и
      <code class="code-inline">SHEET_INTERVIEWS_FIRST_CANDIDATE_COL_INDEX</code>.
    </div>

    <article
      v-for="c in candidates"
      :key="c.column_index"
      class="interview-card card"
    >
      <div class="interview-card__head">
        <div>
          <span class="interview-card__title">{{ cardSubtitle(c) }}</span>
          <span class="muted interview-card__meta"
            >Столбец {{ colIndexToLetters(c.column_index) }} · индекс {{ c.column_index }}</span
          >
        </div>
        <span v-if="!c.parse_ok" class="msg-error interview-card__err">{{ c.error }}</span>
      </div>

      <div v-if="c.parse_ok" class="interview-card__grid">
        <div class="interview-card__col interview-card__col--rubric">
          <section v-if="c.external" class="interview-external">
            <h4 class="interview-external__title">Анкета и ИДЗ — что написали проверяющие</h4>
            <p class="msg-muted interview-external__lead">
              Берётся из листов «Анкеты» и «Домашка» по <strong>той же почте</strong>, что в мете собеседования (строка
              Gmail). Так удобнее задавать вопросы по блокам «Вопрос по анкете» / «Вопрос по ИДЗ».
            </p>
            <p v-if="c.external.candidate_email" class="interview-external__email muted">
              Связка по email: <code>{{ c.external.candidate_email }}</code>
            </p>
            <p v-else class="msg-error interview-external__warn">{{ externalHint(c.external.ankety) }}</p>

            <div class="external-grid">
              <div class="external-block">
                <div class="external-block__head">Анкеты</div>
                <template v-if="c.external.ankety.matched">
                  <label class="external-label">Вопросы по анкете</label>
                  <div class="external-readonly">{{ c.external.ankety.reviewer_questions || "—" }}</div>
                  <label class="external-label">Комментарий по анкете</label>
                  <div class="external-readonly">{{ c.external.ankety.reviewer_comment || "—" }}</div>
                </template>
                <p v-else class="muted external-fail">{{ externalHint(c.external.ankety) }}</p>
              </div>
              <div class="external-block">
                <div class="external-block__head">Домашка (ИДЗ)</div>
                <template v-if="c.external.domashki.matched">
                  <label class="external-label">Вопросы по ИДЗ</label>
                  <div class="external-readonly">{{ c.external.domashki.reviewer_questions || "—" }}</div>
                  <label class="external-label">Комментарий по ИДЗ</label>
                  <div class="external-readonly">{{ c.external.domashki.reviewer_comment || "—" }}</div>
                </template>
                <p v-else class="muted external-fail">{{ externalHint(c.external.domashki) }}</p>
              </div>
            </div>
          </section>

          <details class="interview-details" open>
            <summary>Мета и сценарий</summary>
            <section v-if="c.meta.length" class="interview-meta">
              <h4>Данные кандидата</h4>
              <div v-for="m in c.meta" :key="'m' + m.row" class="interview-field">
                <div class="interview-field__label">{{ m.label }}</div>
                <textarea
                  v-model="initDraftsIfMissing(c.column_index)[m.row]"
                  rows="2"
                  class="interview-textarea"
                />
              </div>
            </section>
            <section class="interview-questions">
              <h4>Вопросы</h4>
              <div class="interview-qa">
                <div v-for="q in c.questions" :key="'q' + q.row" class="interview-qa__block">
                  <div class="interview-qa__q">
                    <span v-if="q.key_characteristic" class="interview-qa__tag">{{ q.key_characteristic }}</span>
                    <span v-if="q.extra_characteristic" class="interview-qa__sub muted">{{
                      q.extra_characteristic
                    }}</span>
                    <div class="interview-qa__text">{{ q.question }}</div>
                  </div>
                  <label class="interview-qa__a-label muted">Заметки / ячейка в таблице</label>
                  <textarea
                    v-model="initDraftsIfMissing(c.column_index)[q.row]"
                    rows="3"
                    class="interview-textarea"
                  />
                </div>
              </div>
            </section>
          </details>
        </div>

        <div class="interview-card__col interview-card__col--scores">
          <section class="interview-scores">
            <h4>Оценка кандидата</h4>
            <div class="interview-scores__grid">
              <template v-for="s in c.scores" :key="'s' + s.row">
                <label
                  v-if="!isItogoRow(s.label)"
                  class="score-field"
                  :class="{ 'score-field--wide': isCommentMoRow(s.label) }"
                >
                  <span class="score-field__label">{{ s.label.replace(/\n/g, " ").trim() }}</span>
                  <textarea
                    v-if="isCommentMoRow(s.label)"
                    v-model="initDraftsIfMissing(c.column_index)[s.row]"
                    rows="4"
                    class="interview-textarea score-field__textarea"
                  />
                  <input
                    v-else
                    v-model="initDraftsIfMissing(c.column_index)[s.row]"
                    type="text"
                    inputmode="decimal"
                    class="score-field__input"
                  />
                </label>
                <div v-else class="score-readonly muted">
                  <span class="score-field__label">{{ s.label.replace(/\n/g, " ").trim() }}</span>
                  <span class="score-readonly__val">{{ initDraftsIfMissing(c.column_index)[s.row] || "—" }}</span>
                </div>
              </template>
            </div>
          </section>
          <footer class="interview-card__foot">
            <button
              type="button"
              class="btn btn-primary"
              :disabled="savingCol !== null"
              @click="saveColumn(c)"
            >
              {{ savingCol === c.column_index ? "…" : "Сохранить" }}
            </button>
          </footer>
        </div>
      </div>
    </article>
  </div>
</template>

<style scoped>
.interviews-page {
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
.code-inline {
  font-size: 0.8rem;
  background: #121620;
  padding: 0.1rem 0.35rem;
  border-radius: 4px;
}
.empty-hint {
  padding: 1rem 1.25rem;
  margin-bottom: 1rem;
  line-height: 1.5;
}
.interview-external {
  margin-bottom: 1.25rem;
  padding: 0.85rem 1rem;
  border: 1px solid var(--accent-dim);
  border-radius: 8px;
  background: rgba(108, 156, 255, 0.06);
}
.interview-external__title {
  margin: 0 0 0.5rem;
  font-size: 0.95rem;
  font-weight: 600;
}
.interview-external__lead {
  font-size: 0.82rem;
  margin: 0 0 0.65rem;
  line-height: 1.45;
}
.interview-external__email {
  font-size: 0.8rem;
  margin: 0 0 0.75rem;
}
.interview-external__email code {
  font-size: 0.85rem;
  color: var(--text);
}
.interview-external__warn {
  font-size: 0.82rem;
  margin: 0 0 0.75rem;
}
.external-grid {
  display: grid;
  gap: 1rem;
  grid-template-columns: 1fr;
}
@media (min-width: 720px) {
  .external-grid {
    grid-template-columns: 1fr 1fr;
  }
}
.external-block {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 0.65rem 0.75rem;
  background: #121620;
}
.external-block__head {
  font-size: 0.78rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--muted);
  margin-bottom: 0.5rem;
}
.external-label {
  display: block;
  font-size: 0.72rem;
  color: var(--muted);
  margin: 0.35rem 0 0.15rem;
}
.external-readonly {
  font-size: 0.88rem;
  white-space: pre-wrap;
  word-break: break-word;
  padding: 0.45rem 0.5rem;
  border-radius: 6px;
  background: #0f1219;
  border: 1px solid var(--border);
  min-height: 2.5rem;
}
.external-fail {
  font-size: 0.82rem;
  margin: 0;
}
.interview-card {
  margin-bottom: 1.25rem;
  padding: 1rem 1.35rem 1.25rem;
}
.interview-card__head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 1rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid var(--border);
}
.interview-card__title {
  font-weight: 600;
  font-size: clamp(1rem, 1.2vw, 1.15rem);
  display: block;
}
.interview-card__meta {
  font-size: 0.8rem;
  display: block;
  margin-top: 0.2rem;
}
.interview-card__err {
  font-size: 0.9rem;
  max-width: min(100%, 420px);
}
.interview-card__grid {
  display: grid;
  gap: 1.25rem 1.75rem;
  grid-template-columns: 1fr;
  align-items: start;
}
@media (min-width: 1040px) {
  .interview-card__grid {
    grid-template-columns: minmax(0, 1.15fr) minmax(320px, 1fr);
  }
}
.interview-details {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 0.4rem 0.85rem;
  background: #121620;
}
.interview-details summary {
  cursor: pointer;
  font-weight: 500;
  padding: 0.35rem 0;
}
.interview-details[open] summary {
  margin-bottom: 0.5rem;
}
.interview-meta h4,
.interview-questions h4,
.interview-scores h4 {
  margin: 0.5rem 0;
  font-size: 0.9rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--muted);
}
.interview-meta {
  margin-bottom: 1rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid var(--border);
}
.interview-field__label {
  font-size: 0.78rem;
  color: var(--muted);
  margin-bottom: 0.2rem;
}
.interview-field {
  display: block;
  margin-bottom: 0.65rem;
}
.interview-textarea {
  width: 100%;
  padding: 0.5rem;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: #0f1219;
  color: var(--text);
  font: inherit;
  resize: vertical;
}
.interview-qa {
  max-height: min(52vh, 640px);
  overflow-y: auto;
  padding-right: 0.35rem;
}
.interview-qa__block {
  margin-bottom: 1rem;
  font-size: 0.9rem;
}
.interview-qa__tag {
  font-size: 0.72rem;
  color: var(--muted);
  display: block;
  margin-bottom: 0.15rem;
}
.interview-qa__sub {
  font-size: 0.78rem;
  display: block;
  margin-bottom: 0.25rem;
}
.interview-qa__text {
  white-space: pre-wrap;
  word-break: break-word;
  margin-bottom: 0.35rem;
  line-height: 1.45;
}
.interview-qa__a-label {
  font-size: 0.75rem;
  display: block;
  margin-bottom: 0.2rem;
}
.interview-scores h4 {
  margin-top: 0;
}
.interview-scores__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(108px, 1fr));
  gap: 0.65rem 0.85rem;
}
@media (min-width: 1400px) {
  .interview-scores__grid {
    grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
  }
}
.score-field--wide {
  grid-column: 1 / -1;
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
  max-height: 3.6em;
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
.score-field__textarea {
  min-height: 5rem;
}
.score-readonly {
  grid-column: 1 / -1;
  padding: 0.35rem 0;
  font-size: 0.85rem;
}
.score-readonly__val {
  display: block;
  margin-top: 0.2rem;
  color: var(--text);
}
.interview-card__foot {
  margin-top: 0.75rem;
  padding-top: 0.75rem;
  border-top: 1px solid var(--border);
}
</style>
