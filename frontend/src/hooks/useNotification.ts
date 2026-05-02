import { useSnackbar } from 'notistack';

export function useNotification() {
  const { enqueueSnackbar } = useSnackbar();

  return {
    success: (message: string) => enqueueSnackbar(message, { variant: 'success', autoHideDuration: 3000 }),
    error: (message: string) => enqueueSnackbar(message, { variant: 'error', persist: true }),
    info: (message: string) => enqueueSnackbar(message, { variant: 'info' }),
    warning: (message: string) => enqueueSnackbar(message, { variant: 'warning' }),
  };
}
