import { PLATFORMS } from '../../constants/platforms';

/** Social Panel (Instagram, Facebook, Threads) */
export function SocialPanel() {
  const socials = [
    { key: 'instagram', ...PLATFORMS.instagram, example: 'https://www.instagram.com/username/', desc: '프로필 및 게시물 분석' },
    { key: 'facebook',  ...PLATFORMS.facebook,  example: 'https://www.facebook.com/page/', desc: '페이지 및 게시물 분석' },
    { key: 'threads',   ...PLATFORMS.threads,   example: 'https://www.threads.net/@username/', desc: '프로필 및 스레드 분석' },
  ];

  return (
    <div className="panel-social">
      <div className="panel-social__grid">
        {socials.map(s => (
          <div key={s.key} className="panel-card panel-social__card">
            <div className="panel-social__icon" style={{ background: s.color }}>{s.icon}</div>
            <h5 className="panel-card__title">{s.label}</h5>
            <p className="panel-card__body">{s.desc}</p>
            <code className="panel-social__example">{s.example}</code>
            <p className="panel-card__hint">상단 URL 입력란에 붙여넣어 분석하세요</p>
          </div>
        ))}
      </div>
    </div>
  );
}
