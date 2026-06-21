try:
    from dotenv import load_dotenv as _load_dotenv
except ModuleNotFoundError:
    def _load_dotenv(*args, **kwargs):
        return False


_load_dotenv()

from app.main import main


if __name__ == "__main__":
    raise SystemExit(main())
