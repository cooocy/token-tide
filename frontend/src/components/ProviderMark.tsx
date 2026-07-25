import deepseekLogo from '@/assets/provider-logos/deepseek.ico';
import openrouterLogo from '@/assets/provider-logos/openrouter.svg';
import xaiLogo from '@/assets/provider-logos/xai.ico';
import { formatProviderMark } from '@/lib/display';

const PROVIDER_LOGOS: Record<string, string> = {
  deepseek: deepseekLogo,
  openrouter: openrouterLogo,
  xai: xaiLogo,
};

interface ProviderMarkProps {
  provider: string;
}

export default function ProviderMark({ provider }: ProviderMarkProps) {
  const logo = PROVIDER_LOGOS[provider.toLowerCase()];

  return (
    <span className={`provider-mark${logo ? ' has-logo' : ''}`} aria-hidden="true">
      {logo ? <img src={logo} alt="" /> : formatProviderMark(provider)}
    </span>
  );
}
