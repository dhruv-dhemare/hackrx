// History.jsx
import React, { useEffect, useState } from "react";
import Header from "../components/AdminHeader";  // ✅ Import header
import "./History.css";

const QueryHistory = () => {
  const [history, setHistory] = useState([]);

  useEffect(() => {
    fetch("http://localhost:3000/user/history")
      .then((res) => res.json())
      .then((data) => {
        console.log("📜 History:", data);
        setHistory(data);
      })
      .catch((err) => console.error("❌ Error loading history:", err));
  }, []);

  return (
    <div className="history-page">
      {/* 🔹 Header */}
      <Header />

      <main className="history-content">
        <h2 className="history-title">Query History</h2>
        {history.length > 0 ? (
          <div className="history-list">
            {history.map((item, index) => (
              <div
                key={item._id || index}
                className={`history-card ${index === 0 ? "latest" : ""}`}
              >
                <p className="history-query">
                  <strong>Q:</strong> {item.query}
                </p>
                <p><strong>Decision:</strong> {item.answer?.decision}</p>
                <p><strong>Amount:</strong> {item.answer?.amount}</p>
                <p><strong>Justification:</strong> {item.answer?.justification}</p>
                <p className="history-time">
                  🕒 {new Date(item.timestamp).toLocaleString()}
                </p>
              </div>
            ))}
          </div>
        ) : (
          <p className="no-history">No queries yet.</p>
        )}
      </main>
    </div>
  );
};

export default QueryHistory;
