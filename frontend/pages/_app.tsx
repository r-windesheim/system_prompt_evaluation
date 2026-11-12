import '../styles/globals.css';
import type { AppProps } from 'next/app';
import { useEffect } from 'react';

export default function App({ Component, pageProps }: AppProps) {
  useEffect(() => {
    // Add smooth scroll behavior
    document.documentElement.style.scrollBehavior = 'smooth';
    
    // Add page transition animations
    const handleRouteChangeStart = () => {
      document.body.style.opacity = '0.8';
    };
    
    const handleRouteChangeComplete = () => {
      document.body.style.opacity = '1';
      window.scrollTo(0, 0);
    };
    
    // Note: Next.js router events would go here in production
    return () => {
      document.body.style.opacity = '1';
    };
  }, []);
  
  return <Component {...pageProps} />;
}
