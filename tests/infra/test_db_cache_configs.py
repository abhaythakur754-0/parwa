#!/usr/bin/env python3
"""PARWA Infrastructure — Database & Cache Config Tests"""
import os, sys

DOCKER_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "infra", "docker")
pass_count = 0
fail_count = 0

def test_pg_hba_no_trust():
    global pass_count, fail_count
    with open(os.path.join(DOCKER_DIR, "pg_hba.conf")) as f:
        for line in f:
            s = line.strip()
            if s.startswith("#") or not s:
                continue
            parts = s.split()
            if parts and parts[-1] == "trust":
                print(f"FAIL  pg_hba.conf: uses trust auth — {s}")
                fail_count += 1
                return
    print(f"PASS  pg_hba.conf: no trust auth")
    pass_count += 1

def test_redis_dangerous_disabled():
    global pass_count, fail_count
    with open(os.path.join(DOCKER_DIR, "redis.conf")) as f:
        content = f.read()
    dangerous = ["FLUSHALL", "FLUSHDB", "DEBUG", "CONFIG", "SHUTDOWN"]
    all_disabled = all(f'rename-command {cmd} ""' in content for cmd in dangerous)
    if all_disabled:
        print(f"PASS  Redis: dangerous commands disabled")
        pass_count += 1
    else:
        print(f"FAIL  Redis: not all dangerous commands disabled")
        fail_count += 1

def test_postgres_shared_preload():
    global pass_count, fail_count
    with open(os.path.join(DOCKER_DIR, "postgresql.conf")) as f:
        content = f.read()
    if "pg_stat_statements" in content and "shared_preload_libraries" in content:
        print(f"PASS  PostgreSQL: pg_stat_statements configured")
        pass_count += 1
    else:
        print(f"FAIL  PostgreSQL: pg_stat_statements not in shared_preload_libraries")
        fail_count += 1

def test_postgres_archive_mode():
    global pass_count, fail_count
    with open(os.path.join(DOCKER_DIR, "postgresql.conf")) as f:
        content = f.read()
    if "archive_mode = on" in content:
        print(f"PASS  PostgreSQL: archive_mode enabled")
        pass_count += 1
    else:
        print(f"FAIL  PostgreSQL: archive_mode not enabled")
        fail_count += 1

def test_postgres_log_rotation():
    global pass_count, fail_count
    with open(os.path.join(DOCKER_DIR, "postgresql.conf")) as f:
        content = f.read()
    if "log_rotation_age" in content and "log_rotation_size" in content:
        print(f"PASS  PostgreSQL: log rotation configured")
        pass_count += 1
    else:
        print(f"FAIL  PostgreSQL: no log rotation")
        fail_count += 1

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  PARWA — Database & Cache Config Tests")
    print("=" * 60 + "\n")
    test_pg_hba_no_trust()
    test_redis_dangerous_disabled()
    test_postgres_shared_preload()
    test_postgres_archive_mode()
    test_postgres_log_rotation()
    total = pass_count + fail_count
    print(f"\n{'=' * 60}\n  RESULTS: {pass_count} passed, {fail_count} failed out of {total}\n{'=' * 60}")
    sys.exit(1 if fail_count > 0 else 0)
