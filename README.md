# SENTINEL — Intelligent Log Triage and Incident Response Agent

An agentic AI system that ingests high-volume infrastructure logs, classifies 
and triages them in real time, investigates root causes autonomously, and 
escalates to human operators with a full reasoning trace.

## Architecture
- **Classifier-as-Router**: XGBoost pre-filter routes only MEDIUM/HIGH logs to the agent
- **LangGraph Agent**: Plan-and-Execute with reflection, 5 tools, HITL checkpoint
- **Memory Layer**: pgvector (long-term) + PostgreSQL (episodic) + LangGraph state (short-term)
- **API Layer**: FastAPI with SSE streaming
- **Monitoring**: LangSmith traces + token cost tracking

## Stack
- Agent: LangGraph + Claude Sonnet
- Classifier: XGBoost + scikit-learn  
- Vector DB: pgvector on Neon
- Storage: PostgreSQL on Neon
- Queue: Redis Streams
- API: FastAPI
- Deployment: Docker + Railway

## Status
🔨 In active development — Phase 2: System Design
