"""
Standalone sentiment analyzer using Kiwi morphological analysis.

Extracted from PlatformAnalyzer to be usable independently.
Provides richer analysis than sentiment.py (Kiwi-based) while
sentiment.py retains lightweight comment-level utility functions.
"""

import logging
import re
from collections import Counter

logger = logging.getLogger(__name__)


class SentimentAnalyzer:
    """Analyze sentiment distribution from a list of text items.

    Usable standalone - has no dependency on PlatformAnalyzer.

    Usage::

        analyzer = SentimentAnalyzer()
        result = analyzer.analyze([{"text": "정말 좋아요"}, ...])
    """

    # Kiwi morphological analyzer (lazy-loaded class-level singleton)
    _kiwi = None

    # POS tags to extract as keywords (nouns, verbs, adjectives)
    _KEYWORD_POS = frozenset({"NNG", "NNP", "VV", "VA", "SL"})  # 일반명사, 고유명사, 동사, 형용사, 외국어

    # Custom dictionary: streamer/vtuber/community terms Kiwi doesn't know
    _CUSTOM_WORDS = [
        # Vtuber / streamer names (NNP = proper noun)
        ("이브닛", "NNP"), ("아카이브", "NNP"), ("여르미", "NNP"), ("결이", "NNP"),
        ("몽이", "NNP"), ("챠니", "NNP"), ("챱츄", "NNP"), ("세구", "NNP"),
        ("버시", "NNP"), ("쿠우", "NNP"), ("사미", "NNP"), ("기원", "NNP"),
        # Platform names
        ("버디", "NNP"), ("숲", "NNP"), ("치지직", "NNP"),
        # Community slang (NNG = common noun)
        ("개추", "NNG"), ("비추", "NNG"), ("꿀잼", "NNG"), ("노잼", "NNG"),
        ("입덕", "NNG"), ("탈덕", "NNG"), ("덕질", "NNG"), ("최애", "NNG"),
        ("갓겜", "NNG"), ("핵노잼", "NNG"), ("개꿀", "NNG"),
        ("방셀", "NNG"), ("디시콘", "NNG"),
        # Sentiment adjectives Kiwi may not parse correctly
        ("존잘", "VA"), ("존예", "VA"), ("킹왕짱", "NNG"),
    ]

    # Stopwords: UI noise, DCInside markup, common particles
    _STOPWORDS = frozenset({
        # DCInside UI / markup noise
        "디시콘", "보기", "이전다음", "이전", "다음", "갤러리", "마이너갤",
        "답글", "추천수", "조회수", "댓글수", "작성일", "말머리",
        "전체글", "개념글", "공지", "설정", "검색", "정렬",
        "로그인", "닉네임", "아이디", "비밀번호", "회원",
        "삭제", "수정", "신고", "차단", "답변",
        # Common Korean particles / fillers
        "그래서", "그런데", "하지만", "그리고", "그래도", "그러면",
        "이거", "저거", "거기", "여기", "어디", "언제", "뭐가",
        "진짜", "근데", "아니", "그냥", "이게", "좀",
        "ㅇㅇ", "ㄴㄴ", "ㄱㄱ", "ㅇㅋ",
        # App / platform noise
        "app", "com", "http", "https", "www", "gall",
        "dcinside", "youtube", "naver", "kakao", "soop",
        "모바일", "갤럭시",
        # DCInside content noise
        "댓글은", "댓글", "해당", "작성자", "이용자", "본문",
        "클린봇", "운영자", "관리자",
        # Short meaningless
        "해서", "했는데", "하는", "되는", "있는", "없는",
        "같은", "라는", "이런", "저런", "어떤",
        "하고", "해야", "해도", "하면", "할까",
    })

    _POSITIVE_KW = [
        # Korean - emotions
        "좋아", "좋다", "좋은", "최고", "감사", "사랑", "축하", "대박",
        "멋지", "예쁘", "귀엽", "화이팅", "응원", "기대", "감동", "행복",
        "설렌", "좋겠", "부럽", "멋있", "잘생", "이쁘", "신기",
        # Korean - community slang
        "개추", "추천", "인정", "재밌", "꿀잼", "웃긴", "레전드", "갓",
        "존잘", "존예", "개꿀", "찐이", "역대급", "헐대박", "쩐다",
        "짱", "굿", "미쳤", "실화냐", "킹왕짱",
        "ㅋㅋㅋ", "ㅎㅎㅎ", "ㅋㅋ", "ㅎㅎ",
        # Korean - streamer/vtuber specific
        "겐끼", "방송잘", "잘봤", "잘본", "존버", "떡상", "개꿀잼",
        "고마워", "수고", "힘내", "잘했", "축하", "재밌었",
        "최애", "덕질", "입덕", "갓겜", "꿀보이스", "존좋",
        # English
        "good", "great", "love", "amazing", "awesome", "best",
        "nice", "cool", "beautiful", "wonderful", "excellent", "perfect",
        "cute", "funny", "lol", "lmao",
    ]

    _NEGATIVE_KW = [
        # Korean - emotions
        "싫어", "싫다", "나쁘", "최악", "짜증", "실망", "별로",
        "역겹", "징그", "불쾌", "화난", "빡치", "열받", "답답",
        "못생", "꼴불견", "어이없", "한심", "쪽팔", "후회", "지겹",
        "시끄", "거슬", "불편", "아쉽", "안타깝",
        # Korean - community slang
        "노잼", "재미없", "쓰레기", "망했", "구라", "거짓",
        "비추", "노답", "헛소리", "뻘소리", "허접",
        "ㅂㅅ", "ㅄ", "ㅡㅡ", "ㅠㅠ", "ㅜㅜ",
        # Korean - stronger negatives
        "꺼져", "닥쳐", "병맛", "구역질", "혐오", "극혐",
        "개별로", "개망", "쓸모없", "폭망", "완전망",
        "탈덕", "안티", "악플", "욕설",
        # English
        "bad", "worst", "hate", "terrible", "awful", "boring",
        "ugly", "trash", "waste", "stupid", "sucks", "cringe",
    ]

    @classmethod
    def _get_kiwi(cls):
        """Lazy-load Kiwi morphological analyzer (class-level singleton)."""
        if cls._kiwi is None:
            try:
                from kiwipiepy import Kiwi
                kiwi = Kiwi()
                for word, tag in cls._CUSTOM_WORDS:
                    try:
                        kiwi.add_user_word(word, tag)
                    except Exception as e:
                        logger.debug("Kiwi add_user_word failed for %r: %s", word, e)
                cls._kiwi = kiwi
                logger.info("Kiwi morphological analyzer loaded with %d custom words", len(cls._CUSTOM_WORDS))
            except ImportError:
                logger.info("kiwipiepy not available, using regex keyword extraction")
                cls._kiwi = False
        return cls._kiwi if cls._kiwi is not False else None

    def _extract_keywords(self, text):
        """Extract meaningful keywords using Kiwi morphological analyzer (or regex fallback)."""
        kiwi = self._get_kiwi()
        if kiwi:
            try:
                tokens = kiwi.tokenize(text)
                return [t.form for t in tokens
                        if t.tag in self._KEYWORD_POS
                        and len(t.form) >= (3 if t.tag == "SL" else 2)]
            except Exception as e:
                logger.debug("Kiwi tokenize failed in _extract_keywords: %s", e)
        # Regex fallback
        return re.findall(r"[가-힣]{2,}|[a-zA-Z]{3,}", text)

    def analyze(self, items):
        """Analyze sentiment distribution from a list of text items.

        Each item should be a dict with a ``text`` key.

        Returns a dict with keys: total, sentiment, distribution, top_keywords, overall.
        """
        if not items:
            return {
                "total": 0,
                "sentiment": {"positive": 0, "neutral": 0, "negative": 0},
            }

        # Build lemma sets for Kiwi-based sentiment (verb/adj stems)
        pos_lemmas = {"좋다", "멋지다", "예쁘다", "귀엽다", "재미있다", "재밌다",
                      "감동하다", "행복하다", "기대하다", "부럽다", "잘생기다",
                      "신기하다", "고맙다", "수고하다", "웃기다", "즐겁다"}
        neg_lemmas = {"싫다", "나쁘다", "짜증나다", "실망하다", "역겹다",
                      "불쾌하다", "답답하다", "후회하다", "지겹다", "불편하다",
                      "한심하다", "어이없다", "아쉽다", "안타깝다", "못생기다"}

        sentiment_counts = {"positive": 0, "neutral": 0, "negative": 0}
        keywords = Counter()

        for item in items:
            text = (item.get("text", "") or "").lower()
            if not text or len(text) < 2:
                continue

            # Score-based sentiment: keyword substring match + Kiwi lemma match
            pos_score = sum(1 for kw in self._POSITIVE_KW if kw in text)
            neg_score = sum(1 for kw in self._NEGATIVE_KW if kw in text)

            # Kiwi morphological sentiment boost (matches verb/adj stems accurately)
            kiwi = self._get_kiwi()
            if kiwi:
                try:
                    tokens = kiwi.tokenize(text)
                    for t in tokens:
                        if t.tag in ("VV", "VA", "XR"):  # verb, adjective, root
                            lemma = t.form + "다"
                            if lemma in pos_lemmas:
                                pos_score += 2
                            elif lemma in neg_lemmas:
                                neg_score += 2
                except Exception as e:
                    logger.debug("Kiwi tokenize failed in analyze: %s", e)

            if pos_score > neg_score:
                sentiment_counts["positive"] += 1
            elif neg_score > pos_score:
                sentiment_counts["negative"] += 1
            elif pos_score > 0 and neg_score > 0:
                sentiment_counts["neutral"] += 1  # mixed
            else:
                sentiment_counts["neutral"] += 1

            # Extract keywords via morphological analysis (Kiwi) or regex fallback
            words = self._extract_keywords(text)
            for w in words:
                if w not in self._STOPWORDS and len(w) >= 2:
                    keywords[w] += 1

        total = sum(sentiment_counts.values())
        distribution = {
            k: round(v / total, 3) if total > 0 else 0
            for k, v in sentiment_counts.items()
        }

        return {
            "total": total,
            "sentiment": sentiment_counts,
            "distribution": distribution,
            "top_keywords": [
                {"word": w, "count": c} for w, c in keywords.most_common(20)
            ],
            "overall": max(sentiment_counts, key=lambda key: sentiment_counts[key])
            if total > 0
            else "neutral",
        }
