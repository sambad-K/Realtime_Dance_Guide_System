import { Navigate } from "react-router-dom";

export default function ProtectedRoute({ children }) {
  const access = localStorage.getItem("access");
  return access ? children : <Navigate to="/login" />;
}
