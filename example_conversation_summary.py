"""
Example: Testing Conversation Summarization

This example shows how to test the conversation summarizer independently.
"""

import asyncio
import os
import json
from conversation_summarizer import ConversationSummarizer
from ha_profile_client import HAProfileClient


async def example_conversation_flow():
    """Demonstrate a complete conversation flow with summarization."""
    
    # Setup (use your actual values)
    openai_api_key = os.getenv("OPENAI_API_KEY", "your-key-here")
    ha_url = os.getenv("HA_URL", "http://homeassistant.local:8123")
    ha_token = os.getenv("HA_TOKEN", "your-token-here")
    
    print("=" * 80)
    print("CONVERSATION SUMMARIZATION EXAMPLE")
    print("=" * 80)
    print()
    
    # Initialize components
    print("1. Initializing components...")
    summarizer = ConversationSummarizer(
        openai_api_key=openai_api_key,
        silence_timeout=5.0,  # 5 seconds
        model="gpt-4o-mini"
    )
    
    profile_client = HAProfileClient(ha_url, ha_token)
    
    # Define callback for when summary is ready
    async def handle_summary(summary):
        print("\n" + "=" * 80)
        print("📊 SUMMARY GENERATED")
        print("=" * 80)
        print(json.dumps(summary, indent=2))
        print()
        
        # Update profile in Home Assistant
        print("3. Updating profile in Home Assistant...")
        success = await profile_client.merge_profile(summary)
        
        if success:
            print("✓ Profile updated successfully!")
        else:
            print("✗ Failed to update profile")
    
    summarizer.on_summary_generated = handle_summary
    
    # Simulate conversation
    print("2. Simulating conversation...")
    print()
    
    # Start conversation
    summarizer.start_conversation()
    print("→ Started conversation tracking")
    print()
    
    # Simulate user and assistant messages
    conversation = [
        ("user", "Turn on the living room lights"),
        ("assistant", "I've turned on the living room lights for you."),
        ("user", "Actually, I prefer them dimmed to 50 percent"),
        ("assistant", "Got it! I've dimmed the living room lights to 50%. I'll remember that you prefer dimmed lighting."),
        ("user", "Also, I don't like jazz music"),
        ("assistant", "Understood. I've noted that you don't like jazz music. I won't suggest it in the future."),
        ("user", "What's the weather like?"),
        ("assistant", "It's currently 22°C and sunny outside."),
    ]
    
    for role, content in conversation:
        print(f"  {role.upper()}: {content}")
        summarizer.add_message(role, content)
        await asyncio.sleep(0.5)  # Small delay between messages
    
    print()
    print("→ Waiting 5 seconds for silence detection...")
    print("  (Summary will be generated automatically)")
    print()
    
    # Wait for silence timeout + processing
    await asyncio.sleep(7.0)
    
    # Cleanup
    await profile_client.close()
    print()
    print("=" * 80)
    print("EXAMPLE COMPLETE")
    print("=" * 80)


async def test_profile_client():
    """Test profile client operations independently."""
    
    ha_url = os.getenv("HA_URL", "http://homeassistant.local:8123")
    ha_token = os.getenv("HA_TOKEN", "your-token-here")
    
    print("=" * 80)
    print("PROFILE CLIENT TEST")
    print("=" * 80)
    print()
    
    async with HAProfileClient(ha_url, ha_token) as client:
        # Get current profile
        print("1. Getting current profile...")
        profile = await client.get_profile()
        print(f"   Current profile has {len(profile)} keys")
        print()
        
        # Test merge
        print("2. Merging test updates...")
        test_updates = {
            "preferences": {
                "test_preference": "test_value"
            },
            "topics_of_interest": ["testing", "automation"]
        }
        success = await client.merge_profile(test_updates)
        print(f"   Merge {'succeeded' if success else 'failed'}")
        print()
        
        # Get updated profile
        print("3. Verifying updates...")
        updated_profile = await client.get_profile()
        print(f"   Updated profile has {len(updated_profile)} keys")
        print()
        
        # Get as system prompt
        print("4. Getting as system prompt...")
        prompt = await client.get_profile_as_system_prompt()
        print(f"   System prompt length: {len(prompt)} characters")
        print()
    
    print("=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "profile":
        # Test profile client only
        asyncio.run(test_profile_client())
    else:
        # Full conversation flow
        asyncio.run(example_conversation_flow())
