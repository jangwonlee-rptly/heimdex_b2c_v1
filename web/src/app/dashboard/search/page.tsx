'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { formatDuration } from '@/lib/utils';

export default function SearchPage() {
  const [query, setQuery] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedPerson, setSelectedPerson] = useState('');

  const { data: people } = useQuery({
    queryKey: ['people'],
    queryFn: () => api.listPeople(),
  });

  const {
    data: results,
    isLoading,
    refetch,
  } = useQuery({
    queryKey: ['search', searchQuery, selectedPerson],
    queryFn: () =>
      api.search({
        q: searchQuery,
        person_id: selectedPerson || undefined,
      }),
    enabled: !!searchQuery,
  });

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setSearchQuery(query);
  };

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Semantic Search</h1>
        <p className="mt-2 text-gray-600">
          Search for scenes in your videos using natural language descriptions
        </p>
      </div>

      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <form onSubmit={handleSearch} className="space-y-4">
          <div>
            <Input
              label="Search Query"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g., 'person crying', 'red car at night', 'beach sunset'"
              required
            />
            <p className="mt-2 text-sm text-gray-500">
              Describe what you're looking for in natural language
            </p>
          </div>

          {people && people.length > 0 && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Filter by Person (optional)
              </label>
              <select
                value={selectedPerson}
                onChange={(e) => setSelectedPerson(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              >
                <option value="">All people</option>
                {people.map((person) => (
                  <option key={person.person_id} value={person.person_id}>
                    {person.name}
                  </option>
                ))}
              </select>
            </div>
          )}

          <Button type="submit" isLoading={isLoading}>
            Search
          </Button>
        </form>
      </div>

      {searchQuery && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold text-gray-900">
              Results for "{searchQuery}"
            </h2>
            {results && (
              <span className="text-sm text-gray-600">{results.total} results found</span>
            )}
          </div>

          {isLoading ? (
            <div className="text-center py-12 bg-white rounded-lg border border-gray-200">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto" />
              <p className="mt-4 text-gray-600">Searching...</p>
            </div>
          ) : results && results.results.length > 0 ? (
            <div className="space-y-4">
              {results.results.map((result, index) => (
                <div
                  key={index}
                  className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 hover:shadow-md transition-shadow"
                >
                  <div className="flex space-x-4">
                    <div className="flex-shrink-0">
                      {result.scene.thumbnail_url ? (
                        <img
                          src={result.scene.thumbnail_url}
                          alt={`Scene from ${result.video.title}`}
                          className="w-48 h-28 bg-gray-200 rounded-lg object-cover"
                          loading="lazy"
                        />
                      ) : (
                        <div className="w-48 h-28 bg-gray-200 rounded-lg flex items-center justify-center">
                          <svg
                            className="w-12 h-12 text-gray-400"
                            fill="currentColor"
                            viewBox="0 0 20 20"
                          >
                            <path d="M2 6a2 2 0 012-2h6a2 2 0 012 2v8a2 2 0 01-2 2H4a2 2 0 01-2-2V6zM14.553 7.106A1 1 0 0014 8v4a1 1 0 00.553.894l2 1A1 1 0 0018 13V7a1 1 0 00-1.447-.894l-2 1z" />
                          </svg>
                        </div>
                      )}
                    </div>

                    <div className="flex-1 space-y-2">
                      <div className="flex items-center justify-between">
                        <h3 className="text-lg font-semibold text-gray-900">
                          {result.video.title}
                        </h3>
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-primary-100 text-primary-800">
                          Score: {(result.score * 100).toFixed(1)}%
                        </span>
                      </div>

                      <div className="flex items-center space-x-4 text-sm text-gray-600">
                        <span>
                          Time: {formatDuration(result.scene.start_time)} -{' '}
                          {formatDuration(result.scene.end_time)}
                        </span>
                      </div>

                      {result.scene.transcript && (
                        <div className="bg-gray-50 rounded-lg p-3">
                          <p className="text-sm text-gray-700">
                            {result.highlights && result.highlights.length > 0
                              ? result.highlights[0]
                              : result.scene.transcript}
                          </p>
                        </div>
                      )}

                      <div className="flex space-x-2">
                        <Button size="sm">Watch Scene</Button>
                        <Button size="sm" variant="outline">
                          View Video
                        </Button>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-12 bg-white rounded-lg border border-gray-200">
              <svg
                className="mx-auto h-12 w-12 text-gray-400"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                />
              </svg>
              <h3 className="mt-2 text-sm font-medium text-gray-900">No results found</h3>
              <p className="mt-1 text-sm text-gray-500">
                Try a different search query or upload more videos
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
