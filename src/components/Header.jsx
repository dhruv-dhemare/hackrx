// Header.jsx
import React from 'react';

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
        <a href="#" style={styles.link}>Home</a>
        <a href="#" style={styles.link}>About</a>
        <a href="#" style={styles.link}>Contact</a>
      </nav>
      <div style={styles.buttonGroup}>
        <button style={styles.login}>Login</button>
        <button style={styles.signup}>Sign Up</button>
      </div>
    </header>
  );
};

const styles = {
  header: {
    width: '100%',
    minHeight: '8vh',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '0 4vw',
    backgroundColor: '#ffffff',
    boxSizing: 'border-box',
    borderBottom: '0.05rem solid #e0e0e0',
    flexWrap: 'wrap',
  },
  logoContainer: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.8rem',
  },
  logo: {
    width: '2rem',
    height: '2rem',
  },
  brand: {
    fontSize: '1.5rem',
    color: '#007edb',
    margin: 0,
  },
  nav: {
    display: 'flex',
    gap: '2rem',
    flexWrap: 'wrap',
    justifyContent: 'center',
    alignItems: 'center',
  },
  link: {
    color: '#4a4a4a',
    textDecoration: 'none',
    fontSize: '1rem',
    fontWeight: '500',
  },
  buttonGroup: {
    display: 'flex',
    gap: '1rem',
    flexWrap: 'wrap',
    justifyContent: 'center',
  },
  login: {
    backgroundColor: '#ffffff',
    color: '#007edb',
    border: '0.1rem solid #007edb',
    padding: '0.5rem 1.2rem',
    borderRadius: '0.5rem',
    cursor: 'pointer',
    fontWeight: '500',
  },
  signup: {
    backgroundColor: '#007edb',
    color: '#ffffff',
    border: 'none',
    padding: '0.5rem 1.2rem',
    borderRadius: '0.5rem',
    cursor: 'pointer',
    fontWeight: '500',
  },
};

export default Header;
