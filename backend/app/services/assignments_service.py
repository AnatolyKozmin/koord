"""Назначения строк/колонок листов проверяющим (SQL)."""

from __future__ import annotations

from sqlalchemy import delete, select

from app.config import get_settings
from app.db.models import Assignment, User
from app.db.session import SessionLocal


def assignable_sheet_names() -> frozenset[str]:
    s = get_settings()
    return frozenset(
        {
            s.sheet_name_ankety,
            s.sheet_name_domashki,
            s.sheet_name_enquiries,
            s.sheet_name_interviews,
        },
    )


def _axis_for_sheet(sheet_name: str) -> str:
    s = get_settings()
    return "column" if sheet_name == s.sheet_name_interviews else "row"


def get_assignment(email: str) -> dict[str, list[int]]:
    em = email.lower()
    with SessionLocal() as session:
        uid = session.scalar(select(User.id).where(User.email == em))
        if uid is None:
            return {}
        rows = session.execute(
            select(Assignment.sheet_name, Assignment.item_index, Assignment.axis).where(Assignment.user_id == uid),
        ).all()
        out: dict[str, list[int]] = {}
        for sheet_name, item_index, _axis in rows:
            out.setdefault(sheet_name, []).append(int(item_index))
        for k in out:
            out[k] = sorted(set(out[k]))
        return out


def set_assignment(email: str, mapping: dict[str, list[int]]) -> None:
    em = email.lower()
    with SessionLocal() as session:
        uid = session.scalar(select(User.id).where(User.email == em))
        if uid is None:
            return
        session.execute(delete(Assignment).where(Assignment.user_id == uid))
        for sheet_name, indices in mapping.items():
            axis = _axis_for_sheet(sheet_name)
            for x in sorted(set(int(i) for i in indices)):
                session.add(
                    Assignment(user_id=uid, sheet_name=sheet_name, item_index=x, axis=axis),
                )
        session.commit()


def merge_sheet_rows(email: str, sheet_name: str, row_indices: list[int]) -> None:
    cur = get_assignment(email)
    cur[sheet_name] = sorted(set(int(x) for x in row_indices))
    set_assignment(email, cur)


def list_all_assignments() -> dict[str, dict[str, list[int]]]:
    with SessionLocal() as session:
        rows = session.execute(
            select(User.email, Assignment.sheet_name, Assignment.item_index, Assignment.axis).join(
                Assignment,
                Assignment.user_id == User.id,
            ),
        ).all()
        out: dict[str, dict[str, list[int]]] = {}
        for email, sheet_name, item_index, _axis in rows:
            out.setdefault(email.lower(), {}).setdefault(sheet_name, []).append(int(item_index))
        for em in out:
            for sh in out[em]:
                out[em][sh] = sorted(set(out[em][sh]))
        return out


def assign_row_to_user(sheet_name: str, row_index: int, email: str | None) -> None:
    """
    Назначает конкретную строку/колонку конкретному пользователю.
    Если email=None — снимает назначение со всех.
    Перед назначением убирает эту строку у всех прочих пользователей.
    """
    axis = _axis_for_sheet(sheet_name)
    with SessionLocal() as session:
        session.execute(
            delete(Assignment).where(
                Assignment.sheet_name == sheet_name,
                Assignment.item_index == row_index,
                Assignment.axis == axis,
            ),
        )
        if email:
            em = email.lower()
            uid = session.scalar(select(User.id).where(User.email == em))
            if uid is not None:
                session.add(
                    Assignment(user_id=uid, sheet_name=sheet_name, item_index=row_index, axis=axis),
                )
        session.commit()


def row_to_reviewer_map(sheet_name: str) -> dict[int, str]:
    """Возвращает {row_index: email} по всем назначениям листа."""
    with SessionLocal() as session:
        rows = session.execute(
            select(User.email, Assignment.item_index).join(Assignment, Assignment.user_id == User.id).where(
                Assignment.sheet_name == sheet_name,
            ),
        ).all()
    return {int(item_index): email for email, item_index in rows}


def _build_student_id_to_faculty_map() -> dict[str, str]:
    """Читает лист «Анкеты» из кэша, возвращает {student_id → faculty}.

    student_id нормализуется (strip + lower) для устойчивого сравнения.
    """
    from app.constants.ankety import find_col
    from app.constants.faculties import canonical_reviewer_faculty
    from app.services import sheets_service

    settings = get_settings()
    rows = sheets_service.read_sheet_cached(settings.sheet_name_ankety)
    if not rows:
        return {}

    header = rows[0]
    sid_col = find_col(header, "Номер студенческого билета в формате 12345") or find_col(header, "Номер студенческого билета")
    fac_col = find_col(header, "Укажи свой факультет")
    if sid_col is None or fac_col is None:
        return {}

    result: dict[str, str] = {}
    for row in rows[1:]:
        sid_raw = row[sid_col] if sid_col < len(row) else ""
        fac_raw = row[fac_col] if fac_col < len(row) else ""
        sid = str(sid_raw).strip().lower() if sid_raw else ""
        fac = canonical_reviewer_faculty(fac_raw)
        if sid and fac:
            result[sid] = fac
    return result


def add_sheet_rows(email: str, sheet_name: str, new_row_indices: list[int]) -> None:
    """Добавляет строки к существующим назначениям (не заменяет)."""
    cur = get_assignment(email)
    existing = set(cur.get(sheet_name, []))
    existing.update(int(x) for x in new_row_indices)
    cur[sheet_name] = sorted(existing)
    set_assignment(email, cur)


def distribute_domashki_balanced_by_faculty(
    sheet_name: str,
    user_emails: list[str],
) -> dict[str, object]:
    """Инкрементально раздаёт строки Домашек по whitelist-логике факультетов.

    Факультет кандидата ищется по студенческому билету в кэше листа «Анкеты».
    Уже назначенные строки не трогаются — добавляются только новые.
    Строка попадает к проверяющему только если её факультет есть в его reviewer_faculties.

    Возвращает {"newly_assigned": {email: [row_indices]}, "unassigned": [row_indices],
                "already_assigned": int}.
    """
    from random import Random

    from app.constants.domashki import DOMASHKI_STUDENT_ID_HEADER, data_start_index, find_col, find_header_row
    from app.constants.faculties import canonical_reviewer_faculty
    from app.db.models import UserReviewerFaculty
    from app.services import sheets_service

    settings = get_settings()
    if sheet_name != settings.sheet_name_domashki:
        raise ValueError("Балансировка по факультетам доступна только для листа «Домашки»")

    rows = sheets_service.read_sheet_cached(sheet_name)
    if not rows:
        raise ValueError("Нет данных в кэше — выполните синхронизацию таблицы")
    if not user_emails:
        raise ValueError("Список проверяющих пуст")

    header = find_header_row(rows)
    if not header:
        raise ValueError("Не найдена строка заголовков в листе «Домашки»")

    # Ищем студ. билет динамически (с fallback на короткое имя)
    sid_col = find_col(header, DOMASHKI_STUDENT_ID_HEADER)
    if sid_col is None:
        raise ValueError(f"В листе не найдена колонка «{DOMASHKI_STUDENT_ID_HEADER}»")

    start = data_start_index(rows)

    # Уже назначенные строки по всем пользователям — не трогаем
    existing_assignments = row_to_reviewer_map(sheet_name)
    already_assigned_count = len(existing_assignments)

    # Только незанятые строки данных
    unprocessed_indices = [i for i in range(start, len(rows)) if i not in existing_assignments]

    # Whitelist: разрешённые факультеты для каждого проверяющего
    norm_emails = [e.lower() for e in user_emails]
    with SessionLocal() as session:
        id_email = dict(session.execute(select(User.id, User.email).where(User.email.in_(norm_emails))).all())
    ids = list(id_email.keys())
    allowed_by_email: dict[str, set[str]] = {em: set() for em in norm_emails}
    if ids:
        with SessionLocal() as session:
            pairs = session.execute(
                select(UserReviewerFaculty.user_id, UserReviewerFaculty.faculty).where(
                    UserReviewerFaculty.user_id.in_(ids),
                ),
            ).all()
        for uid, fac in pairs:
            em = id_email.get(uid)
            if em is not None:
                allowed_by_email[em].add(fac)

    # Карта студ. билет → факультет из анкет
    sid_to_faculty = _build_student_id_to_faculty_map()

    # Текущая нагрузка (считаем существующие назначения, чтобы балансировка была честной)
    load: dict[str, int] = {em: len(get_assignment(em).get(sheet_name, [])) for em in norm_emails}

    rng = Random()
    rng.shuffle(unprocessed_indices)

    newly_assigned: dict[str, list[int]] = {em: [] for em in norm_emails}
    unassigned: list[int] = []

    for idx in unprocessed_indices:
        row = rows[idx]
        sid_raw = row[sid_col] if sid_col < len(row) else ""
        sid = str(sid_raw).strip().lower() if sid_raw else ""
        cand_fac = sid_to_faculty.get(sid) if sid else None

        if cand_fac is None:
            unassigned.append(idx)
            continue

        eligible = [em for em in norm_emails if cand_fac in allowed_by_email.get(em, set())]
        if not eligible:
            unassigned.append(idx)
            continue

        min_load = min(load[e] for e in eligible)
        pool = [e for e in eligible if load[e] == min_load]
        chosen = rng.choice(pool)
        newly_assigned[chosen].append(idx)
        load[chosen] += 1

    # Сохраняем инкрементально (добавляем к существующим)
    for em in norm_emails:
        if newly_assigned[em]:
            add_sheet_rows(em, sheet_name, sorted(newly_assigned[em]))

    return {
        "newly_assigned": {em: sorted(idxs) for em, idxs in newly_assigned.items()},
        "unassigned": sorted(unassigned),
        "already_assigned": already_assigned_count,
    }


def distribute_sheet_custom(
    sheet_name: str,
    user_counts: dict[str, int],
    *,
    by_columns: bool = False,
) -> dict[str, list[int]]:
    """Раздаёт строки/колонки листа каждому пользователю в указанном количестве.
    user_counts: {email: count}. Строки выбираются последовательно из пула, не пересекаясь.
    """
    from app.services import sheets_service
    from app.services.interviews_layout import sheet_max_column_index

    if sheet_name not in assignable_sheet_names():
        raise ValueError(f"Лист не участвует в назначениях: {sheet_name}")

    rows = sheets_service.read_sheet_cached(sheet_name)
    if not rows:
        raise ValueError("Нет данных в кэше — выполните синхронизацию таблицы")

    settings = get_settings()
    if by_columns:
        if sheet_name != settings.sheet_name_interviews:
            raise ValueError("Режим by_columns допустим только для листа «Собеседования»")
        fc = settings.sheet_interviews_first_candidate_col_index
        max_w = sheet_max_column_index(rows)
        data_indices = list(range(fc, max_w)) if max_w > fc else []
    else:
        start = 1 if len(rows) > 0 else 0
        data_indices = list(range(start, len(rows)))

    if not user_counts:
        raise ValueError("Список пользователей пуст")

    pool = list(data_indices)
    result: dict[str, list[int]] = {}
    for em_raw, count in user_counts.items():
        em = em_raw.lower()
        taken = pool[:count]
        pool = pool[count:]
        result[em] = taken

    for em, indices in result.items():
        merge_sheet_rows(em, sheet_name, indices)
    return result


def distribute_anketa_balanced_by_faculty(
    sheet_name: str,
    user_emails: list[str],
) -> dict[str, object]:
    """Распределяет строки листа «Анкеты» поровну между выбранными проверяющими.

    У каждого проверяющего в профиле задан список разрешённых факультетов кандидатов
    (reviewer_faculties); строка попадает только к тем, у кого в этом списке есть факультет
    из ячейки «Укажи свой факультет».

    Если список пуст — координатор не участвует в автораспределении.
    Пустая или нераспознанная ячейка факультета — строка в unassigned.

    Перед назначением снимаются все текущие назначения строк этого листа (у всех пользователей).
    Возвращает {"assigned": {email: [row_indices]}, "unassigned": [row_indices]}.
    """
    from random import Random

    from app.constants.ankety import find_col
    from app.constants.faculties import canonical_reviewer_faculty
    from app.db.models import UserReviewerFaculty
    from app.services import sheets_service

    settings = get_settings()
    if sheet_name != settings.sheet_name_ankety:
        raise ValueError("Балансировка по факультетам доступна только для листа «Анкеты»")

    rows = sheets_service.read_sheet_cached(sheet_name)
    if not rows:
        raise ValueError("Нет данных в кэше — выполните синхронизацию таблицы")
    if not user_emails:
        raise ValueError("Список проверяющих пуст")

    header = rows[0] if rows else []
    fac_col = find_col(header, "Укажи свой факультет")
    if fac_col is None:
        raise ValueError("В листе не найдена колонка «Укажи свой факультет»")

    axis = _axis_for_sheet(sheet_name)
    with SessionLocal() as session:
        session.execute(delete(Assignment).where(Assignment.sheet_name == sheet_name, Assignment.axis == axis))
        session.commit()

    norm_emails = [e.lower() for e in user_emails]
    with SessionLocal() as session:
        id_email = dict(session.execute(select(User.id, User.email).where(User.email.in_(norm_emails))).all())
    ids = list(id_email.keys())
    allowed_by_email: dict[str, set[str]] = {em: set() for em in norm_emails}
    if ids:
        with SessionLocal() as session:
            pairs = session.execute(
                select(UserReviewerFaculty.user_id, UserReviewerFaculty.faculty).where(
                    UserReviewerFaculty.user_id.in_(ids),
                ),
            ).all()
        for uid, fac in pairs:
            em = id_email.get(uid)
            if em is not None:
                allowed_by_email[em].add(fac)

    rng = Random()
    data_indices = list(range(1, len(rows)))
    rng.shuffle(data_indices)

    load = {em: 0 for em in norm_emails}
    assigned: dict[str, list[int]] = {em: [] for em in norm_emails}
    unassigned: list[int] = []

    for idx in data_indices:
        row = rows[idx]
        cand_raw = row[fac_col] if fac_col < len(row) else ""
        cand_fac = canonical_reviewer_faculty(cand_raw)

        if cand_fac is None:
            unassigned.append(idx)
            continue

        eligible: list[str] = []
        for em in norm_emails:
            if cand_fac in allowed_by_email.get(em, set()):
                eligible.append(em)

        if not eligible:
            unassigned.append(idx)
            continue

        min_load = min(load[e] for e in eligible)
        pool = [e for e in eligible if load[e] == min_load]
        chosen = rng.choice(pool)
        assigned[chosen].append(idx)
        load[chosen] += 1

    for em in norm_emails:
        merge_sheet_rows(em, sheet_name, sorted(assigned[em]))

    return {
        "assigned": {em: sorted(idxs) for em, idxs in assigned.items()},
        "unassigned": sorted(unassigned),
    }


def distribute_sheet(
    sheet_name: str,
    per_user: int,
    user_emails: list[str],
    *,
    skip_header_row: bool = True,
    by_columns: bool = False,
) -> dict[str, list[int]]:
    from app.services import sheets_service
    from app.services.interviews_layout import sheet_max_column_index

    if sheet_name not in assignable_sheet_names():
        raise ValueError(f"Лист не участвует в назначениях: {sheet_name}")

    rows = sheets_service.read_sheet_cached(sheet_name)
    if not rows:
        raise ValueError("Нет данных в кэше — выполните синхронизацию таблицы")

    settings = get_settings()
    if by_columns:
        if sheet_name != settings.sheet_name_interviews:
            raise ValueError("Режим by_columns допустим только для листа «Собеседования»")
        fc = settings.sheet_interviews_first_candidate_col_index
        max_w = sheet_max_column_index(rows)
        data_indices = list(range(fc, max_w)) if max_w > fc else []
    else:
        start = 1 if skip_header_row and len(rows) > 0 else 0
        data_indices = list(range(start, len(rows)))

    if not user_emails:
        raise ValueError("Список пользователей пуст")

    chunks: list[list[int]] = []
    for i in range(0, len(data_indices), per_user):
        chunks.append(data_indices[i : i + per_user])

    result: dict[str, list[int]] = {e.lower(): [] for e in user_emails}
    emails_norm = [e.lower() for e in user_emails]
    for i, chunk in enumerate(chunks):
        who = emails_norm[i % len(emails_norm)]
        result[who].extend(chunk)

    for em in emails_norm:
        merge_sheet_rows(em, sheet_name, result.get(em, []))
    return result
