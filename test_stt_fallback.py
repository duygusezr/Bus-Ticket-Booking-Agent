import asyncio
import sys
import unittest
import io
from unittest.mock import MagicMock, patch, AsyncMock

# Path setup
from pathlib import Path
backend_path = Path(r"c:\Users\pc\Desktop\Bus Ticket Booking Agent\backend")
sys.path.append(str(backend_path))

import services.stt_service as stt_service

class TestSTTFallback(unittest.IsolatedAsyncioTestCase):
    
    @patch("services.stt_service.get_eleven_client")
    @patch("services.stt_service._transcribe_gemini_fallback")
    async def test_stt_fallback_to_gemini(self, mock_gemini, mock_eleven_getter):
        # 1. Setup ElevenLabs to fail (Quota)
        mock_client = MagicMock()
        mock_client.speech_to_text.convert.side_effect = Exception("Unsufficient credits (quota exhausted)")
        mock_eleven_getter.return_value = mock_client
        
        # 2. Setup Gemini Mock Response
        mock_gemini.return_value = {
            "text": "Gemini transcript result",
            "lang": "en"
        }
        
        # 3. Run
        print("\nTesting STT Fallback (Expect logging about ElevenLabs failure)...")
        audio_dummy = b"fake audio data"
        result = await stt_service.transcribe_audio(audio_dummy, "test.webm", lang="en")
        
        # 4. Verify
        self.assertEqual(result["text"], "Gemini transcript result")
        mock_gemini.assert_called_once()
        print("Success: STT successfully fell back to Gemini when ElevenLabs hit quota.")

if __name__ == "__main__":
    unittest.main()
