"""CI-only WSGI wrapper for the external production-image smoke test."""

from shazam_project import matcher
from web.app import app as flask_app

app = flask_app


def _mock_match_audio(_clip, _config):
    return {
        "status": "matched",
        "title": "CI Smoke Song",
        "artist": "CI Smoke Artist",
        "backend": "container-smoke",
    }


matcher.match_audio = _mock_match_audio
