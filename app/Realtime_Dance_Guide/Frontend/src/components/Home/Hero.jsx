import React from 'react';
import styles from './Hero.module.css';

export default function Hero({ handleClick }) {
  return (
    <section className={styles.hero}>
      <div className={styles.heroContainer}>
        <div className={styles.badge}>
          <span className={styles.badgeIcon}>✨</span>
          AI-Powered Dance Learning
        </div>

        <h1 className={styles.heroTitle}>
          Master Your Dance Skills
          <span className={styles.highlight}> with Confidence</span>
        </h1>

        <p className={styles.heroSubtitle}>
          Upload your routine, analyze movements, and get personalized feedback—all in your browser.
          No installation required.
        </p>

        <div className={styles.actions}>
          <button className={styles.primaryButton} onClick={() => handleClick('/practice')}>
            <span>Start Practicing</span>
            <span className={styles.arrow}>→</span>
          </button>
          <button className={styles.secondaryButton} onClick={() => handleClick('/test')}>
            Try a Test
          </button>
        </div>

        <div className={styles.stats}>
          <div className={styles.stat}>
            <div className={styles.statValue}>100%</div>
            <div className={styles.statLabel}>Browser-Based</div>
          </div>
          <div className={styles.statDivider}></div>
          <div className={styles.stat}>
            <div className={styles.statValue}>AI</div>
            <div className={styles.statLabel}>Powered Analysis</div>
          </div>
          <div className={styles.statDivider}></div>
          <div className={styles.stat}>
            <div className={styles.statValue}>0$</div>
            <div className={styles.statLabel}>Free to Start</div>
          </div>
        </div>
      </div>

      {/* Decorative elements */}
      <div className={styles.decoration1}></div>
      <div className={styles.decoration2}></div>
    </section>
  );
}
