# backend/app/config.py  —— 整体替换
import logging
from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# __file__ = backend/app/config.py → 向上两级 = backend/
BACKEND_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BACKEND_DIR / ".env"

# 显式指定绝对路径；override=True 防止系统里残留同名环境变量干扰
_loaded = load_dotenv(ENV_PATH, override=True)
logger.info(f"📄 .env 路径: {ENV_PATH} | 存在: {ENV_PATH.exists()} | 加载: {_loaded}")

DATA_DIR = BACKEND_DIR / "data"
SQLITE_PATH = DATA_DIR / "requirementhub.db"
UPLOAD_DIR = DATA_DIR / "uploads"       # 聊天附件
KNOWLEDGE_DIR = DATA_DIR / "knowledge"  # 知识库原始文件暂存

class Settings(BaseSettings):
    DATABASE_URL: str = f"sqlite:///{SQLITE_PATH.as_posix()}"
    SECRET_KEY: str = "dev-secret-change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    AI_PROVIDER: str = "zhipu"
    AI_API_KEY: str = ""
    AI_MODEL: str = "glm-4-flash"
    AI_MODELS_HISTORY: str = "glm-4-flash"   # 历史模型列表，逗号分隔，只增不删

    AI_BASE_URL: str = "https://open.bigmodel.cn/api/paas/v4/"
    EMBEDDING_MODEL: str = "embedding-3"   # 知识库向量化模型（智谱）

    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH),     # 绝对路径，不再看 CWD 脸色
        env_file_encoding="utf-8",
        extra="ignore",
    )

settings = Settings()

if settings.AI_API_KEY:
    logger.info(f"✅ AI_API_KEY 已配置: {settings.AI_API_KEY[:4]}****（长度 {len(settings.AI_API_KEY)}）")
else:
    logger.warning("⚠️ AI_API_KEY 为空。请检查: ①文件名确实是 .env 而非 .env.txt ②UTF-8 无 BOM ③格式 AI_API_KEY=值 且行首无空格")
for _d in (DATA_DIR, UPLOAD_DIR, KNOWLEDGE_DIR):
    _d.mkdir(parents=True, exist_ok=True)
