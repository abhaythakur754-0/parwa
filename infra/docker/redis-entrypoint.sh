#!/bin/sh
set -eu

if [ -z "${REDIS_PASSWORD:-}" ]; then
  echo "REDIS_PASSWORD is required" >&2
  exit 1
fi

case "$REDIS_PASSWORD" in
  *[!A-Za-z0-9_-]*)
    echo "REDIS_PASSWORD must use URL-safe characters" >&2
    exit 1
    ;;
esac

# Keep the secret out of process arguments. Redis reads it from a private
# runtime config file; URL-safe characters avoid Redis config escaping issues.
umask 077
cat /usr/local/etc/redis/redis.conf > /tmp/redis-runtime.conf
printf 'requirepass %s\n' "$REDIS_PASSWORD" >> /tmp/redis-runtime.conf

exec redis-server /tmp/redis-runtime.conf
