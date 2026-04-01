import asyncio
import sys
import unittest
from unittest.mock import MagicMock, patch, AsyncMock

# Path setup
from pathlib import Path
backend_path = Path(r"c:\Users\pc\Desktop\Bus Ticket Booking Agent\backend")
sys.path.append(str(backend_path))

import services.tts_service as tts_service

class TestTTSResilience(unittest.IsolatedAsyncioTestCase):
    
    @patch("services.tts_service.get_eleven_client")
    @patch("services.tts_service.edge_tts.Communicate")
    async def test_graceful_degradation(self, mock_edge, mock_eleven):
        # Setup mocks to fail
        mock_eleven.return_value = None # No ElevenLabs
        
        # Proper async generator mock for edge_tts
        async def mock_stream():
            raise Exception("503 Service Unavailable")
            yield # To make it a generator
            
        mock_comm = MagicMock()
        mock_comm.stream.side_effect = mock_stream
        mock_edge.return_value = mock_comm
        
        # Run
        print("\nTesting TTS Resilience (Expect logging about failures)...")
        result = await tts_service.generate_tts("Hello world", lang="en")
        
        # Verify
        self.assertEqual(result, "", "Result should be empty string on total failure")
        print("Success: generate_tts returned empty string instead of crashing.")

if __name__ == "__main__":
    unittest.main()
