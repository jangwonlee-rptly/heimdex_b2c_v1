/**
 * Utility functions for Heimdex B2C web app
 */

import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * Merge Tailwind CSS classes with proper precedence
 * Uses clsx for conditional classes and tailwind-merge to handle conflicts
 *
 * @param inputs - Class values to merge
 * @returns Merged class string
 *
 * @example
 * cn('px-2 py-1', 'px-4') // => 'py-1 px-4' (px-4 overrides px-2)
 * cn('text-red-500', condition && 'text-blue-500') // conditional classes
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Format bytes to human-readable size
 *
 * @param bytes - Number of bytes
 * @param decimals - Number of decimal places (default: 2)
 * @returns Formatted size string
 *
 * @example
 * formatBytes(1024) // => '1.00 KB'
 * formatBytes(1536000) // => '1.46 MB'
 */
export function formatBytes(bytes: number, decimals: number = 2): string {
  if (bytes === 0) return '0 Bytes';

  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];

  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

/**
 * Format date to human-readable format
 *
 * @param date - ISO date string or Date object
 * @returns Formatted date string
 *
 * @example
 * formatDate('2025-11-12T10:30:00Z') // => 'Nov 12, 2025'
 * formatDate(new Date()) // => 'Nov 12, 2025'
 */
export function formatDate(date: string | Date): string {
  const d = typeof date === 'string' ? new Date(date) : date;

  return d.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

/**
 * Format duration in seconds to human-readable time
 *
 * @param seconds - Duration in seconds
 * @returns Formatted time string
 *
 * @example
 * formatDuration(65) // => '1:05'
 * formatDuration(3665) // => '1:01:05'
 */
export function formatDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);

  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }

  return `${minutes}:${secs.toString().padStart(2, '0')}`;
}

/**
 * Format timestamp to relative time
 *
 * @param date - Date string or Date object
 * @returns Relative time string
 *
 * @example
 * formatRelativeTime(new Date()) // => 'just now'
 * formatRelativeTime(Date.now() - 60000) // => '1 minute ago'
 */
export function formatRelativeTime(date: string | Date): string {
  const now = new Date().getTime();
  const then = typeof date === 'string' ? new Date(date).getTime() : date.getTime();
  const diff = now - then;

  const seconds = Math.floor(diff / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);
  const weeks = Math.floor(days / 7);
  const months = Math.floor(days / 30);
  const years = Math.floor(days / 365);

  if (seconds < 10) return 'just now';
  if (seconds < 60) return `${seconds} seconds ago`;
  if (minutes === 1) return '1 minute ago';
  if (minutes < 60) return `${minutes} minutes ago`;
  if (hours === 1) return '1 hour ago';
  if (hours < 24) return `${hours} hours ago`;
  if (days === 1) return 'yesterday';
  if (days < 7) return `${days} days ago`;
  if (weeks === 1) return '1 week ago';
  if (weeks < 4) return `${weeks} weeks ago`;
  if (months === 1) return '1 month ago';
  if (months < 12) return `${months} months ago`;
  if (years === 1) return '1 year ago';
  return `${years} years ago`;
}

/**
 * Truncate text to specified length with ellipsis
 *
 * @param text - Text to truncate
 * @param maxLength - Maximum length
 * @returns Truncated text
 *
 * @example
 * truncate('Hello world', 5) // => 'Hello...'
 */
export function truncate(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength) + '...';
}

/**
 * Sleep utility for async functions
 *
 * @param ms - Milliseconds to sleep
 * @returns Promise that resolves after the specified time
 *
 * @example
 * await sleep(1000) // wait 1 second
 */
export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Debounce function calls
 *
 * @param func - Function to debounce
 * @param wait - Wait time in milliseconds
 * @returns Debounced function
 *
 * @example
 * const debouncedSearch = debounce((query) => search(query), 300)
 */
export function debounce<T extends (...args: any[]) => any>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: NodeJS.Timeout | null = null;

  return function (this: any, ...args: Parameters<T>) {
    if (timeout) clearTimeout(timeout);
    timeout = setTimeout(() => func.apply(this, args), wait);
  };
}
