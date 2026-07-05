import React, { useState } from "react";

export default function App() {
  const [q, setQ] = useState("");
  const [resp, setResp] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const ask = async () => {
    setLoading(true);
    setError("");
    setResp(null);
    try {
      const apiBase = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
      const r = await fetch(`${apiBase}/api/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q }),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(JSON.stringify(data, null, 2));
      setResp(data);
    } catch (e) {
      setError(e.message || "Request failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: 24, maxWidth: 1000, margin: "auto", fontFamily: "Arial" }}>
      <h2>Car Dealership Sales Analysis Bot</h2>
      <p>Ask any sales-related question about dealers, brands, models, customers, purchases, revenue, colors, parts, or recalls.</p>
      <textarea
        rows={4}
        style={{ width: "100%" }}
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Example: Which dealer sold the most cars in 2025?"
      />
      <br />
      <button onClick={ask} disabled={loading || !q.trim()} style={{ marginTop: 12 }}>
        {loading ? "Thinking..." : "Ask"}
      </button>

      {error && <pre style={{ color: "red", whiteSpace: "pre-wrap" }}>{error}</pre>}

      {resp && (
        <div style={{ marginTop: 20 }}>
          <h3>Answer</h3>
          <p>{resp.answer}</p>
          {resp.sql && <><h3>SQL Query</h3><pre style={{ background: "#f4f4f4", padding: 12, whiteSpace: "pre-wrap" }}>{resp.sql}</pre></>}
          <h3>Validation</h3>
          <p>Status: {resp.validation_status || "not applicable"}</p>
          <p>Retries: {resp.retries ?? 0}</p>
          <h3>Raw Response</h3>
          <pre style={{ background: "#f4f4f4", padding: 12, whiteSpace: "pre-wrap" }}>{JSON.stringify(resp, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}
