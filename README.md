# Language Viewer (Web Viewer / 웹 뷰어)

A Flask-based language learning viewer with CEFR-based progress tracking, vocabulary flashcards (SM-2 SRS), grammar reference, conjugation drills, quizzes, TTS pronunciation, and an enhanced CEFR dashboard.

Flask 기반 언어 학습 뷰어. CEFR 기반 진도 추적, 어휘 플래시카드 (SM-2 SRS), 문법 참조, 활용 연습, 퀴즈, TTS 발음 재생, CEFR 대시보드를 지원합니다.

## Features / 기능

### Core / 핵심
- Markdown rendering with Pygments syntax highlighting / Markdown 렌더링 (Pygments 코드 하이라이팅)
- Full-text search (SQLite FTS5) / 전체 텍스트 검색 (SQLite FTS5)
- CEFR-based course & stage progression / CEFR 기반 코스 및 단계 진도
- Learning progress tracking / 학습 진행률 추적
- Bookmarks / 북마크
- Dark/Light mode / 다크/라이트 모드
- Multilingual support (Korean/English) / 다국어 지원 (한국어/영어)

### Vocabulary & Flashcards / 어휘 & 플래시카드
- Structured vocabulary YAML per lesson / 레슨별 구조화된 어휘 YAML
- Vocabulary list with lesson/level/category filters / 어휘 목록 (레슨/레벨/카테고리 필터)
- SRS flashcards with SM-2 algorithm (Anki-style) / SM-2 간격 반복 플래시카드
- Keyboard shortcuts (Space: flip, 1-4: grade) / 키보드 단축키

### Grammar Reference / 문법 참조
- Verb conjugation tables (22 verbs × 7 tenses) / 동사 활용표
- Grammar rule pages (ser vs estar, preterite vs imperfect, subjunctive, etc.) / 문법 규칙
- Tense rules with formation patterns and examples / 시제 규칙

### Practice & Quiz / 연습 & 퀴즈
- Conjugation drill (random verb+tense+person) / 활용 연습 드릴
- Quiz system: vocab matching, fill-in-blank, conjugation (4 types) / 퀴즈 시스템 (4종)
- Accent-aware input helpers (á, é, í, ó, ú, ñ, ü) / 악센트 입력 도우미
- Score tracking with streak counter / 점수 및 연속 정답 추적
- Practice hub with drill + flashcard + quiz links / 연습 허브

### Audio & Tooltips / 음성 & 툴팁
- TTS pronunciation (Web Speech API, es-ES) / TTS 발음 재생
- Vocabulary tooltips in lesson text (click-to-popup) / 레슨 내 어휘 툴팁

### Dashboard / 대시보드
- CEFR stage progress tracking / CEFR 단계별 진도 추적
- Vocabulary statistics (learning, mastered, due today) / 어휘 통계
- Quiz performance tracking (per-type scores) / 퀴즈 성적 추적
- Study streak counter / 연속 학습일 추적

### UI / 인터페이스
- Unified top/bottom lesson toolbar / 레슨 상/하단 통합 툴바
- Keyboard shortcuts (←/→ lesson navigation) / 키보드 단축키 (←/→ 레슨 이동)
- Scroll-to-top floating button / 맨 위로 스크롤 버튼
- Optional multi-user auth (Flask-Login + bcrypt) / 선택적 다중 사용자 인증

## Auth Modes / 인증 모드

Controlled by `AUTH_ENABLED` environment variable (.env or shell).

`AUTH_ENABLED` 환경변수로 전환합니다.

| Mode | AUTH_ENABLED | Login UI | Progress/Bookmarks |
|------|-------------|----------|-------------------|
| Single-user (default) | `false` | Hidden | Always available (user_id=NULL) |
| Multi-user | `true` | Shown | Login required (per-user data) |

## Installation & Running / 설치 및 실행

### Prerequisites / 사전 요구사항

This viewer reads content from the companion [language-hub](https://github.com/eunsu-park/language-hub) repository. By default, it expects `language-hub` as a sibling directory:

```
parent/
├── language-hub/          # Content repository
└── language-hub-viewer/   # This viewer
```

Or set `LANGUAGE_HUB_PATH` environment variable to the content repo path.

### Single-user mode (default) / 단일 사용자 모드

```bash
cd viewer
pip install -r requirements.txt

flask init-db          # Initialize database
flask build-index      # Build search index
flask run --port 5051  # http://127.0.0.1:5051
```

### Multi-user mode / 다중 사용자 모드

```bash
cd viewer
pip install -r requirements.txt
cp .env.example .env
# Edit .env: AUTH_ENABLED=true, set SECRET_KEY

AUTH_ENABLED=true flask init-db
AUTH_ENABLED=true flask build-index
AUTH_ENABLED=true flask create-user --username admin
AUTH_ENABLED=true flask run --port 5051
```

### Production (Gunicorn) / 프로덕션

```bash
cp .env.example .env
# Edit .env: AUTH_ENABLED=true, SECRET_KEY=<random>, FLASK_ENV=production

gunicorn -c gunicorn.conf.py app:app
```

## Project Structure / 프로젝트 구조

```
language-hub-viewer/
├── README.md
├── LICENSE
├── shared/utils/          # Markdown parser, search
├── viewer/
│   ├── app.py             # Flask main app (all routes + template filters)
│   ├── auth.py            # Auth Blueprint (login/logout, CLI commands)
│   ├── config.py          # Configuration + security settings
│   ├── models.py          # User, LessonRead, Bookmark, VocabularyProgress, QuizAttempt
│   ├── forms.py           # WTForms (LoginForm)
│   ├── progress.py        # Batch query helpers (N+1 optimized)
│   ├── vocabulary.py      # YAML vocabulary loading, filtering
│   ├── grammar.py         # YAML grammar loading (conjugations, rules, tenses)
│   ├── quiz.py            # Quiz question generation engine (4 types)
│   ├── srs.py             # SM-2 spaced repetition engine
│   ├── gunicorn.conf.py   # Gunicorn production config
│   ├── requirements.txt   # Dependencies
│   ├── .env.example       # Environment variable template
│   ├── templates/
│   │   ├── vocabulary/    # Vocabulary list, flashcard session
│   │   ├── grammar/       # Grammar index, conjugation tables, rule pages
│   │   └── practice/      # Practice hub, conjugation drill, quiz
│   └── static/
│       ├── css/           # style, grammar, flashcard, practice, vocabulary, highlight
│       └── js/            # app, lesson, flashcard, practice, vocabulary, bookmarks, dashboard, quiz, tts
└── tests/
```

## API Endpoints / API 엔드포인트

| Method | Path | Description |
|--------|------|-------------|
| GET | `/<lang>/` | Course list / 코스 목록 |
| GET | `/<lang>/course/<name>` | Course home (CEFR stages) / 코스 홈 |
| GET | `/<lang>/course/<name>/lesson/<file>` | Lesson content / 레슨 내용 |
| GET | `/<lang>/course/<name>/vocabulary` | Vocabulary list / 어휘 목록 |
| GET | `/<lang>/course/<name>/flashcard` | Flashcard session / 플래시카드 |
| GET | `/<lang>/course/<name>/grammar` | Grammar index / 문법 참조 |
| GET | `/<lang>/course/<name>/grammar/verb/<verb>` | Conjugation table / 활용표 |
| GET | `/<lang>/course/<name>/grammar/rule/<rule>` | Grammar rule / 문법 규칙 |
| GET | `/<lang>/course/<name>/practice` | Practice hub / 연습 허브 |
| GET | `/<lang>/course/<name>/practice/conjugation` | Conjugation drill / 활용 드릴 |
| GET | `/<lang>/search?q=<query>` | Search / 검색 |
| GET | `/<lang>/dashboard` | Progress dashboard / 진행률 대시보드 |
| GET | `/<lang>/bookmarks` | Bookmark list / 북마크 목록 |
| POST | `/api/mark-read` | Mark as read / 읽음 표시 |
| POST | `/api/bookmark` | Toggle bookmark / 북마크 토글 |
| POST | `/api/flashcard/grade` | Grade flashcard (SRS) / 플래시카드 채점 |
| GET | `/api/practice/drill-set` | Get drill questions / 드릴 문제 조회 |
| POST | `/api/practice/conjugation` | Check conjugation answer / 활용 답 검증 |
| GET | `/<lang>/course/<name>/practice/quiz` | Quiz page / 퀴즈 페이지 |
| GET | `/api/practice/quiz-set` | Generate quiz questions / 퀴즈 문제 생성 |
| POST | `/api/practice/quiz-answer` | Check quiz answer / 퀴즈 답 검증 |
| POST | `/api/practice/quiz-complete` | Save quiz attempt / 퀴즈 결과 저장 |

> When `AUTH_ENABLED=true`, POST endpoints require authentication and `X-CSRFToken` header.

## Configuration / 설정

| Variable | Default | Description |
|---|---|---|
| `LANGUAGE_HUB_PATH` | `../../language-hub` | Path to language-hub content repo |
| `AUTH_ENABLED` | `false` | `true` for multi-user mode |
| `SECRET_KEY` | dev key | Required in production with auth |
| `FLASK_APP` | `app.py` | Flask application module |

## Dependencies / 의존성

- Flask 3.x
- Flask-SQLAlchemy
- Flask-Login (multi-user mode)
- Flask-WTF (multi-user mode)
- bcrypt (multi-user mode)
- Markdown + Pygments
- PyYAML
- Gunicorn (production)

## License

| Target | License |
|---|---|
| Viewer code | [MIT License](./LICENSE) |

## Author

**Eunsu Park**
- [ORCID: 0000-0003-0969-286X](https://orcid.org/0000-0003-0969-286X)
