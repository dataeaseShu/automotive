import { useState } from 'react'
import type { Creative } from '../../types'

interface Props {
  creatives: Creative[]
  selectedIds: string[]
  onUpdate: (ids: string[]) => void
  maxCount?: number
}

function formatCount(n: number): string {
  if (n >= 10000) return `${(n / 10000).toFixed(1)}万`
  return n.toString()
}

export default function CreativeCards({ creatives, selectedIds, onUpdate, maxCount = 10 }: Props) {
  const toggle = (id: string) => {
    if (selectedIds.includes(id)) {
      onUpdate(selectedIds.filter((x) => x !== id))
    } else {
      if (selectedIds.length >= maxCount) return
      onUpdate([...selectedIds, id])
    }
  }

  return (
    <div>
      <div style={{ fontSize: 12, color: '#8c8c8c', marginBottom: 8 }}>
        已选 {selectedIds.length} / {maxCount} 个成片（点击卡片右上角可取消选择）
      </div>
      <div className="cards-container">
        {creatives.map((c) => {
          const isSelected = selectedIds.includes(c.creative_id)
          return (
            <div
              key={c.creative_id}
              className={`creative-card${isSelected ? ' selected' : ''}`}
              onClick={() => toggle(c.creative_id)}
            >
              <img
                src={c.thumbnail || `https://placehold.co/190x100?text=${encodeURIComponent(c.title)}`}
                alt={c.title}
              />
              {isSelected && (
                <div className="creative-check">✓</div>
              )}
              <div className="creative-card-body">
                <div className="creative-card-title">{c.title}</div>
                <div className="creative-card-stats">
                  播放量 {formatCount(c.play_count)} · {c.duration}秒
                </div>
                <div className="creative-card-labels">
                  {c.labels.map((l) => (
                    <span key={l} className="label-tag">{l}</span>
                  ))}
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
