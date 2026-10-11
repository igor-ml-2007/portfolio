# Деплой на Cloudflare Pages

## Инструкция по деплою

### 1. Установите Wrangler CLI

```bash
npm install -g wrangler
```

### 2. Авторизуйтесь в Cloudflare

```bash
wrangler login
```

Это откроет браузер для авторизации в Cloudflare.

### 3. Создайте KV Namespace для галереи

```bash
wrangler kv:namespace create "GALLERY"
```

Скопируйте `id` из вывода команды и добавьте в `wrangler.toml`:

```toml
[[kv_namespaces]]
binding = "GALLERY"
id = "ВАШ_ID_ОТ_КОМАНДЫ_ВЫШЕ"
preview_id = "ВАШ_PREVIEW_ID"
```

### 4. Создайте R2 Bucket для фото

```bash
wrangler r2 bucket create "portfolio-photos"
```

В `wrangler.toml` уже настроено имя `portfolio-photos`, так что если используете это имя, ничего менять не нужно.

### 5. Обновите wrangler.toml

После выполнения команд выше, ваш `wrangler.toml` должен выглядеть примерно так:

```toml
name = "portfolio"
compatibility_date = "2024-01-01"

[site]
bucket = "./"

[[kv_namespaces]]
binding = "GALLERY"
id = "ВАШ_РЕАЛЬНЫЙ_ID"
preview_id = "ВАШ_PREVIEW_ID"

[[r2_buckets]]
binding = "PHOTOS"
bucket_name = "portfolio-photos"
```

### 6. Деплой

```bash
wrangler pages deploy .
```

Или для автоматического деплоя при изменениях:

```bash
wrangler pages deploy . --project-name=portfolio
```

### 7. Настройка домена (опционально)

После деплоя вы получите URL вида `your-project.pages.dev`. Можно добавить свой домен:
- Зайдите в Cloudflare Dashboard
- Pages → ваш проект → Custom domains
- Добавьте свой домен

## Важно

- Пароль админки: `atelier` (можно изменить в `functions/api/index.js` и `functions/_middleware.js`)
- Все фото загружаются в R2 bucket
- Галерея хранится в KV storage
- Авторизация через cookie с токеном

## Локальная разработка

Для локального тестирования с Wrangler:

```bash
wrangler pages dev .
```

Это запустит локальный сервер на http://localhost:8788

## Обновление пароля

Если хотите изменить пароль:

1. Замените `PASSWORD` в `functions/api/index.js` и `functions/_middleware.js`
2. Сгенерируйте новый SHA-256 хеш для `SESSION_TOKEN`:
   ```bash
   echo -n "новый_пароль" | openssl dgst -sha256 -hex | awk '{print $2}'
   ```
3. Обновите `SESSION_TOKEN` в обоих файлах
4. Деплой снова: `wrangler pages deploy .`
