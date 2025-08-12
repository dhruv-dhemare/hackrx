// AdminHeader.jsx (or Header.jsx)
import React from "react";
import { Link } from "react-router-dom";

const Header = () => {
  return (
    <header style={styles.header}>
      <div style={styles.logoContainer}>
        <img
          src="https://img.icons8.com/ios-filled/50/000000/document--v1.png"
          alt="DocAI logo"
          style={styles.logo}
        />
        <h1 style={styles.brand}>DocAI</h1>
      </div>
      <nav style={styles.nav}>
        <Link to="/user/home" style={styles.link}>
          Home
        </Link>
        <Link to="/history" style={styles.link}>
          History
        </Link>
        <Link to="/" style={styles.link}>
          Logout
        </Link>
      </nav>
    </header>
  );
};

const styles = {
  header: {
    width: "100%",
    minHeight: "8vh",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "0 4vw",
    backgroundColor: "#ffffff",
    boxSizing: "border-box",
    borderBottom: "0.05rem solid #e0e0e0",
    flexWrap: "wrap",
  },
  logoContainer: {
    display: "flex",
    alignItems: "center",
    gap: "0.8rem",
  },
  logo: {
    width: "2rem",
    height: "2rem",
  },
  brand: {
    fontSize: "1.5rem",
    color: "#007edb",
    margin: 0,
  },
  nav: {
    display: "flex",
    gap: "2rem",
    flexWrap: "wrap",
    justifyContent: "center",
    alignItems: "center",
  },
  link: {
    color: "#4a4a4a",
    textDecoration: "none",
    fontSize: "1rem",
    fontWeight: "500",
  },
};

export default Header;
