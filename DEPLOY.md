# Serverga o'rnatish (Docker)

Loyiha o'zining MySQL bazasi (`askue-db`) bilan ishlaydi, boshqa loyihalarga tegmaydi.
Local tarmoqda: `http://192.168.100.38:7009`, Cloudflare orqali: `https://askue.elshod.date`.

## Birinchi o'rnatish
```bash
cd ~/progects
git clone https://github.com/elshodatc111/askue_dny.git askue
cd askue
cat > .env <<EOT
SECRET_KEY=$(openssl rand -base64 48 | tr -d '\n=/+')
MYSQL_ROOT_PASSWORD=$(openssl rand -hex 16)
DB_NAME=askue
DB_USER=askue
DB_PASSWORD=$(openssl rand -hex 16)
ADMIN_USER=admin
ADMIN_PASSWORD=$(openssl rand -hex 6)
ALLOWED_HOSTS=askue.elshod.date,192.168.100.38,localhost
CSRF_TRUSTED_ORIGINS=https://askue.elshod.date,http://192.168.100.38:7009
WEB_PORT=7009
EOT
chmod 600 .env
docker compose up -d --build
docker compose logs -f web
```
Admin paroli `.env` dagi `ADMIN_PASSWORD` (`grep ADMIN .env`). Kirgach darhol almashtiring.

## Cloudflare
Zero Trust > Networks > Tunnels > tunnel > Public hostname: `askue.elshod.date` -> HTTP -> `192.168.100.38:7009`.

## Yangilash
```bash
cd ~/progects/askue && git pull && docker compose up -d --build
```

## Zaxira nusxa (baza)
```bash
docker exec askue-db sh -c 'mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction askue' > ~/progects/stack/backups/askue_$(date +%F).sql
```
