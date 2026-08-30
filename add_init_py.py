import os

# 项目根目录（脚本所在目录）
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

# 要排除的目录（不检查也不创建 __init__.py）
EXCLUDE_DIRS = {
    'venv', '__pycache__', '.git', 'data', 'static', 
    'assets', 'css', 'js', 'docs', 'android', 'frontend',
    'backend/data', 'backend/static'
}

def should_exclude(dirpath):
    """检查当前路径是否应该被排除"""
    parts = dirpath.replace(os.sep, '/').split('/')
    for exclude in EXCLUDE_DIRS:
        exclude_parts = exclude.replace(os.sep, '/').split('/')
        # 如果目录名匹配或路径包含排除片段
        if any(part in exclude_parts for part in parts[-len(exclude_parts):]):
            return True
    return False

def ensure_init_py(start_dir):
    for dirpath, dirnames, filenames in os.walk(start_dir):
        # 提前排除不想要的子目录（不进入）
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS and not d.startswith('.')]
        
        # 如果当前目录被排除，跳过
        if should_exclude(dirpath):
            continue
        
        # 检查是否已有 __init__.py
        if '__init__.py' not in filenames:
            init_path = os.path.join(dirpath, '__init__.py')
            with open(init_path, 'w', encoding='utf-8') as f:
                pass  # 创建空文件
            print(f'✅ 已创建: {init_path}')
        else:
            print(f'⏭️  已存在: {os.path.join(dirpath, "__init__.py")}')

if __name__ == '__main__':
    print(f'🔍 检查根目录: {ROOT_DIR}')
    ensure_init_py(ROOT_DIR)
    print('✅ 完成！')