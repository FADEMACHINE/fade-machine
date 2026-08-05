# FADE MACHINE

Sports analytics tool focused on historical trends for moneylines, spreads, totals, and player props.

**Current Phase:** Pure analytical tool (no real-money features yet)

---

## Current Focus: NFL Against The Spread (ATS)

This version includes:
- Sample NFL ATS data for 12 teams
- Filters for teams and season
- Key performance metrics
- Sorted ATS win percentage table
- Quick insights (strongest / weakest ATS teams)

---

## How to Run the App

1. Open a terminal in the project folder
2. Install packages (only needed once):
   ```bash
   pip install -r requirements.txt
   ```
3. Start the app:
   ```bash
   python -m streamlit run app.py
   ```
4. Open the local URL that appears (usually http://localhost:8501)

---

## Next Development Steps

1. Replace sample data with real historical NFL ATS data
2. Add more seasons and full team list
3. Add home/away splits and situational trends
4. Add simple probability / edge calculations
5. Expand to totals, moneylines, and player props

---

## Working with AI

You can improve this app by pasting prompts into AI coding tools (Cursor, Claude, ChatGPT, Grok, etc.).

Always test changes by re-running:
```bash
python -m streamlit run app.py
```

---

**Owner:** [FADEMACHINE](https://github.com/FADEMACHINE)
