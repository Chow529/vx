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

    # 向量模型
    embedding_model: str = "shibing624/text2vec-base-chinese"

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
