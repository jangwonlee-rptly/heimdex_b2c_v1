'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useMutation } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { useAuthStore } from '@/store/auth';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import type { OnboardingRequest } from '@/types/api';

const INDUSTRIES = [
  'Entertainment',
  'Media Broadcasting',
  'Movie/Filmmaking',
  'Youtuber',
  'Other',
] as const;

export default function OnboardingPage() {
  const router = useRouter();
  const { setUser } = useAuthStore();
  const [formData, setFormData] = useState<OnboardingRequest>({
    industry: '',
    job_title: '',
    email_consent: false,
  });
  const [showOtherIndustry, setShowOtherIndustry] = useState(false);
  const [otherIndustry, setOtherIndustry] = useState('');
  const [error, setError] = useState('');

  const onboardingMutation = useMutation({
    mutationFn: (data: OnboardingRequest) => api.completeOnboarding(data),
    onSuccess: (updatedUser) => {
      // Update auth store with the new user data (includes onboarding_completed: true)
      setUser(updatedUser);
      // Redirect to dashboard after successful onboarding
      router.push('/dashboard');
    },
    onError: (error: any) => {
      setError(error.response?.data?.detail || 'Failed to complete onboarding');
    },
  });

  const handleIndustryChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value;

    if (value === 'Other') {
      setShowOtherIndustry(true);
      setFormData({ ...formData, industry: '' });
    } else {
      setShowOtherIndustry(false);
      setOtherIndustry('');
      setFormData({ ...formData, industry: value });
    }
  };

  const handleOtherIndustryChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setOtherIndustry(value);
    setFormData({ ...formData, industry: value });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    // Validation
    if (!formData.industry) {
      setError('Please select an industry');
      return;
    }
    if (!formData.job_title) {
      setError('Please enter your job title');
      return;
    }

    onboardingMutation.mutate(formData);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-primary-50 to-white flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl border border-gray-200 p-8 max-w-md w-full">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Welcome to Heimdex!</h1>
          <p className="text-gray-600">
            Tell us a bit about yourself to get started
          </p>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
            <p className="text-sm text-red-600">{error}</p>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Industry Selection */}
          <div>
            <label htmlFor="industry" className="block text-sm font-medium text-gray-700 mb-2">
              Which industry are you in? *
            </label>
            <select
              id="industry"
              value={showOtherIndustry ? 'Other' : formData.industry}
              onChange={handleIndustryChange}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              required
            >
              <option value="">Select an industry</option>
              {INDUSTRIES.map((industry) => (
                <option key={industry} value={industry}>
                  {industry}
                </option>
              ))}
            </select>
          </div>

          {/* Other Industry Text Input */}
          {showOtherIndustry && (
            <div>
              <label htmlFor="other-industry" className="block text-sm font-medium text-gray-700 mb-2">
                Please specify your industry *
              </label>
              <Input
                id="other-industry"
                type="text"
                value={otherIndustry}
                onChange={handleOtherIndustryChange}
                placeholder="e.g., Education, Healthcare, etc."
                required
              />
            </div>
          )}

          {/* Job Title */}
          <div>
            <Input
              label="What's your job title? *"
              type="text"
              value={formData.job_title}
              onChange={(e) =>
                setFormData({ ...formData, job_title: e.target.value })
              }
              placeholder="e.g., Video Editor, Producer, etc."
              required
            />
          </div>

          {/* Email Consent */}
          <div className="space-y-2">
            <div className="flex items-start">
              <div className="flex items-center h-5">
                <input
                  id="email-consent"
                  type="checkbox"
                  checked={formData.email_consent}
                  onChange={(e) =>
                    setFormData({ ...formData, email_consent: e.target.checked })
                  }
                  className="w-4 h-4 text-primary-600 bg-gray-100 border-gray-300 rounded focus:ring-primary-500 focus:ring-2"
                  required
                />
              </div>
              <label htmlFor="email-consent" className="ml-3 text-sm text-gray-700">
                I agree to receive emails from Heimdex about product updates, tips, and
                special offers. By signing up and using our services, I acknowledge this
                consent. *
              </label>
            </div>
            <p className="text-xs text-gray-500 ml-7">
              You can unsubscribe at any time from the emails you receive.
            </p>
          </div>

          {/* Submit Button */}
          <Button
            type="submit"
            className="w-full"
            size="lg"
            isLoading={onboardingMutation.isPending}
          >
            Get Started
          </Button>
        </form>

        <p className="mt-6 text-xs text-center text-gray-500">
          * Required fields
        </p>
      </div>
    </div>
  );
}
