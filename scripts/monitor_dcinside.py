#!/usr/bin/env python3
"""
DC인사이드 모니터링 스크립트
인기 게시글 3개와 모든 댓글을 수집하고 감성 분석을 수행합니다.
"""

import os
import sys
import json
import requests
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup
import time

# 프로젝트 루트 디렉토리 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'lambda' / 'dcinside-crawler'))
sys.path.insert(0, str(project_root / 'lambda' / 'common'))

# KST 시간 유틸리티 임포트
from timezone_utils import now_kst, format_kst, isoformat_kst, filename_timestamp_kst

# 로컬 모드 활성화
os.environ['LOCAL_MODE'] = 'true'
os.environ['LOCAL_DATA_DIR'] = './local-data'

# DC인사이드 크롤러 함수 임포트
from lambda_function import (
    get_gallery_posts,
    get_post_content,
    GALLERIES
)

def analyze_sentiment_simple(text):
    """간단한 키워드 기반 감성 분석"""
    positive_keywords = ['좋아', '굿', '최고', '감사', '사랑', '축하', '대박', '멋지', '예쁘', '귀엽',
                        '화이팅', '응원', '존경', '멋있', '훌륭', '완벽', '최고야', 'ㄱㅇㄷ', 'ㅊㅊ',
                        '개좋', '레전드', '갓', '천재', '실화', '미쳤', '개꿀', '개이득']
    negative_keywords = ['싫어', '나쁘', '최악', '욕', '비난', '혐오', '짜증', '실망', '별로',
                       '쓰레기', '망했', '노잼', '재미없', '허접', '구리', '병신', '개같', '개별로',
                       '개망', '답없', '노답', 'ㅅㅂ', 'ㅂㅅ', '꺼져', '죽어']

    text_lower = text.lower()

    positive_score = sum(1 for keyword in positive_keywords if keyword in text_lower)
    negative_score = sum(1 for keyword in negative_keywords if keyword in text_lower)

    if positive_score > negative_score:
        return 'positive'
    elif negative_score > positive_score:
        return 'negative'
    else:
        return 'neutral'

def get_top_posts(gallery_id, top_n, min_posts=10):
    """인기 게시글 목록 가져오기 및 정렬"""
    print("🔍 게시글 목록 가져오는 중...")
    posts = get_gallery_posts(gallery_id, max_posts=50)
    
    if not posts:
        print(f"⚠️  게시글을 찾을 수 없습니다.")
        return None
    
    # 인기도 계산 및 정렬
    for post in posts:
        post['popularity_score'] = post['view_count'] * 0.7 + post['recommend_count'] * 100
    posts.sort(key=lambda x: x['popularity_score'], reverse=True)
    
    # 최소/최대 게시글 수 결정
    actual_top_n = max(min_posts, top_n)
    actual_top_n = min(actual_top_n, len(posts))
    top_posts = posts[:actual_top_n]
    
    if actual_top_n > top_n:
        print(f"ℹ️  게시글이 적어 최소 {min_posts}개 게시글을 분석합니다.")
    print(f"✅ 상위 {len(top_posts)}개 게시글 선택 완료\n")
    
    return top_posts


def analyze_post_sentiment(post, content_data, comments):
    """게시글 및 댓글 감성 분석"""
    post_sentiment = analyze_sentiment_simple(post['title'] + ' ' + content_data['content'])
    
    comments_with_sentiment = []
    post_positive = 0
    post_negative = 0
    post_neutral = 0
    
    for comment in comments:
        sentiment = analyze_sentiment_simple(comment['text'])
        comments_with_sentiment.append({
            **comment,
            'sentiment': sentiment
        })
        
        if sentiment == 'positive':
            post_positive += 1
        elif sentiment == 'negative':
            post_negative += 1
        else:
            post_neutral += 1
    
    # 게시글 감성도 카운트에 포함
    if post_sentiment == 'positive':
        post_positive += 1
    elif post_sentiment == 'negative':
        post_negative += 1
    else:
        post_neutral += 1
    
    return post_sentiment, comments_with_sentiment, post_positive, post_negative, post_neutral


def create_post_summary(post, post_sentiment, comments_with_sentiment, post_positive, post_negative, post_neutral):
    """게시글 요약 생성"""
    summary_lines = [
        f"제목: {post['title']}",
        f"작성자: {post['author']}, 조회수: {post['view_count']}, 추천수: {post['recommend_count']}",
        f"게시글 감성: {post_sentiment}",
        f"댓글 {len(comments_with_sentiment)}개: 긍정 {post_positive}개, 부정 {post_negative}개, 중립 {post_neutral}개"
    ]
    
    # 대표 댓글 선정
    positive_comments = [c for c in comments_with_sentiment if c['sentiment'] == 'positive']
    negative_comments = [c for c in comments_with_sentiment if c['sentiment'] == 'negative']
    
    if positive_comments:
        summary_lines.append(f"대표 긍정 댓글: {positive_comments[0]['text'][:50]}...")
    if negative_comments:
        summary_lines.append(f"대표 부정 댓글: {negative_comments[0]['text'][:50]}...")
    
    return '\n'.join(summary_lines)


def process_posts(gallery_id, top_posts):
    """게시글 처리 및 감성 분석"""
    result_data = []
    total_comments = 0
    total_positive = 0
    total_negative = 0
    total_neutral = 0
    
    for idx, post in enumerate(top_posts, 1):
        print(f"📄 게시글 {idx}/{len(top_posts)}: {post['title']}")
        print(f"   작성자: {post['author']} | 조회: {post['view_count']} | 추천: {post['recommend_count']}")
        
        print(f"   💬 댓글 수집 중...")
        content_data = get_post_content(gallery_id, post['post_id'])
        comments = content_data['comments']
        print(f"   ✅ 댓글 {len(comments)}개 수집 완료")
        
        # 감성 분석
        post_sentiment, comments_with_sentiment, post_positive, post_negative, post_neutral = \
            analyze_post_sentiment(post, content_data, comments)
        
        total_comments += len(comments)
        total_positive += post_positive
        total_negative += post_negative
        total_neutral += post_neutral
        
        # 감성 분석 통계
        total_items = len(comments) + 1
        positive_ratio = post_positive / total_items if total_items > 0 else 0
        negative_ratio = post_negative / total_items if total_items > 0 else 0
        neutral_ratio = post_neutral / total_items if total_items > 0 else 0
        
        print(f"   🤖 감성 분석:")
        print(f"      긍정: {post_positive}개 ({positive_ratio*100:.1f}%)")
        print(f"      부정: {post_negative}개 ({negative_ratio*100:.1f}%)")
        print(f"      중립: {post_neutral}개 ({neutral_ratio*100:.1f}%)\n")
        
        # 요약 생성
        summary = create_post_summary(post, post_sentiment, comments_with_sentiment, 
                                     post_positive, post_negative, post_neutral)
        
        result_data.append({
            'post': post,
            'content': content_data['content'],
            'comments': comments_with_sentiment,
            'comment_count': len(comments),
            'post_sentiment': post_sentiment,
            'sentiment_statistics': {
                'positive': post_positive,
                'negative': post_negative,
                'neutral': post_neutral,
                'positive_ratio': round(positive_ratio, 3),
                'negative_ratio': round(negative_ratio, 3),
                'neutral_ratio': round(neutral_ratio, 3)
            },
            'summary': summary
        })
        
        time.sleep(1)  # Rate limiting
    
    return result_data, total_comments, total_positive, total_negative, total_neutral


def monitor_dcinside_gallery(gallery_id, top_n=3):
    """
    DC인사이드 갤러리 모니터링

    Args:
        gallery_id: 갤러리 ID
        top_n: 상위 몇 개의 게시글을 분석할지 (기본: 3개)

    Returns:
        모니터링 결과 딕셔너리
    """
    print("=" * 80)
    print(f"📊 DC인사이드 갤러리 모니터링: {gallery_id}")
    print("=" * 80)

    gallery_info = GALLERIES.get(gallery_id)
    if not gallery_info:
        print(f"❌ 알 수 없는 갤러리: {gallery_id}")
        return None

    print(f"갤러리: {gallery_info['name']}")
    print(f"상위 {top_n}개 인기 게시글 분석\n")

    try:
        # 게시글 목록 가져오기
        top_posts = get_top_posts(gallery_id, top_n)
        if not top_posts:
            return None
        
        # 게시글 처리 및 감성 분석
        result_data, total_comments, total_positive, total_negative, total_neutral = \
            process_posts(gallery_id, top_posts)
        
        # 전체 통계 계산
        total_items = total_comments + len(top_posts)
        overall_positive_ratio = total_positive / total_items if total_items > 0 else 0
        overall_negative_ratio = total_negative / total_items if total_items > 0 else 0
        overall_neutral_ratio = total_neutral / total_items if total_items > 0 else 0
        
        # API 호환 형식으로 데이터 변환
        api_compatible_data = [
            {
                'post': post_data['post'],
                'content': post_data['content'],
                'comments': post_data['comments'],
                'comment_count': post_data['comment_count']
            }
            for post_data in result_data
        ]
        
        result = {
            'gallery_id': gallery_id,
            'gallery_name': gallery_info['name'],
            'platform': 'dcinside',
            'crawled_at': isoformat_kst(),
            'monitoring_date': isoformat_kst(),
            'monitoring_date_formatted': format_kst(now_kst()),
            'top_n': top_n,
            'total_posts': len(top_posts),
            'total_posts_analyzed': len(top_posts),
            'total_comments': total_comments,
            'positive_count': total_positive,
            'negative_count': total_negative,
            'overall_sentiment_statistics': {
                'positive': total_positive,
                'negative': total_negative,
                'neutral': total_neutral,
                'positive_ratio': round(overall_positive_ratio, 3),
                'negative_ratio': round(overall_negative_ratio, 3),
                'neutral_ratio': round(overall_neutral_ratio, 3)
            },
            'keywords': gallery_info.get('keywords', []),
            'data': api_compatible_data,
            'posts': result_data
        }
        
        return result

    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return None

def save_results(results, output_dir='./local-data/dcinside'):
    """모니터링 결과를 JSON 파일로 저장 (API 호환 경로)"""
    gallery_id = results['gallery_id']

    # API가 읽는 경로: local-data/dcinside/{gallery_id}/
    gallery_dir = Path(output_dir) / gallery_id
    gallery_dir.mkdir(parents=True, exist_ok=True)

    timestamp = filename_timestamp_kst()
    filename = f"{timestamp}.json"
    filepath = gallery_dir / filename

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

    print(f"\n🏢 갤러리: {results['gallery_name']} ({results['gallery_id']})")
    print(f"📅 분석 시간: {results.get('monitoring_date_formatted', results['monitoring_date'])}")
    print(f"📄 분석된 게시글: {results['total_posts_analyzed']}개")
    print(f"💬 총 댓글: {results['total_comments']}개")

    stats = results['overall_sentiment_statistics']
    print(f"\n📈 전체 감성 분석:")
    print(f"   긍정: {stats['positive']}개 ({stats['positive_ratio']*100:.1f}%)")
    print(f"   부정: {stats['negative']}개 ({stats['negative_ratio']*100:.1f}%)")
    print(f"   중립: {stats['neutral']}개 ({stats['neutral_ratio']*100:.1f}%)")

    print(f"\n📝 게시글 요약:")
    for idx, post_data in enumerate(results['posts'], 1):
        print(f"\n   {idx}. {post_data['post']['title']}")
        print(f"      조회: {post_data['post']['view_count']} | 추천: {post_data['post']['recommend_count']} | 댓글: {post_data['comment_count']}개")
        post_stats = post_data['sentiment_statistics']
        print(f"      감성: 긍정 {post_stats['positive_ratio']*100:.1f}% | 부정 {post_stats['negative_ratio']*100:.1f}% | 중립 {post_stats['neutral_ratio']*100:.1f}%")

def main():
    """메인 함수"""
    import argparse

    parser = argparse.ArgumentParser(
        description='DC인사이드 모니터링: 인기 게시글 3개와 모든 댓글을 수집하고 감성 분석',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--galleries',
        nargs='+',
        default=['akaiv', 'ivnit'],
        choices=list(GALLERIES.keys()),
        help='모니터링할 갤러리 ID 리스트 (기본: akaiv, ivnit)'
    )
    parser.add_argument(
        '--top-n',
        type=int,
        default=3,
        help='분석할 인기 게시글 수 (기본: 3개, 최소: 10개)'
    )
    parser.add_argument(
        '--output-dir',
        default='./local-data/dcinside',
        help='결과 저장 디렉토리 (기본: ./local-data/dcinside)'
    )

    args = parser.parse_args()

    try:
        all_results = []

        for gallery_id in args.galleries:
            print(f"\n{'='*80}")
            print(f"갤러리 처리 중: {gallery_id}")
            print(f"{'='*80}\n")

            # 모니터링 실행
            results = monitor_dcinside_gallery(gallery_id, top_n=args.top_n)

            if results:
                # 결과 저장
                filepath = save_results(results, args.output_dir)

                # 요약 출력
                print_summary(results)

                all_results.append({
                    'gallery_id': gallery_id,
                    'filepath': filepath,
                    'status': 'success'
                })
            else:
                all_results.append({
                    'gallery_id': gallery_id,
                    'status': 'failed'
                })

        print("\n" + "=" * 80)
        print("✅ 모든 갤러리 모니터링 완료!")
        print("=" * 80)

        for result in all_results:
            status = "✅" if result['status'] == 'success' else "❌"
            print(f"{status} {result['gallery_id']}: {result.get('filepath', 'Failed')}")

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
