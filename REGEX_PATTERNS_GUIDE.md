# Regex Pattern Examples & Reference

This file contains example patterns you can add to `beta_cogs/automod.py` and how they work.

## Your Provided Patterns

### Quarantine Level (Already Added)
```python
QUARANTINE_PATTERNS = [
    r"\b[s$5z]+[\W_]*[h#]+[\W_]*[i1!|l]+[\W_]*[t7+]+[a-z0-9$#@!*+_-]*\b",
    r"\b[n]+[\W_]*[i1!l|]+[\W_]*[gq9]+[\W_]*[gq9]+[\W_]*[ea4r3]*[a-z0-9]*\b",
    r"\b[n][i|1|!][g|9]{2,}[e|3]r\b",
    r"\b[n][!|1][g|9]{2,}[a|@]\b",
]
```

**Matches:**
- Variations of "shit" (with $, 5, z substitutions)
- Variations of n-word (with numbers and symbol substitutions)
- Extended variations: n**gga, n**ger

### Ban Level (Already Added)
```python
BAN_PATTERNS = [
    r"\b[fph@][\W_]*[u*o0v]+[\W_]*[c(kq)(ck)*x]+[\W_]*[kq]+(ing|er|ed|s|in'?|a)?\b",
    r"\b[fF]+[uU*0]+[cC*k]+[kK]+(ing|er|ed|s)?\b",
    r"\b[fFph@]+[\W_]*[uU*0]+[\W_]*[cCckkqx]+[\W_]*[kKqx]+(ing|er|ed|s)?\b",
    r"\b(f+|ph)(y|i|u)?(c+|k+|q+)(y|k|n)?\b",
    r"\b(f+|ph)([a*u*y*i]*)(c+|k+|q+|z+|w+|\*+)([u*c*k*q*z*w]*)(k+|c+|\*)(e+r+|i+n+g+|e+d+)?\b",
    r"\b[s$5z]+[\W_]*[h#]+[\W_]*[i1!|l]+[\W_]*[t7+]+s*\b",
]
```

**Matches:**
- Extensive f-word variations with:
  - f, ph, @ symbols
  - u, *, o, 0, v variations  
  - ck, kq, qck combinations
  - ing, er, ed, s, in' suffixes
- Extended shit variations

## Pattern Building Guide

### Basic Structure
```
\b              - Word boundary (start)
[chars]+        - One or more characters from this set
[\W_]*          - Zero or more non-word or underscore
pattern{n,m}    - Exactly n to m times
(a|b)           - Alternative: a OR b
?               - Optional (0 or 1)
\b              - Word boundary (end)
```

### Common Substitutions

| Real Character | Variations | Pattern |
|----------------|-----------|---------|
| a | 4, @, ∆ | `[a4@]` |
| e | 3, £ | `[e3]` |
| i | 1, !, \|, l | `[i1!|\|l]` |
| o | 0, O | `[o0O]` |
| s | 5, $, z, z | `[s5$z]` |
| t | 7, + | `[t7+]` |
| l | 1, \| | `[l1\|]` |
| g | 9, q, g | `[g9q]` |

### Separators
```
[\W_]*          - Non-word char or underscore (0 or more)
\s*             - Whitespace (0 or more)
[-_.~]*         - Dash, dot, tilde, underscore (0 or more)
```

---

## Example Patterns You Could Add

### Soft Violations (INFRACTION Level)
```python
INFRACTION_PATTERNS = [
    # Mild curse words
    r"\b(damn|dammit|bloody|crap)\b",
    # Incomplete forms
    r"\b(wtf|omfg|smh)\b",
]
```

### Medium Violations (MUTE Level)
```python
MUTE_PATTERNS = [
    # Slurs against groups  
    r"\b(retard|idiot|ableist_terms)\b",
    # Generic strong curses
    r"\b(hell|piss|ass)\b",
]
```

### Severe Violations (QUARANTINE Level)
```python
QUARANTINE_PATTERNS = [
    # Your existing patterns here
    # + Additional severe patterns
    r"\b(slur1|slur2)\b",
]
```

### Most Severe (BAN Level)
```python
BAN_PATTERNS = [
    # Your existing patterns here
    # + Additional hate speech patterns
]
```

---

## Testing Regex Patterns

Use https://regex101.com to test before adding:

1. Go to https://regex101.com
2. Paste your pattern in the "Regular Expression" box
3. Set flags to "i" (case-insensitive)
4. Paste test strings in "Test String" below
5. See matches highlighted

### Example Test Cases

```
Pattern: \b[s$5z]+[\W_]*[h#]+[\W_]*[i1!|l]+[\W_]*[t7+]+[a-z0-9$#@!*+_-]*\b
Flags: i (case-insensitive)

Test Strings:
shit         ✓ Match
SHIT         ✓ Match (due to i flag)
sh1t         ✓ Match
$h!t         ✓ Match
s__h__i__t   ✓ Match
shitting     ✓ Match
s**    ✓ Match
```

---

## Best Practices

1. **Test Everything**
   - Use regex101.com before adding
   - Test with common variations
   - Test with legitimate words

2. **Use Word Boundaries**
   - `\b` prevents false matches
   - Example: `\b(admin)\b` won't match "administer"

3. **Use Character Classes**
   - `[abc]` matches a OR b OR c
   - More efficient than alternation
   - `[a-z]` matches a through z

4. **Start Permissive, Get Stricter**
   - Start with basic pattern
   - Test for false positives
   - Refine if needed

5. **Document Your Patterns**
   - Add comments for clarity
   - Show what each pattern targets

---

## Advanced: Pattern Structure

### Example Pattern Breakdown
```
\b[s$5z]+[\W_]*[h#]+[\W_]*[i1!|l]+[\W_]*[t7+]+[a-z0-9$#@!*+_-]*\b
 │                                                               │
 └─ Word boundary                                                 │
    │                                                              │
    └─ s/5/$/ z variations (1+)                                   │
       │                                                           │
       └─ Optional separator                                       │
          │                                                        │
          └─ h/# (1+)                                             │
             │                                                    │
             └─ Optional separator                               │
                │                                                 │
                └─ i/1/!/|/l (1+)                                │
                   │                                              │
                   └─ Optional separator                          │
                      │                                           │
                      └─ t/7/+ (1+)                              │
                         │                                        │
                         └─ Optional ending chars                 │
                            │                                     │
                            └─ Word boundary
```

This allows matching:
- shit
- sh1t
- $h!t
- s__h__i__t
- shitting (has -ing suffix)

---

## Common Mistakes

❌ No word boundary causes false matches:
```python
# BAD - might match "administration"
r"admin"
# GOOD - only matches word "admin"
r"\b admin\b"
```

❌ Not escaping special characters:
```python
# BAD - dot matches any character
r"im.mature"  # matches "imXmature"
# GOOD - escaped dot means literal dot
r"im\.mature"  # matches "im.mature"
```

❌ Forgetting case-insensitive flag:
```python
# BAD in code - but compile with IGNORECASE flag in Python
r"Shit"  # won't match "shit"

# In Python, use:
re.compile(pattern, re.IGNORECASE)  # Already done in automod!
```

❌ Overly complex without reason:
```python
# BAD - too greedy
r".*shit.*"  # matches anything with shit anywhere

# GOOD - more specific
r"\bshit\b"  # only word "shit"
```

---

## Migration Guide: Adding Patterns

1. **Decide severity level**
   - Low infraction-only → `INFRACTION_PATTERNS`
   - Medium, limit damage → `MUTE_PATTERNS`
   - High, big problem → `QUARANTINE_PATTERNS`
   - Critical, must ban → `BAN_PATTERNS`

2. **Find/test pattern**
   - Use regex101.com
   - Test with variants
   - Check false positives

3. **Add to list**
   ```python
   QUARANTINE_PATTERNS = [
       r"existing_pattern",
       r"your_new_pattern",  # Add here
   ]
   ```

4. **Reload cog**
   - `?cog reload beta_cogs.automod`
   - Or restart bot

5. **Test**
   - Post as personnel member
   - Verify action taken
   - Check embed posted

6. **Monitor**
   - Check moderation_tracking.json
   - Look for false positives
   - Adjust if needed

---

## Performance Considerations

- Each pattern is compiled once (at startup)
- Matching is per-message (fast)
- Highest severity checked first (stops searching early)
- Consider order for efficiency:
  - Ban patterns first (critical)
  - Then quarantine
  - Then mute
  - Then infraction (least critical)

---

## Need Help?

- Test at: https://regex101.com
- Reference at: https://www.regular-expressions.info
- The patterns provided already handle the hard part!

