from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 微信
    wechat_app_id: str = ""
    wechat_app_secret: str = ""

    # JWT
    jwt_secret_key: str = "dev-secret-key"
    jwt_algorithm: str = "HS256"
    jwt_expire_days: int = 30

    # 数据库
    database_url: str = "sqlite:///./data/knowledge.db"

    # 向量模型
    embedding_model: str = "shibing624/text2vec-base-chinese"

    class Config:
        env_file = ".env"


settings = Settings()
