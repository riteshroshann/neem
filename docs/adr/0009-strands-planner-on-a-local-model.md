# 9. A Strands Agents planner on a local model

Date: 2026-10-10
Status: accepted

## Context

A principal does not want to place 85 trees by hand. An agent can propose a plan, but language models invent numbers, and a hosted model needs an account and a bill. The build has no AWS account.

## Decision

Use the Strands Agents SDK with a small open model (qwen3 4B) served by Ollama on the laptop GPU. Give it five coarse tools: read the brief, plant N trees of a species, add a sail, preview, verify. The model chooses quantities and species; the tools choose locations (greedy hottest-first placement, a crown apart, clear of buildings) and compute every figure. Budgets are enforced inside the tools, not by the prompt. The final design always goes through SOLWEIG; if the model skips that step the code runs it anyway.

## Consequences

- Plans for all four twins in about four minutes each, verified: for example 85 neems at KV Sector 25 take the 1 pm yard from 46.6 to 44.8 C.
- Small models drift: one run skipped the tools until `/no_think` moved into the user turn, and one ignored a budget flag until the tool started refusing. Both are now guarded in code.
- Swapping in Bedrock later is a one-line model change in Strands.
