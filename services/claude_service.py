# services/claude_service.py
from anthropic import Anthropic
import logging
from typing import Dict, Any, List, Optional
from config.settings import settings
from config.prompts import SYSTEM_PROMPT

class ClaudeService:
    """Service for handling Claude/Anthropic API interactions"""
    
    def __init__(self):
        self.client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.tools = [{
            "name": "web_search",
            "description": """
            A tool for retrieving current, real-time information from the web.

            WHEN TO USE:
            - Current weather conditions and forecasts
            - Recent news and events
            - Current prices or market data
            - Ongoing or upcoming events
            - Time-sensitive information
            - Facts that may have changed since training
            - Research the latest information about a topic

            WHEN NOT TO USE:
            - Historical facts or general knowledge
            - Basic definitions or concepts
            - Theoretical discussions
            - Simple conversational responses
            - Information that doesn't require real-time updates

            The tool returns current information from reliable web sources.
            Use the information naturally in conversation without explicitly mentioning the search unless asked.
            """,
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "A specific, focused search query for current information"
                    }
                },
                "required": ["query"]
            }
        }]

    async def process_message(
        self, 
        message: str, 
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7
    ) -> str:
        """
        Process a message using Claude with optional conversation history
        """
        try:
            # Build messages list
            messages = []
            if conversation_history:
                messages.extend(conversation_history)
            messages.append({
                "role": "user",
                "content": message
            })

            # Initial response from Claude
            response = self.client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=4096,
                temperature=temperature,
                tools=self.tools,
                tool_choice={"type": "auto"},
                messages=messages,
                system=SYSTEM_PROMPT
            )

            return response.content[0].text, response

        except Exception as e:
            logging.error(f"Error in Claude service: {e}", exc_info=True)
            return "I apologize, but I encountered an error processing your request.", None

    async def process_tool_response(
        self,
        original_message: str,
        first_response: Any,
        tool_result: str,
        tool_call_id: str
    ) -> str:
        """
        Process tool response with Claude
        """
        try:
            final_response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4096,
                tools=self.tools,
                messages=[
                    {"role": "user", "content": original_message},
                    {"role": "assistant", "content": first_response.content},
                    {
                        "role": "user",
                        "content": [{
                            "type": "tool_result",
                            "tool_use_id": tool_call_id,
                            "content": str(tool_result)
                        }]
                    }
                ],
                system=SYSTEM_PROMPT
            )
            
            return final_response.content[0].text

        except Exception as e:
            logging.error(f"Error processing tool response: {e}", exc_info=True)
            return "I apologize, but I encountered an error processing the tool response."

    async def handle_message_with_tools(
        self, 
        message: str,
        web_search_service: Any
    ) -> str:
        """
        Handle message processing with potential tool use
        """
        response_text, first_response = await self.process_message(message)
        
        # Check if tool use is requested
        if first_response and first_response.stop_reason == "tool_use":
            tool_calls = [content for content in first_response.content if content.type == 'tool_use']
            
            if tool_calls:
                tool_call = tool_calls[0]  # Get the first tool call
                
                if tool_call.name == "web_search":
                    search_query = tool_call.input["query"]
                    logging.info(f"Web search query: {search_query}")
                    
                    # Execute web search
                    tool_result = await web_search_service.search(search_query)
                    logging.info(f"Web search result: {tool_result}")
                    
                    # Process with tool result
                    response_text = await self.process_tool_response(
                        message,
                        first_response,
                        tool_result,
                        tool_call.id
                    )

        return response_text

    async def get_conversation_context(
        self,
        conversation_history: List[Dict[str, Any]]
    ) -> str:
        """
        Generate conversation context from history
        """
        try:
            response = self.client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=1000,
                messages=[{
                    "role": "user",
                    "content": "Please analyze our conversation so far and provide a brief context of what we've been discussing."
                }] + conversation_history,
                system=SYSTEM_PROMPT
            )
            
            return response.content[0].text

        except Exception as e:
            logging.error(f"Error getting conversation context: {e}")
            return ""

    def format_system_prompt(self, additional_instructions: Optional[str] = None) -> str:
        """
        Format system prompt with optional additional instructions
        """
        prompt = SYSTEM_PROMPT
        if additional_instructions:
            prompt += f"\n\nAdditional Instructions:\n{additional_instructions}"
        return prompt

    def validate_message(self, message: str) -> bool:
        """
        Validate message before sending to API
        """
        if not message or not message.strip():
            return False
        if len(message) > 4000:  # Arbitrary limit
            logging.warning("Message exceeds recommended length")
        return True