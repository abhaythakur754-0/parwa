import os

def fix_file(path):
    if not os.path.exists(path):
        return
    with open(path, 'rb') as f:
        content = f.read()
    new_content = content.replace(b'\r\n', b'\n')
    if new_content != content:
        with open(path, 'wb') as f:
            f.write(new_content)
        print(f"Fixed {path}. New size: {len(new_content)} bytes.")
    else:
        print(f"No changes needed for {path}.")

# Fix deploy.sh
fix_file('deploy.sh')

# Fix all files in infra/docker
docker_dir = 'infra/docker'
if os.path.exists(docker_dir):
    for filename in os.listdir(docker_dir):
        file_path = os.path.join(docker_dir, filename)
        if os.path.isfile(file_path):
            fix_file(file_path)
