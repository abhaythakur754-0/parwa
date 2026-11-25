/**
 * The legacy marketing/guest Jarvis API stores sessions in process memory.
 * That implementation is suitable only for local development and tests.
 * Production traffic must use the persistent authenticated Customer Care API.
 */
export function isLegacyJarvisGuestFlowEnabled(
  nodeEnv: string | undefined = process.env.NODE_ENV
): boolean {
  return nodeEnv !== 'production';
}
