import type { Slide } from '../../lib/api'

interface SlideSidebarProps {
  slides: Slide[]
  selectedSlideId: string | null
  onSelectSlide: (slideId: string) => void
}

export function SlideSidebar({
  slides,
  selectedSlideId,
  onSelectSlide,
}: SlideSidebarProps): React.JSX.Element {
  return (
    <nav className="slide-list" aria-label="Generated slides">
      {slides.map((slide) => (
        <button
          key={slide.id}
          className={slide.id === selectedSlideId ? 'slide-tab active' : 'slide-tab'}
          type="button"
          onClick={() => onSelectSlide(slide.id)}
        >
          <span>{String(slide.page_number).padStart(2, '0')}</span>
          {slide.title}
        </button>
      ))}
    </nav>
  )
}
