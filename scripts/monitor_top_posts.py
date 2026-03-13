#!/usr/bin/env python3
"""
SNS 모니터링 스크립트
인기 정보 3개와 모든 댓글을 수집하고 감성 분석을 수행합니다.
"""

import os
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path

# 프로젝트 루트 디렉토리 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'lambda' / 'youtube-crawler'))
sys.path.insert(0, str(project_root / 'lambda' / 'llm-analyzer'))
sys.path.insert(0, str(project_root / 'lambda' / 'common'))

# KST 시간 유틸리티 임포트
from timezone_utils import now_kst, format_kst, isoformat_kst, filename_timestamp_kst

# 로컬 모드 활성화
os.environ['LOCAL_MODE'] = 'true'
os.environ['LOCAL_DATA_DIR'] = './local-data'

from googleapiclient.discovery import build
from optimized_youtube_api import (
    search_videos_optimized,
    get_video_comments_optimized,
    print_api_stats,
    reset_api_stats
)

def get_youtube_client():
    """YouTube API 클라이언트 초기화"""
    api_key = os.environ.get('YOUTUBE_API_KEY')
    if not api_key:
        raise ValueError("YOUTUBE_API_KEY 환경 변수가 설정되지 않았습니다.")

    return build('youtube', 'v3', developerKey=api_key)

def analyze_comments_with_bedrock(comments):
    """Bedrock Claude를 사용하여 댓글 감성 분석"""
    try:
        import boto3

        # Bedrock 클라이언트 초기화
        bedrock_runtime = boto3.client(
            'bedrock-runtime',
            region_name=os.environ.get('BEDROCK_REGION', 'us-east-1')
        )

        # 댓글 데이터 준비
        texts = []
        for comment in comments:
            texts.append({
                'text': comment['text'],
                'author': comment['author'],
                'like_count': comment.get('like_count', 0),
                'published_at': comment.get('published_at', '')
            })

        # 감성 분석 수행
        from lambda_function import analyze_sentiment_per_comment

        texts_with_sentiment = analyze_sentiment_per_comment(texts)

        # 통계 계산
        positive_count = sum(1 for t in texts_with_sentiment if t.get('sentiment') == 'positive')
        negative_count = sum(1 for t in texts_with_sentiment if t.get('sentiment') == 'negative')
        neutral_count = sum(1 for t in texts_with_sentiment if t.get('sentiment') == 'neutral')
        total_count = len(texts_with_sentiment)

        return {
            'comments_with_sentiment': texts_with_sentiment,
            'statistics': {
                'total': total_count,
                'positive': positive_count,
                'negative': negative_count,
                'neutral': neutral_count,
                'positive_ratio': round(positive_count / total_count, 3) if total_count > 0 else 0,
                'negative_ratio': round(negative_count / total_count, 3) if total_count > 0 else 0,
                'neutral_ratio': round(neutral_count / total_count, 3) if total_count > 0 else 0
            }
        }
    except Exception as e:
        print(f"⚠️  Bedrock 분석 실패: {e}")
        print("   로컬 분석으로 대체합니다...")

        # 로컬 간단 분석 (키워드 기반)
        positive_keywords = ['좋아', '훌륭', '최고', '멋지', '감사', '완벽', '대박', '사랑', '행복']
        negative_keywords = ['싫어', '나쁘', '최악', '끔찍', '실망', '화나', '짜증']

        comments_with_sentiment = []
        positive_count = 0
        negative_count = 0
        neutral_count = 0

        for comment in comments:
            text = comment['text'].lower()

            # 키워드 기반 분석
            positive_score = sum(1 for keyword in positive_keywords if keyword in text)
            negative_score = sum(1 for keyword in negative_keywords if keyword in text)

            if positive_score > negative_score:
                sentiment = 'positive'
                positive_count += 1
            elif negative_score > positive_score:
                sentiment = 'negative'
                negative_count += 1
            else:
                sentiment = 'neutral'
                neutral_count += 1

            comments_with_sentiment.append({
                **comment,
                'sentiment': sentiment,
                'sentiment_confidence': 0.5
            })

        total_count = len(comments_with_sentiment)

        return {
            'comments_with_sentiment': comments_with_sentiment,
            'statistics': {
                'total': total_count,
                'positive': positive_count,
                'negative': negative_count,
                'neutral': neutral_count,
                'positive_ratio': round(positive_count / total_count, 3) if total_count > 0 else 0,
                'negative_ratio': round(negative_count / total_count, 3) if total_count > 0 else 0,
                'neutral_ratio': round(neutral_count / total_count, 3) if total_count > 0 else 0
            }
        }

def monitor_top_posts(keywords, days_ago=30, top_n=3, max_comments=100):
    """
    인기 정보 모니터링

    Args:
        keywords: 검색 키워드 리스트
        days_ago: 며칠 전부터 검색할지 (기본: 30일)
        top_n: 상위 몇 개의 영상을 분석할지 (기본: 3개)
        max_comments: 영상당 최대 댓글 수 (기본: 100개)

    Returns:
        모니터링 결과 딕셔너리
    """
    print("=" * 80)
    print("📊 SNS 모니터링 시작")
    print("=" * 80)

    # YouTube 클라이언트 초기화
    youtube = get_youtube_client()

    # API 통계 초기화
    reset_api_stats()

    # 최신 날짜 계산 (KST 기준)
    filter_date = now_kst() - timedelta(days=days_ago)
    # YouTube API는 UTC를 요구하므로 UTC로 변환
    published_after = filter_date.astimezone(datetime.now().astimezone().tzinfo.utcoffset(None) and datetime.utcnow().replace(tzinfo=None).tzinfo or None)
    published_after = filter_date.astimezone(datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).astimezone().tzinfo).strftime('%Y-%m-%dT%H:%M:%SZ')
    # 간단하게 UTC로 변환
    from datetime import timezone
    published_after = (now_kst() - timedelta(days=days_ago)).astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

    all_results = []

    for keyword in keywords:
        print(f"\n🔍 키워드: '{keyword}' 검색 중...")
        print(f"   기간: 최근 {days_ago}일")
        print(f"   상위 {top_n}개 인기 영상 분석")

        try:
            # 1. 인기 영상 3개 검색 (조회수 기준)
            videos = search_videos_optimized(
                youtube,
                keyword,
                max_results=20,  # 더 많이 가져와서 필터링
                published_after=published_after,
                order_by='date',  # 최신 순으로 정렬
                top_n_by_views=top_n  # 조회수 기준 상위 N개 선택
            )

            if not videos:
                print(f"   ⚠️  '{keyword}'에 대한 영상을 찾을 수 없습니다.")
                continue

            print(f"   ✅ {len(videos)}개의 인기 영상 발견")

            keyword_result = {
                'keyword': keyword,
                'search_date': isoformat_kst(),
                'search_date_formatted': format_kst(now_kst()),
                'search_period_days': days_ago,
                'videos': []
            }

            # 2. 각 영상의 댓글 수집 및 분석
            for idx, video in enumerate(videos, 1):
                print(f"\n   📹 영상 {idx}/{len(videos)}: {video['title']}")
                print(f"      조회수: {video['view_count']:,} | 좋아요: {video['like_count']:,} | 댓글: {video['comment_count']:,}")

                # 댓글 수집
                comment_result = get_video_comments_optimized(
                    youtube,
                    video['video_id'],
                    max_results=max_comments
                )

                comments = comment_result['comments']
                print(f"      수집된 댓글: {len(comments)}개")

                if not comments:
                    print(f"      ⚠️  댓글이 없거나 수집할 수 없습니다.")
                    continue

                # 3. 댓글 감성 분석
                print(f"      🤖 감성 분석 중...")
                sentiment_analysis = analyze_comments_with_bedrock(comments)

                stats = sentiment_analysis['statistics']
                print(f"      ✅ 감성 분석 완료:")
                print(f"         긍정: {stats['positive']}개 ({stats['positive_ratio']*100:.1f}%)")
                print(f"         부정: {stats['negative']}개 ({stats['negative_ratio']*100:.1f}%)")
                print(f"         중립: {stats['neutral']}개 ({stats['neutral_ratio']*100:.1f}%)")

                # 결과 저장
                video_result = {
                    'video': video,
                    'comments': sentiment_analysis['comments_with_sentiment'],
                    'comment_count': len(comments),
                    'sentiment_statistics': stats,
                    'country_stats': comment_result.get('country_stats', {}),
                    'vtuber_stats': comment_result.get('vtuber_stats', {})
                }

                keyword_result['videos'].append(video_result)

            all_results.append(keyword_result)

        except Exception as e:
            print(f"   ❌ 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            continue

    # API 사용 통계 출력
    print("\n")
    print_api_stats()

    return {
        'monitoring_date': isoformat_kst(),
        'monitoring_date_formatted': format_kst(now_kst()),
        'keywords': keywords,
        'results': all_results
    }

def save_results(results, output_dir='./local-data/monitoring'):
    """모니터링 결과를 JSON 파일로 저장"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = filename_timestamp_kst()
    filename = f"monitoring-{timestamp}.json"
    filepath = output_path / filename

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n💾 결과 저장: {filepath}")
    print(f"   파일 크기: {filepath.stat().st_size:,} bytes")

    return str(filepath)

def print_summary(results):
    """모니터링 결과 요약 출력"""
    print("\n" + "=" * 80)
    print("📊 모니터링 결과 요약")
    print("=" * 80)

    for keyword_result in results['results']:
        keyword = keyword_result['keyword']
        videos = keyword_result['videos']

        print(f"\n🔑 키워드: {keyword}")
        print(f"   분석된 영상: {len(videos)}개")

        total_comments = sum(v['comment_count'] for v in videos)
        total_positive = sum(v['sentiment_statistics']['positive'] for v in videos)
        total_negative = sum(v['sentiment_statistics']['negative'] for v in videos)
        total_neutral = sum(v['sentiment_statistics']['neutral'] for v in videos)

        print(f"   총 댓글 수: {total_comments:,}개")
        print(f"   긍정 댓글: {total_positive:,}개 ({total_positive/total_comments*100:.1f}%)" if total_comments > 0 else "   긍정 댓글: 0개")
        print(f"   부정 댓글: {total_negative:,}개 ({total_negative/total_comments*100:.1f}%)" if total_comments > 0 else "   부정 댓글: 0개")
        print(f"   중립 댓글: {total_neutral:,}개 ({total_neutral/total_comments*100:.1f}%)" if total_comments > 0 else "   중립 댓글: 0개")

        # 각 영상별 요약
        for idx, video in enumerate(videos, 1):
            print(f"\n   📹 영상 {idx}: {video['video']['title'][:50]}...")
            print(f"      조회수: {video['video']['view_count']:,}")
            stats = video['sentiment_statistics']
            print(f"      감성: 긍정 {stats['positive_ratio']*100:.1f}% | 부정 {stats['negative_ratio']*100:.1f}% | 중립 {stats['neutral_ratio']*100:.1f}%")

def main():
    """메인 함수"""
    import argparse

    parser = argparse.ArgumentParser(
        description='SNS 모니터링: 인기 정보 3개와 모든 댓글을 수집하고 감성 분석',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--keywords',
        nargs='+',
        default=['YourKeyword1', 'YourKeyword2'],
        help='검색할 키워드 리스트 (기본: YourKeyword1, YourKeyword2)'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=30,
        help='검색 기간 (일) (기본: 30일)'
    )
    parser.add_argument(
        '--top-n',
        type=int,
        default=3,
        help='분석할 인기 영상 수 (기본: 3개)'
    )
    parser.add_argument(
        '--max-comments',
        type=int,
        default=100,
        help='영상당 최대 댓글 수 (기본: 100개)'
    )
    parser.add_argument(
        '--output-dir',
        default='./local-data/monitoring',
        help='결과 저장 디렉토리 (기본: ./local-data/monitoring)'
    )

    args = parser.parse_args()

    # 환경 변수 확인
    if not os.environ.get('YOUTUBE_API_KEY'):
        print("❌ 오류: YOUTUBE_API_KEY 환경 변수가 설정되지 않았습니다.")
        print("   .env 파일에 YOUTUBE_API_KEY를 설정하거나 환경 변수로 설정하세요.")
        return 1

    try:
        # 모니터링 실행
        results = monitor_top_posts(
            keywords=args.keywords,
            days_ago=args.days,
            top_n=args.top_n,
            max_comments=args.max_comments
        )

        # 결과 저장
        filepath = save_results(results, args.output_dir)

        # 요약 출력
        print_summary(results)

        print("\n✅ 모니터링 완료!")
        return 0

    except KeyboardInterrupt:
        print("\n\n⚠️  사용자에 의해 중단되었습니다.")
        return 1
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
