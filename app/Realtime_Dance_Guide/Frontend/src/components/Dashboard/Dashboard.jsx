export default function Dashboard({ username }) {
  const styles = {
    container: {
      maxWidth: "700px",
      margin: "2rem auto",
      padding: "1rem",
    },
    profile: {
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
    },
    avatar: {
      width: "80px",
      height: "80px",
      borderRadius: "50%",
      background: "#ccc",
      marginBottom: "0.5rem",
    },
    username: {
      fontSize: "1.2rem",
      fontWeight: "bold",
      color: "var(--text)",
    },
    navbar: {
      display: "flex",
      justifyContent: "center",
      gap: "2rem",
      margin: "2rem 0",
    },
    tab: {
      color: "var(--accent)",
      fontWeight: "bold",
      textDecoration: "none",
    },
    section: {
      backgroundColor: "var(--card)",
      padding: "1rem",
      borderRadius: "8px",
      marginBottom: "1rem",
      boxShadow: "0 2px 8px rgba(0,0,0,0.05)",
    },
  };

  return (
    <div style={styles.container}>
      <div style={styles.profile}>
        <div style={styles.avatar}></div>
        <p style={styles.username}>{username}</p>
      </div>

      <nav style={styles.navbar}>
        <a href="#your-videos" style={styles.tab}>Your Videos</a>
        <a href="#base-videos" style={styles.tab}>Base Videos</a>
      </nav>

      <section id="your-videos" style={styles.section}>
        <h3>Your Uploaded Videos</h3>
        <p>(Placeholder for user-uploaded videos)</p>
      </section>

      <section id="base-videos" style={styles.section}>
        <h3>Base Learning Videos</h3>
        <p>(Placeholder for reference videos chosen by the user)</p>
      </section>
    </div>
  );
}
