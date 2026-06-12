---
title: Anarchy Chess
emoji: ♟️
colorFrom: blue
colorTo: red
sdk: gradio
sdk_version: 4.36.1
app_file: app.py
pinned: false
tags:
  - build-small-hackathon
  - game
  - multi-agent
---

# Anarchy Chess: The Great Hall

Welcome to Anarchy Chess, a multi-agent LLM experiment where the players are just as likely to argue and cheat as they are to actually play chess. Built for the Build Small Hackathon, this project replaces a standard AI opponent with two wildly different LLM personas battling each other in a live game. They evaluate the board, make moves, and occasionally attempt physically impossible, highly illegal moves just to spite each other.

When a cheat is detected, the game halts. A multi-agent argument breaks out between the cheater and the opponent before a cynical Goblin Referee steps in to force a legal move.

### The Cast

The game features three distinct personalities driving the chaos. Playing White is xX_ChessGod_Xx, a hyper-energetic, chronically online Gen Z Twitch Streamer who plays for content, tilts easily, and invents fake rules for clout. Playing Black is Lord Malacor, a ruthless 14th-century Medieval Warlord who treats the chessboard as a literal battlefield and views written rules as peasant logic. Caught in the middle is Zog the Referee, an exhausted, minimum-wage Goblin who hates them both and drops cynical one-liners to end their arguments.

### Under the Hood

This isn't just a simple LLM wrapper; it's a stateful multi-agent workflow. The agents are powered by a Gemma model hosted on a custom Modal endpoint. LangGraph orchestrates the turn-based logic, maintaining conversational memory so the agents actually respond to what was just said rather than shouting into the void. 

A Python-based RNG system serves as the chaos engine, forcing a player to cheat about 25% of the time. This triggers a specific argument routing where the opponent roasts the cheater, the cheater makes an excuse, the opponent retorts, and the referee finally intervenes. Everything is wrapped in a Gradio UI featuring custom glassmorphism CSS, streaming typewriter text effects, and an SVG-rendered chessboard via python-chess.

### Running It Yourself

You'll need a Python 3.10+ environment and an active endpoint for your LLM. First, install the dependencies:

```bash
pip install -r requirements.txt
```

If you are running this locally, you'll need to set your Modal endpoint URL as an environment variable (`MODAL_URL`). Note that if you are deploying this to Hugging Face Spaces, you should add the URL via the Space's Settings > Variables and secrets panel instead of hardcoding it.

To start the game, simply launch the Gradio server:

```bash
python app.py
```

Open `http://localhost:7860` in your browser, sit back, and click "Play Next Turn" to watch the chaos unfold.

### Hackathon Tech Stack

This project combines several powerful, small tools to create a highly interactive, serverless experience:

*   **Python 3.10+**: Core programming language.
*   **Gradio (4.36.1)**: Powers the web interface, state management, and real-time streaming.
*   **LangGraph**: Used to build the precise state machine that manages the chaotic multi-agent arguments.
*   **LangChain Core**: Framework for interacting with the LLM.
*   **Modal**: Serverless hosting platform providing the custom endpoint for fast LLM inference.
*   **Gemma4**: The core LLM driving the different agent personas.
*   **python-chess**: Handles the underlying board state, SVG rendering, and strict move validation.
*   **Vanilla CSS**: Injected into Gradio to create the custom glassmorphism aesthetic and UI layouts.
*   **Base64 Encoding**: Used for securely embedding images (like the PFP and background) directly in the code to ensure they load flawlessly on cloud platforms like Hugging Face Spaces.

### Challenges & Solutions

Building a game where the AI is *supposed* to act out of line presented unique hurdles:

1.  **Herding the Chaos (State Management):** Initially, having two LLMs argue over an illegal move led to infinite loops or agents forgetting whose turn it was. We solved this by implementing **LangGraph**. By explicitly routing the conversation (`Roast` ➔ `Excuse` ➔ `Retort` ➔ `Referee`), we contained the chaos within a strict, predictable graph structure.
2.  **Streaming & State Synchronization:** Streaming text character-by-character in the UI while simultaneously updating a complex Python backend state caused several synchronization crashes and `ValueError` unpacking bugs. We overcame this by standardizing the output of our LangGraph execution stream, ensuring the frontend always received a consistent snapshot of the board and chat logs at every node.
3.  **UI & Aesthetic Limitations:** Standard web components felt too rigid for an "Anarchy" themed game. To make the game feel premium and thematic, we bypassed default components in favor of custom CSS, dynamic SVG rendering, and base64-encoded image injection. This allowed us to deploy a stunning glassmorphism UI that is completely robust in serverless environments like Hugging Face Spaces.
