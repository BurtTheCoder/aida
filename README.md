# Aida AI Assistant

Aida is a sophisticated AI assistant that combines voice interaction, text processing, and memory capabilities to provide a natural and context-aware conversational experience.

## ⚠️ Development Status Warning

**IMPORTANT: This project is in early development and is NOT production-ready!**

- 🚧 **Active Development**: This project is under heavy development and changes frequently
- 🐛 **Bugs Expected**: You will encounter bugs, crashes, and incomplete features
- ⚗️ **Experimental**: Many features are experimental and may not work as expected
- 🔧 **Breaking Changes**: Updates may include breaking changes without notice
- ⚡ **Unstable**: Core functionality may be unstable or entirely non-functional

### Known Limitations
- Voice recognition may be unreliable
- Memory system is experimental and slow
- Limited error handling
- Incomplete documentation

**Use at your own risk! This is currently a proof-of-concept and learning project.**

## Features

- Voice and text interaction modes
- Wake word detection ("Jarvis")
- Real-time speech-to-text processing
- Natural text-to-speech responses
- Long-term memory and context awareness
- Web search capabilities
- Conversation history management
- Multi-user support

## Prerequisites

- Python 3.10+
- Docker (for Qdrant vector database)
- Required API keys:
  - ElevenLabs (TTS)
  - Deepgram (STT)
  - Picovoice (Wake word)
  - Anthropic Claude (LLM)
  - Perplexity (Web search)
  - OpenAI (Embeddings)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/BurtTheCoder/aida.git
cd aida
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Unix/macOS
# or
.\venv\Scripts\activate  # Windows
```

3. Install required packages:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your API keys
```

5. Start Qdrant database:
```bash
cd storage
docker-compose up -d
```

6. Initialize memory system:
```bash
python setup_memory.py
```

## Usage

### Running the Assistant

Basic usage:
```bash
python main.py
```

Available command-line arguments:
- `--mode`: Choose between 'voice' or 'text' mode (default: voice)
- `--debug`: Enable debug logging
- `--no-tts`: Disable text-to-speech in text mode
- `--user-id`: Specify user ID for memory persistence

Examples:
```bash
# Run in text mode
python main.py --mode text

# Run with debug logging
python main.py --debug

# Run for specific user
python main.py --user-id user123
```

### Project Structure

```
aida/
├── config/            # Configuration files
├── core/              # Core functionality
├── modes/             # Interaction modes
├── services/          # Service implementations
├── storage/           # Database and persistence
├── tools/             # Agent Tools
├── utils/             # Helper utilities
└── main.py            # Entry point
```

## Core Components

### Assistant (core/assistant.py)
- Main assistant logic
- Tool management
- Input processing

### Memory System (services/memory_service.py)
- Long-term memory storage
- Context retrieval
- Memory management

### Voice Processing
- Wake word detection (services/wake_word.py)
- Speech-to-text (services/stt_service.py)
- Text-to-speech (services/tts_service.py)

### Tools
- Web search (tools/web_search.py)
- Memory operations (tools/memory_tools.py)

## Development

### Adding New Features

1. Create new service in `services/`
2. Add configuration in `config/`
3. Implement tool in `tools/` if needed
4. Update assistant to use new feature

### Testing

Run tests:
```bash
python -m pytest tests/
```

### Logging

Logs are handled by the custom logging system in `utils/logging.py`. Enable debug logging with the `--debug` flag.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit changes
4. Submit pull request


## Acknowledgments

- ElevenLabs for TTS
- Deepgram for STT
- Anthropic for Claude AI
- Picovoice for wake word detection
- Qdrant for vector storage
