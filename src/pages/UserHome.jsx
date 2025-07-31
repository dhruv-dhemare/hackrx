import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import './UserHome.css';
import Header from '../components/UserHeader';

const UserHome = () => {
  const navigate = useNavigate();
  const [query, setQuery] = useState(''); // 🟦 Add state for input

  const handleLogout = () => {
    navigate('/');
  };

  const handleInputChange = (e) => {
    setQuery(e.target.value); // 🟦 Update state on typing
  };

  return (
    <div className="user-home-container">
      <Header />

      <main className="user-home-main">
        <div className="query-box">
          <input
            type="text"
            value={query} // 🟦 Bind input value to state
            onChange={handleInputChange} // 🟦 Handle input change
            placeholder="Ask your document anything..."
            className="query-input"
          />
          <button className="send-btn">➤</button>
        </div>

        <div className="response-box">
          <p className="placeholder-response">
            Your answer will appear here...
          </p>
        </div>
      </main>
    </div>
  );
};

export default UserHome;
