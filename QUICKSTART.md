# Quick Start - Profile Auto-Learning

## ⚡ 3-Minute Setup

### 1. Add Environment Variables

Edit `.env` file:
```bash
# Required
HA_URL=http://homeassistant.local:8123
HA_TOKEN=your_long_lived_access_token

# Optional (defaults shown)
PROFILE_SILENCE_TIMEOUT=5.0
PROFILE_SUMMARY_MODEL=gpt-4o-mini
```

### 2. Get Access Token

Home Assistant → Profile → Long-Lived Access Tokens → Create Token

### 3. Run It

```bash
python src/main.py
```

## 📊 Check Logs

```bash
tail -f logs/ha_realtime_assist.log | grep -i profile
```

Look for:
```
✓ Profile client initialized
✓ Conversation summarizer initialized
✓ Started conversation tracking
✓ Successfully updated user profile
```

## 🧪 Test Manually

```bash
python example_conversation_summary.py
```

## ✅ Verify Profile

Home Assistant → Developer Tools → Services:

```yaml
service: personalized_ai.get_user_profile
data:
  return_response: true
```

## 🎯 What Gets Learned

| Category | Example |
|----------|---------|
| **Preferences** | "lights at 50%" |
| **Topics** | "AI", "home automation" |
| **Dislikes** | "no jazz music" |
| **Style** | "brief answers" |
| **Personality** | "tech curious" |

## 🔧 Troubleshooting

| Problem | Solution |
|---------|----------|
| Not starting | Add HA_URL and HA_TOKEN to .env |
| No summaries | Wait 5+ seconds of silence |
| Profile not updating | Check HA_TOKEN is valid |
| Import errors | `pip install aiohttp openai` |

## 📁 Files Modified

- ✅ `src/main.py` - Integration complete
- ✅ `src/ha_profile_client.py` - New
- ✅ `src/conversation_summarizer.py` - New

## 🚀 Usage

1. Say wake word
2. Have conversation
3. Stop speaking for 5 seconds
4. **Profile automatically updates!**

## 💰 Cost

~$0.01-0.02 per conversation with gpt-4o-mini

## 🎉 Done!

That's it! Your voice assistant now learns from every conversation automatically.

For detailed docs, see:
- `PROFILE_AUTO_LEARNING_README.md`
- `PROFILE_INTEGRATION_GUIDE.md`
- `INTEGRATION_COMPLETE.md`
