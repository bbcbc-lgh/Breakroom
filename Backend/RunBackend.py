from CyberTown.RuntimeStreams import ensure_standard_streams

ensure_standard_streams()

from CyberTown.main import run  # noqa: E402

if __name__ == "__main__":
    run()
