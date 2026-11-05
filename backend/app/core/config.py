from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict
from dotenv import load_dotenv


load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Hotel AI Agent Backend"
    app_version: str = "0.1.0"
    debug: bool = True
    database_url: str = "sqlite:///./hotel_agent.db"
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.1:8b"
    ollama_embed_model: str = "bge-m3"
    ollama_num_ctx: int = 8192
    catalog_provider: str = "json"
    catalog_data_dir: str = "./data/catalog"
    catalog_rag_index_dir: str = "./data/vector_index"
    catalog_source_dir: str = "./datasets"


settings = Settings()
