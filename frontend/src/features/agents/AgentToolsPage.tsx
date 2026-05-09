import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import PsychologyIcon from '@mui/icons-material/Psychology';
import { Alert, Box, Button, Stack, TextField, Typography } from '@mui/material';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useState } from 'react';

import { DataTable } from '../../components/common/DataTable';
import { LoadingSpinner } from '../../components/common/LoadingSpinner';
import { SectionCard } from '../../components/common/SectionCard';
import { useNotification } from '../../hooks/useNotification';
import { getRiskAssessment, parseNaturalLanguageTransaction } from '../../services/agents';
import type { RiskAssessmentResponse } from '../../types/agents';
import { DEFAULT_USER_ID } from '../../utils/constants';
import { formatPercentage } from '../../utils/formatting';

export default function AgentToolsPage() {
  const notifications = useNotification();
  const [text, setText] = useState('4月21号我卖出560.02加元，买入65254日元');

  const parseMutation = useMutation({
    mutationFn: () => parseNaturalLanguageTransaction(text),
    onError: (error: { message: string }) => notifications.error(error.message),
  });

  const riskQuery = useQuery({
    queryKey: ['risk-assessment', DEFAULT_USER_ID],
    queryFn: () => getRiskAssessment(DEFAULT_USER_ID),
  });

  const exposureColumns = [
    { key: 'asset_name', header: '产品', render: (row: RiskAssessmentResponse['result']['exposures'][number]) => row.asset_name || row.asset_code },
    { key: 'asset_code', header: '代码', render: (row: RiskAssessmentResponse['result']['exposures'][number]) => row.asset_code },
    { key: 'asset_type', header: '类型', render: (row: RiskAssessmentResponse['result']['exposures'][number]) => row.asset_type ?? '-' },
    { key: 'weight_pct', header: '权重', align: 'right' as const, render: (row: RiskAssessmentResponse['result']['exposures'][number]) => formatPercentage(row.weight_pct) },
  ];

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h4">Agent Tools</Typography>
        <Typography color="text.secondary">把后端已有的自然语言解析和风险评估能力接到前端，结果先用于核对，不自动写入数据库。</Typography>
      </Box>

      <SectionCard title="自然语言交易解析">
        <Stack spacing={2}>
          <TextField
            label="交易描述"
            value={text}
            onChange={(event) => setText(event.target.value)}
            multiline
            minRows={3}
            fullWidth
          />
          <Button
            variant="contained"
            startIcon={<AutoAwesomeIcon />}
            disabled={parseMutation.isPending || !text.trim()}
            onClick={() => parseMutation.mutate()}
          >
            解析交易
          </Button>
          {parseMutation.isPending ? <LoadingSpinner message="解析中..." /> : null}
          {parseMutation.data?.ok && parseMutation.data.result ? (
            <Box sx={{ p: 2, border: '1px solid', borderColor: 'divider', borderRadius: 2, bgcolor: 'background.paper' }}>
              <Typography variant="subtitle1" fontWeight={700}>解析结果</Typography>
              <Typography sx={{ whiteSpace: 'pre-wrap', mt: 1 }}>
                {JSON.stringify(parseMutation.data.result.parameters, null, 2)}
              </Typography>
              {parseMutation.data.result.missing_fields.length ? (
                <Alert severity="warning" sx={{ mt: 2 }}>
                  缺少字段：{parseMutation.data.result.missing_fields.join(', ')}
                </Alert>
              ) : null}
            </Box>
          ) : null}
        </Stack>
      </SectionCard>

      <SectionCard
        title="风险评估"
        action={<Button startIcon={<PsychologyIcon />} onClick={() => void riskQuery.refetch()}>刷新</Button>}
      >
        {riskQuery.isLoading ? (
          <LoadingSpinner message="加载风险评估..." />
        ) : (
          <Stack spacing={2}>
            <Alert severity={riskQuery.data?.result.risk_level === 'high' ? 'warning' : 'info'}>
              风险等级：{riskQuery.data?.result.risk_level ?? '-'}
            </Alert>
            <Stack spacing={1}>
              {(riskQuery.data?.result.factors ?? []).map((factor) => (
                <Typography key={factor}>{factor}</Typography>
              ))}
            </Stack>
            <DataTable columns={exposureColumns} rows={riskQuery.data?.result.exposures ?? []} />
          </Stack>
        )}
      </SectionCard>
    </Stack>
  );
}
