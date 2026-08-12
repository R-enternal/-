"""全局配置模块

参考 OneCall 项目的 config.py 设计，使用 Pydantic Settings 从 .env 加载配置，
实现类型安全的配置管理。
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 应用配置
    app_name: str = "仓脉智诊"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 9901

    # MySQL 配置
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = "060311"
    mysql_db: str = "cangweiyun"

    # Redis 配置
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0

    # 安全配置
    jwt_secret_key: str = "dev-only-secret-key-cangweiyun-2026"
    jwt_expire_minutes: int = 1440
    auth_enabled: bool = False  # 开发联调期 False（接口免认证）；演示前打开

    # 模拟数据配置
    simulate_interval_seconds: int = 60

    # 监测配置
    alert_debounce_count: int = 3

    # LLM 配置（OpenAI 兼容接口；api_key 为空时 Agent 走内置规则降级，可离线演示）
    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_model: str = "deepseek-chat"
    # Embedding 配置（RAG 知识库向量化，OpenAI 兼容接口）
    embedding_api_key: str = ""
    embedding_base_url: str = "https://open.bigmodel.cn/api/paas/v4/"
    embedding_model: str = "embedding-2"
    # 知识库配置
    kb_top_k: int = 4
    kb_chunk_size: int = 500
    kb_chunk_overlap: int = 50
    kb_vector_dir: str = "./vector_db"
    # Agent 防失控限制
    agent_max_steps: int = 6

    # 预测性告警配置（Holt 双指数平滑外推）
    predictive_horizon: int = 12  # 预测未来步数（每步 1 个采样周期）
    predictive_window: int = 20  # 平滑窗口（采样点数）

    # SQL 日志（开发时如需查看 SQL 可设 True，默认关闭避免刷屏）
    sql_echo: bool = False

    @property
    def mysql_url(self) -> str:
        """MySQL 连接 URL（含数据库名）"""
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_db}?charset=utf8mb4"
        )

    @property
    def redis_url(self) -> str:
        """Redis 连接 URL"""
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"


# 全局配置实例
config = Settings()
