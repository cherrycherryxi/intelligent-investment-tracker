import { useSnackbar } from 'notistack';
import { IconButton } from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import { createElement } from 'react';

export function useNotification() {
  const { enqueueSnackbar, closeSnackbar } = useSnackbar();

  return {
    success: (message: string) => enqueueSnackbar(message, { variant: 'success', autoHideDuration: 3000 }),
    error: (message: string) =>
      enqueueSnackbar(message, {
        variant: 'error',
        autoHideDuration: 6000,
        action: (key) => (
          createElement(
            IconButton,
            { size: 'small', color: 'inherit', onClick: () => closeSnackbar(key) },
            createElement(CloseIcon, { fontSize: 'small' }),
          )
        ),
      }),
    info: (message: string) => enqueueSnackbar(message, { variant: 'info' }),
    warning: (message: string) => enqueueSnackbar(message, { variant: 'warning' }),
  };
}
