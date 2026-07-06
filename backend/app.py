from __future__ import annotations

import json
import os
import re
import sqlite3
from typing import Any, Dict, List, Optional, TypedDict

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, StateGraph
from pydantic import BaseModel

load_dotenv()

app = FastAPI(title="Custom LangChain SQL Agent with Gemini")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = os.getenv("DB_PATH", os.path.abspath("sales.db"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "5"))

FORBIDDEN_SQL = re.compile(
    r"\b(insert|update|delete|drop|alter|create|attach|detach|replace|pragma|vacuum|reindex|truncate)\b",
    re.I,
)


class AskIn(BaseModel):
    question: str


class GraphState(TypedDict, total=False):
    question: str
    plan: Dict[str, Any]
    sql: str
    rows: List[Dict[str, Any]]
    valid: bool
    feedback: str
    attempts: int
    final_answer: str


def get_llm(model_env_name: str, default_model: str):
    api_key = os.getenv("GOOGLE_API_KEY")

    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY is missing in .env file")

    return ChatGoogleGenerativeAI(
        model=os.getenv(model_env_name, default_model),
        temperature=0,
        google_api_key=api_key,
    )


def connect_readonly() -> sqlite3.Connection:
    uri = f"file:{os.path.abspath(DB_PATH)}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def is_safe_select(sql: str) -> tuple[bool, str]:
    q = sql.strip()

    if not q.lower().startswith("select"):
        return False, "Only SELECT queries are allowed."

    if FORBIDDEN_SQL.search(q):
        return False, "Blocked SQL keyword found."

    if ";" in q.rstrip(";"):
        return False, "Multiple SQL statements are not allowed."

    return True, "safe"


def run_readonly_sql(sql: str) -> List[Dict[str, Any]]:
    safe, reason = is_safe_select(sql)

    if not safe:
        raise ValueError(reason)

    conn = connect_readonly()

    try:
        cur = conn.execute(sql)
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def get_schema_text() -> str:
    conn = connect_readonly()

    try:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()

        chunks = []

        for table in tables:
            table_name = table[0]
            cols = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
            col_text = ", ".join([f"{c['name']} {c['type']}" for c in cols])
            chunks.append(f"{table_name}({col_text})")

        return "\n".join(chunks)

    finally:
        conn.close()


def parse_json_from_llm(text: str) -> Dict[str, Any]:
    cleaned = re.sub(r"```json|```", "", text, flags=re.I).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if start != -1 and end != -1:
        cleaned = cleaned[start:end + 1]

    return json.loads(cleaned)


def strip_sql(text: str) -> str:
    cleaned = re.sub(r"```sql|```", "", text, flags=re.I).strip()
    cleaned = cleaned.rstrip(";").strip()
    return cleaned


def planner_agent(question: str) -> Dict[str, Any]:
    llm = get_llm("PLANNER_MODEL", "gemini-2.5-flash")
    schema = get_schema_text()

    prompt = ChatPromptTemplate.from_messages([
        ("system", """
You are the PLANNER AGENT for a car dealership SQLite database.

Your job:
1. Decide if the question is related to this database.
2. If relevant, break it into intent, required tables, filters, grouping, sorting, and expected output.
3. Return JSON only.

Important:
- Customer_Ownership represents purchases/sales.
- Sales-related words include sold, sales, purchase, revenue, dealer, brand, model, customer, vehicle, VIN, color, parts, recall, plant, warranty.
- If unrelated, set relevant=false.

Return JSON only:

{{
  "relevant": true,
  "intent": "...",
  "tables": ["..."],
  "filters": {{}},
  "grouping": "...",
  "sorting": "...",
  "expected_output": "..."
}}
"""),
        ("human", "Schema:\n{schema}\n\nQuestion:\n{question}")
    ])

    msg = (prompt | llm).invoke({
        "schema": schema,
        "question": question
    })

    return parse_json_from_llm(msg.content)


def custom_langchain_sql_agent(
    question: str,
    plan: Dict[str, Any],
    feedback: Optional[str] = None
) -> str:
    """
    Customized LangChain SQL Agent.

    This agent does not execute SQL directly.
    It only generates a safe SQLite SELECT query.
    Execution happens later through read-only guarded database function.
    """

    llm = get_llm("SQL_MODEL", "gemini-2.5-flash")
    schema = get_schema_text()

    prompt = ChatPromptTemplate.from_messages([
        ("system", """
You are a CUSTOM LANGCHAIN SQL AGENT for SQLite.

Your only job:
Generate one correct SQLite SELECT query for the user's question.

Strict SQL rules:
- Return SQL only.
- Do not explain.
- Do not use markdown.
- Generate only SELECT queries.
- Never generate INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, REPLACE, PRAGMA, VACUUM.
- Do not use multiple statements.
- Use only tables and columns from the provided schema.
- Customer_Ownership is the purchase/sales table.
- Use JOINs when required.
- For top/highest/most questions, use GROUP BY, ORDER BY DESC, and LIMIT.
- For listing questions, use LIMIT 50.
- If validator feedback is provided, correct the SQL based on that feedback.

You must produce a query that can run directly in SQLite.
"""),
        ("human", """
Database Schema:
{schema}

User Question:
{question}

Planner Agent Output:
{plan}

Validator Feedback From Previous Attempt:
{feedback}

Return only the SQL query.
""")
    ])

    response = (prompt | llm).invoke({
        "schema": schema,
        "question": question,
        "plan": json.dumps(plan, default=str),
        "feedback": feedback or "None"
    })

    return strip_sql(response.content)


def validation_agent(
    question: str,
    plan: Dict[str, Any],
    sql: str,
    rows: List[Dict[str, Any]]
) -> Dict[str, Any]:
    llm = get_llm("VALIDATION_MODEL", "gemini-2.5-flash")
    schema = get_schema_text()

    prompt = ChatPromptTemplate.from_messages([
        ("system", """
You are the VALIDATION AGENT.

Check whether the SQL query and database result correctly answer the user's question.

Validate:
- correct tables
- correct joins
- correct filters
- correct aggregation
- correct grouping
- correct ordering
- correct limit
- whether the result matches the user's intent

Return JSON only:

{{
  "valid": true,
  "reason": "short reason",
  "fix_hint": "specific correction if invalid"
}}
"""),
        ("human", """
Schema:
{schema}

Question:
{question}

Planner Output:
{plan}

SQL Generated By SQL Agent:
{sql}

Rows Returned From Database:
{rows}
""")
    ])

    msg = (prompt | llm).invoke({
        "schema": schema,
        "question": question,
        "plan": json.dumps(plan, default=str),
        "sql": sql,
        "rows": json.dumps(rows[:10], default=str)
    })

    return parse_json_from_llm(msg.content)


def format_final_answer(question: str, rows: List[Dict[str, Any]], sql: str) -> str:
    if not rows:
        return "No matching records were found for this question."

    llm = get_llm("FORMATTER_MODEL", "gemini-2.5-flash")

    prompt = ChatPromptTemplate.from_messages([
        ("system", """
Write a short business-friendly answer using the database result.
Return only plain text.
Do not mention hidden reasoning.
"""),
        ("human", """
Question:
{question}

SQL:
{sql}

Rows:
{rows}
""")
    ])

    msg = (prompt | llm).invoke({
        "question": question,
        "sql": sql,
        "rows": json.dumps(rows[:10], default=str)
    })

    return msg.content.strip()


def build_validation_graph():
    def generate_sql_node(state: GraphState) -> GraphState:
        attempt_no = state.get("attempts", 0) + 1

        sql = custom_langchain_sql_agent(
            question=state["question"],
            plan=state["plan"],
            feedback=state.get("feedback")
        )

        return {
            "sql": sql,
            "attempts": attempt_no
        }

    def execute_sql_node(state: GraphState) -> GraphState:
        safe, reason = is_safe_select(state["sql"])

        if not safe:
            return {
                "valid": False,
                "feedback": reason,
                "rows": []
            }

        try:
            rows = run_readonly_sql(state["sql"])
            return {"rows": rows}

        except Exception as exc:
            return {
                "valid": False,
                "feedback": f"SQL execution failed: {exc}",
                "rows": []
            }

    def validate_node(state: GraphState) -> GraphState:
        if state.get("valid") is False and state.get("feedback"):
            return {}

        verdict = validation_agent(
            question=state["question"],
            plan=state["plan"],
            sql=state["sql"],
            rows=state.get("rows", [])
        )

        return {
            "valid": bool(verdict.get("valid")),
            "feedback": verdict.get("fix_hint") or verdict.get("reason") or "Validation failed."
        }

    def final_answer_node(state: GraphState) -> GraphState:
        answer = format_final_answer(
            question=state["question"],
            rows=state.get("rows", []),
            sql=state["sql"]
        )

        return {"final_answer": answer}

    def should_retry(state: GraphState) -> str:
        if state.get("valid"):
            return "final"

        if state.get("attempts", 0) >= MAX_RETRIES:
            return "error"

        return "retry"

    graph = StateGraph(GraphState)

    graph.add_node("generate_sql", generate_sql_node)
    graph.add_node("execute_sql", execute_sql_node)
    graph.add_node("validate", validate_node)
    graph.add_node("final", final_answer_node)

    graph.set_entry_point("generate_sql")
    graph.add_edge("generate_sql", "execute_sql")
    graph.add_edge("execute_sql", "validate")

    graph.add_conditional_edges(
        "validate",
        should_retry,
        {
            "retry": "generate_sql",
            "final": "final",
            "error": END
        }
    )

    graph.add_edge("final", END)

    return graph.compile()


@app.get("/")
def root():
    return {
        "message": "Custom LangChain SQL Agent backend is running.",
        "docs": "http://127.0.0.1:8000/docs"
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "db_path": DB_PATH,
        "llm_provider": "Google Gemini",
        "planner_model": os.getenv("PLANNER_MODEL", "gemini-2.5-flash"),
        "sql_model": os.getenv("SQL_MODEL", "gemini-2.5-flash"),
        "validation_model": os.getenv("VALIDATION_MODEL", "gemini-2.5-flash"),
        "formatter_model": os.getenv("FORMATTER_MODEL", "gemini-2.5-flash"),
    }


@app.get("/schema")
def schema():
    return {"schema": get_schema_text()}


@app.post("/ask")
@app.post("/api/ask")
def ask(payload: AskIn):
    question = payload.question.strip()

    if not question:
        raise HTTPException(status_code=400, detail="Question is required.")

    try:
        plan = planner_agent(question)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Planner LLM failed: {exc}")

    if not plan.get("relevant"):
        return {
            "relevant": False,
            "answer_text": "This question is not related to the car dealership sales database.",
            "sql_query_sent_by_sql_agent": None,
            "database_result": [],
            "planner_output": plan,
            "validation_status": "not_required",
            "retry_count": 0,
        }

    graph = build_validation_graph()

    final_state = graph.invoke({
        "question": question,
        "plan": plan,
        "attempts": 0,
        "feedback": ""
    })

    if not final_state.get("valid"):
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Could not produce a validated answer after retries.",
                "answer_text": "Unable to generate a validated answer.",
                "last_sql_query_sent_by_sql_agent": final_state.get("sql"),
                "feedback": final_state.get("feedback"),
                "attempts": final_state.get("attempts")
            }
        )

    return {
    "answer": final_state.get("final_answer"),
    "sql_query": final_state.get("sql")
}