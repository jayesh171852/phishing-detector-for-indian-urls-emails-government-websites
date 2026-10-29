export function mockPredict(features: any): number {
  // Simple mock: combine some feature heuristics
  let score = 0;
  if (features.hasLogin) score += 0.3;
  if (features.tld === 'com') score += 0.2;
  if (features.length > 10) score += 0.2;
  score += Math.random() * 0.3; // add randomness
  return Math.min(score, 1);
}
