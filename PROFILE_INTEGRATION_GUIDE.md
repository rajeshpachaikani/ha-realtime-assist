# Profile Integration Guide

This guide explains how to integrate automatic conversation summarization and profile updates into ha-realtime-assist.

## Overview

The integration adds two new modules:
1. **ha_profile_client.py** - Communicates with Home Assistant's personalized_ai services
2. **conversation_summarizer.py** - Tracks conversations and generates summaries using OpenAI text models

## Architecture

```
User speaks -> VoiceAssistant tracks messages -> 5 seconds silence -> 
Summarizer generates profile updates -> Profile Client updates HA -> Session ends
```

## Integration Steps

### 1. Add Configuration

Add to your `.env` file (or environment):
```bash
# Home Assistant Profile Integration
HA_URL=http://homeassistant.local:8123
HA_TOKEN=your_long_lived_access_token_here

# Conversation Summarization Settings
PROFILE_SILENCE_TIMEOUT=5.0  # Seconds of silence before summarizing
PROFILE_SUMMARY_MODEL=gpt-4o-mini  # OpenAI model for summarization
```

### 2. Initialize Components in VoiceAssistant.__init__()

Add these imports at the top of `main.py`:
```python
from ha_profile_client import HAProfileClient
from conversation_summarizer import ConversationSummarizer
```

Add these attributes to `VoiceAssistant.__init__()`:
```python
# Profile and summarization components
self.profile_client: Optional[HAProfileClient] = None
self.conversation_summarizer: Optional[ConversationSummarizer] = None
```

### 3. Initialize in _initialize_components()

Add to the `_initialize_components()` method:
```python
# Initialize profile client if configured
ha_url = os.getenv("HA_URL")
ha_token = os.getenv("HA_TOKEN")

if ha_url and ha_token:
    self.profile_client = HAProfileClient(ha_url, ha_token)
    
    # Initialize conversation summarizer
    silence_timeout = float(os.getenv("PROFILE_SILENCE_TIMEOUT", "5.0"))
    summary_model = os.getenv("PROFILE_SUMMARY_MODEL", "gpt-4o-mini")
    
    self.conversation_summarizer = ConversationSummarizer(
        openai_api_key=self.config.openai.api_key,
        silence_timeout=silence_timeout,
        model=summary_model
    )
    
    # Set callback for when summary is generated
    self.conversation_summarizer.on_summary_generated = self._on_profile_summary
    
    self.logger.info(f"Profile integration enabled (silence_timeout={silence_timeout}s)")
else:
    self.logger.info("Profile integration disabled (HA_URL or HA_TOKEN not set)")
```

### 4. Add Callback Handler

Add this method to `VoiceAssistant`:
```python
async def _on_profile_summary(self, summary: Dict[str, Any]) -> None:
    """
    Handle generated conversation summary.
    
    Called by ConversationSummarizer when a conversation ends after silence.
    Merges the summary into the user's profile in Home Assistant.
    """
    try:
        self.logger.info(f"Received conversation summary with keys: {list(summary.keys())}")
        
        if not self.profile_client:
            self.logger.warning("Profile client not initialized, cannot update profile")
            return
        
        # Merge summary into profile
        success = await self.profile_client.merge_profile(summary)
        
        if success:
            self.logger.info("Successfully updated user profile with conversation learnings")
        else:
            self.logger.error("Failed to update user profile")
    
    except Exception as err:
        self.logger.error(f"Error handling profile summary: {err}", exc_info=True)
```

### 5. Track Conversation Start

When a session starts (wake word detected), start conversation tracking:
```python
# In your wake word detection handler or session start:
if self.conversation_summarizer:
    self.conversation_summarizer.start_conversation()
    self.logger.debug("Started conversation tracking for profile learning")
```

### 6. Track User Messages

When user speech is transcribed, add to conversation:
```python
# After transcription is available:
if self.conversation_summarizer and user_transcript:
    self.conversation_summarizer.add_message("user", user_transcript)
    self.logger.debug(f"Tracked user message: {user_transcript[:50]}...")
```

### 7. Track Assistant Responses

When assistant responds, add to conversation:
```python
# After assistant response is generated:
if self.conversation_summarizer and assistant_response:
    self.conversation_summarizer.add_message("assistant", assistant_response)
    self.logger.debug(f"Tracked assistant response: {assistant_response[:50]}...")
```

### 8. Cleanup on Stop

Add cleanup in `_cleanup_components()`:
```python
# Close profile client
if self.profile_client:
    await self.profile_client.close()
    self.logger.info("Profile client closed")
```

## How It Works

1. **Conversation Starts**: When wake word is detected, `start_conversation()` is called
2. **Messages Tracked**: User input and assistant responses are added via `add_message()`
3. **Silence Detection**: After each message, a 5-second timer starts
4. **Summary Generation**: If 5 seconds pass without new messages, OpenAI generates a summary
5. **Profile Update**: The summary is automatically merged into the HA profile via services
6. **Session Ends**: Conversation tracking resets, ready for next session

## Testing

1. **Check Logs**: Look for "Started conversation tracking" and "Generated summary" messages
2. **Verify Updates**: Check HA Developer Tools > Services > personalized_ai.get_user_profile
3. **Monitor Silence**: Speak, wait 5 seconds, check logs for summarization

## Example Summary Output

```json
{
  "preferences": {
    "temperature_unit": "celsius",
    "news_topics": ["technology", "AI"]
  },
  "topics_of_interest": ["home automation", "artificial intelligence"],
  "communication_style": "prefers brief, direct answers",
  "dislikes": ["loud music late at night"],
  "personality_notes": "curious about new technology, values privacy"
}
```

## Troubleshooting

### No Summaries Generated
- Check that messages are being added (look for "Tracked user/assistant message" logs)
- Verify silence timeout is sufficient
- Ensure OpenAI API key is valid

### Profile Not Updating
- Verify HA_URL and HA_TOKEN are correct
- Check Home Assistant logs for service call errors
- Test services manually in HA Developer Tools

### Summary Quality Issues
- Try different OpenAI models (gpt-4o-mini, gpt-4, gpt-3.5-turbo)
- Adjust temperature in conversation_summarizer.py (currently 0.3)
- Ensure conversations have enough context (multiple exchanges)

## Advanced: Load Profile into System Prompt

To use the profile in your personality prompt:
```python
if self.profile_client:
    profile_context = await self.profile_client.get_profile_as_system_prompt()
    enhanced_prompt = base_prompt + profile_context
```

This adds user preferences to every conversation, creating truly personalized interactions.
