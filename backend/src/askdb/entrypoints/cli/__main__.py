import argparse

from .app import main


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="python -m askdb.entrypoints.cli",
        description="AskDB V0 · Assistente de consultas PostgreSQL",
    )
    parser.add_argument("--demo", action="store_true", help="usa as três conexões preparadas pela demo")
    raise SystemExit(main(demo=parser.parse_args().demo))
