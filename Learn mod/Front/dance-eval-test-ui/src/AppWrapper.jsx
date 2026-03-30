// src/AppWrapper.jsx
/**
 * App Wrapper with Mode Switching
 * Allows switching between Dance Evaluation and Performance Testing
 */

import React, { useState } from "react";
import App from "./App.jsx";
import PerformanceMonitor from "./PerformanceMonitor.jsx";
import "./AppWrapper.css";

export default function AppWrapper() {
  const [mode, setMode] = useState("dance"); // "dance" or "performance"

  return (
    <div className="app-wrapper">
      {/* Mode Switcher */}
      <div className="app-mode-switcher">
        <button
          className={`mode-button ${mode === "dance" ? "active" : ""}`}
          onClick={() => setMode("dance")}
        >
          <span className="icon">🎭</span>
          <span className="label">Dance Evaluation</span>
        </button>
        <button
          className={`mode-button ${mode === "performance" ? "active" : ""}`}
          onClick={() => setMode("performance")}
        >
          <span className="icon">🚀</span>
          <span className="label">Performance Testing</span>
        </button>
      </div>

      {/* Content */}
      <div className="app-content">
        {mode === "dance" && <App />}
        {mode === "performance" && <PerformanceMonitor />}
      </div>
    </div>
  );
}
