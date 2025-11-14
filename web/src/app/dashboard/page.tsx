'use client';

import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/Button';
import { formatDate, formatDuration, formatBytes } from '@/lib/utils';

export default function DashboardPage() {
  const { data: videos, isLoading } = useQuery({
    queryKey: ['videos'],
    queryFn: () => api.getVideos(),
    // Automatically poll every 3 seconds when there are videos being processed
    refetchInterval: (query) => {
      // Get the actual data from the query object
      const data = query?.state?.data;
      if (!Array.isArray(data)) return false;

      const hasProcessingVideos = data.some(
        (video) => ['uploading', 'validating', 'processing'].includes(video.state)
      );
      return hasProcessingVideos ? 3000 : false;
    },
  });

  return (
    <div className="space-y-8">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">My Videos</h1>
          <p className="mt-2 text-gray-600">Manage and search your video library</p>
        </div>
        <Link href="/dashboard/upload">
          <Button>Upload Video</Button>
        </Link>
      </div>

      {isLoading ? (
        <div className="text-center py-12">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto" />
        </div>
      ) : videos && videos.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {videos.map((video) => (
            <div key={video.video_id} className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
              <div className="aspect-video bg-gray-200 flex items-center justify-center relative">
                {video.thumbnail_url ? (
                  <img
                    src={video.thumbnail_url}
                    alt={video.title || 'Video thumbnail'}
                    className="w-full h-full object-cover"
                    loading="lazy"
                  />
                ) : (
                  <div className="flex flex-col items-center gap-2">
                    <svg className="w-16 h-16 text-gray-400" fill="currentColor" viewBox="0 0 20 20">
                      <path d="M2 6a2 2 0 012-2h6a2 2 0 012 2v8a2 2 0 01-2 2H4a2 2 0 01-2-2V6zM14.553 7.106A1 1 0 0014 8v4a1 1 0 00.553.894l2 1A1 1 0 0018 13V7a1 1 0 00-1.447-.894l-2 1z" />
                    </svg>
                    {['uploading', 'validating', 'processing'].includes(video.state) && (
                      <p className="text-sm text-gray-500">Processing video...</p>
                    )}
                  </div>
                )}
              </div>
              <div className="p-4">
                <h3 className="font-semibold text-gray-900 mb-2">{video.title}</h3>
                <div className="text-sm text-gray-600 space-y-1">
                  {video.duration_s && <p>Duration: {formatDuration(video.duration_s)}</p>}
                  <p>Size: {formatBytes(video.size_bytes)}</p>
                  <p>Uploaded: {formatDate(video.created_at)}</p>
                  <p className="flex items-center gap-2">
                    Status:{' '}
                    <span
                      className={`inline-flex items-center gap-1.5 px-2 py-1 rounded text-xs font-medium ${
                        video.state === 'indexed'
                          ? 'bg-green-100 text-green-800'
                          : video.state === 'processing' || video.state === 'validating'
                          ? 'bg-yellow-100 text-yellow-800'
                          : video.state === 'uploading'
                          ? 'bg-blue-100 text-blue-800'
                          : video.state === 'failed'
                          ? 'bg-red-100 text-red-800'
                          : 'bg-gray-100 text-gray-800'
                      }`}
                    >
                      {['uploading', 'validating', 'processing'].includes(video.state) && (
                        <span className="relative flex h-2 w-2">
                          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-yellow-400 opacity-75"></span>
                          <span className="relative inline-flex rounded-full h-2 w-2 bg-yellow-500"></span>
                        </span>
                      )}
                      {video.state}
                    </span>
                  </p>
                  {video.error_text && (
                    <p className="text-red-600 text-xs mt-1">{video.error_text}</p>
                  )}
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
              d="M7 4v16M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4M4 20h16a1 1 0 001-1V5a1 1 0 00-1-1H4a1 1 0 00-1 1v14a1 1 0 001 1z"
            />
          </svg>
          <h3 className="mt-2 text-sm font-medium text-gray-900">No videos</h3>
          <p className="mt-1 text-sm text-gray-500">Get started by uploading your first video.</p>
          <div className="mt-6">
            <Link href="/dashboard/upload">
              <Button>Upload Video</Button>
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
