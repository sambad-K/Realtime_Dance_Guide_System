import React from 'react';
import styles from './Features.module.css';

export default function Features() {
  const features = [
    {
      icon: '🎯',
      title: 'Practice Mode',
      description: 'Upload and practice your dance routines with real-time feedback and analysis',
      color: 'var(--accent)',
    },
    {
      icon: '📊',
      title: 'Compare & Test',
      description: 'Test your skills by comparing your moves with professional dancers',
      color: 'var(--accent-hover)',
    },
    {
      icon: '💪',
      title: 'Track Progress',
      description: 'Monitor your improvement over time with detailed performance metrics',
      color: '#7BC47F',
    },
    {
      icon: '🎨',
      title: 'Smart Analysis',
      description:
        'Get AI-powered insights and personalized recommendations for better performance',
      color: '#E9A66A',
    },
  ];

  return (
    <section className={styles.features}>
      <div className={styles.featuresContainer}>
        <div className={styles.featuresHeader}>
          <h2 className={styles.sectionTitle}>Everything You Need to Improve</h2>
          <p className={styles.sectionSubtitle}>
            Powerful features designed to help you become a better dancer
          </p>
        </div>

        <div className={styles.featureGrid}>
          {features.map((feature, index) => (
            <div
              key={index}
              className={styles.featureCard}
              style={{ '--feature-color': feature.color }}
            >
              <div className={styles.featureIconWrapper}>
                <div className={styles.featureIcon}>{feature.icon}</div>
              </div>
              <h3 className={styles.featureTitle}>{feature.title}</h3>
              <p className={styles.featureDescription}>{feature.description}</p>
              <div className={styles.featureAccent}></div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
