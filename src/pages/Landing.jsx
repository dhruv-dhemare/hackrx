import React, { useState } from 'react';
import Header from '../components/Header';
import { useNavigate } from 'react-router-dom';


const Landing = () => {
    const navigate = useNavigate();

  const [hoveredBtn, setHoveredBtn] = useState(null);

  const handleMouseEnter = (btn) => setHoveredBtn(btn);
  const handleMouseLeave = () => setHoveredBtn(null);

  const getButtonStyle = (btn) => ({
    backgroundColor: hoveredBtn === btn ? '#e0f0ff' : '#ffffff',
    color: '#007edb',
    padding: '0.9rem 2rem',
    fontSize: '1rem',
    borderRadius: '0.6rem',
    border: 'none',
    cursor: 'pointer',
    fontWeight: '600',
    transition: 'background-color 0.3s ease, transform 0.2s ease',
    transform: hoveredBtn === btn ? 'scale(1.05)' : 'scale(1)',
  });

  return (
    <>
      <Header />
      <section style={styles.hero}>
        <div style={styles.container}>
          <div style={styles.left}>
            <h1 style={styles.heading}>Smarter Document Intelligence with AI</h1>
            <p style={styles.description}>
              Leverage AI to turn messy, unstructured files into clean, structured data.
              Extract insights from PDFs, emails, contracts, and more — instantly.
            </p>
            <div style={styles.buttons}>
              <button
  style={getButtonStyle('user')}
  onMouseEnter={() => handleMouseEnter('user')}
  onMouseLeave={handleMouseLeave}
  onClick={() => navigate('/user/home')} // 👈 Navigation added here
>
  Login as a User
</button>

              <button
                style={getButtonStyle('admin')}
                onMouseEnter={() => handleMouseEnter('admin')}
                onMouseLeave={handleMouseLeave}
                onClick={() => navigate('/admin/home')}
              >
                Login as an Admin
              </button>
            </div>
          </div>
          <div style={styles.right}>
            {/* Optional image here */}
            <img
              src="/your-image.png"
              alt="AI processing documents"
              style={styles.image}
            />
          </div>
        </div>
      </section>
    </>
  );
};

const styles = {
  hero: {
    backgroundColor: '#00a6ff',
    width: '100vw',
    height: '92vh',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
  },
  container: {
    width: '100%',
    maxWidth: '1200px',
    display: 'flex',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    // padding: '4vh 5vw',
    boxSizing: 'border-box',
  },
  left: {
    flex: '1.2',
    color: '#fff',
    paddingRight: '2vw',
    boxSizing: 'border-box',
    paddingBottom: '5rem',

  },
  heading: {
    fontSize: '3rem',
    fontWeight: 'bold',
    marginBottom: '1rem',
    lineHeight: '1.2',
  },
  description: {
    fontSize: '1.2rem',
    lineHeight: '1.6',
    marginBottom: '2rem',
  },
  buttons: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '1rem',
  },
  right: {
    flex: '0.8',
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    boxSizing: 'border-box',
  },
  image: {
    width: '90%',
    maxWidth: '400px',
    height: 'auto',
    borderRadius: '1rem',
  },
};

export default Landing;
