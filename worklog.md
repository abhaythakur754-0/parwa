---
Task ID: 1
Agent: Main Agent
Task: PARWA v2 pipeline improvements and empirical resolution rate analysis

Work Log:
- Analyzed v1 empirical results (18 tickets, 44.4% true resolution, 83.3% intent accuracy)
- Identified key gaps: tech subgraph (0% fully resolved), routing errors (R-002→billing, G-004→tech), intent errors (R-008, T-003)
- Rebuilt tech_subgraph.py with 11 nodes (was 9): added CUSTOMER_CONTEXT, SELF_CORRECTION nodes
- Fixed HTTP error code regex (\b\d{3}\b → \b[45]\d{2}\b), added OS/browser/version detection
- Added 40+ new tech keywords to router, weighted scoring, pattern regex for "can't/won't/doesn't work"
- Upgraded all 4 domain prompts: tech requires 3+ steps + workaround, refund requires exact $ amounts, complaints need concrete actions
- Added NVIDIA API as production LLM provider in real_llm.py with GLM-5.1 + DeepSeek + Llama-3.3-70b failover
- Ran 11 tickets through v2 pipeline using NVIDIA API
- Generated PDF report at /home/z/my-project/download/PARWA_v2_Resolution_Rate_Analysis.pdf

Stage Summary:
- v2 empirically tested on 11 tickets: 100% containment, 90.9% routing, 90.9% intent
- Head-to-head improvements: T-001 (partial→full), T-003 (partial→full + intent fix), R-008 (partial→full)
- Projected v2 metrics for 30 tickets: 50% true resolution (up from 44.4%), 96.7% industry-comparable
- Tech subgraph is biggest win: 0% → 71% true resolution
- Refund true resolution appears low (12%) due to stricter evaluation requiring exact $ amounts
- Key next step: Force exact dollar amounts in refund responses → projected 55-60% true resolution
- Report saved to /home/z/my-project/download/PARWA_v2_Resolution_Rate_Analysis.pdf
