class CartItem < ApplicationRecord
  belongs_to :cart

  validates :item_id, presence: true,
            numericality: { only_integer: true, greater_than: 0 }
  validates :count, presence: true,
            numericality: { only_integer: true, greater_than: 0 }
  validates :item_id, uniqueness: { scope: :cart_id }
end