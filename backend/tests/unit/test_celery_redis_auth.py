from app.tasks.celery_app import _apply_redis_password


def test_apply_redis_password_adds_auth_to_render_redis_url():
    assert _apply_redis_password("redis://redis.internal:6379/0", "a secret") == (
        "redis://:a%20secret@redis.internal:6379/0"
    )


def test_apply_redis_password_preserves_existing_url_credentials():
    url = "redis://default:existing@redis.internal:6379/0"
    assert _apply_redis_password(url, "new-secret") == url


def test_apply_redis_password_leaves_url_unchanged_without_password():
    url = "redis://redis.internal:6379/0"
    assert _apply_redis_password(url, "") == url
