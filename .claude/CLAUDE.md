# Development Logging

## Session Initialization

**At the start of every session:**
1. Check for recent devlogs: `ls -lt devlogs/ | head -n 5`
2. Read the 3 most recent devlog entries to understand recent context
3. Summarize key points from recent devlogs (changes, ongoing issues, patterns)
4. Ask if there are specific devlogs I should review for current work

This ensures continuity and awareness of:
- Recent bugs and their solutions
- Current architectural decisions
- Known issues or limitations
- Recent patterns established

## Devlog Requirements

After completing any significant work session (bug fixes, feature implementations, refactoring), create a devlog entry in `devlogs/` with the filename format `YYMMDDHHMM.txt` (e.g., `2511111430.txt` for November 11, 2025 at 2:30 PM).

### Devlog Structure

Each devlog must include:

1. **Session Overview**
   - Brief summary of what was attempted
   - Files modified

2. **Changes Made**
   - Detailed list of code changes
   - New functions/classes added
   - Modified logic or patterns
   - Configuration changes

3. **Errors Encountered**
   - Full error messages and stack traces
   - Context when the error occurred
   - Initial diagnosis

4. **Solution Attempts**
   - Each approach tried (even failed ones)
   - Why each approach was attempted
   - Results of each attempt

5. **Final Solution**
   - What actually worked
   - Why this approach succeeded
   - Any trade-offs or caveats
   - Related documentation or references

6. **Lessons Learned**
   - Key insights from this session
   - What to do differently next time
   - Patterns to remember or avoid

### When to Create Devlogs

Create a devlog entry when:
- Fixing a bug that took multiple attempts
- Implementing a new feature
- Encountering and resolving errors
- Making architectural changes
- Learning something non-obvious about the codebase
- Completing a work session with significant progress

### Devlog Best Practices

- Be thorough - future you will thank you
- Document failed attempts - they prevent repeating mistakes
- Include exact error messages and stack traces
- Note why solutions worked, not just what worked
- Cross-reference related devlogs when relevant