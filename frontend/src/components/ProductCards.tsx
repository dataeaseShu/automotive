import type { Product } from '../../types'

interface Props {
  products: Product[]
  onSelect: (product: Product) => void
  selectedId?: string
}

export default function ProductCards({ products, onSelect, selectedId }: Props) {
  return (
    <div className="cards-container">
      {products.map((p) => (
        <div
          key={p.product_id}
          className={`product-card${selectedId === p.product_id ? ' selected' : ''}`}
          onClick={() => onSelect(p)}
          title="点击选择此商品"
        >
          <img
            src={p.thumbnail || `https://placehold.co/180x80?text=${encodeURIComponent(p.model)}`}
            alt={p.product_name}
          />
          <div className="product-card-body">
            <div className="product-card-name">{p.product_name}</div>
            <div className="product-card-brand">{p.brand}</div>
          </div>
        </div>
      ))}
    </div>
  )
}
