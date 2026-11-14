"""Local English transcription; recordings are never logged."""
import os
import tempfile
import threading
from functools import lru_cache
from fastapi import APIRouter, File, HTTPException, UploadFile

router = APIRouter()
_lock = threading.Lock()
TYPES = {"audio/webm", "video/webm", "audio/ogg", "audio/mp4", "audio/wav", "audio/x-wav", "audio/mpeg"}

@lru_cache(maxsize=1)
def get_model():
    from faster_whisper import WhisperModel
    return WhisperModel(os.getenv("WHISPER_MODEL", "base.en"),
        device=os.getenv("WHISPER_DEVICE", "cpu"),
        compute_type=os.getenv("WHISPER_COMPUTE_TYPE", "int8"),
        download_root=os.getenv("WHISPER_CACHE_DIR", None))

@router.post("/api/v1/audio/transcriptions")
def transcribe(file: UploadFile = File(...)):
    path = None
    try:
        if (file.content_type or "").split(";")[0].lower() not in TYPES:
            raise HTTPException(415, "Unsupported audio type")
        limit = int(os.getenv("AUDIO_MAX_BYTES", "10485760"))
        size = 0
        with tempfile.NamedTemporaryFile(delete=False) as target:
            path = target.name
            while chunk := file.file.read(65536):
                size += len(chunk)
                if size > limit:
                    raise HTTPException(413, "Audio exceeds upload limit")
                target.write(chunk)
        if not size:
            raise HTTPException(400, "Empty audio")
        if not _lock.acquire(blocking=False):
            raise HTTPException(429, "Transcription busy; please retry")
        try:
            try:
                model = get_model()
            except Exception:
                raise HTTPException(503, "Speech model unavailable") from None
            try:
                segments, info = model.transcribe(path, language=os.getenv("WHISPER_LANGUAGE", "en"), vad_filter=True)
                if info.duration > float(os.getenv("AUDIO_MAX_SECONDS", "60")):
                    raise HTTPException(413, "Recording exceeds duration limit")
                text = " ".join(s.text.strip() for s in segments).strip()
            except HTTPException:
                raise
            except Exception:
                raise HTTPException(422, "Audio could not be decoded or transcribed") from None
            return {"text": text}
        finally:
            _lock.release()
    finally:
        file.file.close()
        if path:
            os.unlink(path)
