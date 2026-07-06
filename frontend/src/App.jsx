import { useState } from "react";
import axios from "axios";
import "./style.css";

function App() {
  const [question, setQuestion] = useState("");
  const [response, setResponse] = useState(null);
  const [loading, setLoading] = useState(false);

  const askQuestion = async () => {
    if (!question.trim()) return;

    setLoading(true);
    setResponse(null);

    try {
      const res = await axios.post("http://127.0.0.1:8000/api/ask", {
        question: question,
      });

      setResponse(res.data);
    } catch (error) {
      setResponse({
        answer: "Something went wrong. Please check backend or API key.",
        sql_query: error.response?.data?.detail || error.message,
      });
    }

    setLoading(false);
  };

  return (
    <div className="page">
      <div className="glow glow1"></div>
      <div className="glow glow2"></div>

      <nav className="navbar">
        <div className="logo">AutoSQL AI</div>
        <div className="tag">LangChain • LangGraph • Gemini</div>
      </nav>

      <section className="hero">
        <h1>AI-Powered Car Dealership SQL Assistant</h1>
        <p>
          Ask questions about your dealership database in plain English. The AI
          planner understands your question, generates SQL, validates the result,
          and shows the exact query used.
        </p>
      </section>

      <div className="main-card">
        <div className="input-box">
          <textarea
            placeholder="Ask something like: Which customers own more than one vehicle?"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
          ></textarea>

          <button onClick={askQuestion} disabled={loading}>
            {loading ? "Thinking..." : "Ask AI Agent"}
          </button>
        </div>

        <div className="suggestions">
          <button onClick={() => setQuestion("Which customers own more than one vehicle?")}>
            Multiple vehicle owners
          </button>
          <button onClick={() => setQuestion("Which dealer generated the highest revenue?")}>
            Highest revenue dealer
          </button>
          <button onClick={() => setQuestion("Which brand sold the most vehicles?")}>
            Top selling brand
          </button>
        </div>
      </div>

      {loading && (
        <div className="loader-card">
          <div className="spinner"></div>
          <p>Planner Agent → SQL Agent → Validator Agent is working...</p>
        </div>
      )}

      {response && (
        <div className="result-grid">
          <div className="result-card answer-card">
            <h2>Final Answer</h2>
            <p>{response.answer || response.answer_text}</p>
          </div>

          <div className="result-card sql-card">
            <h2>SQL Query Sent to Database</h2>
            <pre>{response.sql_query || response.sql_query_sent_by_sql_agent}</pre>
          </div>
        </div>
      )}

      <section className="flow">
        <h2>Backend Agent Flow</h2>
        <div className="steps">
          <div>Planner Agent</div>
          <span>→</span>
          <div>SQL Agent</div>
          <span>→</span>
          <div>Guardrail</div>
          <span>→</span>
          <div>SQLite DB</div>
          <span>→</span>
          <div>Validator</div>
        </div>
      </section>
    </div>
  );
}

export default App;