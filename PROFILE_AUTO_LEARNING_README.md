# Automatic Profile Learning Integration

## Overview

This integration adds **automatic profile learning** to ha-realtime-assist. After each conversation, the system:

1. **Detects silence** (5 seconds by default)
2. **Generates a summary** using OpenAI text models
3. **Updates your profile** in Home Assistant automatically
4. **No manual input required** - learns from natural conversations

## What Gets Learned

The system extracts and stores:

- **Preferences**: Specific likes/choices (e.g., "prefers lights dimmed to 50%")
- **Topics of Interest**: Subjects you discuss often
- **Communication Style**: How you prefer to communicate
- **Dislikes**: Things you explicitly don't like
- **Personality Notes**: Your characteristics and traits

## Files Added

```
ha-realtime-assist/src/
├── ha_profile_client.py           # Communicates with Home Assistant
├── conversation_summarizer.py      # Tracks conversations and generates summaries
└── (main.py modifications)         # Integration hooks

ha-realtime-assist/
├── PROFILE_INTEGRATION_GUIDE.md   # Detailed integration steps
├── integration_patch.py            # Exact code changes needed
└── example_conversation_summary.py # Testing example
```

## Quick Start

### 1. Prerequisites

✅ Home Assistant with `personalized_ai` custom component installed  
✅ Long-lived access token from Home Assistant  
✅ OpenAI API key (already configured in ha-realtime-assist)

### 2. Add Environment Variables

Add to `.env` file:
```bash
# Home Assistant Connection
HA_URL=http://homeassistant.local:8123
HA_TOKEN=your_long_lived_access_token

# Conversation Settings (optional)
PROFILE_SILENCE_TIMEOUT=5.0         # Seconds before summarizing
PROFILE_SUMMARY_MODEL=gpt-4o-mini   # OpenAI model to use
```

### 3. Apply Integration

Follow **ONE** of these methods:

#### Method A: Automatic (Recommended)
```bash
cd ha-realtime-assist
python integration_patch.py  # Shows all changes needed
```

Then manually apply the changes shown in `integration_patch.py` to `src/main.py`.

#### Method B: Manual Integration
Follow step-by-step instructions in `PROFILE_INTEGRATION_GUIDE.md`.

### 4. Test It

```bash
# Test profile client
python example_conversation_summary.py profile

# Test full conversation flow
python example_conversation_summary.py
```

## How It Works

### Conversation Flow

```
┌─────────────────────────────────────────────────────────┐
│  1. Wake Word Detected                                   │
│     → Start conversation tracking                        │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  2. User Speaks: "Turn on the lights"                   │
│     → Track message: ("user", "Turn on the lights")     │
│     → Start 5-second timer                              │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  3. Assistant Responds: "Lights are on"                 │
│     → Track message: ("assistant", "Lights are on")     │
│     → Reset 5-second timer                              │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  4. User: "Actually, I prefer them dimmed"              │
│     → Track message                                      │
│     → Reset timer                                        │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  5. Assistant: "Dimmed to 50%. I'll remember that"      │
│     → Track message                                      │
│     → Reset timer                                        │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  6. Silence (5 seconds)                                  │
│     → Timer expires                                      │
│     → Generate summary with OpenAI                       │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  7. Summary Generated                                    │
│     {                                                    │
│       "preferences": {                                   │
│         "lighting_level": "50% dimmed"                  │
│       }                                                  │
│     }                                                    │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  8. Update Home Assistant Profile                        │
│     → Call personalized_ai.merge_user_profile           │
│     → Profile updated with new preferences              │
└─────────────────────────────────────────────────────────┘
```

### Technical Details

**Conversation Summarizer**
- Tracks all user/assistant messages during a session
- Implements a silence detection timer (default 5 seconds)
- Timer resets with each new message
- When timer expires, calls OpenAI text API for summarization
- Uses structured JSON output for profile fields

**Profile Client**
- Async HTTP client using aiohttp
- Communicates with Home Assistant REST API
- Calls `personalized_ai` services (get/update/merge)
- Handles authentication via long-lived token
- Implements proper cleanup and session management

**Integration Points in main.py**
1. Initialize components in `_initialize_components()`
2. Start tracking in wake word/session start handler
3. Track user messages in transcription handler
4. Track assistant messages in response handler
5. Cleanup in `_cleanup_components()`

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `HA_URL` | Yes | - | Home Assistant URL |
| `HA_TOKEN` | Yes | - | Long-lived access token |
| `PROFILE_SILENCE_TIMEOUT` | No | 5.0 | Seconds of silence before summary |
| `PROFILE_SUMMARY_MODEL` | No | gpt-4o-mini | OpenAI model for summaries |

### Silence Timeout Tuning

- **Too short** (< 3s): May trigger during natural pauses
- **Too long** (> 10s): User may leave before summary
- **Recommended**: 5-7 seconds for natural conversation

### Model Selection

| Model | Cost | Quality | Speed |
|-------|------|---------|-------|
| gpt-4o-mini | Lowest | Good | Fast |
| gpt-4o | Medium | Better | Fast |
| gpt-4 | Highest | Best | Slow |

## Examples

### Example 1: Learning Preferences

**Conversation:**
```
User: "Turn on the bedroom lights"
Assistant: "Bedroom lights are on"
User: "Actually, I always want them at 30% at night"
Assistant: "Got it! I've set them to 30%. I'll remember that for nighttime."
[5 seconds silence]
```

**Generated Summary:**
```json
{
  "preferences": {
    "bedroom_lights_night": "30%"
  },
  "personality_notes": "prefers dimmed bedroom lights at night"
}
```

### Example 2: Learning Topics

**Conversation:**
```
User: "What's the latest in artificial intelligence?"
Assistant: "Recent AI news includes..."
User: "Tell me more about machine learning"
Assistant: "Machine learning is..."
[5 seconds silence]
```

**Generated Summary:**
```json
{
  "topics_of_interest": [
    "artificial intelligence",
    "machine learning"
  ]
}
```

### Example 3: Learning Dislikes

**Conversation:**
```
User: "Play some music"
Assistant: "I'll play jazz music"
User: "No, I don't like jazz"
Assistant: "Understood! I won't play jazz. What would you prefer?"
User: "I prefer classical"
[5 seconds silence]
```

**Generated Summary:**
```json
{
  "preferences": {
    "music_genre": "classical"
  },
  "dislikes": ["jazz music"]
}
```

## Troubleshooting

### No Summaries Being Generated

**Symptom**: Conversations happen but no profile updates

**Check:**
1. Verify environment variables are set correctly
2. Look for "Started conversation tracking" in logs
3. Ensure OpenAI API key is valid
4. Check that messages are being tracked (look for "Tracked user/assistant" logs)

**Common Issues:**
- `HA_URL` or `HA_TOKEN` not set → Integration disabled
- OpenAI API key invalid → Summarization fails
- No messages tracked → Check integration hooks in main.py

### Profile Not Updating

**Symptom**: Summaries generated but profile doesn't change

**Check:**
1. Test profile client: `python example_conversation_summary.py profile`
2. Check Home Assistant logs for service call errors
3. Verify token has permissions to call services
4. Test manually in HA Developer Tools

**Common Issues:**
- Invalid HA_TOKEN → Authentication fails
- Wrong HA_URL → Connection refused
- personalized_ai not installed → Service not found

### Summary Quality Issues

**Symptom**: Summaries don't capture the right information

**Solutions:**
1. Try different models (gpt-4o, gpt-4)
2. Ensure conversations have multiple exchanges
3. Check system prompt in `conversation_summarizer.py`
4. Adjust temperature parameter (currently 0.3)

### Integration Not Working

**Symptom**: Errors when starting ha-realtime-assist

**Check:**
1. Verify all files are in correct locations
2. Check imports at top of main.py
3. Look for syntax errors in integration code
4. Ensure Python dependencies are installed (aiohttp, openai)

**Install Dependencies:**
```bash
pip install aiohttp openai
```

## Performance Considerations

### API Costs

**Per Conversation (typical):**
- Input tokens: ~500-1000 (conversation + system prompt)
- Output tokens: ~200-300 (JSON summary)
- Cost: ~$0.01-0.02 per conversation (with gpt-4o-mini)

**Monthly estimate (10 conversations/day):**
- ~$3-6/month

### Latency

- Silence detection: ~5 seconds
- Summary generation: ~2-3 seconds
- Profile update: < 1 second
- **Total overhead**: ~7-9 seconds after conversation ends

### Resource Usage

- Memory: ~10MB for message tracking
- CPU: Minimal (idle during conversation)
- Network: One API call per conversation

## Advanced Usage

### Loading Profile into Personality

Add to your personality generation in main.py:

```python
async def _generate_device_aware_personality(self) -> str:
    base_prompt = self.personality.generate_prompt()
    
    # Add profile context
    if self.profile_client:
        profile_context = await self.profile_client.get_profile_as_system_prompt()
        base_prompt += profile_context
    
    return base_prompt
```

This makes the assistant aware of user preferences from the start.

### Manual Summary Trigger

Force a summary without waiting for silence:

```python
if self.conversation_summarizer:
    summary = await self.conversation_summarizer.force_summary()
```

### Custom Summary Processing

Override the callback to add custom logic:

```python
async def _on_profile_summary(self, summary: Dict[str, Any]) -> None:
    # Custom processing
    self.logger.info(f"Got summary: {summary}")
    
    # Add custom fields
    summary["last_updated"] = datetime.now().isoformat()
    
    # Update profile
    await self.profile_client.merge_profile(summary)
```

## Security Considerations

### Long-Lived Tokens

- Store in `.env` file (never commit to git)
- Set file permissions: `chmod 600 .env`
- Use dedicated token for this integration
- Regularly rotate tokens

### Data Privacy

- Conversations are sent to OpenAI for summarization
- Only summaries (not raw conversations) stored in HA
- Follow OpenAI data retention policies
- Consider using local LLM for privacy-sensitive deployments

### Network Security

- Use HTTPS for Home Assistant (not HTTP)
- Consider VPN if accessing remotely
- Validate SSL certificates
- Use firewall rules to restrict access

## Future Enhancements

Planned features:
- [ ] Local LLM support (Ollama, llama.cpp)
- [ ] Profile conflict resolution
- [ ] Multi-user profile support
- [ ] Profile version history
- [ ] Smart timeout adjustment based on conversation flow
- [ ] Export/import profiles
- [ ] Profile analytics dashboard

## Support

### Getting Help

1. Check logs first: `tail -f logs/ha_realtime_assist.log`
2. Review integration guide: `PROFILE_INTEGRATION_GUIDE.md`
3. Test components independently: `example_conversation_summary.py`
4. Check Home Assistant logs
5. Verify OpenAI API status

### Reporting Issues

Include:
- Relevant log excerpts
- Environment variables (redact tokens!)
- Steps to reproduce
- Expected vs actual behavior

## License

Same as ha-realtime-assist project.

## Acknowledgments

Built on top of:
- ha-realtime-assist by [original authors]
- Home Assistant personalized_ai custom component
- OpenAI Realtime and Chat Completion APIs
