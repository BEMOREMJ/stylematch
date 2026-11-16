"""Synthetic range-transfer checks; no public network or private data reads."""
from hashlib import sha256
from io import BytesIO

import pytest

from scripts.download_vlm import ranged_download


def test_zip_resume_reuses_complete_prefix_and_verifies_whole_artifact(tmp_path, monkeypatch):
    chunk = 1024 * 1024
    content = b'a' * chunk + b'b' * chunk + b'last bytes'
    path = tmp_path / 'runtime.zip'
    prefix = path.with_suffix('.zip.partial')
    prefix.write_bytes(content[:chunk + 13])
    requested = []

    class Response(BytesIO):
        status = 206

    def fetch(request, timeout):
        start, end = map(int, request.get_header('Range').removeprefix('bytes=').split('-'))
        requested.append(start)
        response = Response(content[start:end + 1])
        response.headers = {'Content-Range': f'bytes {start}-{end}/{len(content)}'}
        return response

    monkeypatch.setattr('scripts.download_vlm.urllib.request.urlopen', fetch)
    ranged_download('https://publisher.invalid/runtime.zip', path,
                    {'bytes': len(content), 'sha256': sha256(content).hexdigest()})
    assert path.read_bytes() == content
    assert sorted(requested) == [chunk, 2 * chunk]
    assert prefix.read_bytes() == content[:chunk + 13]


def test_range_header_mismatch_never_creates_loadable_artifact(tmp_path, monkeypatch):
    path = tmp_path / 'model.gguf'

    class Response(BytesIO):
        status = 200
        headers = {}

    monkeypatch.setattr('scripts.download_vlm.urllib.request.urlopen', lambda *a, **k: Response(b'wrong'))
    with pytest.raises(ValueError, match='exact range'):
        ranged_download('https://publisher.invalid/model.gguf', path,
                        {'bytes': 5, 'sha256': sha256(b'wrong').hexdigest()})
    assert not path.exists()
