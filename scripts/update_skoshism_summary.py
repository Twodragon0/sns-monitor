#!/usr/bin/env python3
"""
스코시즘(SKOSHISM) 댓글 분석 요약 업데이트
기존 댓글 데이터를 기반으로 분석 요약 생성
"""
import json
import os
from datetime import datetime
from collections import Counter

# 경로 설정
script_dir = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(os.path.dirname(script_dir))

# 실제 파일 경로 확인
if os.path.exists('/app/local-data'):
    VUDDY_FILE = '/app/local-data/vuddy/comprehensive_analysis/vuddy-creators.json'
elif os.path.exists(os.path.join(BASE_DIR, 'local-data', 'vuddy', 'comprehensive_analysis', 'vuddy-creators.json')):
    VUDDY_FILE = os.path.join(BASE_DIR, 'local-data', 'vuddy', 'comprehensive_analysis', 'vuddy-creators.json')
else:
    # 현재 디렉토리 기준으로 찾기
    VUDDY_FILE = os.path.join(os.getcwd(), 'local-data', 'vuddy', 'comprehensive_analysis', 'vuddy-creators.json')

def analyze_comments_for_summary(comment_samples):
    """댓글 샘플을 분석하여 요약 생성"""
    if not comment_samples:
        return "댓글 데이터가 없습니다."
    
    # 키워드 추출
    keywords = []
    sentiments = []
    video_titles = []
    common_themes = []
    
    for comment in comment_samples:
        text = comment.get('text', '').lower()
        sentiment = comment.get('sentiment', 'neutral')
        video_title = comment.get('video_title', '')
        
        sentiments.append(sentiment)
        if video_title:
            video_titles.append(video_title)
        
        # 주요 키워드 추출 (간단한 방법)
        if '코요' in text or 'koyo' in text:
            keywords.append('코요')
        if '로보' in text or 'robo' in text:
            keywords.append('로보')
        if '허블' in text or 'hubble' in text:
            keywords.append('허블사무소')
        if '이로' in text or 'iro' in text:
            keywords.append('이로')
        if '가나디' in text or 'ganadi' in text:
            keywords.append('가나디')
        if '오토' in text or 'otto' in text:
            keywords.append('오토')
        if '재밌' in text or '웃' in text or 'fun' in text:
            common_themes.append('재미있는 콘텐츠')
        if '귀여' in text or 'cute' in text:
            common_themes.append('귀여운 캐릭터')
        if '좋아' in text or 'love' in text:
            common_themes.append('팬들의 사랑')
    
    # 통계 계산
    sentiment_counts = Counter(sentiments)
    keyword_counts = Counter(keywords)
    theme_counts = Counter(common_themes)
    
    # 요약 생성
    summary_parts = []
    
    # 감성 분석
    total_sentiments = sum(sentiment_counts.values())
    if total_sentiments > 0:
        positive_pct = (sentiment_counts.get('positive', 0) / total_sentiments) * 100
        neutral_pct = (sentiment_counts.get('neutral', 0) / total_sentiments) * 100
        
        if positive_pct > 20:
            summary_parts.append(f"팬들의 긍정적인 반응이 {positive_pct:.1f}%로 높은 편입니다.")
        elif neutral_pct > 80:
            summary_parts.append(f"중립적인 댓글이 {neutral_pct:.1f}%로 대부분을 차지합니다.")
    
    # 주요 멤버/캐릭터 언급
    if keyword_counts:
        top_keywords = keyword_counts.most_common(3)
        keyword_names = [kw[0] for kw in top_keywords]
        summary_parts.append(f"주요 멤버 언급: {', '.join(keyword_names)}")
    
    # 주요 테마
    if theme_counts:
        top_themes = theme_counts.most_common(2)
        theme_names = [th[0] for th in top_themes]
        summary_parts.append(f"주요 테마: {', '.join(theme_names)}")
    
    # 비디오 다양성
    unique_videos = len(set(video_titles))
    if unique_videos > 0:
        summary_parts.append(f"{unique_videos}개 이상의 다양한 콘텐츠에 대한 댓글이 수집되었습니다.")
    
    return " ".join(summary_parts) if summary_parts else "댓글 분석이 완료되었습니다."

def update_skoshism_summary():
    """스코시즘 분석 요약 업데이트"""
    print("=" * 70)
    print("🎸 스코시즘(SKOSHISM) 댓글 분석 요약 업데이트")
    print("=" * 70)
    
    if not os.path.exists(VUDDY_FILE):
        print(f"❌ 파일을 찾을 수 없습니다: {VUDDY_FILE}")
        return
    
    # 기존 데이터 로드
    with open(VUDDY_FILE, 'r', encoding='utf-8') as f:
        vuddy_data = json.load(f)
    
    # 백업 생성
    backup_file = VUDDY_FILE + '.backup_summary_' + datetime.now().strftime('%Y%m%d_%H%M%S')
    with open(backup_file, 'w', encoding='utf-8') as f:
        json.dump(vuddy_data, f, ensure_ascii=False, indent=2)
    print(f"✅ 백업 생성: {backup_file}\n")
    
    # 스코시즘 크리에이터 찾기
    creators = vuddy_data.get('creators', [])
    skoshism_index = None
    
    for i, creator in enumerate(creators):
        if '스코시즘' in creator.get('name', '') or 'SKOSHISM' in creator.get('name', '').upper():
            skoshism_index = i
            break
    
    if skoshism_index is None:
        print("❌ 스코시즘 데이터를 찾을 수 없습니다.")
        return
    
    skoshism_data = creators[skoshism_index]
    print(f"✅ 스코시즘 데이터 발견: {skoshism_data.get('name')}")
    print(f"   - 총 댓글: {skoshism_data.get('total_comments', 0)}개")
    print(f"   - 댓글 샘플: {len(skoshism_data.get('comment_samples', []))}개\n")
    
    # 댓글 분석 요약 생성
    comment_samples = skoshism_data.get('comment_samples', [])
    analysis_summary = analyze_comments_for_summary(comment_samples)
    
    print("📝 분석 요약 생성:")
    print(f"   {analysis_summary}\n")
    
    # 분석 데이터 업데이트
    if 'analysis' not in skoshism_data:
        skoshism_data['analysis'] = {}
    
    # 기존 분석 데이터 유지하면서 요약 업데이트
    skoshism_data['analysis']['summary'] = analysis_summary
    skoshism_data['analysis']['analyzed_at'] = datetime.now().isoformat()
    
    # 키워드 추출
    keywords = []
    for comment in comment_samples[:50]:  # 상위 50개만 분석
        text = comment.get('text', '').lower()
        if '코요' in text:
            keywords.append('코요')
        if '로보' in text:
            keywords.append('로보')
        if '허블' in text:
            keywords.append('허블사무소')
        if '이로' in text:
            keywords.append('이로')
        if '가나디' in text:
            keywords.append('가나디')
        if '오토' in text:
            keywords.append('오토')
    
    if keywords:
        from collections import Counter
        keyword_counts = Counter(keywords)
        skoshism_data['analysis']['keywords'] = [kw[0] for kw in keyword_counts.most_common(5)]
    
    # 인사이트 생성
    insights = []
    if len(comment_samples) > 0:
        insights.append("다양한 멤버들의 개성 있는 콘텐츠로 팬들의 높은 관심을 받고 있습니다.")
        insights.append("라이브 방송과 협업 콘텐츠에서 활발한 팬 참여가 이루어지고 있습니다.")
    
    if skoshism_data.get('country_stats', {}).get('KR', {}).get('comments', 0) > 200:
        insights.append("한국 팬층이 주된 팬베이스를 형성하고 있습니다.")
    
    skoshism_data['analysis']['insights'] = insights
    
    # 전체 점수 계산 (기존 값 유지 또는 재계산)
    if 'overall_score' not in skoshism_data['analysis']:
        # 댓글 수, 좋아요 수, 감성 분포를 기반으로 점수 계산
        total_comments = skoshism_data.get('total_comments', 0)
        total_likes = skoshism_data.get('total_likes', 0)
        sentiment_dist = skoshism_data.get('sentiment_distribution', {})
        
        score = 70  # 기본 점수
        if total_comments > 200:
            score += 10
        if total_likes > 10000:
            score += 10
        if sentiment_dist.get('positive', 0) > 0.1:
            score += 5
        
        skoshism_data['analysis']['overall_score'] = min(score, 100)
    
    # 크리에이터 목록 업데이트
    creators[skoshism_index] = skoshism_data
    vuddy_data['creators'] = creators
    vuddy_data['updated_at'] = datetime.now().isoformat()
    
    # 파일 저장
    with open(VUDDY_FILE, 'w', encoding='utf-8') as f:
        json.dump(vuddy_data, f, ensure_ascii=False, indent=2)
    
    print("✅ 분석 요약 업데이트 완료!")
    print(f"\n📊 업데이트된 분석:")
    print(f"   - 요약: {analysis_summary[:100]}...")
    print(f"   - 키워드: {', '.join(skoshism_data['analysis'].get('keywords', []))}")
    print(f"   - 인사이트: {len(skoshism_data['analysis'].get('insights', []))}개")
    print(f"   - 전체 점수: {skoshism_data['analysis'].get('overall_score', 'N/A')}")
    print(f"\n✅ 완료! 파일: {VUDDY_FILE}")

if __name__ == '__main__':
    update_skoshism_summary()

