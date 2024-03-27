from pathlib import Path


class Settings:
    PERLND = Path(__file__).resolve().parent / "wwhm_data" / "WWHM_PERLNDs.csv"
    IMPLND = Path(__file__).resolve().parent / "wwhm_data" / "WWHM_IMPLNDs.csv"


settings = Settings()
