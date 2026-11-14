"""API contract tests without downloading a speech model.

Run: python -m unittest backend.test_audio_service -v
Real English recognition must additionally be tested with a real model/audio.
"""
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.main import app
from backend import audio_service as audio


class AudioTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def upload(self, data, mime="audio/webm"):
        return self.client.post("/api/v1/audio/transcriptions",
                                files={"file": ("test.webm", data, mime)})

    def test_invalid_uploads(self):
        self.assertEqual(self.upload(b"").status_code, 400)
        self.assertEqual(self.upload(b"text", "text/plain").status_code, 415)
        with patch.dict(os.environ, {"AUDIO_MAX_BYTES": "2"}):
            self.assertEqual(self.upload(b"123").status_code, 413)

    def test_json_contract_with_stub_model(self):
        model = SimpleNamespace(transcribe=lambda *a, **k: (
            iter([SimpleNamespace(text=" maize gene ")]), SimpleNamespace(duration=1)))
        with patch.object(audio, "get_model", return_value=model):
            response = self.upload(b"stub audio")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"text": "maize gene"})

    def test_model_unavailable_and_bad_audio(self):
        with patch.object(audio, "get_model", side_effect=RuntimeError):
            self.assertEqual(self.upload(b"audio").status_code, 503)
        model = SimpleNamespace(transcribe=lambda *a, **k: (_ for _ in ()).throw(ValueError()))
        with patch.object(audio, "get_model", return_value=model):
            self.assertEqual(self.upload(b"corrupt").status_code, 422)


if __name__ == "__main__":
    unittest.main()
