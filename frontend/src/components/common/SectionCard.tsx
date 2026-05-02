import { Card, CardContent, CardHeader } from '@mui/material';
import type { PropsWithChildren, ReactNode } from 'react';

export function SectionCard({
  title,
  action,
  children,
}: PropsWithChildren<{ title: string; action?: ReactNode }>) {
  return (
    <Card elevation={0} sx={{ borderRadius: 4, border: '1px solid', borderColor: 'divider' }}>
      <CardHeader title={title} action={action} />
      <CardContent>{children}</CardContent>
    </Card>
  );
}
