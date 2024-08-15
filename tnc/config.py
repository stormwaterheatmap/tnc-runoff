from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PERLND: Path = Path(__file__).resolve().parent / "data" / "WWHM_PERLNDs.csv"
    IMPLND: Path = Path(__file__).resolve().parent / "data" / "WWHM_IMPLNDs.csv"
    TEMP_EVAP: Path = Path(__file__).resolve().parent / "data" / "_temp_evap.csv"
    PET_MM_DAILY: Path = Path(__file__).resolve().parent / "data" / "pet_mm_daily.csv"
    GOOGLE_APPLICATION_CREDENTIALS_JSON: str = ""
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
