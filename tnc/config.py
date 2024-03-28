from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PERLND: Path = Path(__file__).resolve().parent / "wwhm_data" / "WWHM_PERLNDs.csv"
    IMPLND: Path = Path(__file__).resolve().parent / "wwhm_data" / "WWHM_IMPLNDs.csv"
    BS_EVAP: Path = (
        Path(__file__).resolve().parent / "wwhm_data" / "_no_git_bs_evap.csv"
    )
    GOOGLE_APPLICATION_CREDENTIALS_JSON: str = ""
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
