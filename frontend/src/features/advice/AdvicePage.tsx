import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import {
  Alert,
  Box,
  Button,
  FormControl,
  FormControlLabel,
  Radio,
  RadioGroup,
  Stack,
  Typography,
} from '@mui/material';
import { useMutation } from '@tanstack/react-query';
import { useState } from 'react';

import { LoadingSpinner } from '../../components/common/LoadingSpinner';
import { SectionCard } from '../../components/common/SectionCard';
import { useNotification } from '../../hooks/useNotification';
import { getAdvice } from '../../services/advice';
import type { RiskPreference } from '../../types/advice';
import { DEFAULT_USER_ID } from '../../utils/constants';
import { formatCurrency, formatPercentage } from '../../utils/formatting';

export default function AdvicePage() {
  const notifications = useNotification();
  const [riskPreference, setRiskPreference] = useState<RiskPreference>('balanced');

  const mutation = useMutation({
    mutationFn: () => getAdvice(DEFAULT_USER_ID, riskPreference),
    onError: (error: { message: string }) => notifications.error(error.message),
  });

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h4">Investment Advice</Typography>
        <Typography color="text.secondary">前端只提交风险偏好并渲染结构化建议，AI 生成逻辑仍留在后端工具层。</Typography>
      </Box>

      <SectionCard title="Request Advice">
        <Stack spacing={3}>
          <Alert severity="info">如果后端未配置 AI 凭证，这一页会返回错误提示；前端不会内嵌任何模型逻辑。</Alert>

          <FormControl>
            <RadioGroup row value={riskPreference} onChange={(event) => setRiskPreference(event.target.value as RiskPreference)}>
              <FormControlLabel value="conservative" control={<Radio />} label="Conservative" />
              <FormControlLabel value="balanced" control={<Radio />} label="Balanced" />
              <FormControlLabel value="aggressive" control={<Radio />} label="Aggressive" />
            </RadioGroup>
          </FormControl>

          <Button
            variant="contained"
            startIcon={<AutoAwesomeIcon />}
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending}
          >
            Get Advice
          </Button>

          {mutation.isPending ? <LoadingSpinner message="Generating advice..." /> : null}

          {mutation.data?.ok ? (
            <Stack spacing={2}>
              <Box sx={{ p: 2.5, borderRadius: 3, bgcolor: 'background.paper', border: '1px solid', borderColor: 'divider' }}>
                <Typography variant="h6">Portfolio Summary</Typography>
                <Typography>Total Cost: {formatCurrency(mutation.data.result.portfolio_summary.total_cost_cny)}</Typography>
                <Typography>Total Value: {formatCurrency(mutation.data.result.portfolio_summary.total_value_cny)}</Typography>
                <Typography>Total PnL: {formatCurrency(mutation.data.result.portfolio_summary.total_pnl_cny)}</Typography>
                <Typography>Total Return: {formatPercentage(mutation.data.result.portfolio_summary.total_return_pct)}</Typography>
              </Box>

              <Box sx={{ p: 2.5, borderRadius: 3, bgcolor: 'background.paper', border: '1px solid', borderColor: 'divider' }}>
                <Typography variant="h6">{mutation.data.result.advice.summary}</Typography>
                <Typography color="text.secondary" sx={{ mt: 1 }}>
                  Risk Level: {mutation.data.result.advice.risk_level}
                </Typography>
                <Typography sx={{ mt: 2, whiteSpace: 'pre-wrap' }}>{mutation.data.result.advice.reasoning}</Typography>
              </Box>

              <Box sx={{ p: 2.5, borderRadius: 3, bgcolor: 'background.paper', border: '1px solid', borderColor: 'divider' }}>
                <Typography variant="h6">Actions</Typography>
                <Stack spacing={1.5} sx={{ mt: 1.5 }}>
                  {mutation.data.result.advice.actions.map((action, index) => (
                    <Alert key={`${action.asset_code}-${index}`} severity="info">
                      {action.asset_code}: {action.action} {action.rationale ? `- ${action.rationale}` : ''}
                    </Alert>
                  ))}
                </Stack>
              </Box>

              {mutation.data.result.advice.warnings.length ? (
                <Box sx={{ p: 2.5, borderRadius: 3, bgcolor: 'background.paper', border: '1px solid', borderColor: 'divider' }}>
                  <Typography variant="h6">Warnings</Typography>
                  <Stack spacing={1.5} sx={{ mt: 1.5 }}>
                    {mutation.data.result.advice.warnings.map((warning, index) => (
                      <Alert key={`${warning}-${index}`} severity="warning">{warning}</Alert>
                    ))}
                  </Stack>
                </Box>
              ) : null}
            </Stack>
          ) : null}
        </Stack>
      </SectionCard>
    </Stack>
  );
}
