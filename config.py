from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    llm_provider: str = "groq"
    llm_model: str = "llama-3.3-70b-versatile"
    groq_api_key: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db: str = "vas_db"
    mongodb_collection: str = "orders1"
    export_output_dir: str = "./exports"
    fields_to_compare: str = "amount,status"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()

# Configurable column name mapping for partner Excel files.
# Keys are possible incoming column names (lowercase), values are canonical names.
PARTNER_COLUMN_MAP = {
    "reference": "referenceId",
    "reference_id": "referenceId",
    "ref_id": "referenceId",
    "transaction_id": "referenceId",
    "referenceid": "referenceId",
    "txn_amount": "amount",
    "amount": "amount",
    "txn_status": "status",
    "status": "status",
    "date": "timestamp",
    "created_at": "timestamp",
    "timestamp": "timestamp",
}


def get_llm():
    """Factory for LLM client. Imports are lazy to avoid requiring all provider packages."""
    provider = settings.llm_provider.lower()
    if provider == "groq":
        from langchain_groq import ChatGroq
        if not settings.groq_api_key:
            raise ValueError("GROQ_API_KEY is required when LLM_PROVIDER=groq")
        return ChatGroq(model=settings.llm_model, api_key=settings.groq_api_key)
    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic")
        return ChatAnthropic(model=settings.llm_model, api_key=settings.anthropic_api_key)
    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        return ChatOpenAI(model=settings.llm_model, api_key=settings.openai_api_key)
    else:
        raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")


def get_fields_to_compare() -> list[str]:
    return [f.strip() for f in settings.fields_to_compare.split(",")]
