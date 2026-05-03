/**
 * Auth Layout Component
 * Layout for authentication pages (login, signup)
 */
import React from "react";
import { Outlet } from "react-router-dom";
import styles from "./AuthLayout.module.css";

export const AuthLayout = () => {
  return (
    <div className={styles.authContainer}>
      <div className={styles.authContent}>
        <Outlet />
      </div>
    </div>
  );
};
