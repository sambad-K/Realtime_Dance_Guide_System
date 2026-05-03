import React, { useState } from 'react';
import HeroSection from '../Herosection/HeroSection';

export default function HomePage({ isLoggedIn }) {
  const [showLogin, setShowLogin] = useState(false);

  return <HeroSection isLoggedIn={isLoggedIn} setShowLogin={setShowLogin} />;
}
