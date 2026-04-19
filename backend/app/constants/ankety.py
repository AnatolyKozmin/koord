"""
Структура листа «Анкеты» в Google Sheets.

Колонки слева направо (как в вашей таблице): анкетные поля респондента,
затем блок оценок проверяющим, сумма/уровень, затем поля ввода проверяющим.
Индексы колонок считаются от 0 для строки заголовков (первая колонка A = 0).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Имя листа в таблице Google
SHEET_NAME = "Анкеты"

# Баллы выставляются проверяющим по этим столбцам (подряд в шапке таблицы).
ANKETY_SCORE_HEADERS: tuple[str, ...] = (
    "Заинтересованность\n(Сквозная)",
    "Работа в команде",
    "Соблюдение ДД ",
    "Девиантность\n(Маркер)",
    "Опыт похожей деятельности \n(Маркер)",
    "Мотивация (маркер)",
    "Использование ГПТ (Маркер)",
    "Характеристика Х",
)

# Следующий столбец после баллов — сумма (часто формула SUM в Sheets).
HEADER_SUM = "Общая оценка по анкете "

HEADER_LEVEL = "Уровень по итогам анкеты"

# Пишет проверяющий
HEADER_REVIEWER_QUESTIONS = "Вопросы по анкете (если вопросов нет, так и пишите)"

HEADER_REVIEWER_COMMENT = "Комментарий по анкете"

# Полный перечень заголовков первой строки (для документации и сверки с экспортом).
ANKETY_HEADER_ROW_DOC: tuple[str, ...] = (
    "Фамилия",
    "Имя",
    "Отчество",
    "Курс обучения",
    "Учебная группа",
    "Форма обучения",
    "Ссылка на ВК (например: vk.com/ivanivanov)",
    "Почта gmail-",
    "Ник в Tg",
    "Назови свои 3 сильные и 3 слабые стороны. Как они влияют на твою работу?",
    (
        "Есть ли у тебя дополнительная занятость помимо учёбы (работа и т.д.)? \n"
        "Какие у тебя планы на этот учебный год?"
    ),
    "Опиши свой опыт командной работы. Ты можешь привести пример в рамках школьных активностей или учебы, где ты работал(-а) в команде или в паре с кем-либо.",
    "Если есть, опиши свой опыт участия в организации мероприятий и членства в школьных или молодёжных организациях самоуправления.",
    "Расскажи о своих особенных навыках (например, навыках работы в графических и видеоредакторах, написания ботов, работы в продуктах Microsoft, Google) или любых других, которыми хочешь поделиться.",
    "Почему ты решил(-а) заполнить эту анкету?",
    "Что бы ты хотел(-а) получить от нахождения в Студенческом совете?",
    "Как ты узнал(-а) об отборе в Студенческий совет? (Варианты ответов: Через группу первокурсников; Через координатора; Через старосту / одногруппников; Через официальные источники вуза; Через рассылку деканата на почту; Через выступления на парах ССт; Через друзей / родных, которые уже были или есть в ССт; Через печатную продукцию в корпусе)",
    *ANKETY_SCORE_HEADERS,
    HEADER_SUM,
    HEADER_LEVEL,
    HEADER_REVIEWER_QUESTIONS,
    HEADER_REVIEWER_COMMENT,
)


def _norm(s: str) -> str:
    return " ".join(s.replace("\r", "").split()).strip().lower()


def find_col(header_row: list[Any], title: str) -> int | None:
    """Найти индекс колонки по заголовку (устойчиво к лишним пробелам и переносам строк)."""
    want = _norm(title)
    for i, cell in enumerate(header_row):
        if cell is None:
            continue
        if _norm(str(cell)) == want:
            return i
    return None


@dataclass(frozen=True)
class AnketyColumnMap:
    """Индексы колонок по фактической строке заголовков листа «Анкеты»."""

    score_cols: tuple[int, ...]
    sum_col: int | None
    level_col: int | None
    reviewer_questions_col: int | None
    reviewer_comment_col: int | None


def map_headers(header_row: list[Any]) -> AnketyColumnMap:
    """
    Сопоставить ожидаемые заголовки с реальной первой строкой листа.
    Если названия в таблице слегка отличаются — часть полей может остаться None.
    """
    scores: list[int] = []
    for h in ANKETY_SCORE_HEADERS:
        idx = find_col(header_row, h)
        if idx is not None:
            scores.append(idx)
    return AnketyColumnMap(
        score_cols=tuple(scores),
        sum_col=find_col(header_row, HEADER_SUM),
        level_col=find_col(header_row, HEADER_LEVEL),
        reviewer_questions_col=find_col(header_row, HEADER_REVIEWER_QUESTIONS),
        reviewer_comment_col=find_col(header_row, HEADER_REVIEWER_COMMENT),
    )
