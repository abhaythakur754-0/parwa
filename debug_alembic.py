from alembic.config import Config
from alembic.script import ScriptDirectory
import os

config = Config("alembic.ini")
script = ScriptDirectory.from_config(config)

print(f"Script location: {script.dir}")
print(f"Versions location: {script.versions}")

for m in script.walk_revisions():
    print(f"Found migration: {m.revision} -> {m.down_revision}")
