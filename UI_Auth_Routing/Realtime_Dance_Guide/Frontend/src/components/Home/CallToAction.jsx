import React from 'react';
import styles from './CallToAction.module.css';

export default function CallToAction({ handleClick }) {
  return (
    <section className={styles.cta}>
      <div className={styles.ctaContainer}>
        <div className={styles.ctaContent}>
          <div className={styles.ctaIcon}>🚀</div>
          <h2 className={styles.ctaTitle}>Ready to Get Started?</h2>
          <p className={styles.ctaSubtitle}>
            Join dancers worldwide who are improving their skills every day
          </p>
          <button className={styles.ctaButton} onClick={() => handleClick('/practice')}>
            <span>Begin Your Journey</span>
            <span className={styles.ctaArrow}>→</span>
          </button>
          <p className={styles.ctaNote}>No credit card required • Start practicing in minutes</p>
        </div>

        {/* Decorative circles */}
        <div className={styles.circle1}></div>
        <div className={styles.circle2}></div>
        <div className={styles.circle3}></div>
      </div>
    </section>
  );
}
