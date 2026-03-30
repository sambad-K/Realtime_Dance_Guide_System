import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import styles from './LoginPage.module.css';

export default function LoginPage({ onLoginSuccess }) {
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [googleReady, setGoogleReady] = useState(false);
  const navigate = useNavigate();

  // Load Google OAuth script
  useEffect(() => {
    const script = document.createElement('script');
    script.src = 'https://accounts.google.com/gsi/client';
    script.async = true;
    script.defer = true;
    document.body.appendChild(script);

    return () => {
      if (document.body.contains(script)) {
        document.body.removeChild(script);
      }
    };
  }, []);

  // Initialize Google OAuth and One Tap
  useEffect(() => {
    const initializeGoogle = () => {
      if (!import.meta.env.VITE_GOOGLE_CLIENT_ID) {
        console.error('VITE_GOOGLE_CLIENT_ID is not configured');
        setError('Google Sign-In is not configured. Please contact the administrator.');
        return;
      }

      if (window.google) {
        try {
          window.google.accounts.id.initialize({
            client_id: import.meta.env.VITE_GOOGLE_CLIENT_ID,
            callback: handleGoogleCallback,
            auto_select: false,
            cancel_on_tap_outside: true,
          });

          // Render the standard Google Sign-In button
          const buttonDiv = document.getElementById('googleSignInButton');
          if (buttonDiv) {
            window.google.accounts.id.renderButton(buttonDiv, {
              theme: 'filled_blue',
              size: 'large',
              width: '100%',
              text: 'continue_with',
              shape: 'rectangular',
            });
            setGoogleReady(true);
          }

          // Display One Tap prompt
          window.google.accounts.id.prompt((notification) => {
            if (notification.isNotDisplayed()) {
              console.log('One Tap not displayed:', notification.getNotDisplayedReason());
            } else if (notification.isSkippedMoment()) {
              console.log('One Tap skipped:', notification.getSkippedReason());
            }
          });
        } catch (err) {
          console.error('Google initialization error:', err);
          setError('Failed to initialize Google Sign-In');
        }
      }
    };

    const timer = setTimeout(initializeGoogle, 1000);
    return () => clearTimeout(timer);
  }, []);

  const handleGoogleCallback = async (response) => {
    setLoading(true);
    setError('');

    try {
      const res = await fetch('http://localhost:8000/api/auth/google/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          token: response.credential,
        }),
      });

      const data = await res.json();

      if (res.ok) {
        localStorage.setItem('access', data.access);
        localStorage.setItem('refresh', data.refresh);
        localStorage.setItem('user', JSON.stringify(data.user));
        localStorage.setItem('isLoggedIn', 'true');

        if (onLoginSuccess) {
          onLoginSuccess();
        }

        // Force navigation with reload to update auth state
        window.location.href = '/';
      } else {
        setError(data.error || 'Google login failed');
      }
    } catch (err) {
      setError('Network error. Please try again.');
      console.error('Google login error:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.loginPage}>
      <div className={styles.loginContainer}>
        <div className={styles.loginLeft}>
          <div className={styles.brandSection}>
            <div className={styles.brandLogo}>
              <span className={styles.logoIcon}>🎭</span>
              <span className={styles.logoText}>RDG</span>
            </div>
            <h1 className={styles.brandTitle}>Welcome to Dance Learning Platform</h1>
            <p className={styles.brandDescription}>
              Master your dance skills with AI-powered analysis and personalized feedback.
            </p>
            <div className={styles.features}>
              <div className={styles.feature}>
                <span className={styles.featureIcon}>✓</span>
                <span>Real-time feedback</span>
              </div>
              <div className={styles.feature}>
                <span className={styles.featureIcon}>✓</span>
                <span>AI-powered analysis</span>
              </div>
              <div className={styles.feature}>
                <span className={styles.featureIcon}>✓</span>
                <span>Track your progress</span>
              </div>
            </div>
          </div>
        </div>

        <div className={styles.loginRight}>
          <div className={styles.formContainer}>
            <div className={styles.formHeader}>
              <h2 className={styles.formTitle}>Sign In with Google</h2>
              <p className={styles.formSubtitle}>
                Continue your dance learning journey with one click
              </p>
            </div>

            {error && (
              <div className={styles.errorAlert}>
                <span className={styles.errorIcon}>⚠️</span>
                {error}
              </div>
            )}

            <div className={styles.googleOnlyContainer}>
              <div className={styles.oneTapNotice}>
                <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
                <span>You may see a Google One Tap popup for quick sign-in</span>
              </div>

              <div id="googleSignInButton" className={styles.googleButton}></div>

              {!googleReady && !error && (
                <div className={styles.setupInfo}>
                  <h3>🔧 Setup Required</h3>
                  <p>To enable Google Sign-In, please:</p>
                  <ol>
                    <li>
                      Create a <code>.env</code> file in the Frontend folder
                    </li>
                    <li>
                      Add: <code>VITE_GOOGLE_CLIENT_ID=your-client-id-here</code>
                    </li>
                    <li>
                      Get your Client ID from{' '}
                      <a
                        href="https://console.cloud.google.com/"
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        Google Cloud Console
                      </a>
                    </li>
                    <li>Restart the development server</li>
                  </ol>
                </div>
              )}

              {loading && (
                <div className={styles.loadingContainer}>
                  <span className={styles.spinner}></span>
                  <span>Authenticating...</span>
                </div>
              )}

              {googleReady && (
                <div className={styles.securityNote}>
                  <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
                    />
                  </svg>
                  <span>Secure authentication powered by Google</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
