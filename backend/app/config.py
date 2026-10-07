from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 微信
    wechat_app_id: str = ""
    wechat_app_secret: str = ""

    # JWT
    jwt_secret_key: str = "dev-secret-key"
    jwt_algorithm: str = "HS256"
    jwt_expire_days: int = 30

    # ─── 数据库配置（分字段，URL 自动拼装）───
    # DB_TYPE: sqlite 或 mysql
    db_type: str = "mysql"

    # SQLite（db_type=sqlite 时使用）
    sqlite_path: str = "./data/knowledge.db"

    # MySQL（db_type=mysql 时使用）
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = ""
    mysql_db: str = "knowledge"

    # 也可通过 DATABASE_URL 直接覆盖自动拼装的连接串（可选）
    database_url: str = ""

    # ─── Ollama 本地大模型 ───
    ollama_host: str = "http://localhost:11434"
    ollama_chat_model: str = "qwen3.5:2b"            # 出题 / 分析技术栈难度
    ollama_embed_model: str = "qwen3-embedding:0.6b"  # 向量化（语义搜索），1024 维

    # ─── 管理员 ───
    # 指定哪些 openid 是管理员（逗号分隔）。这些账号每次登录都会自动获得管理员权限。
    # 用 `.env` 里的 ADMIN_OPENIDS 配置；留空则只有「首个注册用户」是管理员。
    admin_openids: str = ""

    @property
    def admin_openid_set(self) -> set:
        return {x.strip() for x in self.admin_openids.split(",") if x.strip()}

    @model_validator(mode="after")
    def _build_database_url(self):
        """根据 db_type 自动拼装连接串；若已显式设置 database_url 则优先使用"""
        if not self.database_url:
            if self.db_type == "mysql":
                self.database_url = (
                    f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
                    f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_db}?charset=utf8mb4"
                )
            else:
                self.database_url = f"sqlite:///{self.sqlite_path}"
        return self

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    class Config:
        env_file = ".env"


settings = Settings()
