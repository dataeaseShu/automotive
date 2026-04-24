import { useState, useEffect, useRef, useCallback } from 'react'
import './styles/index.css'
import type { ChatMessageData, Product, Creative, SlotsSummary, SessionState } from './types'
import {
  startChat,
  sendMessage,
  selectProduct,
  updateCreatives,
} from './services/api'
import ProductCards from './components/ProductCards'
import CreativeCards from './components/CreativeCards'
import PlanPreviewCard from './components/PlanPreviewCard'
import PlanConfirmCard from './components/PlanConfirmCard'
import UploadButton from './components/UploadButton'

// ── 状态标签 ────────────────────────────────────────────────────────────────
const STATE_LABELS: Record<string, string> = {
  init: '初始化',
  slot_filling: '需求解析中',
  clarifying: '追问确认',
  product_search: '商品搜索',
  product_selected: '商品已选',
  creative_selection: '成片选择',
  upload_prompt: '上传提示',
  uploading: '上传素材',
  preview: '预览确认',
  submitted: '已提交',
}

// ── 槽位展示名 ───────────────────────────────────────────────────────────────
const SLOT_LABELS: Record<string, string> = {
  vehicle: '车型',
  scene: '营销场景',
  goal: '营销目标',
  location: '地域',
  budget: '预算(元)',
  bid_strategy: '出价策略',
  schedule: '排期',
  audience: '定向人群',
}

const RECOMMENDED_QUESTIONS: Partial<Record<SessionState, string[]>> = {
  init: [
    '我想推广比亚迪海豹，预算2万，目标试驾预约',
    '给我做一个同城门店引流计划，车型是特斯拉Model Y',
    '短视频投放，预算每天1000元，主要获客',
  ],
  slot_filling: [
    '预算控制在5000元以内，先跑7天',
    '只投放上海同城，圈店周边5公里',
    '目标改成线索收集，优先30-45岁家庭用户',
  ],
  clarifying: [
    '优先门店引流，出价用智能出价',
    '排期改成14天，预算每天800元',
    '投放区域先全国，后续再收窄',
  ],
  product_search: [
    '比亚迪汉',
    '问界M7',
    '小鹏G6',
  ],
}

function formatSlotValue(key: string, val: unknown): string {
  if (val === null || val === undefined) return '—'
  if (key === 'scene') return val === 'short_video' ? '短视频' : '直播'
  if (key === 'goal') {
    const map: Record<string, string> = { store_traffic: '门店引流', test_drive: '试驾预约', lead_collection: '线索收集' }
    return map[val as string] || String(val)
  }
  if (key === 'location' && typeof val === 'object') {
    const l = val as Record<string, unknown>
    if (l.type === 'radius') return `周边${l.km}公里`
    if (l.type === 'city') return '同城'
    if (l.type === 'nationwide') return '全国'
  }
  if (key === 'budget' && typeof val === 'number') return val.toLocaleString()
  if (key === 'bid_strategy' && typeof val === 'object') {
    const b = val as Record<string, unknown>
    return b.type === 'manual' ? `手动出价${b.amount || ''}元` : '智能出价'
  }
  if (key === 'schedule' && typeof val === 'object') {
    const s = val as Record<string, unknown>
    return `${s.days}天`
  }
  if (typeof val === 'object') return JSON.stringify(val)
  return String(val)
}

// ── 消息渲染 ─────────────────────────────────────────────────────────────────
interface MsgProps {
  msg: ChatMessageData
  sessionId: string
  selectedProductId?: string
  selectedCreativeIds: string[]
  uploadedCount: number
  onProductSelect: (p: Product) => void
  onCreativesUpdate: (ids: string[]) => void
  onConfirmPreview: () => void
  onConfirmPlan: () => Promise<void>
  onUploaded: (mat: unknown) => void
  submitting: boolean
}

function MessageBubble({
  msg, sessionId, selectedProductId, selectedCreativeIds, uploadedCount,
  onProductSelect, onCreativesUpdate, onConfirmPreview, onConfirmPlan, onUploaded, submitting,
}: MsgProps) {
  const hideContentBubble = msg.role === 'assistant' && msg.type === 'plan_confirm_card'

  return (
    <div className={`message-row ${msg.role}`}>
      <div className={`avatar ${msg.role}`}>
        {msg.role === 'assistant' ? '🤖' : '我'}
      </div>
      <div className="message-content">
        {msg.content && !hideContentBubble && (
          <div className={`bubble ${msg.role}${msg.type === 'error' ? ' error' : ''}`}>
            {msg.content}
          </div>
        )}

        {msg.type === 'product_cards' && msg.products && (
          <ProductCards
            products={msg.products}
            onSelect={onProductSelect}
            selectedId={selectedProductId}
          />
        )}

        {msg.type === 'creative_cards' && msg.creatives && (
          <CreativeCards
            creatives={msg.creatives}
            selectedIds={selectedCreativeIds}
            onUpdate={onCreativesUpdate}
          />
        )}

        {msg.type === 'upload_button' && (
          <UploadButton
            sessionId={sessionId}
            currentCount={uploadedCount}
            onUploaded={onUploaded}
          />
        )}

        {msg.type === 'plan_confirm_card' && msg.plan_confirm && (
          <PlanConfirmCard
            data={msg.plan_confirm}
            onConfirm={onConfirmPlan}
          />
        )}

        {msg.type === 'preview_card' && msg.preview && (
          <PlanPreviewCard
            preview={msg.preview}
            onConfirm={onConfirmPreview}
            loading={submitting}
          />
        )}
      </div>
    </div>
  )
}

// ── 主 App ──────────────────────────────────────────────────────────────────
export default function App() {
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [state, setState] = useState<SessionState>('init')
  const [messages, setMessages] = useState<ChatMessageData[]>([])
  const [slotsSummary, setSlotsSummary] = useState<SlotsSummary | null>(null)
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [selectedProductId, setSelectedProductId] = useState<string | undefined>()
  const [selectedCreativeIds, setSelectedCreativeIds] = useState<string[]>([])
  const [uploadedCount, setUploadedCount] = useState(0)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  // ── 初始化会话 ──────────────────────────────────────────────────────────
  const init = useCallback(async () => {
    setLoading(true)
    try {
      const res = await startChat()
      setSessionId(res.session_id)
      setMessages([{
        role: 'assistant',
        type: 'text',
        content: res.message,
      }])
      setState('init')
      setSelectedProductId(undefined)
      setSelectedCreativeIds([])
      setUploadedCount(0)
      setSlotsSummary(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { init() }, [init])

  // ── 自动滚动到底部 ───────────────────────────────────────────────────────
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // ── 追加消息到列表 ───────────────────────────────────────────────────────
  const appendMessages = (incoming: (ChatMessageData & Record<string, unknown>)[]) => {
    setMessages((prev) => [
      ...prev,
      ...incoming.map((m) => ({
        role: 'assistant' as const,
        type: (m.type || 'text') as ChatMessageData['type'],
        content: String(m.content || ''),
        products: m.products as Product[] | undefined,
        creatives: m.creatives as Creative[] | undefined,
        selected_ids: m.selected_ids as string[] | undefined,
        preview: m.preview as ChatMessageData['preview'],
        plan_confirm: m.plan_confirm as any,
      })),
    ])
  }

  // ── 发送文本消息 ─────────────────────────────────────────────────────────
  const sendUserText = async (text: string) => {
    if (!sessionId || !text || loading) return
    setMessages((prev) => [...prev, { role: 'user', type: 'text', content: text }])
    setLoading(true)
    try {
      const res = await sendMessage(sessionId, text)
      setState(res.state)
      setSlotsSummary(res.slots_summary)
      appendMessages(res.messages)
      // 同步成片选择
      const creativeMsg = res.messages.find((m) => m.type === 'creative_cards')
      if (creativeMsg && creativeMsg.selected_ids) {
        setSelectedCreativeIds(creativeMsg.selected_ids as string[])
      }
    } catch {
      setMessages((prev) => [...prev, { role: 'assistant', type: 'error', content: '请求失败，请稍后重试。' }])
    } finally {
      setLoading(false)
    }
  }

  const handleSend = async () => {
    const text = input.trim()
    if (!text) return
    setInput('')
    await sendUserText(text)
  }

  const handleRecommendedQuestion = async (question: string) => {
    if (isInputDisabled) return
    await sendUserText(question)
    inputRef.current?.focus()
  }

  // ── 选择商品（卡片点击） ─────────────────────────────────────────────────
  const handleProductSelect = async (product: Product) => {
    if (!sessionId || loading) return
    setSelectedProductId(product.product_id)
    setLoading(true)
    try {
      const res = await selectProduct(sessionId, product.product_id, product)
      setState(res.state)
      setSlotsSummary(res.slots_summary)
      appendMessages(res.messages)
      const creativeMsg = res.messages.find((m) => m.type === 'creative_cards')
      if (creativeMsg && (creativeMsg as Record<string, unknown>).selected_ids) {
        setSelectedCreativeIds((creativeMsg as Record<string, unknown>).selected_ids as string[])
      }
    } catch {
      setMessages((prev) => [...prev, { role: 'assistant', type: 'error', content: '选择商品失败，请重试。' }])
    } finally {
      setLoading(false)
    }
  }

  // ── 更新成片选择 ─────────────────────────────────────────────────────────
  const handleCreativesUpdate = async (ids: string[]) => {
    if (!sessionId) return
    setSelectedCreativeIds(ids)
    try {
      await updateCreatives(sessionId, ids)
    } catch {
      console.error('更新成片失败')
    }
  }

  // ── 预览确认提交 ─────────────────────────────────────────────────────────
  const handleConfirmPreview = async () => {
    if (!sessionId || submitting) return
    setSubmitting(true)
    try {
      const res = await sendMessage(sessionId, '确认提交')
      setState(res.state)
      appendMessages(res.messages)
    } finally {
      setSubmitting(false)
    }
  }

  // ── 计划确认提交 ─────────────────────────────────────────────────────────
  const handleConfirmPlan = async () => {
    if (!sessionId) return
    try {
      const res = await sendMessage(sessionId, '确认推送计划至巨量引擎')
      setState(res.state)
      appendMessages(res.messages)
    } catch (err) {
      console.error('计划推送失败:', err)
      throw err
    }
  }

  // ── 上传回调 ─────────────────────────────────────────────────────────────
  const handleUploaded = (_mat: unknown) => {
    setUploadedCount((c) => c + 1)
  }

  // ── 键盘快捷键 ───────────────────────────────────────────────────────────
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const isInputDisabled = loading || state === 'submitted'
  const suggestedQuestions = RECOMMENDED_QUESTIONS[state] || RECOMMENDED_QUESTIONS.slot_filling || []

  return (
    <div className="app-layout">
      {/* ─ 侧边栏：槽位状态 ─ */}
      <aside className="sidebar">
        <div className="sidebar-logo">🚗 Lumax</div>
        <div className="sidebar-subtitle">智能投手 AI Copilot</div>
        <div className="sidebar-spacer" />

        {(state === 'submitted' || messages.length > 2) && (
          <button className="new-plan-btn" onClick={init} disabled={loading}>
            ＋ 新建计划
          </button>
        )}
      </aside>

      {/* ─ 聊天主区域 ─ */}
      <div className="chat-container">
        <div className="chat-header">
          <span style={{ fontWeight: 600 }}>建计划对话流</span>
          <span className="state-badge">{STATE_LABELS[state] || state}</span>
        </div>

        <div className="chat-messages">
          {messages.map((msg, i) => (
            <MessageBubble
              key={i}
              msg={msg}
              sessionId={sessionId || ''}
              selectedProductId={selectedProductId}
              selectedCreativeIds={selectedCreativeIds}
              uploadedCount={uploadedCount}
              onProductSelect={handleProductSelect}
              onCreativesUpdate={handleCreativesUpdate}
              onConfirmPreview={handleConfirmPreview}
              onConfirmPlan={handleConfirmPlan}
              onUploaded={handleUploaded}
              submitting={submitting}
            />
          ))}
          {loading && (
            <div className="message-row assistant">
              <div className="avatar assistant">🤖</div>
              <div className="bubble assistant">
                <div className="typing-indicator">
                  <div className="dot" /><div className="dot" /><div className="dot" />
                </div>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <div className="recommended-bar">
          <span className="recommended-title">推荐问题</span>
          <div className="recommended-list">
            {suggestedQuestions.map((q) => (
              <button
                key={q}
                className="recommended-chip"
                onClick={() => handleRecommendedQuestion(q)}
                disabled={isInputDisabled}
              >
                {q}
              </button>
            ))}
          </div>
        </div>

        <div className="chat-input-bar">
          <textarea
            ref={inputRef}
            className="chat-input"
            placeholder={
              state === 'product_search'
                ? '输入商品关键字，如"比亚迪汉"、"特斯拉"…'
                : state === 'submitted'
                ? '计划已提交'
                : '描述您的推广需求，Enter 发送，Shift+Enter 换行'
            }
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isInputDisabled}
            rows={1}
          />
          <button
            className="send-btn"
            onClick={handleSend}
            disabled={isInputDisabled || !input.trim()}
          >
            发送
          </button>
        </div>
      </div>
    </div>
  )
}
