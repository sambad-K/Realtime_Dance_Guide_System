import React, { useEffect, useState } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext.jsx';
import { BrowserRouter as Router, Routes, Route, useLocation } from 'react-router-dom';
import './App.css';
import Navbar from './components/Navbar/Navbar.jsx';
import HomePage from './components/Home/HomePage.jsx';
import LoginPage from './components/LoginPage/LoginPage.jsx';
import Practice from './components/Practice/Practice.jsx';
import Test from './components/Test/Test.jsx';
import Dashboard from './components/Dashboard/Dashboard.jsx';
import Profile from './components/Profile/Profile.jsx';
import VideoList from './components/VideoList/VideoList.jsx';
import LoginModal from './components/LoginModal/LoginModal.jsx';
import Footer from './components/Footer/Footer.jsx';

const baseVideos = [
  { src: '/videoplayback.mp4', title: 'Intro to React' },
  { src: '/88c3bed637e2dd9491d53b6910fab51b.mp4', title: 'CSS Fundamentals' },
];
const userVideos = [
  { src: 'user1.mp4', title: 'Project Showcase' },
  { src: 'user2.mp4', title: 'Custom Hooks Demo' },
];

function AppContent() {
  const location = useLocation();
  const [theme, setTheme] = useState(() => localStorage.getItem('theme') || 'light');
  const { user, isAuthenticated } = useAuth();
  const [showLogin, setShowLogin] = useState(false);

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
    localStorage.setItem('theme', theme);
  }, [theme]);

  const handleLoginSuccess = () => {
    localStorage.setItem('isLoggedIn', 'true');
    setShowLogin(false);
    window.location.reload();
  };

  // Hide navbar and footer on login page
  const isLoginPage = location.pathname === '/login';

  return (
    <>
      {!isLoginPage && (
        <Navbar
          theme={theme}
          setTheme={setTheme}
          isLoggedIn={isAuthenticated}
          setIsLoggedIn={() => {}}
          setShowLogin={setShowLogin}
        />
      )}
      <main>
        <Routes>
          <Route path="/" element={<HomePage isLoggedIn={isAuthenticated} />} />
          <Route path="/login" element={<LoginPage onLoginSuccess={handleLoginSuccess} />} />
          <Route path="/practice" element={<Practice />} />
          <Route path="/test" element={<Test />} />
          <Route path="/dashboard" element={<Dashboard username={(user && (user.data?.username || user.username)) || 'User'} />} />
          <Route path="/profile" element={<Profile username={(user && (user.data?.username || user.username)) || 'User'} />} />
          <Route path="/profile/base" element={<VideoList videos={baseVideos} />} />
          <Route path="/profile/user" element={<VideoList videos={userVideos} />} />
        </Routes>
      </main>
      {!isLoginPage && <Footer />}
    </>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <Router>
        <AppContent />
      </Router>
    </AuthProvider>
  );
}
