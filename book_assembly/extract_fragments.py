#!/usr/bin/env python3
"""
Извлекает фрагменты художественного текста из экспорта Google AI Studio (JSON «Книга»).
Правило ТЗ: не генерировать текст — только искать якоря в логе.
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

# Вся книга — внутри book_assembly/ (экспорт «Книга» + сборка HTML)
BOOK_DIR = Path(__file__).resolve().parent
BOOK_JSON = BOOK_DIR / "Книга"
OUT_DIR = BOOK_DIR


def collect_strings(obj, out: list[str]) -> None:
    if isinstance(obj, dict):
        for v in obj.values():
            collect_strings(v, out)
    elif isinstance(obj, list):
        for v in obj:
            collect_strings(v, out)
    elif isinstance(obj, str) and len(obj.strip()) > 30:
        out.append(obj)


def build_corpus(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    parts: list[str] = []
    collect_strings(data, parts)
    # Убираем явный мусор (англ. thinking без кириллицы в длинных кусках)
    merged = []
    for p in parts:
        if re.search(r"[а-яА-ЯЁё]", p) and not p.strip().startswith("**Analyzing"):
            merged.append(p)
    return "\n\n---\n\n".join(merged)


def extract_between(
    corpus: str, start: str, end: str | None, max_len: int = 25000, cap_if_no_end: int | None = None
) -> str | None:
    i = corpus.find(start)
    if i < 0:
        return None
    if end:
        j = corpus.find(end, i + len(start))
        if j < 0:
            lim = cap_if_no_end if cap_if_no_end is not None else max_len
            return corpus[i : i + lim]
        return corpus[i : j + len(end)]
    return corpus[i : i + max_len]


def extract_smart_window(corpus: str, start: str, max_len: int = 4500) -> str | None:
    """Берёт окно от якоря; обрезает на границе --- чтобы не затянуть комментарии Атласа."""
    i = corpus.find(start)
    if i < 0:
        return None
    chunk = corpus[i : i + max_len]
    sep = chunk.find("\n\n---\n\n")
    if 80 < sep < len(chunk) - 50:
        chunk = chunk[:sep]
    # второй проход: если явно мета про «проводник» в первых 900 симв. — взять следующее вхождение
    if "проводником" in chunk[:900] and "Левицк" not in chunk[:1200]:
        i2 = corpus.find(start, i + len(start))
        if i2 > 0:
            chunk = corpus[i2 : i2 + max_len]
            sep = chunk.find("\n\n---\n\n")
            if 80 < sep < len(chunk) - 50:
                chunk = chunk[:sep]
    return chunk


def first_paragraph_containing(corpus: str, needle: str, min_len: int = 200, max_len: int = 12000) -> str | None:
    idx = corpus.find(needle)
    if idx < 0:
        return None
    # расширяем окно
    a = max(0, idx - 500)
    b = min(len(corpus), idx + max_len)
    chunk = corpus[a:b]
    if len(chunk) < min_len:
        return chunk
    return chunk


def main() -> int:
    if not BOOK_JSON.is_file():
        print(f"Нет файла: {BOOK_JSON}", file=sys.stderr)
        return 1

    corpus = build_corpus(BOOK_JSON)
    log_lines: list[str] = [f"Корпус: {len(corpus)} символов после фильтра кириллицы.\n"]

    results: dict[str, dict] = {}

    def add(sid: str, title: str, kind: str, text: str | None, note: str = "") -> None:
        results[sid] = {"title": title, "kind": kind, "text": text or "", "note": note}
        log_lines.append(f"[{sid}] {title}: {'OK ' + str(len(text or '')) + ' симв.' if text else 'НЕ НАЙДЕН'} {note}")

    # АКТ I
    t = extract_between(corpus, "Мне 21 год", "Или не придется?!", cap_if_no_end=3800)
    if not t:
        t = extract_between(corpus, "Мне 21 год", "не придется", cap_if_no_end=3800)
    if not t:
        t = extract_smart_window(corpus, "Мне 21 год", 3500)
    if t and "\n\n---\n\n" in t:
        t = t.split("\n\n---\n\n", 1)[0].strip()
    add("act1_levitsky_max", "Кабинет Левицкого (Макс)", "max", t)

    t = first_paragraph_containing(
        corpus, "легких не были воспалены", max_len=4000
    ) or first_paragraph_containing(corpus, "сдались раньше времени", max_len=4000)
    add("act1_levitsky_atlas", "Мысли Левицкого / лёгкие (Атлас)", "atlas", t)

    t = extract_between(corpus, "Стал перебирать", "после оргазма")
    if not t:
        t = extract_smart_window(corpus, "Стал перебирать чего бы", 6000)
    if not t:
        t = first_paragraph_containing(corpus, "успешный успех", max_len=8000)
    add("act1_success_max", "Успешный успех (Макс)", "max", t)

    t = first_paragraph_containing(corpus, "Дударь", max_len=8000)
    add("act1_dudar_max", "Очередь и Дударь (Макс)", "max", t)

    t = first_paragraph_containing(corpus, "Нелли", max_len=9000)
    if not t or "цвет" not in t.lower():
        t = first_paragraph_containing(corpus, "цветы", max_len=9000)
    add("act1_flowers_max", "Цветы / Лучик (Макс)", "max", t)

    t = first_paragraph_containing(corpus, "Кирюх", max_len=10000)
    add("act1_kiryuha_max", "Кирюха (Макс)", "max", t)

    # АКТ II
    t = first_paragraph_containing(corpus, "собрание раньше", max_len=8000)
    if not t:
        t = first_paragraph_containing(corpus, "на собрание", max_len=8000)
    if not t:
        t = first_paragraph_containing(corpus, "Собрание.", max_len=8000)
    add("act2_meeting_max", "Собрание (Макс)", "max", t)

    t = first_paragraph_containing(corpus, "Этой водой", max_len=12000)
    if not t:
        t = first_paragraph_containing(corpus, "ТОПИШЬ", max_len=12000)
    add("act2_timur_riot_atlas", "Бунт Тимура (Атлас)", "atlas", t)

    t = first_paragraph_containing(corpus, "одну бутылку", max_len=12000)
    if not t:
        t = first_paragraph_containing(corpus, "Всего одна бутылка", max_len=12000)
    add("act2_accident_atlas", "Авария / Тимур в машине (Атлас)", "atlas", t)

    t = first_paragraph_containing(corpus, "Тимур вошел в квартиру", max_len=14000)
    if not t:
        t = first_paragraph_containing(corpus, "Тимур вошёл в квартиру", max_len=14000)
    add("act2_home_truth_atlas", "Правда дома / Юлия (Атлас)", "atlas", t)

    # АКТ III
    add("act3_sochi_prep", "Подготовка / 108 млн (Макс)", "placeholder", None, "по ТЗ — допишет Макс")

    t = first_paragraph_containing(corpus, "Нет на свете улыбки", max_len=10000)
    add("act3_mask_max", "Маска / стихи (Макс)", "max", t)

    t = first_paragraph_containing(corpus, "пианист", max_len=10000)
    if not t:
        t = first_paragraph_containing(corpus, "Пустой стул", max_len=10000)
    add("act3_escape_atlas", "Бегство / маска / 14:45 (Атлас)", "atlas", t)

    add("act3_run", "Забег 7.7 км (Макс)", "placeholder", None)

    # АКТ IV
    t = first_paragraph_containing(corpus, "108", max_len=8000)
    if t and "миллион" not in t.lower() and "млн" not in t.lower():
        t = first_paragraph_containing(corpus, "108 млн", max_len=12000)
    add("act4_functional_death_atlas", "Провал 108 млн (Атлас)", "atlas", t)

    # АКТ V
    t = first_paragraph_containing(corpus, "Звуки сирены", max_len=12000)
    if not t:
        t = first_paragraph_containing(corpus, "скорой помощи", max_len=12000)
    add("act5_siren_max", "Сирена / Резанов (Макс)", "max", t)

    t = first_paragraph_containing(corpus, "Живой уголок", max_len=10000)
    add("act5_fruits_montage", "Плоды / уголок / Аня (сборка)", "mixed", t)

    t = first_paragraph_containing(corpus, "14:46", max_len=6000)
    add("act5_finale", "14:46 / финал", "mixed", t)

    # Сохранить JSON для отладки
    serializable = {k: {**v, "text_len": len(v["text"])} for k, v in results.items()}
    (OUT_DIR / "fragments_meta.json").write_text(
        json.dumps(serializable, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    (OUT_DIR / "extraction_log.txt").write_text("\n".join(log_lines), encoding="utf-8")

    # HTML
    css_max = "color:#000000;"
    css_atlas = "color:#B85D19;"
    css_ph = "color:#666666;font-style:italic;"

    def block(sid: str, heading: str, data: dict) -> str:
        kind = data["kind"]
        note = data.get("note", "")
        text = data["text"].strip()
        if kind == "placeholder":
            body = f'<p style="{css_ph}">[ЗДЕСЬ МАКС ДОПИШЕТ ТЕКСТ] {html.escape(note or "")}</p>'
        elif not text:
            body = f'<p style="{css_ph}">[ФРАГМЕНТ НЕ НАЙДЕН В ЭКСПОРТЕ «Книга» — вставь вручную из рукописи]</p>'
        else:
            sty = css_max if kind == "max" else css_atlas if kind == "atlas" else css_max
            body = f'<div style="{sty} white-space:pre-wrap;">{html.escape(text)}</div>'
        return f"<h3>{html.escape(heading)}</h3>\n{body}\n"

    html_parts: list[str] = [
        "<!DOCTYPE html>",
        '<html lang="ru"><head><meta charset="utf-8">',
        "<title>14:45 — сборка (FORGE)</title>",
        "<style>body{font-family:Georgia,serif;max-width:48rem;margin:2rem auto;line-height:1.5;} h1,h2,h3{color:#111;} .check li{margin:0.35em 0;}</style>",
        "</head><body>",
        "<h1>14:45 — рукопись (сборка по ТЗ Атласа)</h1>",
        "<p><strong>Легенда:</strong> чёрный — текст Макса; <span style='color:#B85D19'>терракота</span> — черновики/вставки Атласа; серый курсив — плейсхолдеры.</p>",
        "<h2>Чек-лист концепций</h2>",
        "<ul class='check'>",
        "<li>(Внедрено) «Вспомнить будущее»</li>",
        "<li>(Внедрено) 14:45 диагноз и Сочи</li>",
        "<li>(Внедрено) Финал 14:46</li>",
        "<li>(Внедрено) Тимур, авария, одна бутылка</li>",
        "<li>(Внедрено) Медицинская этика Артура</li>",
        "<li>(В плане) Счёт 2 млн — лёгкие vs уголок</li>",
        "<li>(В плане) Стол и Аня</li>",
        "<li>(В процессе) Арка Вадима — душа в ящике</li>",
        "<li>(В плане) Забег 5:00, 7.7 км, темп 5:33</li>",
        "<li>(Внедрено) Сын Кирюхи, вода перед матчем</li>",
        "</ul>",
    ]

    html_parts.append("<h2>АКТ I — ПРИГОВОР</h2>")
    html_parts.append(block("act1_levitsky_max", "Глава: Кабинет Левицкого", results["act1_levitsky_max"]))
    html_parts.append(block("act1_levitsky_atlas", "Черновик Атласа: Левицкий / лёгкие", results["act1_levitsky_atlas"]))
    html_parts.append(block("act1_success_max", "Глава: Успешный успех и пустота", results["act1_success_max"]))
    html_parts.append(block("act1_dudar_max", "Глава: Очередь и Дударь", results["act1_dudar_max"]))
    html_parts.append(block("act1_flowers_max", "Глава: Цветы на три года", results["act1_flowers_max"]))
    html_parts.append(block("act1_kiryuha_max", "Глава: Встреча с Кирюхой", results["act1_kiryuha_max"]))

    html_parts.append("<h2>АКТ II — ПОДЪЁМ И НАДЕЖДА</h2>")
    html_parts.append(block("act2_meeting_max", "Глава: Собрание", results["act2_meeting_max"]))
    html_parts.append(block("act2_timur_riot_atlas", "Глава: Бунт Тимура", results["act2_timur_riot_atlas"]))
    html_parts.append(block("act2_accident_atlas", "Глава: Авария", results["act2_accident_atlas"]))
    html_parts.append(block("act2_home_truth_atlas", "Глава: Правда дома", results["act2_home_truth_atlas"]))
    html_parts.append(
        f'<p style="{css_ph}">[ЗДЕСЬ МАКС ДОПИШЕТ ТЕКСТ: выбор на 2 млн, история плотника и стола, арка Вадима]</p>'
    )

    html_parts.append("<h2>АКТ III — СОЧИ. КРАХ</h2>")
    html_parts.append(
        f'<p style="{css_ph}">[ЗДЕСЬ МАКС ДОПИШЕТ ТЕКСТ: сюрприз, 108 млн, предвкушение]</p>'
    )
    html_parts.append(block("act3_mask_max", "Глава: Маска и 14:45", results["act3_mask_max"]))
    html_parts.append(block("act3_escape_atlas", "Глава: Бегство", results["act3_escape_atlas"]))
    html_parts.append(block("act3_run", "Место: забег", results["act3_run"]))

    html_parts.append("<h2>АКТ IV — ПРОВАЛ 108 МИЛЛИОНОВ</h2>")
    html_parts.append(block("act4_functional_death_atlas", "Глава: Функциональная смерть", results["act4_functional_death_atlas"]))

    html_parts.append("<h2>АКТ V — РЕАНИМАЦИЯ (14:46)</h2>")
    html_parts.append(block("act5_siren_max", "Глава: Последний вдох", results["act5_siren_max"]))
    html_parts.append(block("act5_fruits_montage", "Глава: Плоды семян", results["act5_fruits_montage"]))
    html_parts.append(block("act5_finale", "Глава: Выбор / 14:46", results["act5_finale"]))

    html_parts.append("<hr><p><small>Собрано FORGE по ТЗ ATLAS. Источник фрагментов: экспорт «Книга». Не сгенерировано новое художественное.</small></p>")
    html_parts.append("</body></html>")

    (OUT_DIR / "14-45_manuscript.html").write_text("\n".join(html_parts), encoding="utf-8")
    print("OK:", OUT_DIR / "14-45_manuscript.html")
    print("Log:", OUT_DIR / "extraction_log.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
