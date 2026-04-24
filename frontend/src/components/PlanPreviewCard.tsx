import type { PlanPreview } from '../../types'

interface Props {
  preview: PlanPreview
  onConfirm: () => void
  loading?: boolean
}

const SCENE_LABELS: Record<string, string> = {
  short_video: '短视频',
  live: '直播',
}

const GOAL_LABELS: Record<string, string> = {
  store_traffic: '门店引流',
  test_drive: '试驾预约',
  lead_collection: '线索收集',
}

export default function PlanPreviewCard({ preview, onConfirm, loading }: Props) {
  const rows: [string, string][] = [
    ['推广车型', preview.vehicle || '—'],
    ['营销场景', preview.scene ? (SCENE_LABELS[preview.scene] || preview.scene) : '—'],
    ['营销目标', preview.goal ? (GOAL_LABELS[preview.goal] || preview.goal) : '—'],
    ['投放地域', preview.location || '—'],
    ['商品', preview.product?.product_name || '—'],
    ['人群包', preview.audience_package?.name || '（自动绑定）'],
    ['定向包', preview.targeting_package?.name || '（自动绑定）'],
    ['总预算', preview.budget],
    ['出价策略', preview.bid_strategy],
    ['排期', preview.schedule],
    ['成片数量', `${preview.creative_count} 个`],
  ]

  return (
    <div className="preview-card">
      <h3>📋 投放计划预览</h3>
      {rows.map(([label, value]) => (
        <div key={label} className="preview-row">
          <span className="preview-row-label">{label}</span>
          <span className="preview-row-value">{value}</span>
        </div>
      ))}
      {Object.keys(preview.slot_explanations).length > 0 && (
        <div className="explanations">
          <strong>解析来源：</strong>
          {Object.entries(preview.slot_explanations).map(([k, v]) => (
            <div key={k}>{k}：{v}</div>
          ))}
        </div>
      )}
      <button className="confirm-btn" onClick={onConfirm} disabled={loading}>
        {loading ? '提交中...' : '✅ 确认提交'}
      </button>
    </div>
  )
}
