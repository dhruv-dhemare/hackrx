// App.jsx
import React from "react";
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";

import Landing from "./pages/Landing";
import UserHome from "./pages/UserHome";
import AdminHome from "./pages/AdminHome";
import History from "./components/History"; // ✅ Import History page

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/user/home" element={<UserHome />} />
        <Route path="/admin/home" element={<AdminHome />} />
        <Route path="/history" element={<History />} /> {/* ✅ New Route */}
      </Routes>
    </Router>
  );
}

export default App;