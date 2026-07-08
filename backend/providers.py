import os
import io
import uuid
import asyncio
from abc import ABC, abstractmethod

class VoiceCloneProvider(ABC):
    @abstractmethod
    async def generate(self, text: str, audio_sample_path: str) -> bytes:
        """
        Generates synthetic audio bytes from input text, optionally guided by the participant's voice sample.
        """
        pass

class MockVoiceProvider(VoiceCloneProvider):
    async def generate(self, text: str, audio_sample_path: str) -> bytes:
        """
        Generates a high-quality human-sounding synthetic voice using macOS's native 'say' command.
        Runs entirely offline, zero dependency.
        """
        temp_filename = f"temp_tts_{uuid.uuid4().hex}.wav"
        temp_filepath = os.path.join(os.path.dirname(audio_sample_path), temp_filename)
        
        full_text = f"Fallback demo audio. This does not clone the voice. {text}"
        
        cmd = [
            "say",
            "-o", temp_filepath,
            "--data-format=LEI16@22050",
            full_text
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await process.communicate()
        
        audio_bytes = b""
        if os.path.exists(temp_filepath):
            try:
                with open(temp_filepath, "rb") as f:
                    audio_bytes = f.read()
            finally:
                try:
                    os.remove(temp_filepath)
                except OSError:
                    pass
                    
        return audio_bytes

class BrowserTTSProvider(VoiceCloneProvider):
    async def generate(self, text: str, audio_sample_path: str) -> bytes:
        """
        This provider is client-driven.
        """
        return b""
