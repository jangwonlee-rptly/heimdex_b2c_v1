'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { api } from '@/lib/api';
import { useAuthStore } from '@/store/auth';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';

export function RegisterForm() {
  const router = useRouter();
  const { setUser } = useAuthStore();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    setIsLoading(true);

    try {
      const response = await api.register({ email, password, display_name: displayName });

      // Check if email confirmation is required
      if (!response.access_token) {
        setSuccess('Registration successful! Please check your email to confirm your account.');
      } else {
        // Store tokens in localStorage for subsequent requests
        localStorage.setItem('access_token', response.access_token);
        localStorage.setItem('refresh_token', response.refresh_token);

        setUser(response.user);
        router.push('/dashboard');
      }
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      if (typeof detail === 'object' && detail.email_confirmation_required) {
        setSuccess(detail.message);
      } else {
        setError(typeof detail === 'string' ? detail : 'Registration failed. Please try again.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="w-full max-w-md space-y-8">
      <div className="text-center">
        <h2 className="text-3xl font-bold text-gray-900">Create your account</h2>
        <p className="mt-2 text-sm text-gray-600">
          Already have an account?{' '}
          <Link href="/login" className="font-medium text-primary-600 hover:text-primary-500">
            Sign in
          </Link>
        </p>
      </div>

      <form onSubmit={handleSubmit} className="mt-8 space-y-6">
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
            {error}
          </div>
        )}

        {success && (
          <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg">
            {success}
          </div>
        )}

        <div className="space-y-4">
          <Input
            label="Display Name"
            type="text"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            placeholder="John Doe"
          />

          <Input
            label="Email address"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
            placeholder="you@example.com"
          />

          <Input
            label="Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete="new-password"
            placeholder="••••••••"
          />
          <p className="text-xs text-gray-500">
            Password must be at least 8 characters long
          </p>
        </div>

        <Button type="submit" className="w-full" isLoading={isLoading}>
          Create account
        </Button>
      </form>
    </div>
  );
}
