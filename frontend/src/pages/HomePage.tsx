import { Sparkles } from 'lucide-react'
import { useMemo, useState } from 'react'
import { DeckWorkspace } from '../components/deck/DeckWorkspace'
import { GenerationForm } from '../components/generation/GenerationForm'
import { ProgressPanel } from '../components/generation/ProgressPanel'
import { RecentDecks } from '../components/generation/RecentDecks'
import { useDeckGeneration } from '../hooks/useDeckGeneration'
import { I18nContext, messages, type UiLanguage } from '../i18n'

export function HomePage(): React.JSX.Element {
  const generation = useDeckGeneration()
  const [language, setLanguage] = useState<UiLanguage>(() =>
    navigator.language.toLowerCase().startsWith('zh') ? 'zh-CN' : 'en-US',
  )
  const i18n = useMemo(
    () => ({
      language,
      t: (key: keyof typeof messages['en-US']) => messages[language][key],
    }),
    [language],
  )

  return (
    <I18nContext.Provider value={i18n}>
      <main className="app-shell">
      <section className="hero-panel">
        <div className="eyebrow">
          <Sparkles size={16} />
          {i18n.t('aiWorkbench')}
        </div>
        <button
          className="language-toggle"
          type="button"
          onClick={() => setLanguage((current) => (current === 'zh-CN' ? 'en-US' : 'zh-CN'))}
        >
          {i18n.t('languageToggle')}
        </button>
        <h1>tokenvizPPT</h1>
        <p>{i18n.t('heroDescription')}</p>
      </section>

      <RecentDecks
        sessions={generation.sessions}
        loading={generation.sessionsLoading}
        activeSessionId={generation.sessionId}
        onOpen={generation.openSession}
        onDelete={generation.deleteSavedSession}
      />

      <section className="workspace">
        <GenerationForm
          loading={generation.loading}
          error={generation.error}
          onSubmit={generation.startGeneration}
        />
        <ProgressPanel
          events={generation.events}
          latestProgress={generation.latestProgress}
          sessionId={generation.sessionId}
        />
      </section>

      {generation.deck ? (
        <DeckWorkspace
          deck={generation.deck}
          selectedSlide={generation.selectedSlide}
          selectedSlideId={generation.selectedSlideId}
          editing={generation.editing}
          editError={generation.editError}
          slideVersions={generation.slideVersions}
          historyLoading={generation.historyLoading}
          assets={generation.assets}
          assetLoading={generation.assetLoading}
          exporting={generation.exporting}
          exportUrl={generation.exportUrl}
          onSelectSlide={generation.setSelectedSlideId}
          onEditSlide={generation.editSelectedSlide}
          onPatchElement={generation.patchSelectedElement}
          onUploadAsset={generation.uploadAsset}
          onInsertAsset={generation.insertAssetIntoSelectedSlide}
          onPlaceAsset={generation.placeAssetInSelectedSlide}
          onExportPptx={generation.exportEditablePptx}
          onRollbackSlide={generation.rollbackSelectedSlide}
        />
      ) : null}
      </main>
    </I18nContext.Provider>
  )
}
