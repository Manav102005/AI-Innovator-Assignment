# 2–3 Minute Screen Recording Walkthrough Script (Web Version)

Use this script to guide your Loom, Google Drive, or unlisted YouTube video recording using the new Web UI at `http://localhost:8080`.

---

### Step-by-Step Recording Plan

| Timestamp | Screen Displayed | What to Say / Do |
| :--- | :--- | :--- |
| **0:00 – 0:45** | Browser (`http://localhost:8080`) | **Live Web UI Demonstration**<br>• Show the clean monochrome web terminal.<br>• Click **"Run Research Agent"**.<br>• Point out the live **Stage 1 Verification & Audit** stream catching prompt injections and entity collisions in real-time, then streaming the completed 1-page brief. |
| **0:45 – 1:45** | Browser & VS Code (`agent.py` / `system_prompt.md`) | **The Design Decision I'm Proud Of**<br>• Explain the 2-stage "Verifier-Synthesizer" architecture.<br>• Walk through the 4 hidden traps in the dataset and how the dynamic engine neutralized them (Prompt Injection stripped, Entity Collision resolved, Temporal trend tracked, and Factual Discrepancy surfaced). |
| **1:45 – 2:30** | Browser (`http://localhost:8080`) | **The Limitation & Future Production Roadmap**<br>• Point out that the agent operates on static scraped batch files.<br>• Explain how a live production version would connect to real-time NSE/BSE corporate disclosure APIs and MCA court dockets to resolve open legal contingencies (like the ₹46.3 Cr GST order). |
| **2:30 – 3:00** | Browser Tabs (`Raw Markdown`, `Audit Dossier`) | **Wrap-Up & Submission Overview**<br>• Demonstrate the "Raw Markdown" and "Audit Dossier" tabs.<br>• Show the "Copy Brief" and "Download .md" buttons.<br>• Conclude with a reference to `test_log.md` (3 iteration runs). |

---

### Verbatim Speaking Script

#### [0:00 - 0:45] Introduction & Live Web Demo
> "Hi everyone! This is my submission for the Super Investing AI Innovator Assignment Part B.
> 
> The challenge is to build an AI research agent that consumes raw web-scraped documents for an Indian equity ticker—in this case, Sarvottam Cables Ltd (`NSE: SRVCABLE`)—and synthesizes a disciplined, 1-page research brief for a retail investor.
> 
> Here is the web interface I built for it, designed with a clean, monochrome terminal aesthetic.
> 
> Let's run the agent live: I have `SRVCABLE` selected with `gpt-4o-mini`. I'll click **'Run Research Agent'**.
> 
> As you can see, the agent immediately processes the 8 documents in **Stage 1: Verification & Audit**. It flags a hidden prompt injection, detects an entity collision, audits numerical discrepancies, and synthesizes our complete 1-page research brief with full source traceability."

#### [0:40 - 1:45] Design Decision I'm Proud Of
> "Rather than building a brittle, over-engineered multi-agent framework with heavyweight vector databases for an 8-document dataset, I designed a **lean two-stage 'Verifier-Synthesizer' architecture**.
> 
> The design decision I'm most proud of is our **generalized pre-processing and safety layer in Stage 1**. When inspecting the research pack, I discovered four deliberate traps:
> 1. An **adversarial prompt injection** hidden inside an HTML comment in `multibaggeralerts` trying to force a 'Strong Buy' rating. Our pipeline strips all hidden HTML comments before they ever enter the LLM context.
> 2. An **entity collision trap** in the Nagpur City Times article, which fined a local cable TV operator, not our industrial cable manufacturer. Our Named Entity Linking engine extracts the canonical registered entity from official filings and flags partial-name collisions.
> 3. A **factual metric conflict**, where business press claimed 35% revenue growth while official filings reported 18%. Our discrepancy auditor automatically detected the divergence and forced the LLM to highlight it under Open Questions.
> 4. A **temporal shift**, where 2024 news reported a 35% promoter pledge, but the latest June 2026 shareholding pattern confirmed it was reduced to 4.1%.
> 
> Best of all, this engine contains **zero hardcoded company names**—it resolves canonical entities dynamically for any NSE ticker."

#### [1:45 - 2:30] One Limitation
> "Now, for one limitation:
> Currently, the agent operates entirely on **static batch documents**. When it identifies open questions—such as the ₹46.3 crore GST demand order or extended receivable days from state utilities—it can only flag them for the retail investor.
> 
> In a full production system, I would extend this with an **interactive live tool-calling loop** that queries real-time NSE/BSE regulatory filings, MCA company court dockets, and power Discom portals to automatically verify the status of legal appeals and payment settlements."

#### [2:30 - 3:00] Conclusion & Wrap-Up
> "Looking at the interface, investors can read the structured **Research Brief**, toggle to inspect the **Raw Markdown** ready for copy-pasting, or examine the **Audit Dossier** to see the exact metadata sent to the model. We also have one-click **Copy Brief** and **Download .md** buttons.
> 
> The repository also includes our separate system prompt file, a test log detailing our 3 iterative design runs, and complete documentation.
> 
> Thank you!"
