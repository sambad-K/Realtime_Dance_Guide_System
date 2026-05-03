import React from "react";

export default function VideoList({ videos }) {
  const isMobile = window.innerWidth <= 600;

  const styles = {
    grid: {
      display: "flex",
      flexWrap: "wrap",
      gap: "1rem",
      justifyContent: "center",
      padding: "1rem",
      flexDirection: isMobile ? "column" : "row",
      alignItems: isMobile ? "center" : "stretch",
    },
    card: {
      position: "relative",
      flex: "1 1 300px",
      width: isMobile ? "90%" : "100%",
      maxWidth: isMobile ? "340px" : "400px",
      backgroundColor: "var(--card)",
      padding: isMobile ? "0.75rem" : "1rem",
      borderRadius: "8px",
      boxShadow: "0 2px 8px rgba(0,0,0,0.1)",
      color: "var(--text)",
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
    },
    videoWrapper: {
      width: "100%",
      height: "240px",
      display: "flex",
      justifyContent: "center",
      alignItems: "center",
    },
    video: {
      maxWidth: "100%",
      maxHeight: "100%",
      objectFit: "contain",
      borderRadius: "6px",
    },
    title: {
      position: "absolute",
      bottom: "0.75rem",
      left: "0",
      right: "0",
      textAlign: "center",
      fontWeight: "600",
      fontSize: "1rem",
    },
  };

  return (
    <div style={styles.grid}>
      {videos.map((video, index) => (
        <div key={index} style={styles.card}>
          <div style={styles.videoWrapper}>
            <video style={styles.video} src={video.src} controls />
          </div>
          <p style={styles.title}>{video.title}</p>
        </div>
      ))}
    </div>
  );
}
