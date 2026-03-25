# BLOOM Recovery Runbook

Этот файл нужен, чтобы быстро и спокойно вернуть Bloom в рабочее состояние.

## 1) Что считать "Bloom возвращен"

- Открывается страница: `https://marabot.tw1.ru/bloom.html`
- Работает опросник и запись ответов в БД
- Сохранена актуальная версия из `E:\BLOOM 2026\index.html`
- (Опционально) работает автоконтур отчетов из `E:\Island\_scripts`

## 2) Источник правды в этой папке

- Основной профиль Bloom: `README.md`
- Актуальная веб-страница для выкладки: `index.html`
- Инструкция деплоя: `DEPLOY_INDEX.md`
- Старый деплой-гайд: `archive/DEPLOY_BLOOM.md`
- Быстрый рестарт Caddy: `restart_caddy.sh`

## 3) Быстрое восстановление страницы (10-15 минут)

1. Открой `E:\BLOOM 2026\index.html`
2. Подключись к серверу (SSH Timeweb)
3. На сервере:
   - `cd /home/www/public`
   - `nano bloom.html`
4. Вставь содержимое `index.html`, сохрани (`Ctrl+O`, `Enter`) и выйди (`Ctrl+X`)
5. Проверь файл:
   - `ls -lh bloom.html`
6. При необходимости перезапусти Caddy:
   - `docker restart api_server-caddy-1`
7. Проверь в браузере:
   - `https://marabot.tw1.ru/bloom.html`

Примечание: тот же сценарий описан в `DEPLOY_INDEX.md`.

## 4) Проверка "жив ли Bloom" после выкладки

- Открывается страница без 404/502
- Форма отправляется без ошибок браузера
- Нет Mixed Content (HTTPS страница не должна дергать HTTP API)
- Запись появляется в БД через рабочий API-роут

## 5) Если не работает

- Очисти кеш браузера: `Ctrl+Shift+R`
- Проверь, что Caddy действительно перезапущен
- Проверь, что фронтенд использует HTTPS-домен, а не прямой `http://IP:8080`
- Сверься с контекстом инцидентов в `E:\Island\history\2025-11-24_api_https_fix.md`

## 6) Восстановление отчетов Bloom (опционально)

Если нужно вернуть автоматические ежедневные отчеты:

1. Перейди в `E:\Island\_scripts`
2. Выполни:
   - `powershell -ExecutionPolicy Bypass -File setup_bloom_daily_schedule.ps1`
3. Проверка задачи:
   - `Get-ScheduledTask -TaskName BloomDailyReport`

Ручной запуск отчета:

- `cd E:\Island`
- `python _scripts\bloom_daily_report.py [день]`

См. `E:\Island\_scripts\README_bloom_auto_reports.md` и `E:\Island\_scripts\disable_bloom_reports.md`.

## 7) Мини-чеклист на сегодня

- [ ] Выложить `index.html` как `bloom.html`
- [ ] Перезапустить Caddy
- [ ] Проверить страницу в браузере
- [ ] Проверить тестовую отправку формы
- [ ] Зафиксировать состояние в `DOCUMENTATION/journey.md`

---

Bloom не потерян, пока живы его артефакты, контекст и действие.
Этот runbook создан как точка опоры для быстрого возвращения.
