import React, { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import styles from './Navbar.module.css';

export default function Navbar({ theme, setTheme, isLoggedIn, setIsLoggedIn }) {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();

  const handleProtectedNav = (route) => {
    if (isLoggedIn) {
      navigate(route);
    } else {
      navigate('/login');
    }
  };

  return (
    <nav className={styles.navbar}>
      <div className={styles.navContainer}>
        <NavLink to="/" className={styles.brand} onClick={() => setOpen(false)}>
          <span className={styles.logo}>🎭</span>
          <span className={styles.brandText}>RDG</span>
        </NavLink>

        <button
          className={styles.hamburger}
          aria-label={open ? 'Close menu' : 'Open menu'}
          aria-expanded={open}
          onClick={() => setOpen((p) => !p)}
        >
          <span />
          <span />
          <span />
        </button>

        <div className={`${styles.links} ${open ? styles.open : ''}`}>
          <button
            className={styles.navLink}
            onClick={() => {
              handleProtectedNav('/practice');
              setOpen(false);
            }}
          >
            Practice
          </button>
          <button
            className={styles.navLink}
            onClick={() => {
              handleProtectedNav('/test');
              setOpen(false);
            }}
          >
            Test
          </button>
          {/* duplicate profile/login inside mobile menu so it’s always reachable */}
          <div className={styles.mobileProfileWrapper}>
            {isLoggedIn ? (
              <button
                className={styles.profileButton}
                onClick={() => {
                  navigate('/profile');
                  setOpen(false);
                }}
              >
                <span className={styles.profileIcon}>👤</span>
                <span>Profile</span>
              </button>
            ) : (
              <button
                className={styles.loginButton}
                onClick={() => {
                  navigate('/login');
                  setOpen(false);
                }}
              >
                Login
              </button>
            )}
          </div>
        </div>
      </div>

      {/* bottom actions */}
      <div className={styles.bottom}>
        {isLoggedIn ? (
          <button className={styles.profileButton} onClick={() => { navigate('/profile'); setOpen(false); }}>
            <span className={styles.profileIcon}>👤</span>
            <span>Profile</span>
          </button>
        ) : (
          <button className={styles.loginButton} onClick={() => { navigate('/login'); setOpen(false); }}>
            Login
          </button>
        )}
      </div>
    </nav>
  );
}
