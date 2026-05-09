import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import InsightsIcon from '@mui/icons-material/Insights';
import QueryStatsIcon from '@mui/icons-material/QueryStats';
import SendIcon from '@mui/icons-material/Send';
import TimelineIcon from '@mui/icons-material/Timeline';
import {
  Alert,
  Box,
  Button,
  Chip,
  FormControl,
  FormControlLabel,
  IconButton,
  Paper,
  Radio,
  RadioGroup,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import { useMutation } from '@tanstack/react-query';
import { useMemo, useState } from 'react';

import { LoadingSpinner } from '../../components/common/LoadingSpinner';
import { SectionCard } from '../../components/common/SectionCard';
import { useNotification } from '../../hooks/useNotification';
import { sendAdviceChat } from '../../services/advice';
import type { AdviceChatMode, AdviceChatResponse, RiskPreference } from '../../types/advice';
import { DEFAULT_USER_ID } from '../../utils/constants';
import { formatCurrency, formatPercentage } from '../../utils/formatting';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  mode: AdviceChatMode;
}

const actionButtons: Array<{ mode: AdviceChatMode; label: string; prompt: string; icon: JSX.Element }> = [
  { mode: 'generate_advice', label: '生成建议', prompt: '请根据当前持仓、收益和风险偏好生成投资建议。', icon: <AutoAwesomeIcon /> },
  { mode: 'position_analysis', label: '仓位分析', prompt: '请分析当前仓位结构、集中度、币种暴露和主要风险。', icon: <InsightsIcon /> },
  { mode: 'transaction_analysis', label: '交易分析', prompt: '请分析最近交易流水中的模式、异常和需要核对的数据。', icon: <TimelineIcon /> },
];

function renderResult(response: AdviceChatResponse): string {
  if (!response.ok) {
    return `AI 调用失败：${response.error?.message || '未知错误'}`;
  }
  const result = response.result;
  if (result && typeof result === 'object' && 'answer' in result) {
    return String((result as { answer?: string }).answer || '');
  }
  if (!result || typeof result !== 'object') {
    return String(result || '');
  }

  const data = result as Record<string, unknown>;
  const lines: string[] = [];
  const appendList = (title: string, value: unknown) => {
    if (!Array.isArray(value) || value.length === 0) {
      return;
    }
    lines.push(`${title}：`);
    value.forEach((item) => {
      if (typeof item === 'string') {
        lines.push(`- ${item}`);
        return;
      }
      if (item && typeof item === 'object') {
        const action = item as Record<string, unknown>;
        const asset = action.asset_code || action.asset_name || '组合';
        const command = action.action ? `｜${String(action.action)}` : '';
        const rationale = action.rationale || action.reason || action.explanation || '';
        lines.push(`- ${String(asset)}${command}${rationale ? `：${String(rationale)}` : ''}`);
      }
    });
  };

  if (data.summary) {
    lines.push(`结论：${String(data.summary)}`);
  }
  if (data.risk_level) {
    lines.push(`风险等级：${String(data.risk_level)}`);
  }
  if (data.frequency_summary) {
    lines.push(`交易频率：${String(data.frequency_summary)}`);
  }
  if (data.concentration_risk) {
    lines.push(`集中度风险：${String(data.concentration_risk)}`);
  }
  if (data.reasoning) {
    lines.push(`依据：${String(data.reasoning)}`);
  }
  appendList('主要风险', data.factors);
  appendList('操作建议', data.actions);
  appendList('分散化建议', data.diversification_suggestions);
  appendList('异常提示', data.anomalies);
  appendList('交易建议', data.recommendations);
  appendList('注意事项', data.warnings);

  return lines.length ? lines.join('\n') : JSON.stringify(result, null, 2);
}

export default function AdvicePage() {
  const notifications = useNotification();
  const [riskPreference, setRiskPreference] = useState<RiskPreference>('balanced');
  const [message, setMessage] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [lastResponse, setLastResponse] = useState<AdviceChatResponse | null>(null);

  const mutation = useMutation({
    mutationFn: ({ mode, prompt }: { mode: AdviceChatMode; prompt: string }) =>
      sendAdviceChat({
        user_id: DEFAULT_USER_ID,
        mode,
        message: prompt,
        risk_preference: riskPreference,
      }),
    onSuccess: (data, variables) => {
      setLastResponse(data);
      setMessages((items) => [
        ...items,
        { role: 'user', content: variables.prompt, mode: variables.mode },
        { role: 'assistant', content: renderResult(data), mode: variables.mode },
      ]);
      if (!data.ok) {
        notifications.error(data.error?.message || 'AI 调用失败');
      }
    },
    onError: (error: { message: string }) => notifications.error(error.message),
  });

  const canSend = useMemo(() => message.trim().length > 0 && !mutation.isPending, [message, mutation.isPending]);

  const runMode = (mode: AdviceChatMode, prompt: string) => {
    mutation.mutate({ mode, prompt });
  };

  const sendMessage = () => {
    const prompt = message.trim();
    if (!prompt) {
      return;
    }
    setMessage('');
    runMode('chat', prompt);
  };

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h4">AI 投资助手</Typography>
        <Typography color="text.secondary">基于当前持仓、绩效和最近交易流水生成回答。</Typography>
      </Box>

      <SectionCard title="AI Chat">
        <Stack spacing={2.5}>
          <Alert severity="info">本页请求会调用后端 AI Client；未配置 AI 凭证或网络不可用时会直接显示失败原因。</Alert>

          <FormControl>
            <RadioGroup row value={riskPreference} onChange={(event) => setRiskPreference(event.target.value as RiskPreference)}>
              <FormControlLabel value="conservative" control={<Radio />} label="保守" />
              <FormControlLabel value="balanced" control={<Radio />} label="均衡" />
              <FormControlLabel value="aggressive" control={<Radio />} label="积极" />
            </RadioGroup>
          </FormControl>

          <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5}>
            {actionButtons.map((item) => (
              <Button
                key={item.mode}
                variant="outlined"
                startIcon={item.icon}
                onClick={() => runMode(item.mode, item.prompt)}
                disabled={mutation.isPending}
              >
                {item.label}
              </Button>
            ))}
          </Stack>

          <Paper variant="outlined" sx={{ minHeight: 360, maxHeight: 560, overflowY: 'auto', p: 2, borderRadius: 2 }}>
            {messages.length === 0 ? (
              <Stack spacing={1.5} alignItems="center" justifyContent="center" sx={{ minHeight: 300, color: 'text.secondary' }}>
                <QueryStatsIcon fontSize="large" />
                <Typography>选择一个操作，或直接提问。</Typography>
              </Stack>
            ) : (
              <Stack spacing={1.5}>
                {messages.map((item, index) => (
                  <Box
                    key={`${item.role}-${index}`}
                    sx={{
                      alignSelf: item.role === 'user' ? 'flex-end' : 'flex-start',
                      maxWidth: { xs: '100%', md: '78%' },
                    }}
                  >
                    <Chip
                      size="small"
                      label={item.role === 'user' ? '你' : `AI · ${item.mode}`}
                      color={item.role === 'user' ? 'primary' : 'default'}
                      sx={{ mb: 0.75 }}
                    />
                    <Paper
                      elevation={0}
                      sx={{
                        p: 1.5,
                        borderRadius: 2,
                        bgcolor: item.role === 'user' ? 'primary.main' : 'background.default',
                        color: item.role === 'user' ? 'primary.contrastText' : 'text.primary',
                        border: item.role === 'user' ? 'none' : '1px solid',
                        borderColor: 'divider',
                        whiteSpace: 'pre-wrap',
                        overflowWrap: 'anywhere',
                      }}
                    >
                      <Typography component="pre" sx={{ m: 0, fontFamily: 'inherit', whiteSpace: 'pre-wrap' }}>
                        {item.content}
                      </Typography>
                    </Paper>
                  </Box>
                ))}
                {mutation.isPending ? <LoadingSpinner message="AI 正在分析..." /> : null}
              </Stack>
            )}
          </Paper>

          {lastResponse?.portfolio_summary ? (
            <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5}>
              <Chip label={`总市值 ${formatCurrency(lastResponse.portfolio_summary.total_value_cny)}`} />
              <Chip label={`总收益 ${formatCurrency(lastResponse.portfolio_summary.total_pnl_cny)}`} />
              <Chip label={`收益率 ${formatPercentage(lastResponse.portfolio_summary.total_return_pct)}`} />
            </Stack>
          ) : null}

          <Stack direction="row" spacing={1.5} alignItems="flex-end">
            <TextField
              fullWidth
              multiline
              minRows={2}
              maxRows={5}
              label="输入问题"
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
                  sendMessage();
                }
              }}
            />
            <Tooltip title="发送">
              <span>
                <IconButton color="primary" size="large" onClick={sendMessage} disabled={!canSend}>
                  <SendIcon />
                </IconButton>
              </span>
            </Tooltip>
          </Stack>
        </Stack>
      </SectionCard>
    </Stack>
  );
}
