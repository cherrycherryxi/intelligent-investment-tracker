import { Box, CircularProgress, Typography } from '@mui/material';

export function LoadingSpinner({ message }: { message?: string }) {
  return (
    <Box sx={{ py: 6, display: 'grid', placeItems: 'center', gap: 1.5 }}>
      <CircularProgress />
      {message ? <Typography color="text.secondary">{message}</Typography> : null}
    </Box>
  );
}
