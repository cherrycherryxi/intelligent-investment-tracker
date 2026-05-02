import { format, formatDistanceToNow, parseISO } from 'date-fns';

export function formatDate(value?: string | null): string {
  if (!value) return '-';
  return format(parseISO(value), 'yyyy-MM-dd');
}

export function formatTime(value?: string | null): string {
  if (!value) return '-';
  return format(parseISO(value), 'HH:mm:ss');
}

export function formatDateTime(value?: string | null): string {
  if (!value) return '-';
  return format(parseISO(value), 'yyyy-MM-dd HH:mm:ss');
}

export function formatRelativeTime(value?: string | null): string {
  if (!value) return '-';
  return formatDistanceToNow(parseISO(value), { addSuffix: true });
}

export function formatCurrency(value?: number | null, currency = 'CNY'): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '-';
  return new Intl.NumberFormat('zh-CN', {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

export function formatNumber(value?: number | null, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '-';
  return new Intl.NumberFormat('zh-CN', {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  }).format(value);
}

export function formatPercentage(value?: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '-';
  return `${value.toFixed(2)}%`;
}

export function toDatetimeLocalValue(value?: string | null): string {
  if (!value) return '';
  return format(parseISO(value), "yyyy-MM-dd'T'HH:mm");
}
