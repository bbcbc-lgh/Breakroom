from src.RuntimeStreams import ensure_standard_streams

ensure_standard_streams()

from src.main import run  # noqa: E402

if __name__ == "__main__":
    run()
