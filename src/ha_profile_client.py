"""
Home Assistant Profile Client for ha-realtime-assist

Handles communication with Home Assistant's Personalized AI integration
to retrieve and update user personalization profiles.
"""

import aiohttp
import json
import logging
from typing import Any, Optional, Dict

logger = logging.getLogger(__name__)


class HAProfileClient:
    """Client for accessing Home Assistant user personalization profiles."""
    
    def __init__(self, ha_url: str, ha_token: str):
        """
        Initialize the HA Profile Client.
        
        Args:
            ha_url: Home Assistant URL (e.g., "http://homeassistant.local:8123")
            ha_token: Long-lived access token from HA
        """
        self.ha_url = ha_url.rstrip('/')
        self.headers = {
            "Authorization": f"Bearer {ha_token}",
            "Content-Type": "application/json",
        }
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def close(self) -> None:
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def get_profile(self) -> Dict[str, Any]:
        """
        Get the current user personalization profile.
        
        Returns:
            dict: The user profile with all personalization data
        """
        session = await self._get_session()
        
        try:
            async with session.post(
                f"{self.ha_url}/api/services/personalized_ai/get_user_profile",
                headers=self.headers,
                json={"return_response": True},
            ) as response:
                response.raise_for_status()
                result = await response.json()
                
                # The service returns {"profile": {...}, "profile_json": "..."}
                profile = result.get("profile", {})
                logger.debug(f"Retrieved profile with {len(profile)} top-level keys")
                return profile
                
        except aiohttp.ClientError as err:
            logger.error(f"Failed to get profile from Home Assistant: {err}")
            return {}
        except Exception as err:
            logger.error(f"Unexpected error getting profile: {err}")
            return {}
    
    async def update_profile(self, profile: Dict[str, Any]) -> bool:
        """
        Update the entire user profile (replaces existing profile).
        
        Args:
            profile: Complete new profile dictionary
            
        Returns:
            bool: True if successful, False otherwise
        """
        session = await self._get_session()
        
        try:
            async with session.post(
                f"{self.ha_url}/api/services/personalized_ai/update_user_profile",
                headers=self.headers,
                json={"profile": profile},
            ) as response:
                response.raise_for_status()
                logger.info("Profile updated successfully")
                return True
                
        except aiohttp.ClientError as err:
            logger.error(f"Failed to update profile in Home Assistant: {err}")
            return False
        except Exception as err:
            logger.error(f"Unexpected error updating profile: {err}")
            return False
    
    async def merge_profile(self, updates: Dict[str, Any]) -> bool:
        """
        Merge partial updates into existing profile (preserves existing data).
        
        This performs a deep merge, so nested dictionaries are merged recursively
        rather than replaced.
        
        Args:
            updates: Partial profile dictionary to merge
            
        Returns:
            bool: True if successful, False otherwise
        """
        session = await self._get_session()
        
        try:
            async with session.post(
                f"{self.ha_url}/api/services/personalized_ai/merge_user_profile",
                headers=self.headers,
                json={"updates": updates},
            ) as response:
                response.raise_for_status()
                logger.info("Profile updates merged successfully")
                return True
                
        except aiohttp.ClientError as err:
            logger.error(f"Failed to merge profile updates in Home Assistant: {err}")
            return False
        except Exception as err:
            logger.error(f"Unexpected error merging profile: {err}")
            return False
    
    async def get_profile_as_system_prompt(self) -> str:
        """
        Get the profile formatted as a system prompt for AI models.
        
        Returns:
            str: Formatted system prompt with user context
        """
        profile = await self.get_profile()
        
        if not profile:
            return ""
        
        prompt_parts = []
        
        if "preferences" in profile:
            prefs = profile["preferences"]
            if prefs:
                prompt_parts.append(f"User preferences: {json.dumps(prefs)}")
        
        if "topics_of_interest" in profile:
            topics = profile["topics_of_interest"]
            if topics:
                prompt_parts.append(f"Topics of interest: {', '.join(topics)}")
        
        if "communication_style" in profile:
            style = profile["communication_style"]
            if style:
                prompt_parts.append(f"Communication style: {style}")
        
        if "dislikes" in profile:
            dislikes = profile["dislikes"]
            if dislikes:
                prompt_parts.append(f"User dislikes: {', '.join(dislikes)}")
        
        if "personality_notes" in profile:
            notes = profile["personality_notes"]
            if notes:
                prompt_parts.append(f"Personality: {notes}")
        
        if prompt_parts:
            return "\n\nUser Context:\n" + "\n".join(prompt_parts)
        return ""
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
