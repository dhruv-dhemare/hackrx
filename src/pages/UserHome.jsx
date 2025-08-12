import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import './UserHome.css';
import Header from '../components/UserHeader';

const UserHome = () => {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [response, setResponse] = useState(null);
  const [history, setHistory] = useState([]);

  const handleLogout = () => {
    navigate('/');
  };

  const handleInputChange = (e) => {
    setQuery(e.target.value);
  };

  // 🔹 Fetch history on page load
  useEffect(() => {
    fetch("http://localhost:3000/user/history")
      .then(res => res.json())
      .then(data => {
        console.log("📜 History:", data);
        setHistory(data);
      })
      .catch(err => console.error("❌ Error fetching history:", err));
  }, []);

  const handleSubmit = async () => {
    if (!query.trim()) return;

    try {
      const res = await fetch("http://localhost:3000/user/query", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ query }),
      });

      const data = await res.json();
      console.log("✅ Backend Response:", data);

      setResponse(data.answer);
      setQuery("");

      // Refresh history after new query
      setHistory(prev => [data, ...prev]);

    } catch (err) {
      console.error("❌ Error fetching response:", err);
    }
  };

  return (
    <div className="user-home-container">
      <Header />

      <main className="user-home-main">
        {/* Query Input */}
        <div className="query-box">
          <input
            type="text"
            value={query}
            onChange={handleInputChange}
            placeholder="Ask your document anything..."
            className="query-input"
          />
          <button className="send-btn" onClick={handleSubmit}>➤</button>
        </div>

        {/* Response + History */}
        <div className="response-box">
          {history.length > 0 ? (
            <div className="history-list">
              {history.map((item, index) => (
                <div key={item._id || index} className="history-item">
                  <p><strong>Q:</strong> {item.query}</p>
                  <p><strong>Decision:</strong> {item.answer?.decision}</p>
                  <p><strong>Amount:</strong> {item.answer?.amount}</p>
                  <p><strong>Justification:</strong> {item.answer?.justification}</p>
                  <hr />
                </div>
              ))}
            </div>
          ) : (
            <p className="placeholder-response">No queries yet. Ask your first one!</p>
          )}
        </div>
      </main>
    </div>
  );
};

export default UserHome;
