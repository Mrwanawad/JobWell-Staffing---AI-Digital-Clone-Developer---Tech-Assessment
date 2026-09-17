# Dr. Mark AI Clone: Strategy

Mrwan Awad, AI Digital Clone Developer Assignment
September 2026

---

## 1. Capturing how Dr. Mark thinks and talks

- **Knowledge:** his course outlines, slides, past posts, emails and video transcripts. Transcribe videos with Whisper, then store everything in a searchable knowledge base.
- **Style:** a short style guide (tone, words he uses, words he avoids) plus 20 to 30 real examples of his writing.
- **Preferences and decisions:** a 90-minute interview with questions like "When would you say no to a student?" and "What claims do you never make?" His answers become written rules.
- **Corrections:** every edit he makes to a draft is saved and fed back into the next drafts. The demo already does this.

## 2. When the clone doesn't know

- Facts like price, dates and venue live in one profile file. Empty means "not decided".
- The clone never guesses these. It says they are not set yet and saves the question for Dr. Mark.
- Some topics always go to him first: prices, dates, clinical claims, patient cases, and anything he hasn't approved before.

## 3. Voice and video tools

| Need | Tool | What we need from him |
|---|---|---|
| Voice | ElevenLabs Professional Voice Clone | Clean audio of him talking, quiet room, good mic. Length **[CHECK]** |
| Video | HeyGen (backup: Synthesia) | A few minutes of footage facing the camera, plus a consent clip. Length **[CHECK]** |
| Transcripts | Whisper | His existing videos |

## 4. Software: configure vs. build

| Configure (ready tools) | Build (my work) |
|---|---|
| LLM (Claude or Gemini) | Knowledge base and profile |
| ElevenLabs voice | Prompt rules and "don't guess" logic |
| HeyGen avatar | Corrections and pending questions |
| Slack or email for approvals | Idea to video pipeline (Python + n8n) |
| GitHub, hosting | Tests, checks, handoff docs |

## 5. From idea to finished video

```
Idea -> Script draft -> Dr. Mark approves or edits -> Voice -> Video -> Final check -> Publish
```

1. Dr. Mark (or his team) sends a topic.
2. The clone writes a script in his style.
3. He approves or edits it by email or Slack. Edits are saved as corrections.
4. The approved script goes to ElevenLabs, then HeyGen.
5. He watches the final video once before it goes out.

## 6. Challenges and limits

- The clone is only as good as the material he gives. Little material means generic output.
- Video avatars still look slightly off with big hand moves or fast speech.
- Medical education needs care. No clinical claims without his approval.
- We depend on ElevenLabs and HeyGen staying available and keeping their prices.
- No patient data goes into any tool.

## 7. Timeline

| Week | Work |
|---|---|
| 1 to 2 | Interview, collect material, text clone with his style |
| 3 | Voice clone and testing |
| 4 to 5 | Video avatar and the approval pipeline |
| 6 to 7 | Real use, tuning from his corrections |
| 8 | Handoff and docs |

**Fully working means:** he approves most drafts with small edits, the clone never makes up prices, dates or clinical claims, voice and video pass his review, and a video goes from idea to done in under 2 days with one approval step.

## 8. Costs (estimates, in USD)

Assumption: developer rate of $40/hour **[ADD your real rate]**.

| Item | Estimate |
|---|---|
| Development (about 180 hours) | about $7,200 |
| ElevenLabs plan | **[CHECK]** per month |
| HeyGen plan | **[CHECK]** per month |
| LLM API usage | $20 to $100 per month, depends on volume |
| Hosting and n8n | $20 to $50 per month |
| Maintenance | 5 to 10 hours per month |

## 9. What we need from Dr. Mark

| Task | Time |
|---|---|
| Interview | 1.5 hours |
| Voice recording | 1 to 2 hours |
| Video filming | 1 to 2 hours |
| Reviewing drafts in weeks 1 to 7 | about 30 minutes per week |
| After launch: approvals | about 1 hour per week |

Total in the first 2 months: roughly 8 to 10 hours.

## 10. Privacy and ownership

- All accounts (LLM, ElevenLabs, HeyGen, GitHub, hosting) are opened in Dr. Mark's name. I am added as a team member.
- His voice, face and content belong to him. Written consent before cloning. He can ask to delete the clone at any time.
- The code lives in his GitHub. He owns it.
- At handoff: a short guide, a list of every account, and all keys changed so I no longer have access.

## 11. What I add beyond ready AI tools

Tools like ElevenLabs and HeyGen make the voice and the face. They don't know Dr. Mark. I build the part in the middle: his knowledge, his rules, the "ask me first" logic, and a loop that learns from his edits. All of it tied into one simple workflow he owns.

## Sources reviewed

- First Movers home page: https://firstmovers.ai
- AI Labs: https://firstmovers.ai/labs/
- Blog: https://firstmovers.ai/blog/
- YouTube videos watched: **[ADD links]**

## Assumptions

- Dr. Mark has existing content (slides, posts, videos) to learn from.
- The clone is for marketing and education content, not patient care.
- English is the main language. Spanish for Colombia would be extra work. **[ADD if needed]**
- Tool prices and recording lengths are from public pages and may change.
