-- Добавляем поля для хранения имени и возраста прямо в ответах
-- (чтобы не создавать пользователей в таблице users)

ALTER TABLE bloom_questionnaire_responses 
ADD COLUMN IF NOT EXISTS user_name VARCHAR(200),
ADD COLUMN IF NOT EXISTS user_age INTEGER;

-- Делаем user_id необязательным (может быть NULL)
ALTER TABLE bloom_questionnaire_responses 
ALTER COLUMN user_id DROP NOT NULL;

-- Комментарии
COMMENT ON COLUMN bloom_questionnaire_responses.user_name IS 'Имя пользователя (если не привязан к users)';
COMMENT ON COLUMN bloom_questionnaire_responses.user_age IS 'Возраст пользователя';

SELECT 'Таблица bloom_questionnaire_responses обновлена!' as result;




