import MenuIcon from '@mui/icons-material/Menu';
import ShowChartIcon from '@mui/icons-material/ShowChart';
import {
  AppBar,
  Box,
  Drawer,
  IconButton,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Toolbar,
  Typography,
} from '@mui/material';
import type { ReactNode } from 'react';
import { useMemo, useState } from 'react';
import { NavLink } from 'react-router-dom';

const navItems = [
  { to: '/transactions', label: 'Transactions' },
  { to: '/performance', label: 'Performance' },
  { to: '/performance/audit', label: 'Audit' },
  { to: '/positions', label: 'Positions' },
  { to: '/imports', label: 'Import' },
  { to: '/advice', label: 'Advice' },
  { to: '/agent-tools', label: 'Agent Tools' },
  { to: '/exchange-rates', label: 'Exchange Rates' },
];

export function AppLayout({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);

  const navigation = useMemo(
    () => (
      <List sx={{ px: 1 }}>
        {navItems.map((item) => (
          <ListItemButton
            key={item.to}
            component={NavLink}
            to={item.to}
            onClick={() => setOpen(false)}
            sx={{
              mb: 0.5,
              borderRadius: 2,
              '&.active': {
                bgcolor: 'primary.main',
                color: 'primary.contrastText',
              },
            }}
          >
            <ListItemIcon sx={{ minWidth: 36 }}>
              <ShowChartIcon fontSize="small" />
            </ListItemIcon>
            <ListItemText primary={item.label} />
          </ListItemButton>
        ))}
      </List>
    ),
    [],
  );

  return (
    <Box sx={{ minHeight: '100vh', bgcolor: 'background.default' }}>
      <AppBar
        position="sticky"
        color="transparent"
        elevation={0}
        sx={{ backdropFilter: 'blur(14px)', borderBottom: '1px solid', borderColor: 'divider' }}
      >
        <Toolbar>
          <IconButton edge="start" onClick={() => setOpen(true)} sx={{ mr: 1, display: { md: 'none' } }}>
            <MenuIcon />
          </IconButton>
          <Typography variant="h6" sx={{ fontWeight: 700, flexGrow: 1 }}>
            Investment Tracker
          </Typography>
          <Typography variant="body2" color="text.secondary">
            User #{1}
          </Typography>
        </Toolbar>
      </AppBar>

      <Drawer open={open} onClose={() => setOpen(false)} sx={{ display: { md: 'none' } }}>
        <Box sx={{ width: 280, pt: 2 }}>{navigation}</Box>
      </Drawer>

      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '280px 1fr' } }}>
        <Box
          sx={{
            display: { xs: 'none', md: 'block' },
            borderRight: '1px solid',
            borderColor: 'divider',
            minHeight: 'calc(100vh - 65px)',
            position: 'sticky',
            top: 65,
            pt: 3,
          }}
        >
          {navigation}
        </Box>
        <Box sx={{ p: { xs: 2, md: 4 } }}>{children}</Box>
      </Box>
    </Box>
  );
}
