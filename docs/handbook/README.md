# Island ↔ Bridge — контракты (handbook)

Живая спецификация между **Островом** (веб, API, БД) и **ботом Bloom** (`bridge`).  
**Правило:** поменял API или общие поля БД — обнови этот репозиторий **в том же изменении или сразу следующим коммитом**.

## Содержание

| Файл | Назначение |
|------|------------|
| [api.md](api.md) | HTTP: эндпоинты, query/body, коды ошибок, примеры |
| [db-shared.md](db-shared.md) | Поля и таблицы, которыми пользуются и веб, и бот; владелец данных |
| [runbook.md](runbook.md) | Опционально: деплой, nginx, ключи, куда смотреть при инцидентах |

## Два агента Cursor и один GitHub (как не перепутать репозитории)

Оба агента ходят в GitHub **под твоим аккаунтом**. Отдельный collaborator для «второго агента» **не нужен** — у агента нет своего `@username` на GitHub. Путаница возможна только если **commit/push сделать из не той папки**.

### Развести окна по воркспейсам

| Окно Cursor (условно) | Папка на диске | `origin` на GitHub | Что правим |
|-----------------------|----------------|-------------------|------------|
| Бот / Bloom | `…/bridge` | `makcbarabanov/bridge` | Код бота, `Bloom/`, `island_*.py`, `.env.example`, утилиты; плюс **`docs/handbook/`** как копия рядом с кодом |
| Контракт Island ↔ Bridge | `…/island-bridge-contract` | `makcbarabanov/island-bridge-contract` | Только спека: `api.md`, `db-shared.md`, `runbook.md`, этот `README.md` |

В начале задачи можно явно написать агенту: *«репо **contract**»* или *«репо **bridge**»* — так проще держать контекст.

### Перед `git commit` / `git push` (проверка на автопилоте)

1. **Корень проекта** в Cursor или `pwd` в терминале — это `bridge` или `island-bridge-contract`?
2. **`git remote -v`** — для контракта в URL должно быть `island-bridge-contract`; для бота — `bridge` (не наоборот).
3. **Сообщение коммита** с префиксом: `contract: …` / `bridge: …` — по желанию, но сильно помогает в истории.

### Две копии markdown (`bridge/docs/handbook/` и отдельный репо)

**Канон по смыслу контракта** — репозиторий **[island-bridge-contract](https://github.com/makcbarabanov/island-bridge-contract)** (отдельный PR-источник правды для Острова ↔ бот).

**`bridge/docs/handbook/`** — зеркало в репо бота. После существенных правок в contract-репо имеет смысл **скопировать `.md` в `bridge/docs/handbook/`** и сделать коммит в `bridge`, чтобы шаблон не отставал (или наоборот в том же духе — главное не оставлять расхождение по полям API/БД).

```bash
# пример путей на одной машине:
cp /home/makc/island-bridge-contract/*.md /home/makc/bridge/docs/handbook/
```

## Как завести отдельный репозиторий на GitHub (делает Макс, один раз)

1. На GitHub: **New repository** → имя, например `island-bridge-contract` → **без** README (пустой), приватный по желанию.
2. Локально (один раз):

```bash
cd ~/where-you-clone   # любая папка вне bridge, если хочешь отдельный клон
git clone https://github.com/YOUR_USER/island-bridge-contract.git
cd island-bridge-contract
```

3. Скопируй сюда файлы из репозитория `bridge`: каталог **`docs/handbook/`** целиком (в корень нового репо: `README.md`, `api.md`, …).

```bash
# пример, если bridge лежит рядом:
cp -r ../bridge/docs/handbook/* .
```

4. Первый коммит и push:

```bash
git add .
git commit -m "Initial handbook: Bridge ↔ Island contracts"
git push -u origin main
```

5. **Collaborators:** нужен только если появится **живой** соавтор с GitHub-аккаунтом. Два агента Cursor в двух окнах — это не два пользователя GitHub.

6. В репозитории **`bridge`** в корневом `README.md` — ссылка на contract-репо (у этого проекта: `makcbarabanov/island-bridge-contract`).

### Почему `git push origin main` в разных папках — «разные репозитории»

Команда всегда пушит в **remote `origin` того репозитория, в чей каталог ты сейчас зашёл** (`git status` покажет ветку и путь). Репо `bridge` и репо `island-bridge-contract` — **два разных `.git`**. Перед пушем: `pwd` и при сомнении `git remote -v`.

### Пуш из Cursor

У ассистента на части машин **нет твоих GitHub credentials** — если `git push` из агента падает, тот же push из **твоего** терминала на сервере, где настроен GitHub (HTTPS + token или SSH), решает вопрос.

---

Шаблон этого набора файлов в монорепо бота: **`bridge/docs/handbook/`**.
