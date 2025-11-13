'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useDropzone } from 'react-dropzone';
import { api } from '@/lib/api';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { formatBytes } from '@/lib/utils';

const MAX_SIZE = 1024 * 1024 * 1024; // 1GB
const MAX_DURATION = 600; // 10 minutes

export default function UploadPage() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState('');

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: {
      'video/*': ['.mp4', '.mov', '.avi', '.mkv', '.webm'],
    },
    maxSize: MAX_SIZE,
    maxFiles: 1,
    onDrop: (acceptedFiles) => {
      if (acceptedFiles.length > 0) {
        const selectedFile = acceptedFiles[0];
        setFile(selectedFile);
        if (!title) {
          setTitle(selectedFile.name.replace(/\.[^/.]+$/, ''));
        }
        setError('');
      }
    },
    onDropRejected: (fileRejections) => {
      const rejection = fileRejections[0];
      if (rejection.errors[0]?.code === 'file-too-large') {
        setError(`File is too large. Maximum size is ${formatBytes(MAX_SIZE)}`);
      } else {
        setError('Invalid file type. Please upload a video file.');
      }
    },
  });

  const handleUpload = async () => {
    if (!file || !title) {
      setError('Please select a file and provide a title');
      return;
    }

    setUploading(true);
    setProgress(0);
    setError('');

    try {
      // Step 1: Initialize upload
      setProgress(10);
      const { upload_url, video_id } = await api.initVideoUpload({
        filename: file.name,
        mime_type: file.type,
        size_bytes: file.size,
        title,
        description: description || undefined,
      });

      // Step 2: Upload to storage
      setProgress(30);
      await api.uploadVideoFile(upload_url, file);

      // Step 3: Complete upload
      setProgress(80);
      await api.completeVideoUpload({
        video_id,
      });

      setProgress(100);
      router.push('/dashboard');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Upload failed. Please try again.');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Upload Video</h1>
        <p className="mt-2 text-gray-600">
          Upload a video to start searching its content. Maximum size: 1GB, duration: 10 minutes.
        </p>
      </div>

      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 space-y-6">
        {!file ? (
          <div
            {...getRootProps()}
            className={`border-2 border-dashed rounded-lg p-12 text-center cursor-pointer transition-colors ${
              isDragActive
                ? 'border-primary-600 bg-primary-50'
                : 'border-gray-300 hover:border-primary-400'
            }`}
          >
            <input {...getInputProps()} />
            <svg
              className="mx-auto h-12 w-12 text-gray-400"
              stroke="currentColor"
              fill="none"
              viewBox="0 0 48 48"
            >
              <path
                d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02"
                strokeWidth={2}
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            <p className="mt-4 text-lg font-medium text-gray-900">
              {isDragActive ? 'Drop your video here' : 'Drag and drop a video file'}
            </p>
            <p className="mt-2 text-sm text-gray-600">or click to browse</p>
            <p className="mt-1 text-xs text-gray-500">MP4, MOV, AVI, MKV, WebM (max 1GB)</p>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
              <div className="flex items-center space-x-3">
                <svg className="h-10 w-10 text-primary-600" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M2 6a2 2 0 012-2h6a2 2 0 012 2v8a2 2 0 01-2 2H4a2 2 0 01-2-2V6zM14.553 7.106A1 1 0 0014 8v4a1 1 0 00.553.894l2 1A1 1 0 0018 13V7a1 1 0 00-1.447-.894l-2 1z" />
                </svg>
                <div>
                  <p className="font-medium text-gray-900">{file.name}</p>
                  <p className="text-sm text-gray-600">{formatBytes(file.size)}</p>
                </div>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setFile(null)}
                disabled={uploading}
              >
                Remove
              </Button>
            </div>

            <Input
              label="Title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="My awesome video"
              required
              disabled={uploading}
            />

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Description (optional)
              </label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Add a description..."
                rows={3}
                disabled={uploading}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent disabled:bg-gray-100 disabled:cursor-not-allowed"
              />
            </div>

            {uploading && (
              <div>
                <div className="flex justify-between text-sm text-gray-600 mb-2">
                  <span>Uploading...</span>
                  <span>{progress}%</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-primary-600 h-2 rounded-full transition-all"
                    style={{ width: `${progress}%` }}
                  />
                </div>
              </div>
            )}

            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
                {error}
              </div>
            )}

            <div className="flex space-x-3">
              <Button onClick={handleUpload} isLoading={uploading} disabled={!title}>
                Upload Video
              </Button>
              <Button
                variant="outline"
                onClick={() => router.push('/dashboard')}
                disabled={uploading}
              >
                Cancel
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
