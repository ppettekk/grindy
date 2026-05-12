# Деплой Grindy на VPS (Hetzner / Helsinki)

Полный пошаговый гайд от пустого сервера до работающего бота с WebApp на HTTPS.

---

## 0. Перед началом

**Нужно:**
- VPS с Ubuntu 22.04 / Debian 12 (минимум 1 GB RAM, рекомендую 2+)
- Домен (например, `grindy.ru`)
- BOT_TOKEN от `@BotFather`
- API-ключ Google Gemini (https://aistudio.google.com → Get API key)
- (опционально) SuperJob API key (https://api.superjob.ru/info/)

**Рекомендуемый сервер:** Hetzner Cloud `CX22` в Helsinki — 2 vCPU / 4 GB RAM / 40 GB SSD ≈ €4.51/мес.

---

## 1. Создание сервера

1. Регистрация на https://console.hetzner.cloud
2. **New Project → Add Server**
3. **Location:** Helsinki (`hel1`)
4. **Image:** Ubuntu 22.04
5. **Type:** CX22 (Shared vCPU / x86)
6. **Networking:** включи IPv4 + IPv6
7. **SSH key:** добавь свой публичный ключ (`~/.ssh/id_ed25519.pub`)
8. **Name:** `grindy-prod` → **Create & Buy**

Через 30 секунд получишь IP (например, `135.181.X.X`).

---

## 2. DNS

В панели регистратора домена (REG.RU / Beget / Namecheap) добавь A-записи:

| Тип | Имя | Значение | TTL |
|---|---|---|---|
| A | `@` | `135.181.X.X` | 600 |
| A | `www` | `135.181.X.X` | 600 |

Подожди 5–15 минут, проверь: `nslookup grindy.ru 8.8.8.8` должен вернуть твой IP.

---

## 3. Первичная настройка сервера

Подключись по SSH:

```bash
ssh root@135.181.X.X
```

### 3.1 Создать пользователя и обновить систему

```bash
# Обновление пакетов
apt update && apt upgrade -y

# Часовой пояс (для корректной работы scheduler 09:00/19:00 МСК)
timedatectl set-timezone Europe/Moscow

# Создание non-root пользователя
adduser grindy
usermod -aG sudo grindy

# Перенос SSH-ключа
mkdir -p /home/grindy/.ssh
cp /root/.ssh/authorized_keys /home/grindy/.ssh/
chown -R grindy:grindy /home/grindy/.ssh
chmod 700 /home/grindy/.ssh
chmod 600 /home/grindy/.ssh/authorized_keys
```

### 3.2 Файрвол (UFW)

```bash
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp        # SSH
ufw allow 80/tcp        # HTTP (для Let's Encrypt)
ufw allow 443/tcp       # HTTPS
ufw --force enable
```

### 3.3 Защита от брутфорса (опционально, но желательно)

```bash
apt install -y fail2ban
systemctl enable --now fail2ban
```

### 3.4 Запретить root-логин по SSH

```bash
sed -i 's/^#\?PermitRootLogin .*/PermitRootLogin no/' /etc/ssh/sshd_config
sed -i 's/^#\?PasswordAuthentication .*/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl restart ssh
```

Дальше работаем под `grindy`:

```bash
exit
ssh grindy@135.181.X.X
```

---

## 4. Установка Docker

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
# Перелогинься чтобы группа docker применилась
exit
ssh grindy@135.181.X.X
docker --version
docker compose version
```

---

## 5. Деплой кода

### 5.1 Залить код

Вариант А — через git (если репо в GitHub):

```bash
cd ~
git clone git@github.com:твой_логин/grindy.git
cd grindy
```

Вариант Б — через `rsync` со своей машины:

```powershell
# С Windows-машины
cd C:\Users\Petr\Desktop\Grindy
rsync -av --exclude node_modules --exclude __pycache__ --exclude .git Grindy/ grindy@135.181.X.X:/home/grindy/grindy/
```

Или через `scp -r`.

### 5.2 Заполнить .env

```bash
cd ~/grindy
cp .env.example .env
nano .env
```

Минимальный набор для прода:

```env
POSTGRES_USER=grindy
POSTGRES_PASSWORD=<сгенерируй openssl rand -hex 16>
POSTGRES_DB=grindy
DATABASE_URL=postgresql+asyncpg://grindy:<пароль>@db:5432/grindy

BOT_TOKEN=<твой токен от BotFather>
WEBAPP_URL=https://grindy.ru
BOT_PROXY=

GEMINI_API_KEY=<ключ из aistudio.google.com>
GEMINI_MODEL=gemini-2.5-flash

SUPERJOB_API_KEY=<или оставь пустым>
HH_USER_AGENT=Grindy/0.1 (huqtuy@gmail.com)

YOOKASSA_SHOP_ID=
YOOKASSA_SECRET_KEY=

RUN_SCHEDULER=true
PARSE_INTERVAL_MIN=60
DIGEST_MORNING="0 9 * * *"
DIGEST_EVENING="0 19 * * *"

CORS_ORIGINS=https://grindy.ru,https://www.grindy.ru
```

### 5.3 Подправить домен в Caddyfile

```bash
nano Caddyfile
```

Замени `grindy.ru` на свой домен в обеих позициях.

---

## 6. Запуск

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Первый запуск:
- сборка образов (~5–10 минут)
- Caddy запросит сертификат у Let's Encrypt (нужен открытый 80/443 порт и работающий DNS)
- backend создаст таблицы в БД
- bot подключится к Telegram и начнёт polling
- scheduler запустит первый ingest через 60 минут

Проверка:

```bash
docker compose -f docker-compose.prod.yml ps         # все running
docker compose -f docker-compose.prod.yml logs -f bot
docker compose -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.prod.yml logs -f caddy
```

---

## 7. Настройка бота в @BotFather

Открой `@BotFather` → выбери своего бота:

1. **Bot Settings → Menu Button → Configure menu button** → URL: `https://grindy.ru`
2. **Bot Settings → Configure Mini App → Edit Mini App URL** → `https://grindy.ru`
3. **Bot Settings → Domain → Set domain** → `grindy.ru`
4. **Edit Bot → Edit Description / About / Picture** — наполни инфой

После — открой бот, нажми `/start`, проверь онбординг и кнопку «Открыть Grindy».

---

## 8. Мониторинг и обслуживание

**Просмотр логов:**
```bash
docker compose -f docker-compose.prod.yml logs -f --tail=100
```

**Рестарт сервиса:**
```bash
docker compose -f docker-compose.prod.yml restart bot
```

**Обновление кода:**
```bash
cd ~/grindy
git pull            # или rsync
docker compose -f docker-compose.prod.yml up -d --build
```

**Бэкап БД (раз в сутки в крон):**
```bash
crontab -e
# добавь:
0 3 * * * docker exec grindy-db-1 pg_dump -U grindy grindy | gzip > /home/grindy/backup-$(date +\%F).sql.gz && find /home/grindy -name 'backup-*.sql.gz' -mtime +7 -delete
```

**Использование ресурсов:**
```bash
docker stats
```

**Размер БД:**
```bash
docker exec -it grindy-db-1 psql -U grindy -c "SELECT pg_size_pretty(pg_database_size('grindy'));"
```

---

## 9. Если что-то не работает

| Симптом | Что проверить |
|---|---|
| Caddy не получает сертификат | DNS A-запись отвечает с IP сервера? Порты 80/443 открыты? |
| Бот не отвечает | `docker compose logs bot` — есть ли `Cannot connect to host api.telegram.org`? |
| Парсеры не находят вакансий | `HH_USER_AGENT` указан? `SUPERJOB_API_KEY`? Часовой пояс? |
| WebApp не открывается из бота | URL в BotFather соответствует Caddyfile? Сертификат TLS валиден (`curl -I https://grindy.ru`)? |
| Gemini-модерация молчит | `GEMINI_API_KEY` не пустой? `docker compose logs backend` — есть ли ошибки? |

---

## 10. CI/CD через GitLab (приватный репо)

После того как сервер настроен и первый раз вручную запущен `docker-compose.prod.yml`, можно подключить автодеплой через GitLab CI.

### 10.1 Создать Deploy Token (для server-side `docker pull`)

GitLab → твой проект → **Settings → Repository → Deploy Tokens → Add token**:
- **Name:** `grindy-server-pull`
- **Username:** `grindy-deploy` (это и будет `DEPLOY_TOKEN_USER`)
- **Scopes:** ✅ `read_registry`
- **Create token** → скопируй пароль (это `DEPLOY_TOKEN_PASSWORD`, больше не покажется).

### 10.2 Создать SSH deploy-ключ для CI

На своей машине:
```bash
ssh-keygen -t ed25519 -C "gitlab-ci" -f ./gitlab_deploy -N ""
ssh-copy-id -i ./gitlab_deploy.pub grindy@<IP>
```

Содержимое файла `gitlab_deploy` (без `.pub`) пойдёт в переменную `SSH_PRIVATE_KEY`.

### 10.3 Прописать CI/CD переменные

GitLab → проект → **Settings → CI/CD → Variables → Add variable**:

| Key | Type | Protected | Masked | Value |
|---|---|---|---|---|
| `SSH_PRIVATE_KEY` | **File** | ✅ | ❌ | содержимое `gitlab_deploy` |
| `SSH_HOST` | Variable | ✅ | ❌ | `135.181.X.X` |
| `SSH_USER` | Variable | ✅ | ❌ | `grindy` |
| `SSH_PORT` | Variable | ✅ | ❌ | `22` (опционально) |
| `PROD_DOMAIN` | Variable | ✅ | ❌ | `grindy.ru` |
| `DEPLOY_TOKEN_USER` | Variable | ✅ | ✅ | `grindy-deploy` |
| `DEPLOY_TOKEN_PASSWORD` | Variable | ✅ | ✅ | пароль из 10.1 |

`Protected` означает «доступно только в protected ветках/тегах». Сделай `main` protected (Settings → Repository → Protected Branches), чтобы переменные не утекали из feature-веток.

### 10.4 Дать CI-пользователю права в registry

В GitLab → проект → **Packages and registries → Container Registry** → проверь, что включён.

### 10.5 Первый раз — клон репо на сервере

CI деплоит через `git fetch && git reset --hard`, поэтому репозиторий должен уже быть на сервере. Один раз вручную:

```bash
ssh grindy@<IP>
cd ~
git clone https://<DEPLOY_TOKEN_USER>:<DEPLOY_TOKEN_PASSWORD>@gitlab.com/<group>/grindy.git
# Альтернативно — через SSH deploy key, если предпочитаешь
cd grindy
cp .env.example .env && nano .env  # заполни прод-секреты
```

`.env` лежит на сервере — CI его не перезаписывает (он не в репо). Меняешь токены/ключи вручную через SSH.

### 10.6 Готово

Push в `main` запускает пайплайн:
1. `lint` — ruff
2. `test` — pytest + smoke
3. `build` — vite build
4. `package` — собирает и пушит `backend` и `frontend` образы в `registry.gitlab.com/<group>/grindy/{backend,frontend}:<sha>` и `:latest`
5. `deploy` — SSH на сервер, подмена `.env.deploy`, `docker compose pull && up -d`, smoke-чек `/health`

Smoke-чек упадёт если HTTPS не отвечает — пайплайн помечается красным, environment в GitLab показывает Failed.

### Откат

```bash
ssh grindy@<IP>
cd ~/grindy
echo "IMAGE_TAG=<previous-short-sha>" > .env.deploy
echo "REGISTRY_IMAGE=registry.gitlab.com/<group>/grindy" >> .env.deploy
docker compose --env-file .env --env-file .env.deploy -f docker-compose.deploy.yml pull
docker compose --env-file .env --env-file .env.deploy -f docker-compose.deploy.yml up -d
```

---

## 11. Безопасность

- Регулярные `apt upgrade` — раз в неделю
- Ротация `BOT_TOKEN` если он засветился в логах/скриншотах (BotFather → `/revoke`)
- `POSTGRES_PASSWORD` — не дефолтный, минимум 32 символа
- Доступ к серверу — только по SSH-ключу
- Бэкапы базы лежат не только на сервере (синхронизируй в S3 / B2 / Google Drive)
