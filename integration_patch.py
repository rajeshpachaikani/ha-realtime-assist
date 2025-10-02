"""
Integration Patch for main.py

This file contains the exact changes needed to integrate conversation
summarization and profile updates into ha-realtime-assist's main.py.

Apply these changes manually or use as a reference.
"""

# =============================================================================
# STEP 1: Add imports at the top of main.py (after existing imports)
# =============================================================================

IMPORTS_TO_ADD = """
import os
from ha_profile_client import HAProfileClient
from conversation_summarizer import ConversationSummarizer
"""

# =============================================================================
# STEP 2: Add to VoiceAssistant.__init__() - after existing component initialization
# Find the line with "self.wake_word_detector: Optional[OpenWakeWordDetector] = None"
# and add these lines after it:
# =============================================================================

INIT_ADDITIONS = """
        # Profile and conversation tracking components
        self.profile_client: Optional[HAProfileClient] = None
        self.conversation_summarizer: Optional[ConversationSummarizer] = None
"""

# =============================================================================
# STEP 3: Add to _initialize_components() method
# Find where components are initialized (after wake word detector initialization)
# Add this at the end of the method, before the return statement:
# =============================================================================

INITIALIZE_COMPONENTS_ADDITION = """
        # Initialize profile client if configured
        ha_url = os.getenv("HA_URL")
        ha_token = os.getenv("HA_TOKEN")

        if ha_url and ha_token:
            self.profile_client = HAProfileClient(ha_url, ha_token)
            self.logger.info(f"Profile client initialized for {ha_url}")
            
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
            
            self.logger.info(
                f"Conversation summarizer initialized "
                f"(silence_timeout={silence_timeout}s, model={summary_model})"
            )
        else:
            self.logger.info(
                "Profile integration disabled "
                "(set HA_URL and HA_TOKEN in .env to enable)"
            )
"""

# =============================================================================
# STEP 4: Add new method to VoiceAssistant class
# Add this method anywhere in the VoiceAssistant class:
# =============================================================================

NEW_METHOD_ON_PROFILE_SUMMARY = """
    async def _on_profile_summary(self, summary: Dict[str, Any]) -> None:
        \"\"\"
        Handle generated conversation summary.
        
        Called by ConversationSummarizer when a conversation ends after silence.
        Merges the summary into the user's profile in Home Assistant.
        
        Args:
            summary: Extracted preferences, topics, style, etc.
        \"\"\"
        try:
            self.logger.info(f"Received conversation summary: {list(summary.keys())}")
            self.logger.debug(f"Summary content: {json.dumps(summary, indent=2)}")
            
            if not self.profile_client:
                self.logger.warning("Profile client not initialized, cannot update profile")
                return
            
            # Merge summary into profile (preserves existing data)
            success = await self.profile_client.merge_profile(summary)
            
            if success:
                self.logger.info("✓ Successfully updated user profile with conversation learnings")
                
                # Optionally log what was learned
                learned_items = []
                if "preferences" in summary:
                    learned_items.append(f"{len(summary['preferences'])} preferences")
                if "topics_of_interest" in summary:
                    learned_items.append(f"{len(summary['topics_of_interest'])} topics")
                if "dislikes" in summary:
                    learned_items.append(f"{len(summary['dislikes'])} dislikes")
                
                if learned_items:
                    self.logger.info(f"Learned: {', '.join(learned_items)}")
            else:
                self.logger.error("✗ Failed to update user profile")
        
        except Exception as err:
            self.logger.error(f"Error handling profile summary: {err}", exc_info=True)
"""

# =============================================================================
# STEP 5: Add conversation start tracking
# Find where the session starts (likely after wake word detection)
# Look for session_active = True or similar
# Add after session starts:
# =============================================================================

SESSION_START_ADDITION = """
        # Start conversation tracking for profile learning
        if self.conversation_summarizer:
            self.conversation_summarizer.start_conversation()
            self.logger.debug("Started conversation tracking for profile learning")
"""

# =============================================================================
# STEP 6: Track user messages
# Find where user transcription is received/processed
# Common event handlers: input_audio_transcription.completed, conversation.item.created
# Add after receiving user transcript:
# =============================================================================

TRACK_USER_MESSAGE = """
        # Track user message for profile learning
        if self.conversation_summarizer and user_transcript:
            self.conversation_summarizer.add_message("user", user_transcript)
            self.logger.debug(f"Tracked user: {user_transcript[:50]}...")
"""

# =============================================================================
# STEP 7: Track assistant responses
# Find where assistant response is received (audio transcript or text response)
# Common events: response.audio_transcript.done, response.done
# Add after receiving assistant response:
# =============================================================================

TRACK_ASSISTANT_MESSAGE = """
        # Track assistant message for profile learning
        if self.conversation_summarizer and assistant_response:
            self.conversation_summarizer.add_message("assistant", assistant_response)
            self.logger.debug(f"Tracked assistant: {assistant_response[:50]}...")
"""

# =============================================================================
# STEP 8: Add cleanup
# Find _cleanup_components() method
# Add before the final return or at the end:
# =============================================================================

CLEANUP_ADDITION = """
        # Cleanup profile client
        if self.profile_client:
            await self.profile_client.close()
            self.logger.info("Profile client closed")
        
        # End conversation tracking if active
        if self.conversation_summarizer and self.conversation_summarizer.is_active:
            self.conversation_summarizer.end_conversation()
            self.logger.info("Conversation tracking ended")
"""

# =============================================================================
# STEP 9: Update .env file
# Add these environment variables:
# =============================================================================

ENV_ADDITIONS = """
# Home Assistant Profile Integration
HA_URL=http://homeassistant.local:8123
HA_TOKEN=your_long_lived_access_token_here

# Conversation Summarization (optional, defaults shown)
PROFILE_SILENCE_TIMEOUT=5.0
PROFILE_SUMMARY_MODEL=gpt-4o-mini
"""

# =============================================================================
# Integration Notes
# =============================================================================

INTEGRATION_NOTES = """
INTEGRATION NOTES:
==================

1. The conversation summarizer uses a 5-second silence timer
   - Timer resets with each new message
   - After 5 seconds of silence, it triggers summarization
   - Summary is automatically sent to Home Assistant

2. Message tracking is passive
   - Just call add_message() when you have user/assistant text
   - No need to manage state transitions
   - Summarizer handles everything automatically

3. Profile updates are non-destructive
   - Uses merge_profile() service for deep merge
   - Existing profile data is preserved
   - Only adds/updates with new learnings

4. Integration is optional
   - If HA_URL/HA_TOKEN not set, nothing happens
   - No impact on existing functionality
   - All tracking code checks if summarizer exists first

5. OpenAI usage
   - Uses text models (gpt-4o-mini default) for summarization
   - Separate from Realtime API
   - Uses same API key from config
   - Cost is minimal (~0.01-0.02 cents per summary)

FINDING THE RIGHT HOOKS:
=========================

To find where to add tracking code in main.py:

1. For session start:
   - Search for: "session_active = True" or "SessionState.LISTENING"
   - Look in wake word callback or session initialization

2. For user messages:
   - Search for: "input_audio_transcription" or "transcript"
   - Look for OpenAI Realtime API event handlers
   - May be in openai_client/realtime.py

3. For assistant responses:
   - Search for: "response.audio_transcript" or "response.done"
   - Look for response completion handlers
   - Check for audio playback callbacks

4. Alternative approach:
   - Add logging to see event flow
   - Track events from OpenAI Realtime API
   - Use event names to find handler methods

If you can't find specific hooks, you can:
- Share the event handler code with me
- Search for "def _handle" or "async def on_" patterns
- Look at OpenAI Realtime API documentation for event names
"""

if __name__ == "__main__":
    print("=" * 80)
    print("CONVERSATION SUMMARIZATION INTEGRATION PATCH")
    print("=" * 80)
    print()
    print(INTEGRATION_NOTES)
    print()
    print("=" * 80)
    print("STEP-BY-STEP CHANGES")
    print("=" * 80)
    print()
    print("1. IMPORTS:", IMPORTS_TO_ADD)
    print()
    print("2. INIT ATTRIBUTES:", INIT_ADDITIONS)
    print()
    print("3. INITIALIZE COMPONENTS:", INITIALIZE_COMPONENTS_ADDITION)
    print()
    print("4. NEW METHOD:", NEW_METHOD_ON_PROFILE_SUMMARY)
    print()
    print("5. SESSION START:", SESSION_START_ADDITION)
    print()
    print("6. TRACK USER:", TRACK_USER_MESSAGE)
    print()
    print("7. TRACK ASSISTANT:", TRACK_ASSISTANT_MESSAGE)
    print()
    print("8. CLEANUP:", CLEANUP_ADDITION)
    print()
    print("9. ENVIRONMENT:", ENV_ADDITIONS)
