"""
Conversation Summarizer for ha-realtime-assist

Tracks conversation messages and generates summaries using OpenAI's text models
to extract user preferences and personalization information.
"""

import asyncio
import json
import logging
import os
from typing import List, Dict, Any, Optional
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class ConversationMessage:
    """Represents a single message in the conversation."""
    
    def __init__(self, role: str, content: str, timestamp: float):
        self.role = role  # "user" or "assistant"
        self.content = content
        self.timestamp = timestamp
    
    def to_dict(self) -> Dict[str, str]:
        """Convert to OpenAI chat format."""
        return {"role": self.role, "content": self.content}


class ConversationSummarizer:
    """
    Tracks conversation messages and generates summaries for profile updates.
    
    Monitors conversation activity and automatically triggers summarization
    after a period of silence (e.g., 5 seconds).
    """
    
    def __init__(
        self,
        openai_api_key: str,
        silence_timeout: float = 5.0,
        model: str = "gpt-4o-mini"
    ):
        """
        Initialize the conversation summarizer.
        
        Args:
            openai_api_key: OpenAI API key
            silence_timeout: Seconds of silence before triggering summary
            model: OpenAI model to use for summarization
        """
        self.client = AsyncOpenAI(api_key=openai_api_key)
        self.silence_timeout = silence_timeout
        self.model = model
        
        self.messages: List[ConversationMessage] = []
        self.last_activity_time: float = 0
        self.summary_task: Optional[asyncio.Task] = None
        self.is_active = False
        
        # Callbacks
        self.on_summary_generated = None  # Callback(summary: Dict[str, Any])
    
    def start_conversation(self) -> None:
        """Start a new conversation session."""
        self.messages.clear()
        self.is_active = True
        self.last_activity_time = asyncio.get_event_loop().time()
        logger.info("Started new conversation tracking")
    
    def add_message(self, role: str, content: str) -> None:
        """
        Add a message to the conversation.
        
        Args:
            role: "user" or "assistant"
            content: Message content
        """
        if not self.is_active:
            return
        
        timestamp = asyncio.get_event_loop().time()
        message = ConversationMessage(role, content, timestamp)
        self.messages.append(message)
        self.last_activity_time = timestamp
        
        logger.debug(f"Added {role} message: {content[:50]}...")
        
        # Cancel existing summary task and schedule new one
        if self.summary_task and not self.summary_task.done():
            self.summary_task.cancel()
        
        self.summary_task = asyncio.create_task(self._wait_and_summarize())
    
    async def _wait_and_summarize(self) -> None:
        """Wait for silence timeout, then generate summary."""
        try:
            await asyncio.sleep(self.silence_timeout)
            
            # Check if conversation is still active and has messages
            if self.is_active and len(self.messages) > 0:
                logger.info(f"Silence detected for {self.silence_timeout}s, generating summary...")
                await self._generate_and_deliver_summary()
        
        except asyncio.CancelledError:
            logger.debug("Summary task cancelled (new message received)")
    
    async def _generate_and_deliver_summary(self) -> None:
        """Generate summary and deliver via callback."""
        try:
            summary = await self.generate_summary()
            
            if summary and self.on_summary_generated:
                await self.on_summary_generated(summary)
            
            # End conversation after successful summary
            self.end_conversation()
        
        except Exception as err:
            logger.error(f"Error generating summary: {err}", exc_info=True)
    
    def end_conversation(self) -> None:
        """End the conversation session."""
        self.is_active = False
        
        if self.summary_task and not self.summary_task.done():
            self.summary_task.cancel()
        
        logger.info(f"Ended conversation (tracked {len(self.messages)} messages)")
        self.messages.clear()
    
    async def generate_summary(self) -> Optional[Dict[str, Any]]:
        """
        Generate a summary of the conversation using OpenAI.
        
        Returns:
            dict: Structured summary with preferences, topics, etc.
        """
        if len(self.messages) == 0:
            logger.warning("No messages to summarize")
            return None
        
        # Build conversation history
        conversation = [msg.to_dict() for msg in self.messages]
        
        # System prompt for summarization
        system_prompt = """You are analyzing a conversation to extract user personalization information.

Analyze the conversation and extract:
1. **preferences**: Specific likes, preferences, or choices (as key-value dict)
2. **topics_of_interest**: Topics the user showed interest in (as list)
3. **communication_style**: How the user prefers to communicate (as string)
4. **dislikes**: Things the user explicitly dislikes (as list)
5. **personality_notes**: Notable personality traits or characteristics (as string)

Return ONLY a valid JSON object with these keys. If no information is available for a category, omit that key.
Be specific and concise. Extract only factual information mentioned in the conversation.

Example format:
{
    "preferences": {"temperature_unit": "celsius", "news_sources": ["BBC", "Reuters"]},
    "topics_of_interest": ["artificial intelligence", "home automation"],
    "communication_style": "prefers brief, direct answers",
    "dislikes": ["celebrity gossip"],
    "personality_notes": "curious about technology, enjoys learning"
}"""
        
        try:
            logger.info(f"Calling OpenAI {self.model} to summarize {len(conversation)} messages...")
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Conversation to analyze:\n{json.dumps(conversation, indent=2)}"}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            summary_text = response.choices[0].message.content
            summary = json.loads(summary_text)
            
            logger.info(f"Generated summary with keys: {list(summary.keys())}")
            logger.debug(f"Summary content: {json.dumps(summary, indent=2)}")
            
            return summary
        
        except json.JSONDecodeError as err:
            logger.error(f"Failed to parse summary JSON: {err}")
            return None
        except Exception as err:
            logger.error(f"Error calling OpenAI for summary: {err}", exc_info=True)
            return None
    
    async def force_summary(self) -> Optional[Dict[str, Any]]:
        """
        Force generation of summary immediately (bypass silence timeout).
        
        Returns:
            dict: Summary or None if error
        """
        if len(self.messages) == 0:
            logger.warning("No messages to summarize")
            return None
        
        summary = await self.generate_summary()
        self.end_conversation()
        return summary
