import json
import os
import tempfile
from pathlib import Path


def read_json(path: str | Path):
    with open(path, encoding='utf8') as stream:
        return json.load(stream)


def write_json(path: str | Path, data) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        # Replace only after a complete write; the old file survives any failure.
        with tempfile.NamedTemporaryFile(
            mode='w', encoding='utf8', dir=path.parent,
            prefix=f'.{path.name}.', suffix='.tmp', delete=False,
        ) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, ensure_ascii=False, indent=4, allow_nan=False)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
