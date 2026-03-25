"""Entry point for `python -m vargen` — launches FastAPI backend."""
import argparse
import logging
import uvicorn

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s", datefmt="%H:%M:%S")

parser = argparse.ArgumentParser(description="vargen — AI image pipeline engine")
parser.add_argument("--port", type=int, default=8188)
parser.add_argument("--host", type=str, default="0.0.0.0")
parser.add_argument("--dev", action="store_true", help="Enable auto-reload")
args = parser.parse_args()

uvicorn.run(
    "vargen.api:app",
    host=args.host,
    port=args.port,
    reload=args.dev,
    log_level="info",
)
