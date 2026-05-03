import React, { useState } from "react";
import styles from "./LoginModal.module.css";

export default function LoginModal({ onClose, onLoginSuccess }) {
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({
    username: "",
    email: "",
    password: "",
    agree: false,
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setForm((prev) => ({
      ...prev,
      [name]: type === "checkbox" ? checked : value,
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (mode === "signup") {
        if (!form.agree) {
          setError("You must agree to the Terms & Conditions");
          setLoading(false);
          return;
        }
        const res = await fetch("http://localhost:8000/api/signup/", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            username: form.username,
            email: form.email,
            password: form.password,
          }),
        });
        const data = await res.json();
        if (!res.ok) {
          setError(data.error || "Signup failed");
        } else {
          setMode("login");
          setError("Signup successful! Please login.");
        }
      } else {
        // login
        const res = await fetch("http://localhost:8000/api/login/", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            username: form.username || form.email,
            password: form.password,
          }),
        });
        const data = await res.json();
        if (data.access) {
          localStorage.setItem("access", data.access);
          localStorage.setItem("refresh", data.refresh);
          onLoginSuccess();
        } else {
          setError(data.detail || "Login failed");
        }
      }
    } catch (err) {
      setError("Network error");
    }
    setLoading(false);
  };

  return (
    <div className={styles.overlay}>
      <div className={styles.modal}>
        <h2>{mode === "login" ? "Login" : "Sign Up"}</h2>
        <form className={styles.form} onSubmit={handleSubmit}>
          {mode === "signup" && (
            <input
              type="text"
              name="username"
              placeholder="Username"
              className={styles.input}
              value={form.username}
              onChange={handleChange}
              required
            />
          )}
          <input
            type="email"
            name="email"
            placeholder="Email"
            className={styles.input}
            value={form.email}
            onChange={handleChange}
            required
          />
          <input
            type="password"
            name="password"
            placeholder="Password"
            className={styles.input}
            value={form.password}
            onChange={handleChange}
            required
          />

          {mode === "signup" && (
            <label className={styles.checkbox}>
              <input
                type="checkbox"
                name="agree"
                checked={form.agree}
                onChange={handleChange}
                required
              />
              <span>
                I agree to the{" "}
                <a href="/terms" target="_blank">
                  Terms & Conditions
                </a>
              </span>
            </label>
          )}
          <button type="submit" className={styles.submit} disabled={loading}>
            {loading
              ? "Please wait..."
              : mode === "login"
              ? "Login"
              : "Sign Up"}
          </button>
        </form>
        {error && <div style={{ color: "red", marginTop: 8 }}>{error}</div>}

        <p className={styles.toggle}>
          {mode === "login"
            ? "Don't have an account?"
            : "Already have an account?"}{" "}
          <span
            onClick={() => {
              setMode(mode === "login" ? "signup" : "login");
              setError("");
            }}
          >
            {mode === "login" ? "Sign Up" : "Login"}
          </span>
        </p>

        <button className={styles.close} onClick={onClose}>
          ✖
        </button>
      </div>
    </div>
  );
}
