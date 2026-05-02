import { createTheme } from '@mui/material/styles';

export const theme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#0f5d46',
    },
    secondary: {
      main: '#d97706',
    },
    background: {
      default: '#f4f1ea',
      paper: '#fffdf8',
    },
    success: {
      main: '#13795b',
    },
    error: {
      main: '#b42318',
    },
  },
  shape: {
    borderRadius: 16,
  },
  typography: {
    fontFamily: '"IBM Plex Sans", "Noto Sans SC", sans-serif',
    h4: {
      fontWeight: 700,
    },
    h6: {
      fontWeight: 700,
    },
  },
});
