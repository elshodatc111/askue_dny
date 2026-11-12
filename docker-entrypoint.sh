#!/bin/sh
set -e

python manage.py migrate --noinput
python manage.py collectstatic --noinput > /dev/null

# Birinchi administrator: faqat ADMIN_PASSWORD berilgan bo'lsa (mavjud bo'lsa tegilmaydi)
if [ -n "$ADMIN_PASSWORD" ]; then
  python manage.py init_admin "${ADMIN_USER:-admin}" "$ADMIN_PASSWORD" > /dev/null
fi

exec "$@"
