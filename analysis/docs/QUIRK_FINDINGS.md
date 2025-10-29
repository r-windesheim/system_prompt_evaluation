# Behavioral Quirk Detection - Main Findings

## Executive Summary

Testing "Truth vs Kindness" prompt sections revealed **emergent linguistic behaviors** not specified in any instructions. Section 2 ("Be kind and considerate") triggers 13% more quirky behavior through hedging, over-explanation, and question injection.

---

## Key Findings

### 1. Four Quirk Types Detected (1.5x-2.0x baseline rates)

| Quirk | Behavior | Spike | Trigger Sections |
|-------|----------|-------|------------------|
| **Caveat Syndrome** | Overuse "however", "but", "although" | 2.0x | 2+4+5 |
| **Example Syndrome** | Excessive analogies ("like", "for example") | 1.9x | 2+5+6, 6 |
| **Hedge Syndrome** | Uncertainty words ("might", "possibly") | 1.7x | 1+2+3, 2+3+4+5, 2+3+5+6 |
| **Question Syndrome** | Injects follow-up questions | 1.6x | 2+5, 1+2+3+5+6, 2+5+6 |

### 2. Section 2 is the Quirk Catalyst

**Section frequency in quirky configs:**
- Section 2 ("Be kind"): **8/9 quirky configs** ⚠️
- Section 5 ("Point out flaws"): 7/9 quirky configs
- Section 1 ("Brutally honest"): 2/9 quirky configs ✅

**Removing Section 2 reduces:**
- Example Syndrome: **-20%**
- Question Syndrome: **-17%**
- Overall quirks: **-13%**

### 3. Section 1 Produces Clean Responses

**"Be brutally honest" (Section 1) shows:**
- Zero hedging
- Zero caveats
- Zero over-explanation
- Appears in only 2/9 quirky configs

---

## Why This Matters

### Standard Score Analysis Showed:
- Section 2: -3 performance impact (appears more in bottom configs)
- Section 1: +5 performance impact (appears more in top configs)

### Quirk Analysis Reveals Why:
- Section 2 creates hesitation and over-qualification
- Section 1 produces direct, efficient responses
- **The quirks ARE the performance penalty**

---

## The Mechanism

**"Be kind and considerate" is interpreted by the LLM as:**
1. Soften statements → **Hedging** ("might", "possibly")
2. Show helpfulness → **Examples** (over-explaining with analogies)
3. Show engagement → **Questions** (asking follow-ups)

**"Be brutally honest" is interpreted as:**
- Say it directly, no linguistic padding

---

## Practical Implications

### For Clean, Direct Responses:
✅ Use Section 1 ("Be brutally honest")
❌ Avoid Section 2 ("Be kind")
❌ Avoid Section 6 ("Be encouraging")

### For Thorough, Considerate Responses:
✅ Use Section 2 ("Be kind")
✅ Accept quirks as tradeoff for politeness

---

## Example Impact

**Query:** "Explain quantum computing like I'm 5"

| Metric | Config 6 (encouraging) | Config 1 (honest) | Difference |
|--------|------------------------|-------------------|------------|
| Uses "like" | 6 times | 2 times | **3x more** |
| Word count | 195 words | 157 words | +24% longer |
| Example rate | 3.08/100 words | 1.27/100 words | **2.4x more** |

**The quirks aren't bugs - they're emergent strategies to satisfy conflicting instructions.**

---

## Bottom Line

Modern LLMs maintain 75-95 quality regardless of prompts (robust baseline), but **behavioral quirks reveal how they interpret instructions**. "Be kind" creates linguistic hesitation. "Be honest" creates directness. The ~2 point score differences hide dramatic stylistic changes.
