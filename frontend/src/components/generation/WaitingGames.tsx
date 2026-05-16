import { useEffect, useMemo, useState } from 'react'
import { Brain, Gamepad2, RotateCcw } from 'lucide-react'
import { useI18n } from '../../i18n'

type GameMode = 'guess' | 'snake'
type Direction = 'up' | 'down' | 'left' | 'right'
type Point = { x: number; y: number }

const GRID_SIZE = 12
const INITIAL_SNAKE: Point[] = [
  { x: 5, y: 6 },
  { x: 4, y: 6 },
  { x: 3, y: 6 },
]

const guessQuestions = [
  {
    answer: { 'en-US': 'coffee', 'zh-CN': '咖啡' },
    hints: {
      'en-US': ['I wake people up.', 'I am often bitter.', 'Meetings pretend to need me.'],
      'zh-CN': ['我经常负责叫醒人类。', '我常常有点苦。', '很多会议假装离不开我。'],
    },
  },
  {
    answer: { 'en-US': 'umbrella', 'zh-CN': '雨伞' },
    hints: {
      'en-US': ['I am useful only when the sky gets dramatic.', 'People forget me everywhere.', 'I bloom in rain.'],
      'zh-CN': ['天空开始表演时我才有用。', '人类经常把我忘在各处。', '我会在雨里开花。'],
    },
  },
  {
    answer: { 'en-US': 'keyboard', 'zh-CN': '键盘' },
    hints: {
      'en-US': ['I hear every typo.', 'I work harder when deadlines approach.', 'I have keys but open no doors.'],
      'zh-CN': ['每一个错别字我都听见了。', '越临近截止日期我越忙。', '我有很多键，但打不开门。'],
    },
  },
] as const

const snakeReviews = {
  'en-US': [
    'Bold route. The strategy was mostly optimism wearing a tiny hat.',
    'A respectable collapse. The snake had ambition, the wall had boundaries.',
    'Efficiently chaotic. Somewhere, a product manager is calling this agile.',
  ],
  'zh-CN': [
    '路线很有想法，主要问题是想法比蛇活得久。',
    '崩得很体面。蛇有野心，墙有原则。',
    '混乱但高效。某个产品经理已经准备把它叫敏捷了。',
  ],
} as const

export function WaitingGames(): React.JSX.Element {
  const { language, t } = useI18n()
  const [mode, setMode] = useState<GameMode>('guess')

  return (
    <section className="waiting-games">
      <div className="waiting-games-header">
        <span className="eyebrow compact">
          <Gamepad2 size={14} />
          {t('waitingGames')}
        </span>
        <small>{t('waitingGamesFree')}</small>
      </div>
      <div className="game-tabs">
        <button className={mode === 'guess' ? 'active' : ''} type="button" onClick={() => setMode('guess')}>
          <Brain size={15} />
          {t('mindGuess')}
        </button>
        <button className={mode === 'snake' ? 'active' : ''} type="button" onClick={() => setMode('snake')}>
          <Gamepad2 size={15} />
          {t('snakeGame')}
        </button>
      </div>
      {mode === 'guess' ? <MindGuessGame /> : <SnakeGame language={language} />}
    </section>
  )
}

function MindGuessGame(): React.JSX.Element {
  const { language, t } = useI18n()
  const [round, setRound] = useState(0)
  const [hintCount, setHintCount] = useState(1)
  const [guess, setGuess] = useState('')
  const [result, setResult] = useState<string | null>(null)
  const [wrongCount, setWrongCount] = useState(0)
  const [answerVisible, setAnswerVisible] = useState(false)
  const current = guessQuestions[round % guessQuestions.length]
  const answer = current.answer[language].toLowerCase()
  const hints = current.hints[language].slice(0, hintCount)
  const canRevealAnswer = wrongCount >= 3

  function submitGuess(): void {
    const normalized = guess.trim().toLowerCase()
    if (!normalized) return
    const correct = normalized === answer
    setResult(correct ? t('guessCorrect') : t('guessWrong'))
    if (correct) {
      setAnswerVisible(false)
      return
    }
    setWrongCount((value) => value + 1)
  }

  function nextRound(): void {
    setRound((value) => value + 1)
    setHintCount(1)
    setGuess('')
    setResult(null)
    setWrongCount(0)
    setAnswerVisible(false)
  }

  return (
    <div className="mind-game">
      <ul>
        {hints.map((hint) => (
          <li key={hint}>{hint}</li>
        ))}
      </ul>
      <div className="mind-game-row">
        <input
          value={guess}
          placeholder={t('guessPlaceholder')}
          onChange={(event) => setGuess(event.target.value)}
        />
        <button type="button" onClick={submitGuess}>
          {t('guessSubmit')}
        </button>
      </div>
      <div className="mind-game-actions">
        <button
          className="secondary-button compact-button"
          type="button"
          onClick={() => setHintCount((value) => Math.min(current.hints[language].length, value + 1))}
          disabled={hintCount >= current.hints[language].length}
        >
          {t('moreHint')}
        </button>
        <button className="secondary-button compact-button" type="button" onClick={nextRound}>
          <RotateCcw size={15} />
          {t('nextQuestion')}
        </button>
        {canRevealAnswer ? (
          <button
            className="secondary-button compact-button"
            type="button"
            onClick={() => setAnswerVisible(true)}
          >
            {t('revealAnswer')}
          </button>
        ) : null}
      </div>
      {result ? <p className="game-comment">{result}</p> : null}
      {answerVisible ? (
        <p className="game-comment">
          {t('answerLabel')}: {current.answer[language]}
        </p>
      ) : null}
    </div>
  )
}

function SnakeGame({ language }: { language: 'en-US' | 'zh-CN' }): React.JSX.Element {
  const { t } = useI18n()
  const [snake, setSnake] = useState<Point[]>(INITIAL_SNAKE)
  const [food, setFood] = useState<Point>({ x: 8, y: 6 })
  const [direction, setDirection] = useState<Direction>('right')
  const [running, setRunning] = useState(false)
  const [gameOver, setGameOver] = useState(false)
  const [review, setReview] = useState('')
  const score = Math.max(0, snake.length - INITIAL_SNAKE.length)
  const occupied = useMemo(() => new Set(snake.map((point) => `${point.x}:${point.y}`)), [snake])

  useEffect(() => {
    function handleKey(event: KeyboardEvent): void {
      if (!running) return
      if (event.key === 'ArrowUp' && direction !== 'down') setDirection('up')
      if (event.key === 'ArrowDown' && direction !== 'up') setDirection('down')
      if (event.key === 'ArrowLeft' && direction !== 'right') setDirection('left')
      if (event.key === 'ArrowRight' && direction !== 'left') setDirection('right')
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [direction, running])

  useEffect(() => {
    if (!running || gameOver) return
    const timer = window.setInterval(() => {
      setSnake((current) => {
        const head = current[0]
        const next = nextPoint(head, direction)
        if (
          next.x < 0 ||
          next.y < 0 ||
          next.x >= GRID_SIZE ||
          next.y >= GRID_SIZE ||
          current.some((point) => point.x === next.x && point.y === next.y)
        ) {
          setRunning(false)
          setGameOver(true)
          setReview(randomReview(language))
          return current
        }
        const ate = next.x === food.x && next.y === food.y
        const nextSnake = [next, ...current]
        if (!ate) nextSnake.pop()
        if (ate) setFood(placeFood(nextSnake))
        return nextSnake
      })
    }, 180)
    return () => window.clearInterval(timer)
  }, [direction, food, gameOver, language, running])

  function reset(): void {
    setSnake(INITIAL_SNAKE)
    setFood({ x: 8, y: 6 })
    setDirection('right')
    setRunning(false)
    setGameOver(false)
    setReview('')
  }

  return (
    <div className="snake-game">
      <div className="snake-meta">
        <span>{t('snakeScore')}: {score}</span>
        <span>{t('snakeControls')}</span>
      </div>
      <div className="snake-board" aria-label={t('snakeGame')}>
        {Array.from({ length: GRID_SIZE * GRID_SIZE }, (_, index) => {
          const point = { x: index % GRID_SIZE, y: Math.floor(index / GRID_SIZE) }
          const key = `${point.x}:${point.y}`
          const isHead = snake[0].x === point.x && snake[0].y === point.y
          const isSnake = occupied.has(key)
          const isFood = food.x === point.x && food.y === point.y
          return (
            <span
              className={[
                'snake-cell',
                isHead ? 'head' : '',
                isSnake ? 'snake' : '',
                isFood ? 'food' : '',
              ].join(' ')}
              key={key}
            />
          )
        })}
      </div>
      <div className="mind-game-actions">
        <button type="button" onClick={() => setRunning(true)} disabled={running || gameOver}>
          {t('snakeStart')}
        </button>
        <button className="secondary-button" type="button" onClick={reset}>
          <RotateCcw size={15} />
          {t('snakeReset')}
        </button>
      </div>
      {gameOver ? <p className="game-comment">{review}</p> : null}
    </div>
  )
}

function nextPoint(head: Point, direction: Direction): Point {
  if (direction === 'up') return { x: head.x, y: head.y - 1 }
  if (direction === 'down') return { x: head.x, y: head.y + 1 }
  if (direction === 'left') return { x: head.x - 1, y: head.y }
  return { x: head.x + 1, y: head.y }
}

function placeFood(snake: Point[]): Point {
  const occupied = new Set(snake.map((point) => `${point.x}:${point.y}`))
  const openCells = []
  for (let y = 0; y < GRID_SIZE; y += 1) {
    for (let x = 0; x < GRID_SIZE; x += 1) {
      if (!occupied.has(`${x}:${y}`)) openCells.push({ x, y })
    }
  }
  return openCells[Math.floor(Math.random() * openCells.length)] ?? { x: 0, y: 0 }
}

function randomReview(language: 'en-US' | 'zh-CN'): string {
  const reviews = snakeReviews[language]
  return reviews[Math.floor(Math.random() * reviews.length)] ?? reviews[0]
}
