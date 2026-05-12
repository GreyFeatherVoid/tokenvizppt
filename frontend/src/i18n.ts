import { createContext, useContext } from 'react'

export type UiLanguage = 'en-US' | 'zh-CN'

export const messages = {
  'en-US': {
    aiWorkbench: 'AI slide workbench',
    heroDescription: 'Generate, edit, and export polished editable PPT decks from prompts and files.',
    languageToggle: '中文',
    topic: 'Topic',
    brief: 'Brief',
    slides: 'Slides',
    style: 'Style',
    stylePrompt: 'Style prompt for this generation',
    resetStylePrompt: 'Reset style prompt',
    allowAiVisuals: 'Allow AI-generated visuals',
    allowAiVisualsHelp:
      'Conservative mode: the backend only generates images when a specific slide truly needs one and image generation is enabled in backend config.',
    sourceFiles: 'Source files',
    sourceFilesHelp: 'Upload txt, md, csv, pdf, docx, xlsx, or image files for this generation.',
    sourceNotesPlaceholder: 'Notes for the model, e.g. product screenshot; use on cover',
    mustAppear: 'Must appear in the PPT',
    remove: 'Remove',
    startGeneration: 'Start generation',
    hideHistory: 'Hide history',
    history: 'History',
    recentDecks: 'Recent decks',
    savedLocally: 'Saved locally',
    loading: 'Loading...',
    records: 'records',
    noSavedDecks: 'No saved decks yet. Generated decks will appear here.',
    deleteConfirmPrefix: 'Delete',
    deleteConfirmSuffix: 'This cannot be undone.',
    slidesUnit: 'slides',
    updated: 'updated',
  },
  'zh-CN': {
    aiWorkbench: 'AI 幻灯片工作台',
    heroDescription: '用提示词和文件生成、编辑并导出可编辑的精美 PPT。',
    languageToggle: 'English',
    topic: '主题',
    brief: '需求说明',
    slides: '页数',
    style: '风格',
    stylePrompt: '本次生成使用的风格提示词',
    resetStylePrompt: '重置风格提示词',
    allowAiVisuals: '允许 AI 生成配图',
    allowAiVisualsHelp:
      '保守模式：只有当某一页确实需要图片，且后端已启用生图配置时，才会生成图片。',
    sourceFiles: '参考文件',
    sourceFilesHelp: '上传 txt、md、csv、pdf、docx、xlsx 或图片文件作为本次生成素材。',
    sourceNotesPlaceholder: '给模型的备注，例如：产品截图；用于封面',
    mustAppear: '必须出现在 PPT 中',
    remove: '移除',
    startGeneration: '开始生成',
    hideHistory: '收起历史',
    history: '历史',
    recentDecks: '最近项目',
    savedLocally: '本地保存',
    loading: '加载中...',
    records: '条记录',
    noSavedDecks: '暂无保存项目。生成后的 PPT 会显示在这里。',
    deleteConfirmPrefix: '删除',
    deleteConfirmSuffix: '此操作不可撤销。',
    slidesUnit: '页',
    updated: '更新于',
  },
} satisfies Record<UiLanguage, Record<string, string>>

export type TranslationKey = keyof typeof messages['en-US']

export interface I18nValue {
  language: UiLanguage
  t: (key: TranslationKey) => string
}

export const I18nContext = createContext<I18nValue>({
  language: 'en-US',
  t: (key) => messages['en-US'][key],
})

export function useI18n(): I18nValue {
  return useContext(I18nContext)
}
