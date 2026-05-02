import { z } from 'zod';

const DECIMAL_LIMIT = /^\d+(\.\d{1,6})?$/;
const ASSET_CODE_PATTERN = /^[A-Za-z0-9_-]+$/;

export function trimText(value?: string | null): string {
  return (value ?? '').trim();
}

export const transactionSchema = z
  .object({
    asset_type: z.enum(['FOREX', 'BOND', 'FUND', 'WEALTH_PRODUCT', 'FX_SWAP', 'INTEREST_INCOME']),
    asset_code: z
      .string()
      .transform((value) => value.trim().toUpperCase())
      .refine((value) => value.length > 0, '资产代码不能为空')
      .refine((value) => ASSET_CODE_PATTERN.test(value), '仅允许字母、数字、下划线和连字符'),
    asset_name: z.string().optional(),
    direction: z.enum(['BUY', 'SELL']),
    quantity: z
      .number({ invalid_type_error: '请输入数量' })
      .positive('数量必须大于 0')
      .refine((value) => DECIMAL_LIMIT.test(String(value)), '数量最多保留 6 位小数'),
    unit_price: z
      .number({ invalid_type_error: '请输入单价' })
      .positive('单价必须大于 0')
      .refine((value) => DECIMAL_LIMIT.test(String(value)), '单价最多保留 6 位小数'),
    trade_currency: z.string().trim().length(3, '币种需为 3 位代码').transform((value) => value.toUpperCase()),
    trade_time: z
      .string()
      .min(1, '请选择交易时间')
      .refine((value) => new Date(value).getTime() <= Date.now(), '交易时间不能晚于当前时间'),
    exchange_rate_to_cny: z.preprocess(
      (value) => (typeof value === 'number' && Number.isNaN(value) ? undefined : value),
      z.number().optional(),
    ),
    notes: z.string().optional(),
  })
  .superRefine((value, context) => {
    if (value.asset_type !== 'FX_SWAP' && value.trade_currency !== 'CNY' && value.exchange_rate_to_cny !== undefined && value.exchange_rate_to_cny <= 0) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['exchange_rate_to_cny'],
        message: '汇率必须大于 0；不确定时请留空',
      });
    }
  });

export type TransactionFormValues = z.infer<typeof transactionSchema>;
