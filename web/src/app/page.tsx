import Link from 'next/link';
import { Button } from '@/components/ui/Button';

export default function Home() {
  return (
    <main className="min-h-screen bg-gradient-to-b from-primary-50 to-white">
      <div className="container mx-auto px-4 py-16">
        <div className="text-center max-w-4xl mx-auto">
          <h1 className="text-5xl font-bold text-gray-900 mb-6">
            Search Your Videos Semantically
          </h1>
          <p className="text-xl text-gray-600 mb-8">
            Heimdex uses AI-powered scene detection to help you find exactly what you're looking for in your videos.
            Search by text, visual content, or even faces.
          </p>

          <div className="flex gap-4 justify-center">
            <Link href="/register">
              <Button size="lg">Get Started</Button>
            </Link>
            <Link href="/login">
              <Button size="lg" variant="outline">
                Sign In
              </Button>
            </Link>
          </div>

          <div className="mt-16 grid md:grid-cols-3 gap-8">
            <FeatureCard
              icon="🎬"
              title="Smart Indexing"
              description="Automatic scene detection and AI-powered indexing of your video content"
            />
            <FeatureCard
              icon="🔍"
              title="Semantic Search"
              description="Search by meaning, not just keywords. Find 'man crying' or 'red car at night'"
            />
            <FeatureCard
              icon="👤"
              title="Face Recognition"
              description="Search for specific people in your videos with face enrollment"
            />
          </div>
        </div>
      </div>
    </main>
  );
}

function FeatureCard({ icon, title, description }: { icon: string; title: string; description: string }) {
  return (
    <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
      <div className="text-4xl mb-4">{icon}</div>
      <h3 className="text-lg font-semibold text-gray-900 mb-2">{title}</h3>
      <p className="text-gray-600">{description}</p>
    </div>
  );
}
