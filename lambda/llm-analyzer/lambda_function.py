"""
Bedrock LLM 분석기
수집된 SNS 데이터를 Amazon Bedrock Claude로 분석
- 감성 분석 (긍정/부정/중립)
- 트렌드 분석
- 키워드 추출
- 요약 생성
"""

import json
import os
import boto3
from datetime import datetime
from decimal import Decimal

# AWS 클라이언트
s3_client = boto3.client('s3')
bedrock_runtime = boto3.client('bedrock-runtime', region_name=os.environ.get('BEDROCK_REGION', 'us-east-1'))
dynamodb = boto3.resource('dynamodb')
sns_client = boto3.client('sns')

# 환경 변수
S3_BUCKET = os.environ.get('S3_BUCKET')
BEDROCK_MODEL_ID = os.environ.get('BEDROCK_MODEL_ID', 'anthropic.claude-3-haiku-20240307-v1:0')
DYNAMODB_TABLE = os.environ.get('DYNAMODB_TABLE')
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN')
ALERT_THRESHOLD_NEGATIVE = float(os.environ.get('ALERT_THRESHOLD_NEGATIVE', '0.7'))  # 부정 비율 70% 이상 시 알림

def load_data_from_s3(s3_key):
    """S3에서 크롤링 데이터 로드"""
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=s3_key)
        data = json.loads(response['Body'].read().decode('utf-8'))
        return data
    except Exception as e:
        print(f"Error loading data from S3: {e}")
        raise

def extract_text_content(data):
    """플랫폼별 데이터에서 텍스트 추출"""
    platform = data.get('platform', '')
    texts = []

    if platform == 'youtube':
        # YouTube 댓글 추출
        for video_item in data.get('data', []):
            for comment in video_item.get('comments', []):
                texts.append({
                    'text': comment['text'],
                    'author': comment['author'],
                    'like_count': comment.get('like_count', 0),
                    'published_at': comment.get('published_at', '')
                })

                # 대댓글도 포함
                for reply in comment.get('replies', []):
                    texts.append({
                        'text': reply['text'],
                        'author': reply['author'],
                        'like_count': reply.get('like_count', 0),
                        'published_at': reply.get('published_at', '')
                    })

    elif platform == 'telegram':
        # Telegram 메시지 추출
        for message in data.get('messages', []):
            texts.append({
                'text': message['text'],
                'author': message.get('author', 'Unknown'),
                'views': message.get('views', 0),
                'date': message.get('date', '')
            })

    elif platform == 'twitter':
        # Twitter 트윗 추출
        for tweet in data.get('tweets', []):
            texts.append({
                'text': tweet['text'],
                'author': tweet['author'],
                'likes': tweet.get('like_count', 0),
                'retweets': tweet.get('retweet_count', 0),
                'created_at': tweet.get('created_at', '')
            })

    elif platform == 'rss':
        # RSS 피드 엔트리 추출
        for entry in data.get('entries', []):
            # 제목 + 요약 + 내용 결합
            text = f"{entry.get('title', '')}\n{entry.get('summary', '')}"
            if 'content' in entry:
                text += f"\n{entry['content']}"

            texts.append({
                'text': text,
                'author': entry.get('author', 'Unknown'),
                'source': entry.get('source', ''),
                'feed_title': entry.get('feed_title', ''),
                'link': entry.get('link', ''),
                'published': entry.get('published', '')
            })

    return texts

def call_bedrock_claude(prompt, max_tokens=2000):
    """Bedrock Claude API 호출"""
    try:
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.3,
            "top_p": 0.9
        })

        response = bedrock_runtime.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            body=body
        )

        response_body = json.loads(response['body'].read())
        return response_body['content'][0]['text']

    except Exception as e:
        print(f"Error calling Bedrock: {e}")
        raise

def analyze_sentiment_per_comment(texts):
    """각 댓글별 감성 분석 (배치 처리)"""

    # 최대 30개씩 배치 처리 (비용과 정확도 균형)
    batch_size = 30
    all_comment_sentiments = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]

        # 댓글 목록을 번호와 함께 생성
        text_content = "\n".join([f"{idx}. {t['text']}" for idx, t in enumerate(batch)])

        prompt = f"""다음은 SNS에서 수집한 댓글입니다. 각 댓글의 감성을 분석해주세요.

댓글 목록:
{text_content}

각 댓글에 대해 다음 JSON 배열 형식으로 분석 결과를 제공해주세요:
[
  {{"index": 0, "sentiment": "positive|negative|neutral", "confidence": 0.0-1.0}},
  {{"index": 1, "sentiment": "positive|negative|neutral", "confidence": 0.0-1.0}},
  ...
]

분석 기준:
- positive: 긍정적, 호의적, 칭찬, 지지
- negative: 부정적, 비판적, 불만, 반대
- neutral: 중립적, 사실 전달, 질문

JSON 배열만 반환하세요."""

        response = call_bedrock_claude(prompt, max_tokens=2000)

        try:
            # JSON 파싱
            batch_sentiments = json.loads(response)

            # 원본 댓글에 감성 정보 추가
            for sentiment_data in batch_sentiments:
                idx = sentiment_data['index']
                if idx < len(batch):
                    batch[idx]['sentiment'] = sentiment_data['sentiment']
                    batch[idx]['sentiment_confidence'] = sentiment_data.get('confidence', 0.5)

            all_comment_sentiments.extend(batch)
        except json.JSONDecodeError:
            # Fallback: 기본값으로 neutral 설정
            for comment in batch:
                comment['sentiment'] = 'neutral'
                comment['sentiment_confidence'] = 0.5
            all_comment_sentiments.extend(batch)

    return all_comment_sentiments

def analyze_sentiment(texts):
    """감성 분석 (전체 + 개별)"""

    # 1. 개별 댓글 감성 분석
    texts_with_sentiment = analyze_sentiment_per_comment(texts)

    # 2. 전체 통계 계산
    positive_count = sum(1 for t in texts_with_sentiment if t.get('sentiment') == 'positive')
    negative_count = sum(1 for t in texts_with_sentiment if t.get('sentiment') == 'negative')
    neutral_count = sum(1 for t in texts_with_sentiment if t.get('sentiment') == 'neutral')
    total_count = len(texts_with_sentiment)

    sentiment_distribution = {
        'positive': round(positive_count / total_count, 3) if total_count > 0 else 0,
        'negative': round(negative_count / total_count, 3) if total_count > 0 else 0,
        'neutral': round(neutral_count / total_count, 3) if total_count > 0 else 0
    }

    # 전체 감성 결정
    if positive_count > negative_count and positive_count > neutral_count:
        overall_sentiment = 'positive'
    elif negative_count > positive_count and negative_count > neutral_count:
        overall_sentiment = 'negative'
    else:
        overall_sentiment = 'neutral'

    # 3. 주목할 만한 댓글 선정 (좋아요가 많고 감성이 명확한 댓글)
    notable_comments = []

    # 긍정적 댓글 중 좋아요가 많은 것
    positive_comments = [t for t in texts_with_sentiment if t.get('sentiment') == 'positive']
    positive_comments.sort(key=lambda x: x.get('like_count', 0), reverse=True)
    for comment in positive_comments[:3]:
        notable_comments.append({
            'text': comment['text'][:200],  # 최대 200자
            'sentiment': 'positive',
            'reason': f"좋아요 {comment.get('like_count', 0)}개 - 긍정적 반응"
        })

    # 부정적 댓글 중 좋아요가 많은 것
    negative_comments = [t for t in texts_with_sentiment if t.get('sentiment') == 'negative']
    negative_comments.sort(key=lambda x: x.get('like_count', 0), reverse=True)
    for comment in negative_comments[:3]:
        notable_comments.append({
            'text': comment['text'][:200],  # 최대 200자
            'sentiment': 'negative',
            'reason': f"좋아요 {comment.get('like_count', 0)}개 - 부정적 반응"
        })

    return {
        'overall_sentiment': overall_sentiment,
        'sentiment_distribution': sentiment_distribution,
        'sentiment_explanation': f"총 {total_count}개 댓글 중 긍정 {positive_count}개({sentiment_distribution['positive']*100:.1f}%), 부정 {negative_count}개({sentiment_distribution['negative']*100:.1f}%), 중립 {neutral_count}개({sentiment_distribution['neutral']*100:.1f}%)",
        'notable_comments': notable_comments,
        'comments_with_sentiment': texts_with_sentiment  # 개별 댓글별 감성 정보 포함
    }

def extract_keywords(texts, keyword):
    """키워드 및 트렌드 추출"""

    sample_texts = texts[:50] if len(texts) > 50 else texts
    text_content = "\n".join([f"- {t['text']}" for t in sample_texts])

    prompt = f"""다음은 "{keyword}" 키워드로 검색된 SNS 게시글/댓글입니다.

텍스트 목록:
{text_content}

다음을 분석해주세요:
1. 주요 키워드 5-10개 추출 (연관어, 자주 언급되는 단어)
2. 트렌드 및 패턴 파악
3. 주요 이슈 요약

JSON 형식으로 반환:
{{
  "keywords": ["키워드1", "키워드2", ...],
  "trends": ["트렌드 설명 1", "트렌드 설명 2"],
  "summary": "전체 내용을 3-4문장으로 요약",
  "topics": [
    {{"topic": "주제명", "frequency": "높음|중간|낮음", "description": "설명"}}
  ]
}}

JSON만 반환하세요."""

    response = call_bedrock_claude(prompt, max_tokens=1500)

    try:
        analysis = json.loads(response)
        return analysis
    except json.JSONDecodeError:
        return {
            "keywords": [keyword],
            "trends": [],
            "summary": "분석 실패",
            "topics": []
        }

def generate_insights(sentiment_analysis, keyword_analysis, platform, keyword):
    """종합 인사이트 생성"""

    prompt = f"""다음은 {platform} 플랫폼에서 "{keyword}" 키워드로 수집한 데이터 분석 결과입니다.

감성 분석:
{json.dumps(sentiment_analysis, ensure_ascii=False, indent=2)}

키워드 분석:
{json.dumps(keyword_analysis, ensure_ascii=False, indent=2)}

이 데이터를 바탕으로 다음을 제공해주세요:
1. 핵심 인사이트 3-5개
2. 주의가 필요한 사항
3. 추천 액션 아이템

JSON 형식:
{{
  "key_insights": ["인사이트 1", "인사이트 2", ...],
  "warnings": ["주의사항 1", ...],
  "action_items": ["액션 1", "액션 2", ...],
  "overall_score": 0-100 (전반적인 긍정도 점수)
}}

JSON만 반환하세요."""

    response = call_bedrock_claude(prompt, max_tokens=1000)

    try:
        insights = json.loads(response)
        return insights
    except json.JSONDecodeError:
        return {
            "key_insights": [],
            "warnings": [],
            "action_items": [],
            "overall_score": 50
        }

def save_analysis_to_dynamodb(analysis_result):
    """분석 결과를 DynamoDB에 저장"""
    table = dynamodb.Table(DYNAMODB_TABLE)

    try:
        # Decimal 변환 (DynamoDB 요구사항)
        def convert_to_decimal(obj):
            if isinstance(obj, float):
                return Decimal(str(obj))
            elif isinstance(obj, dict):
                return {k: convert_to_decimal(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_to_decimal(item) for item in obj]
            return obj

        item = convert_to_decimal(analysis_result)

        table.put_item(Item=item)
        print(f"Analysis saved to DynamoDB: {analysis_result['analysis_id']}")

    except Exception as e:
        print(f"Error saving to DynamoDB: {e}")
        raise

def send_alert_if_needed(analysis_result):
    """부정 감성 비율이 높으면 알림 발송"""
    sentiment = analysis_result.get('sentiment_analysis', {})
    negative_ratio = sentiment.get('sentiment_distribution', {}).get('negative', 0)

    if negative_ratio >= ALERT_THRESHOLD_NEGATIVE:
        try:
            message = f"""
🚨 부정 감성 급증 알림

키워드: {analysis_result['keyword']}
플랫폼: {analysis_result['platform']}
부정 비율: {negative_ratio * 100:.1f}%

전체 요약:
{analysis_result.get('keyword_analysis', {}).get('summary', 'N/A')}

주의사항:
{chr(10).join(['- ' + w for w in analysis_result.get('insights', {}).get('warnings', [])])}

상세 확인: [대시보드 URL]
            """

            sns_client.publish(
                TopicArn=SNS_TOPIC_ARN,
                Subject=f'[SNS 모니터링] {analysis_result["keyword"]} 부정 감성 급증',
                Message=message
            )

            print(f"Alert sent for high negative sentiment: {negative_ratio}")

        except Exception as e:
            print(f"Error sending alert: {e}")

def lambda_handler(event, context):
    """
    Lambda 핸들러

    크롤러에서 호출하여 수집된 데이터 분석
    """

    print(f"Event: {json.dumps(event)}")

    # 이벤트에서 정보 추출
    source = event.get('source', 'unknown')
    s3_key = event.get('s3_key')
    keyword = event.get('keyword', '')
    total_items = event.get('total_items', 0)

    if not s3_key:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Missing s3_key in event'})
        }

    try:
        # S3에서 데이터 로드
        print(f"Loading data from s3://{S3_BUCKET}/{s3_key}")
        data = load_data_from_s3(s3_key)

        platform = data.get('platform', source)

        # 텍스트 추출
        texts = extract_text_content(data)
        print(f"Extracted {len(texts)} text items for analysis")

        if not texts:
            print("No texts to analyze")
            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'No texts to analyze'})
            }

        # 감성 분석
        print("Performing sentiment analysis...")
        sentiment_analysis = analyze_sentiment(texts)

        # 키워드 분석
        print("Extracting keywords and trends...")
        keyword_analysis = extract_keywords(texts, keyword)

        # 종합 인사이트
        print("Generating insights...")
        insights = generate_insights(sentiment_analysis, keyword_analysis, platform, keyword)

        # 분석 결과 조합
        analysis_result = {
            'analysis_id': f"{platform}-{keyword}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            'platform': platform,
            'keyword': keyword,
            'analyzed_at': datetime.utcnow().isoformat(),
            's3_key': s3_key,
            'total_items': total_items,
            'analyzed_items': len(texts),
            'sentiment_analysis': sentiment_analysis,
            'keyword_analysis': keyword_analysis,
            'insights': insights,
            'ttl': int((datetime.utcnow().timestamp() + 90 * 24 * 3600))  # 90일 후 삭제
        }

        # DynamoDB에 저장
        save_analysis_to_dynamodb(analysis_result)

        # 알림 확인
        send_alert_if_needed(analysis_result)

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Analysis completed',
                'analysis_id': analysis_result['analysis_id'],
                'overall_sentiment': sentiment_analysis.get('overall_sentiment'),
                'overall_score': insights.get('overall_score')
            }, ensure_ascii=False)
        }

    except Exception as e:
        print(f"Error in analysis: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
