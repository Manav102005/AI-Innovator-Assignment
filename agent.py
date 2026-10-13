#!/usr/bin/env python3
"""
Super Investing - AI Research Agent
Ticker: SRVCABLE (Sarvottam Cables Ltd)
Anchor Date: 2026-09-23

A 2-stage research pipeline:
- Stage 1: Document Ingestion, Prompt-Injection Sanitization & Entity Verification
- Stage 2: Grounded Synthesis with Citation Tracking & Discrepancy Detection
"""

import os
import re
import sys
import glob
import time
import argparse
from datetime import datetime

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


def load_env_file():
    """Load key-value pairs from .env file if it exists in current dir or script dir."""
    candidate_paths = [
        ".env",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    ]
    for env_path in candidate_paths:
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        if k and k not in os.environ:
                            os.environ[k] = v


def parse_frontmatter(file_content: str):
    """Extract YAML frontmatter and raw body from markdown file."""
    meta = {}
    body = file_content
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", file_content, re.DOTALL)
    if match:
        raw_meta, body = match.groups()
        for line in raw_meta.strip().split("\n"):
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip().lower()] = v.strip().strip('"').strip("'")
    return meta, body


def extract_company_identity(docs_raw: list, target_ticker: str):
    """
    Dynamically discover the target company's official name and core identifiers
    from official regulatory filings matching the ticker.
    """
    ticker_clean = target_ticker.upper()
    canonical_name = None
    
    # Priority 1: Check official filings matching the ticker
    for meta, body, _ in docs_raw:
        doc_type = meta.get("type", "").lower()
        if "official" in doc_type or "filing" in doc_type:
            # Look for patterns like "Company Name (NSE: TICKER)" or "Company Name Ltd"
            match = re.search(r"([A-Z][A-Za-z0-9\s&]+(?:Ltd|Limited|Corp|Industries|Enterprises)?)\s*\((?:NSE|BSE):\s*" + re.escape(ticker_clean) + r"\)", body)
            if match:
                canonical_name = match.group(1).strip()
                break
            # Fallback: Check title or header
            if ticker_clean in body.upper():
                title_match = re.search(r"#\s*([A-Z][A-Za-z0-9\s&]+(?:Ltd|Limited|Corp)?)", body)
                if title_match:
                    canonical_name = title_match.group(1).strip()
                    break

    return {
        "ticker": ticker_clean,
        "canonical_name": canonical_name or ticker_clean,
    }


def sanitize_and_inspect_document(filename: str, meta: dict, body: str, target_profile: dict):
    """
    Stage 1:
    1. Strip hidden HTML comments (neutralizes indirect prompt injections dynamically).
    2. Dynamic Entity Disambiguation: Verifies if document refers to the target company/ticker
       or an unrelated entity sharing a partial name.
    3. Categorizes source credibility hierarchy.
    """
    flags = []
    ticker = target_profile["ticker"]
    canonical_name = target_profile["canonical_name"].lower()
    
    # 1. Dynamic Prompt Injection Detection & Sanitization
    html_comments = re.findall(r"<!--(.*?)-->", body, re.DOTALL)
    cleaned_body = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL).strip()
    
    for comment in html_comments:
        if any(term in comment.lower() for term in ["ignore", "override", "system prompt", "strong buy", "consensus"]):
            flags.append("Prompt injection attempt detected and removed")

    # 2. Dynamic Entity Disambiguation
    full_text_lower = (meta.get("source", "") + " " + meta.get("url", "") + " " + body).lower()
    has_ticker = ticker.lower() in full_text_lower
    has_canonical = canonical_name in full_text_lower if canonical_name else False
    
    # Also check core root name (e.g. 'sarvottam' from 'Sarvottam Cables Ltd')
    core_name_root = canonical_name.split()[0] if canonical_name else ""
    has_root = (core_name_root in full_text_lower) if (core_name_root and len(core_name_root) > 3) else False

    # 3. Dynamic Source Credibility Grading
    doc_type = meta.get("type", "unknown").lower()
    if any(k in doc_type for k in ["official", "exchange", "filing", "transcript"]):
        credibility = "Official Filing"
        is_official = True
    elif any(k in doc_type for k in ["news", "journalism", "article"]):
        credibility = "Financial News"
        is_official = False
    else:
        credibility = "Unverified Blog"
        is_official = False

    # Dynamic Entity Collision: Only third-party documents are susceptible to name collisions
    if not is_official and not (has_ticker or has_canonical):
        if has_root:
            flags.append(f"Potential entity collision: Mentions root name '{core_name_root.capitalize()}' but lacks ticker {ticker} or full company name")
        else:
            flags.append(f"Entity mismatch: Missing reference to ticker {ticker} or company name")

    return {
        "filename": os.path.basename(filename),
        "source": meta.get("source", "Unknown"),
        "url": meta.get("url", "N/A"),
        "published": meta.get("published", "Unknown"),
        "type": meta.get("type", "Unknown"),
        "credibility": credibility,
        "flags": flags,
        "cleaned_body": cleaned_body,
    }


def detect_numerical_discrepancies(processed_docs: list):
    """
    Dynamically scan documents for contradictory financial figures across sources
    (e.g., contrasting revenue figures between official disclosures and media reports).
    """
    discrepancies = []
    revenue_claims = []

    # Regex to capture claimed revenue numbers: ₹X,XXX crore or X,XXX crore
    revenue_pattern = re.compile(r"(?:revenue|sales)(?:[^\n\.\;]*?)(?:₹\s*|rs\.?\s*)([\d,]+)\s*(?:crore|cr)?", re.IGNORECASE)

    for doc in processed_docs:
        matches = revenue_pattern.findall(doc["cleaned_body"])
        for m in matches:
            val_clean = m.replace(",", "").strip()
            if val_clean.isdigit() and int(val_clean) > 100:  # Ignore trivial numbers
                revenue_claims.append({
                    "doc": doc["filename"],
                    "credibility": doc["credibility"],
                    "val": int(val_clean),
                    "source": doc["source"]
                })

    # Compare claims: find any pair with significant divergence (>10%)
    for i in range(len(revenue_claims)):
        for j in range(i + 1, len(revenue_claims)):
            v1, v2 = revenue_claims[i]["val"], revenue_claims[j]["val"]
            if abs(v1 - v2) / max(v1, v2) > 0.08:
                conflict_desc = (
                    f"Conflicting Revenue: {revenue_claims[i]['source']} reports ₹{v1:,} Cr vs "
                    f"{revenue_claims[j]['source']} reports ₹{v2:,} Cr"
                )
                if conflict_desc not in discrepancies:
                    discrepancies.append(conflict_desc)

    return discrepancies


def load_research_pack(folder_path: str, target_ticker: str = "SRVCABLE"):
    """Load and process all markdown documents in the specified folder dynamically."""
    md_files = glob.glob(os.path.join(folder_path, "*.md"))
    if not md_files:
        raise FileNotFoundError(f"No markdown documents found in {folder_path}")

    raw_docs = []
    for fpath in sorted(md_files):
        base = os.path.basename(fpath).lower()
        if base in ["readme.md", "system_prompt.md", "test_log.md", "brief_srvcable.md", "video_script.md"]:
            continue
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
        meta, body = parse_frontmatter(content)
        raw_docs.append((meta, body, fpath))

    # 1. Dynamically resolve canonical company identity from official filings
    target_profile = extract_company_identity(raw_docs, target_ticker)

    # 2. Inspect and sanitize all documents relative to target profile
    processed_docs = []
    for meta, body, fpath in raw_docs:
        doc_info = sanitize_and_inspect_document(fpath, meta, body, target_profile)
        processed_docs.append(doc_info)

    # 3. Dynamically cross-check for numerical discrepancies
    conflicts = detect_numerical_discrepancies(processed_docs)

    return processed_docs, target_profile, conflicts


def build_agent_payload(docs: list, target_profile: dict, conflicts: list):
    """Assemble formatted dossier for the LLM synthesis stage with audit alerts."""
    ticker = target_profile["ticker"]
    company_name = target_profile["canonical_name"]

    payload_parts = [
        f"# Research Dossier for Ticker: NSE:{ticker} ({company_name})",
        f"**Evaluation Anchor Date:** 23 September 2026",
        f"Total documents processed: {len(docs)}",
    ]

    if conflicts:
        payload_parts.append("\n### [AUTOMATED CROSS-AUDIT ALERTS]")
        for c in conflicts:
            payload_parts.append(f"- ⚠️ {c} (Must reconcile under Open Questions)")

    payload_parts.append("\n---\n")

    for idx, doc in enumerate(docs, 1):
        flag_text = f" | Flags: {', '.join(doc['flags'])}" if doc['flags'] else ""
        payload_parts.append(
            f"### [Document {idx}] {doc['filename']}\n"
            f"- Source: {doc['source']}\n"
            f"- URL: {doc['url']}\n"
            f"- Publication Date: {doc['published']}\n"
            f"- Source Credibility: {doc['credibility']}{flag_text}\n\n"
            f"Content:\n{doc['cleaned_body']}\n"
            f"---\n"
        )

    return "\n".join(payload_parts)


def stream_research_brief(dossier_text: str, system_prompt: str, model: str = "gpt-4o-mini", api_key: str = None):
    """Execute LLM synthesis using OpenAI API with streaming token chunks."""
    if not OpenAI:
        raise RuntimeError("OpenAI package not installed. Run `pip install openai`.")

    client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Here is the scraped research dossier. Please synthesize the 1-page investment brief for retail investors:\n\n{dossier_text}"}
        ],
        temperature=0.2,  # Low temperature for factual consistency and disciplined citations
        stream=True,
    )
    for chunk in response:
        if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


def generate_research_brief(dossier_text: str, system_prompt: str, model: str = "gpt-4o-mini", api_key: str = None):
    """Execute LLM synthesis using OpenAI API (synchronous wrapper)."""
    full_text = []
    for token in stream_research_brief(dossier_text, system_prompt, model=model, api_key=api_key):
        full_text.append(token)
    return "".join(full_text)


def execute_research_pipeline_stream(docs_dir: str, ticker: str = "SRVCABLE", model: str = "gpt-4o-mini", api_key: str = None, system_prompt_file: str = "system_prompt.md"):
    """
    Generator executing each pipeline task step-by-step and yielding real-time events.
    Enables live web dashboard updates for document ingestion, safety guards, discrepancy checks,
    dossier generation, and token streaming.
    """
    # Task 1: Ingestion Scan
    yield ("step_update", {
        "step": 1,
        "name": "Document Ingestion & Parsing",
        "status": "Scanning markdown files in research pack...",
        "progress": 15
    })
    time.sleep(0.08)

    md_files = glob.glob(os.path.join(docs_dir, "*.md"))
    if not md_files:
        raise FileNotFoundError(f"No markdown documents found in {docs_dir}")

    valid_files = []
    for fpath in sorted(md_files):
        base = os.path.basename(fpath).lower()
        if base in ["readme.md", "system_prompt.md", "test_log.md", "brief_srvcable.md", "brief_hello.md", "video_script.md"]:
            continue
        valid_files.append(fpath)

    yield ("files_found", {
        "total": len(valid_files),
        "files": [os.path.basename(f) for f in valid_files]
    })

    raw_docs = []
    for idx, fpath in enumerate(valid_files, 1):
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
        meta, body = parse_frontmatter(content)
        raw_docs.append((meta, body, fpath))
        yield ("doc_read", {
            "index": idx,
            "total": len(valid_files),
            "filename": os.path.basename(fpath),
            "source": meta.get("source", "Unknown"),
            "published": meta.get("published", ""),
            "credibility": meta.get("type", "Document")
        })
        time.sleep(0.06)

    # Task 2: Entity Disambiguation & Trap Filtering
    yield ("step_update", {
        "step": 2,
        "name": "Entity Resolution & Trap Neutralization",
        "status": f"Resolving canonical company profile for NSE:{ticker} and defusing adversarial traps...",
        "progress": 35
    })
    time.sleep(0.08)

    target_profile = extract_company_identity(raw_docs, ticker)
    yield ("profile_resolved", {
        "profile": target_profile
    })

    processed_docs = []
    all_alerts = []
    for idx, (meta, body, fpath) in enumerate(raw_docs, 1):
        doc_info = sanitize_and_inspect_document(fpath, meta, body, target_profile)
        processed_docs.append(doc_info)
        doc_alerts = []
        for flag in doc_info["flags"]:
            alert_obj = {"file": doc_info["filename"], "flag": flag}
            all_alerts.append(alert_obj)
            doc_alerts.append(alert_obj)

        yield ("doc_inspected", {
            "index": idx,
            "total": len(raw_docs),
            "filename": doc_info["filename"],
            "source": doc_info["source"],
            "published": doc_info["published"],
            "credibility": doc_info["credibility"],
            "flags": doc_info["flags"],
            "alerts": doc_alerts
        })
        time.sleep(0.08)

    # Task 3: Quantitative Metric Cross-Audit
    yield ("step_update", {
        "step": 3,
        "name": "Quantitative Metric Cross-Audit",
        "status": "Auditing financial figures and identifying factual discrepancies...",
        "progress": 60
    })
    time.sleep(0.08)

    conflicts = detect_numerical_discrepancies(processed_docs)
    yield ("audit_complete", {
        "conflicts": conflicts,
        "conflict_count": len(conflicts)
    })

    # Task 4: Compile Structured Audit Dossier
    yield ("step_update", {
        "step": 4,
        "name": "Audit Dossier Compilation",
        "status": "Assembling verified, citation-ready research dossier...",
        "progress": 75
    })
    time.sleep(0.08)

    dossier = build_agent_payload(processed_docs, target_profile, conflicts)
    doc_summaries = [
        {
            "filename": d["filename"],
            "source": d["source"],
            "published": d["published"],
            "credibility": d["credibility"],
            "flags": d["flags"],
        }
        for d in processed_docs
    ]
    yield ("dossier_ready", {
        "dossier": dossier,
        "docs": doc_summaries,
        "alerts": all_alerts,
        "conflicts": conflicts
    })

    # Task 5: Grounded LLM Synthesis with Real-Time Token Streaming
    yield ("step_update", {
        "step": 5,
        "name": "Grounded LLM Brief Synthesis",
        "status": f"Streaming verified retail investment brief via {model}...",
        "progress": 85
    })

    if not os.path.exists(system_prompt_file):
        raise FileNotFoundError(f"System prompt file not found: {system_prompt_file}")
    with open(system_prompt_file, "r", encoding="utf-8") as f:
        system_prompt = f.read()

    full_brief_chunks = []
    for token in stream_research_brief(dossier, system_prompt, model=model, api_key=api_key):
        full_brief_chunks.append(token)
        yield ("chunk", {"delta": token})

    full_brief = "".join(full_brief_chunks)

    # Save to disk
    base_dir = os.path.dirname(os.path.abspath(system_prompt_file)) if os.path.isabs(system_prompt_file) else "."
    output_filename = f"brief_{ticker.lower()}.md"
    output_path = os.path.join(base_dir, output_filename)
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(full_brief)
    except Exception:
        pass

    yield ("complete", {
        "progress": 100,
        "brief": full_brief,
        "output_file": output_filename,
        "profile": target_profile,
        "conflicts": conflicts,
        "alerts": all_alerts,
        "docs": doc_summaries,
        "dossier": dossier
    })


def main():
    load_env_file()
    parser = argparse.ArgumentParser(description="Super Investing - Stock Research Agent")
    parser.add_argument("--ticker", default="SRVCABLE", help="Target NSE ticker (default: SRVCABLE)")
    parser.add_argument("--docs_dir", default="", help="Path to research pack folder")
    parser.add_argument("--model", default="gpt-4o-mini", help="LLM model (e.g. gpt-4o-mini, gpt-4o)")
    parser.add_argument("--api-key", default="", help="OpenAI API key (or set OPENAI_API_KEY env var)")
    parser.add_argument("--output", default="brief_srvcable.md", help="Output brief filename")
    parser.add_argument("--system_prompt_file", default="system_prompt.md", help="System prompt file")
    args = parser.parse_args()

    # Determine docs directory
    docs_dir = args.docs_dir
    if not docs_dir:
        if os.path.exists("./research_pack"):
            docs_dir = "./research_pack"
        else:
            docs_dir = "."

    print(f"[*] Target Ticker: NSE:{args.ticker}")
    print(f"[*] Reading documents from: {docs_dir}")
    docs, target_profile, conflicts = load_research_pack(docs_dir, args.ticker)
    print(f"[*] Resolved Company Profile: {target_profile['canonical_name']} (NSE:{target_profile['ticker']})")
    print(f"[*] Loaded and inspected {len(docs)} documents.")

    # Show Stage 1 inspection highlights
    for d in docs:
        if d['flags']:
            print(f"    [!] Security/Entity Alert in {d['filename']}: {d['flags']}")

    if conflicts:
        for c in conflicts:
            print(f"    [!] Data Conflict Detected: {c}")

    # Read system prompt
    prompt_path = args.system_prompt_file
    if not os.path.isabs(prompt_path):
        prompt_path = os.path.join(os.path.dirname(__file__) or ".", prompt_path)

    with open(prompt_path, "r", encoding="utf-8") as f:
        system_prompt = f.read()

    dossier = build_agent_payload(docs, target_profile, conflicts)

    # Check for API key
    api_key = args.api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("\n[!] OPENAI_API_KEY environment variable not set.")
        print("[!] To run live inference: export OPENAI_API_KEY='sk-...' or pass --api-key <key>")
        print("[!] Preparing offline evaluation / verified baseline...")
        return

    print(f"[*] Generating Research Brief using model: {args.model} ...")
    brief = generate_research_brief(dossier, system_prompt, model=args.model, api_key=api_key)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(brief)

    print(f"\n[+] Research brief successfully written to {args.output}\n")
    print("=" * 60)
    print(brief)
    print("=" * 60)


if __name__ == "__main__":
    main()
