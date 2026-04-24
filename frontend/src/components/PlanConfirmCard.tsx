import { useState } from 'react'
import type { PlanConfirmData } from '../types'

interface Props {
  data: PlanConfirmData
  onConfirm: () => Promise<void>
}

export default function PlanConfirmCard({ data, onConfirm }: Props) {
  const [isLocked, setIsLocked] = useState(false)
  const [isLoading, setIsLoading] = useState(false)

  const audienceText = data.audience && Object.keys(data.audience).length > 0
    ? Object.entries(data.audience).map(([key, val]) => `${key}: ${val}`).join(' / ')
    : '—'

  const fields = [
    { label: '车型', value: data.vehicle || '—' },
    { label: '营销场景', value: data.scene || '—' },
    { label: '营销目标', value: data.goal || '—' },
    { label: '地域', value: data.location || '—' },
    { label: '预算(元)', value: typeof data.budget === 'number' ? data.budget.toLocaleString() : '—' },
    { label: '出价策略', value: data.bid_strategy || '—' },
    { label: '投放排期', value: data.schedule || '—' },
    { label: '定向人群', value: audienceText, full: true },
  ]

  const handleConfirm = async () => {
    setIsLoading(true)
    try {
      await onConfirm()
      setIsLocked(true)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="plan-confirm-card">
      <div className="plan-confirm-header">
        <h3>巨量本地推·计划参数确认</h3>
        {isLocked && <span className="pushed-tag">✓ API已推送</span>}
      </div>

      <div className="plan-confirm-content">
        <div className="plan-params-grid">
          {fields.map((field) => (
            <div key={field.label} className={`param-item${field.full ? ' param-item-full' : ''}`}>
              <label>{field.label}</label>
              <div className="param-value">{field.value}</div>
            </div>
          ))}
        </div>
      </div>

      <button
        className={`plan-confirm-btn ${isLocked ? 'locked' : ''}`}
        onClick={handleConfirm}
        disabled={isLocked || isLoading}
      >
        {isLoading && <span className="btn-spinner">⏳ </span>}
        {isLocked ? '计划配置已锁定' : '确认推送至巨量引擎'}
      </button>
    </div>
  )
}
