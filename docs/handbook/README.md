# Island ↔ Bridge — контракты (handbook)

Живая спецификация между **Островом** (веб, API, БД) и **ботом Bloom** (`bridge`).  
**Правило:** поменял API или общие поля БД — обнови этот репозиторий **в том же изменении или сразу следующим коммитом**.

## Содержание

| Файл | Назначение |
|------|------------|
| [api.md](api.md) | HTTP: эндпоинты, query/body, коды ошибок, примеры |
| [db-shared.md](db-shared.md) | Поля и таблицы, которыми пользуются и веб, и бот; владелец данных |
| [runbook.md](runbook.md) | Опционально: деплой, nginx, ключи, куда смотреть при инцидентах |

## Как завести отдельный репозиторий на GitHub (делает Макс)

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

5. **Collaborators:** Settings → Collaborators → добавить аккаунт Форжа (и кого ещё нужно).

6. В репозитории **`bridge`** в корневом `README.md` добавь **одну строку** со ссылкой на новый репо: «актуальные контракты: https://github.com/…».

### Почему `git push origin main` в разных папках — «разные репозитории»

Команда всегда пушит в **remote `origin` того репозитория, в чей каталог ты сейчас зашёл** (`git status` покажет ветку и путь). Репо `bridge` и репо `island-bridge-contract` — **два разных `.git`**. Перед пушем: `pwd` и при сомнении `git remote -v`.

### Пуш из Cursor

У ассистента часто **нет твоих GitHub credentials** — первый `git push` надёжнее выполнить **у себя в терминале** на машине, где залогинен GitHub (HTTPS + token или SSH). Если три попытки не взлетели — пуш вручную по командам выше, это нормально.

---

— Bridge (шаблон для отдельного репо; подпись можно убрать после копирования)
