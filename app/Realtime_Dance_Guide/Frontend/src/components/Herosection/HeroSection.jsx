import { useNavigate } from 'react-router-dom';
import styles from './HeroSection.module.css';

export default function HeroSection({ isLoggedIn, setShowLogin }) {
  const navigate = useNavigate();

  const handleClick = (path) => {
    if (isLoggedIn) {
      navigate(path);
    } else {
      setShowLogin(true);
    }
  };

  return (
    <div className={styles.homePage}>
      {/* Hero Section - Full Width */}
      <section className={styles.hero}>
        <div className={styles.heroOverlay}></div>
        <div className={styles.heroOverlay}></div>

        <div className={styles.heroContent}>
          <div className={styles.heroContainer}>
            <div className={styles.heroTextContent}>
              <h1 className={styles.heroTitle}>Master Your Dance Skills</h1>
              <p className={styles.heroSubtitle}>
                Upload, analyze, and perfect your moves with real-time feedback—all in your browser
              </p>
              <div className={styles.actions}>
                <button className={styles.primaryButton} onClick={() => handleClick('/practice')}>
                  Start Practicing
                  <span className={styles.arrow}>→</span>
                </button>
                <button className={styles.secondaryButton} onClick={() => handleClick('/test')}>
                  Try Test Mode
                </button>
              </div>
            </div>
            <div className={styles.heroVideoPreview}>
              <div className={styles.videoPlaceholder}>
                <video className={styles.previewVideo} autoPlay loop muted playsInline>
                  <source src="/dance3.mp4" type="video/mp4" />
                </video>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Welcome Section */}
      <section className={styles.welcome}>
        <div className={styles.welcomeContainer}>
          <div className={styles.welcomeBadge}>👋 Welcome</div>
          <h2 className={styles.welcomeTitle}>Your Dance Journey Starts Here</h2>
          <p className={styles.welcomeText}>
            Whether you're a beginner or a professional, our platform helps you improve your dance
            skills at your own pace. Track progress, get feedback, and perfect your moves.
          </p>
        </div>
      </section>

      {/* CTA Section - Full Width */}
      <section className={styles.cta}>
        <div className={styles.ctaContainer}>
          <h2 className={styles.ctaTitle}>Ready to Transform Your Dance Journey?</h2>
          <p className={styles.ctaSubtitle}>
            Join thousands of dancers improving their skills every day
          </p>
          <button className={styles.ctaButton} onClick={() => handleClick('/practice')}>
            Get Started
            <span className={styles.ctaArrow}>→</span>
          </button>
        </div>
      </section>
    </div>
  );
}
