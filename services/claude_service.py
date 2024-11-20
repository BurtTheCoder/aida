# services/claude_service.py
from anthropic import Anthropic, APITimeoutError, RateLimitError
import logging
import asyncio
from typing import Dict, Any, List, Optional
from config.settings import settings
from config.prompts import SYSTEM_PROMPT

class ClaudeService:
    def __init__(self):
        self.client = Anthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=30.0)  # Increased timeout
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
            },
        },
        {
                "name": "search_memories",
                "description": """
                Search through the user's memory for relevant past interactions and information.

                Use this tool when you need to:
                - Recall specific past conversations
                - Check user preferences or information previously shared
                - Maintain consistency with past interactions
                - Reference historical context

                The tool returns relevant memories in chronological order.
                """,
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query to find relevant memories"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of memories to return",
                            "default": 5
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "get_context",
                "description": """
                Retrieve user context from memory to understand preferences and history.

                Use this tool when you need to:
                - Get overall context about the user
                - Understand user preferences
                - Check important historical information
                """,
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "user_id": {
                            "type": "string",
                            "description": "ID of the user to get context for"
                        }
                    }
                }
            }
        ]

    async def _make_request_with_retry(self, func, *args, max_retries=3, **kwargs):
        """Helper method to make requests with retry logic"""
        for attempt in range(max_retries):
            try:
                return await asyncio.wait_for(
                    asyncio.to_thread(func, *args, **kwargs),
                    timeout=30.0
                )
            except (APITimeoutError, RateLimitError) as e:
                if attempt == max_retries - 1:
                    raise
                wait_time = (attempt + 1) * 2
                logging.warning(f"Request failed (attempt {attempt + 1}/{max_retries}), waiting {wait_time}s: {str(e)}")
                await asyncio.sleep(wait_time)
            except Exception as e:
                logging.error(f"Unexpected error in Claude request: {str(e)}")
                raise

    async def handle_message_with_tools(self, message: str, web_search_service: Any, memory_tools: Any, user_id: str) -> str:
        """Process user input using Claude with tool use capabilities"""
        try:
            # Initial response from Claude
            response = await self._make_request_with_retry(
                self.client.messages.create,
                model="claude-3-5-haiku-20241022",
                max_tokens=4096,
                temperature=0.7,
                tools=self.tools,
                tool_choice={"type": "auto"},
                messages=[{
                    "role": "user",
                    "content": message
                }],
                system=SYSTEM_PROMPT
            )

            # If Claude wants to use a tool
            if response.stop_reason == "tool_use":
                logging.info("Tool use requested")
                tool_calls = [content for content in response.content if content.type == 'tool_use']

                if tool_calls:
                    tool_call = tool_calls[0]  # Get the first tool call
                    logging.info(f"Tool Response Request: {tool_calls}")

                    tool_result = None
                    if tool_call.name == "web_search":
                        search_query = tool_call.input["query"]
                        tool_result = await web_search_service.search(search_query)
                    elif tool_call.name == "search_memories":
                        query = tool_call.input["query"]
                        tool_result = await memory_tools.search_memories(query, user_id)
                    elif tool_call.name == "get_context":
                        tool_result = await memory_tools.get_context(user_id)

                    if tool_result:
                        tool_result_content = {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": tool_call.id,
                                    "content": str(tool_result)
                                }
                            ]
                        }

                        # Send tool results back to Claude with proper format
                        final_response = await self._make_request_with_retry(
                            self.client.messages.create,
                            model="claude-3-5-sonnet-20241022",
                            max_tokens=4096,
                            tools=self.tools,
                            messages=[
                                {"role": "user", "content": message},
                                {"role": "assistant", "content": response.content},
                                tool_result_content
                            ],
                            system=SYSTEM_PROMPT
                        )
                        return final_response.content[0].text

            # Return direct response if no tool was used
            return response.content[0].text

        except Exception as e:
            logging.error(f"Error processing input: {e}", exc_info=True)
            return "I apologize, but I encountered an error processing your request. Please try again."
