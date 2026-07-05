# Where LLMs are used in this project

This version uses real LLM calls in the backend.

## 1. Planner Agent
File: `backend/app.py`
Function: `planner_agent()`

Uses a small LLM to:
- check whether the question is related to the DB
- decompose the question
- identify tables, filters, grouping, sorting, and expected output

Model env variable:
`PLANNER_MODEL`

## 2. SQL Agent
File: `backend/app.py`
Function: `sql_agent()`

Uses a small/medium LLM to:
- convert natural language + planner output + DB schema into SQLite SELECT SQL
- correct SQL based on validator feedback during retries

Model env variable:
`SQL_MODEL`

## 3. MCP Read-only SQL Tool
File: `backend/app.py`
Function: `run_readonly_sql()`

This represents the MCP database tool:
- accepts only SELECT SQL
- checks guardrails
- opens SQLite in read-only mode
- executes the query

## 4. Validation Agent
File: `backend/app.py`
Function: `validation_agent()`
Function: `build_validation_graph()`

Uses LangGraph to control retry loop:
- generate SQL
- execute read-only SQL
- validate with strong LLM
- retry up to 5 times when invalid

Model env variable:
`VALIDATION_MODEL`

## 5. Final Formatter
File: `backend/app.py`
Function: `format_final_answer()`

Uses a small LLM to convert result rows into a clean human answer.

Model env variable:
`FORMATTER_MODEL`

## Run backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# add your API key in .env
uvicorn app:app --reload
```

## Run frontend

```bash
cd frontend
npm install
npm run dev
```
