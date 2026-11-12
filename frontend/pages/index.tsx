import { useEffect } from 'react';
import { useRouter } from 'next/router';

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    // Redirect to analyze page immediately
    router.replace('/analyze');
  }, [router]);

  return null;
}
