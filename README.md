# aida
AI Digital Assistant


# Project Structure

.
├── README.md
├── config
│   ├── __init__.py
│   ├── prompts.py
│   └── settings.py
├── core
│   ├── __init__.py
│   ├── assistant.py
│   ├── audio_manager.py
│   └── websocket_client.py
├── main.py
├── modes
│   ├── __init__.py
│   ├── text_mode.py
│   └── voice_mode.py
├── requirements.txt
├── services
│   ├── __init__.py
│   ├── claude_service.py
│   ├── stt_service.py
│   ├── tts_service.py
│   └── wake_word.py
├── tests
│   ├── __init__.py
│   ├── test_assistant.py
│   ├── test_audio.py
│   └── test_services.py
├── tools
│   └── web_search.py
└── utils
    ├── __init__.py
    ├── cleanup.py
    ├── logging.py
    └── timer.py