export interface ApiError {
  message: string;
  detail?: unknown;
  status: number;
}
