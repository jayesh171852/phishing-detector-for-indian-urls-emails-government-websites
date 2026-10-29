export interface UrlFeatures {
  hostname: string;
  tld: string;
  pathLength: number;
  hasLogin: boolean;
  length: number;
}

export function extractSimpleFeatures(url: string): UrlFeatures {
  try {
    const parsed = new URL(url);
    const hostname = parsed.hostname;
    const tld = hostname.split('.').pop() || '';
    const path = parsed.pathname;
    const hasLogin = /(login|signin|auth)/i.test(url);
    const length = hostname.length;
    return {
      hostname,
      tld,
      pathLength: path.length,
      hasLogin,
      length,
    };
  } catch (e) {
    return {
      hostname: '',
      tld: '',
      pathLength: 0,
      hasLogin: false,
      length: 0,
    };
  }
}
