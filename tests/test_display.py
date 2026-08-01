from __future__ import annotations

from unittest.mock import patch

import pytest

from shazam_project.display import show_result


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("not_configured", "not configured"),
        ("invalid_audio", "Invalid audio"),
        ("rate_limited", "Safe message"),
        ("error", "Recognition error"),
        ("no_match", "No match found"),
    ],
)
def test_display_handles_public_failure_statuses(status, expected, capsys):
    show_result({"status": status, "error_code": "stable_code", "error": "Safe message"})

    assert expected in capsys.readouterr().out


def test_display_uses_safe_fallbacks_for_incomplete_metadata(capsys):
    show_result({"status": "matched"}, open_image=False)

    output = capsys.readouterr().out
    assert "Song:   (unknown)" in output
    assert "Artist: (unknown)" in output
    assert "Album:  (unknown)" in output


def test_album_art_failure_is_safe_and_does_not_echo_exception(capsys):
    with patch("shazam_project.display.requests.get", side_effect=RuntimeError("private secret")):
        show_result({"status": "matched", "image": "https://example.test/art.jpg"})

    output = capsys.readouterr().out
    assert "Album art could not be loaded." in output
    assert "private secret" not in output
