# PCA AI Integration Plan

## Current AI Status: ACTIVE ✅

The AI system is **already integrated and running** in your current FinBrain implementation:

### Existing AI Infrastructure
- **AI Adapter**: Production AI Adapter initialized (provider=gemini)
- **AI Router**: Production Router with bulletproof RL-2 and flag-gated AI
- **AI Rate Limiting**: 120 global/min, 4 per user/min
- **AI Features**: Always-on (no flags, no allowlists)

### How PCA Uses Existing AI

The overlay system leverages your existing AI through the Canonical Command (CC) generation:

```
User Message → AI (Gemini) → Canonical Command → PCA Overlay Processing
```

1. **User sends message** (e.g., "lunch 100")
2. **AI generates CC** with intent, slots, confidence, decision
3. **PCA processes CC** based on mode:
   - FALLBACK: Use current AI flow
   - SHADOW: Log CC only
   - DRYRUN: Write raw only
   - ON: Apply overlays based on CC decision

### AI-Driven Overlay Decisions

The AI makes key decisions that drive overlay behavior:

- **confidence ≥ 0.85**: AUTO_APPLY → Create overlay automatically
- **0.55 ≤ confidence < 0.85**: ASK_ONCE → Show clarifier, wait for user
- **confidence < 0.55**: RAW_ONLY → Store raw, no overlay

### No Additional AI Work Needed

The overlay system uses the **same AI infrastructure** that's already working:
- Same Gemini integration
- Same rate limiting
- Same CC generation
- Just adds overlay processing based on AI decisions

## Phase Integration Points

### Phase 1 (Complete) ✅
- CC enhanced with schema versioning
- AI decisions map to overlay actions
- Multi-item support for complex messages

### Phase 2 (Next)
- Test AI → CC → Overlay flow in SHADOW mode
- Validate confidence thresholds
- Ensure clarifier flow works with overlays

### Phase 3 (Future)
- Fine-tune confidence thresholds based on user feedback
- Add rule suggestions from AI patterns
- Enhance category detection for overlay corrections

## Key Point

**The AI is NOT turned off** - it's the brain that generates Canonical Commands which the overlay system then processes. The overlay is an enhancement layer on top of your existing, working AI system.