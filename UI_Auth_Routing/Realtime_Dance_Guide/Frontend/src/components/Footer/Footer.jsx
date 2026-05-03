import React from 'react';
import { Link } from 'react-router-dom';
import styles from './Footer.module.css';

export default function Footer() {
  const currentYear = new Date().getFullYear();

  return (
    <footer className={styles.footer}>
      <div className={styles.footerContainer}>
        {/* Brand Section */}
        <div className={styles.footerSection}>
          <div className={styles.footerBrand}>
            <span className={styles.footerLogo}>🎭</span>
            <span className={styles.footerBrandText}>RDG</span>
          </div>
          <p className={styles.footerDescription}>
            Empowering dancers worldwide with AI-powered analysis and personalized feedback.
          </p>
          <div className={styles.socialLinks}>
            <a href="#" className={styles.socialIcon} aria-label="Facebook">
              📘
            </a>
            <a href="#" className={styles.socialIcon} aria-label="Twitter">
              🐦
            </a>
            <a href="#" className={styles.socialIcon} aria-label="Instagram">
              📷
            </a>
            <a href="#" className={styles.socialIcon} aria-label="YouTube">
              🎬
            </a>
          </div>
        </div>

        {/* Quick Links */}
        <div className={styles.footerSection}>
          <h3 className={styles.footerTitle}>Quick Links</h3>
          <ul className={styles.footerLinks}>
            <li>
              <Link to="/">Home</Link>
            </li>
            <li>
              <Link to="/practice">Practice</Link>
            </li>
            <li>
              <Link to="/test">Test</Link>
            </li>
            <li>
              <Link to="/profile">Profile</Link>
            </li>
          </ul>
        </div>

        {/* Resources */}
        <div className={styles.footerSection}>
          <h3 className={styles.footerTitle}>Resources</h3>
          <ul className={styles.footerLinks}>
            <li>
              <a href="#">About Us</a>
            </li>
            <li>
              <a href="#">How It Works</a>
            </li>
            <li>
              <a href="#">Blog</a>
            </li>
            <li>
              <a href="#">FAQs</a>
            </li>
          </ul>
        </div>

        {/* Support */}
        <div className={styles.footerSection}>
          <h3 className={styles.footerTitle}>Support</h3>
          <ul className={styles.footerLinks}>
            <li>
              <a href="#">Contact Us</a>
            </li>
            <li>
              <a href="#">Privacy Policy</a>
            </li>
            <li>
              <a href="#">Terms of Service</a>
            </li>
            <li>
              <a href="#">Help Center</a>
            </li>
          </ul>
        </div>
      </div>

      {/* Bottom Bar */}
      <div className={styles.footerBottom}>
        <p className={styles.copyright}>© {currentYear} HCOE. All rights reserved.</p>

      </div>
    </footer>
  );
}
