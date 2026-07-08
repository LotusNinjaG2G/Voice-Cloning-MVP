import re
import io
import wave
import math
import struct
from typing import Tuple, List

FINANCIAL_PATTERNS = [
    r"authorize\s+payment",
    r"approve\s+transaction",
    r"confirm\s+transfer",
    r"wire\s+money",
    r"credit\s+card",
    r"bank\s+account",
    r"send\s+payment",
    r"pay\s+now",
    r"transfer\s+funds",
    r"wire\s+transfer",
    r"wire\s+funds",
    r"bank\s+transfer",
    r"send\s+money",
    r"transfer\s+money",
    r"pay\s+me",
    r"routing\s+number",
    r"swift\s+code",
]

URGENCY_PATTERNS = [
    r"send\s+money\s+now",
    r"send\s+money\s+immediately",
    r"urgent\s+transfer",
    r"transfer\s+money\s+now",
    r"immediately\s+transfer",
    r"quick\s+payment",
    r"need\s+cash\s+now",
]

CREDENTIAL_PATTERNS = [
    r"verification\s+code",
    r"one-time\s+password",
    r"otp",
    r"security\s+code",
    r"2fa",
    r"two-factor",
    r"pin\s+number",
    r"my\s+pin\s+is",
    r"your\s+pin\s+is",
    r"password\s+is",
    r"access\s+code\s+is",
    r"login\s+credentials",
]

PUBLIC_FIGURES = [
    r"president\s+biden",
    r"president\s+trump",
    r"president\s+obama",
    r"elon\s+musk",
    r"donald\s+trump",
    r"joe\s+biden",
    r"taylor\s+swift",
    r"bill\s+gates",
    r"barack\s+obama",
    r"senator",
    r"congressman",
    r"governor",
    r"ceo\s+of",
]

def check_content_policy(text: str, current_participant_name: str, all_participant_names: List[str]) -> Tuple[bool, str]:
    """
    Checks the input text against the content security policy rules.
    Returns (is_blocked, reason)
    """
    text_lower = text.lower()
    
    # 1. Financial check
    for pattern in FINANCIAL_PATTERNS:
        if re.search(pattern, text_lower):
            return True, f"Blocked: Contains financial authorization language ('{pattern.replace(chr(92), '')}')"
            
    # 2. Urgency check
    for pattern in URGENCY_PATTERNS:
        if re.search(pattern, text_lower):
            return True, f"Blocked: Contains urgent request/financial prompt ('{pattern.replace(chr(92), '')}')"
            
    # 3. Credentials check
    for pattern in CREDENTIAL_PATTERNS:
        if re.search(pattern, text_lower):
            return True, f"Blocked: Contains sensitive credentials or security code words ('{pattern.replace(chr(92), '')}')"
            
    # 4. Public figure check
    for pattern in PUBLIC_FIGURES:
        if re.search(pattern, text_lower):
            return True, f"Blocked: Request attempts to impersonate a public figure ('{pattern.replace(chr(92), '')}')"
            
    # 5. Impersonation of someone not in the session's participant list
    # Look for "I am [Name]", "This is [Name]", "Speaking as [Name]"
    impersonation_phrases = [
        r"i\s+am\s+([a-zA-Z\s]+)",
        r"this\s+is\s+([a-zA-Z\s]+)",
        r"speaking\s+as\s+([a-zA-Z\s]+)"
    ]
    
    for phrase in impersonation_phrases:
        matches = re.findall(phrase, text_lower)
        for match in matches:
            name_mentioned = match.strip()
            name_words = name_mentioned.split()
            if not name_words:
                continue
            # Check up to 2 words
            for i in range(1, min(len(name_words) + 1, 3)):
                candidate = " ".join(name_words[:i]).strip()
                if candidate in ["a", "the", "an", "here", "ready", "speaking"]:
                    continue
                matches_any_participant = any(candidate == p.lower() for p in all_participant_names)
                if not matches_any_participant:
                    return True, f"Blocked: Request attempts to impersonate a person ('{candidate}') who is not in the participant list."
                    
    # 6. Selected participant tries to impersonate another participant in the session
    for p_name in all_participant_names:
        if p_name.lower() != current_participant_name.lower():
            for phrase in [f"i am {p_name.lower()}", f"this is {p_name.lower()}", f"speaking as {p_name.lower()}"]:
                if phrase in text_lower:
                    return True, f"Blocked: Selected participant '{current_participant_name}' cannot impersonate another participant '{p_name}'."
                    
    return False, ""

def generate_sine_pcm(freq: float, duration: float, sample_rate: int, channels: int, sample_width: int, volume: float = 0.4) -> bytes:
    num_samples = int(sample_rate * duration)
    data = bytearray()
    for i in range(num_samples):
        t = i / sample_rate
        val = int(volume * 32767 * math.sin(2 * math.pi * freq * t))
        if sample_width == 2:
            packed = struct.pack('<h', val)
        elif sample_width == 1:
            val_8 = int((val + 32768) / 256)
            packed = struct.pack('<B', val_8)
        else:
            packed = struct.pack('<h', val)
        for _ in range(channels):
            data.extend(packed)
    return bytes(data)

def generate_silence_pcm(duration: float, sample_rate: int, channels: int, sample_width: int) -> bytes:
    num_samples = int(sample_rate * duration)
    frame_size = channels * sample_width
    return b'\x00' * (num_samples * frame_size)

def add_watermark_to_wav(wav_bytes: bytes) -> bytes:
    """
    Parses a WAV file, generates a dual-beep sine wave watermark,
    prepends it, and returns the modified WAV file bytes.
    """
    try:
        with wave.open(io.BytesIO(wav_bytes), 'rb') as wav_in:
            params = wav_in.getparams()
            n_channels = params.nchannels
            sampwidth = params.sampwidth
            framerate = params.framerate
            n_frames = params.nframes
            pcm_data = wav_in.readframes(n_frames)
    except Exception:
        # Fallback default parameters if not a valid WAV
        n_channels = 1
        sampwidth = 2
        framerate = 22050
        pcm_data = wav_bytes

    # Generate watermarking tone: double-beep (beep, silence, beep)
    beep_duration = 0.15
    silence_duration = 0.1
    frequency = 880  # distinct high pitch tone
    
    watermark_pcm = bytearray()
    watermark_pcm.extend(generate_sine_pcm(frequency, beep_duration, framerate, n_channels, sampwidth))
    watermark_pcm.extend(generate_silence_pcm(silence_duration, framerate, n_channels, sampwidth))
    watermark_pcm.extend(generate_sine_pcm(frequency, beep_duration, framerate, n_channels, sampwidth))
    watermark_pcm.extend(generate_silence_pcm(silence_duration, framerate, n_channels, sampwidth))
    
    combined_pcm = bytes(watermark_pcm) + pcm_data
    
    out_io = io.BytesIO()
    with wave.open(out_io, 'wb') as wav_out:
        wav_out.setnchannels(n_channels)
        wav_out.setsampwidth(sampwidth)
        wav_out.setframerate(framerate)
        wav_out.writeframes(combined_pcm)
        
    return out_io.getvalue()
